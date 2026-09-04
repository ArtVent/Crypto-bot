"""Risk-Engine: Positionsgrößen, Limits, Kill-Switch, Exit-Zustandsmaschine.

Setzt docs/strategien.md Abschnitt 4 um: Totalverlust-Prämisse pro Position,
Korrelations-Deckel über max. gleichzeitige Positionen, Tages-Kill-Switch,
asymmetrische Exits (Derisk bei 2x, Rest laufen lassen, harter Stop, Zeit-Stop,
These-Stop bei Creator-Verkauf). Zustandsmaschine aus docs/bot-architektur.md 5:
entered -> derisked -> closed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class PositionState(str, Enum):
    ENTERED = "entered"
    DERISKED = "derisked"  # Einsatz zurückgeholt, Rest ist "House Money"
    CLOSED = "closed"


class ExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_STOP = "time_stop"
    CREATOR_SOLD = "creator_sold"
    MIGRATION = "migration"
    TRAILING_STOP = "trailing_stop"
    KILL_SWITCH = "kill_switch"
    RECYCLE = "recycle"  # Teilverkaufs-Leiter: Basis raus, Gewinn läuft weiter


@dataclass
class RiskConfig:
    budget_sol: float = 1.0
    position_sol: float = 0.05          # pro Trade; bei 1 SOL sind kleinere
    max_concurrent: int = 3             # Positionen fee-dominiert (fee-oekonomie.md)
    daily_loss_stop_sol: float = 0.15   # Kill-Switch: keine neuen Entries UND
    # offene Positionen werden beim nächsten Event glattgestellt (harter Tages-
    # Stopp des Risikos; check_exit gibt bei halted für jede Position KILL_SWITCH)
    stop_loss_pct: float = -35.0
    derisk_at_pct: float = 100.0        # bei 2x: Einsatz raus
    derisk_sell_fraction: float = 0.5
    take_profit_pct: float = 250.0      # Rest-Exit-Ziel
    max_hold_seconds: float = 20 * 60.0
    progress_deadline_seconds: float = 8 * 60.0  # Zeit-Stop: bis dahin > +20 %
    progress_min_pct: float = 20.0
    # Graduierte durch die Migration halten? A/B auf dem realen Tag klar
    # NEGATIV (-15,3 % vs. +17,8 % mit Sofort-Exit): Verkauf in die
    # Graduation-Stärke schlägt Halten+Trailing, und gehaltene Positionen
    # blockieren stundenlang Slots. Default daher AUS; Mechanik bleibt
    # als Option erhalten. (docs/realtest-echte-daten.md, Teil 2)
    hold_through_migration: bool = False
    trailing_stop_pct: float = 30.0        # Exit, wenn PnL X Punkte unter Peak fällt
    migrated_max_hold_seconds: float = 4 * 3600.0
    # Teilverkaufs-Leiter ("Einsatz raus, Gewinn läuft"): Liegt der Positionswert
    # recycle_trigger_pct über der aktuellen Basis (anfangs = Einsatz), wird genau
    # die Basis verkauft; der Gewinnanteil bleibt im Markt und wird zur neuen
    # Basis – das wiederholt sich, bis der Restwert unter recycle_min_value_sol
    # fällt oder ein anderer Exit greift. 0 = aus (A/B-Ergebnis: siehe
    # docs/realtest-echte-daten.md).
    recycle_trigger_pct: float = 0.0
    recycle_min_value_sol: float = 0.01


@dataclass
class Position:
    mint: str
    symbol: str
    tokens: float
    cost_sol: float
    entered_at: float
    state: PositionState = PositionState.ENTERED
    realized_sol: float = 0.0
    peak_pnl_pct: float = -100.0
    recycle_basis_sol: float = 0.0  # 0 = noch keine Leiter-Stufe; sonst aktuelle Basis

    def pnl_pct(self, value_sol: float) -> float:
        if self.cost_sol <= 0:
            return 0.0
        return (self.realized_sol + value_sol - self.cost_sol) / self.cost_sol * 100.0


@dataclass
class ExitAction:
    reason: ExitReason
    sell_fraction: float  # Anteil der aktuellen Token-Position


@dataclass
class RiskManager:
    config: RiskConfig = field(default_factory=RiskConfig)
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl_sol: float = 0.0
    daily_realized_pnl_sol: float = 0.0
    spent_sol: float = 0.0
    halted: bool = False

    def reset_day(self) -> None:
        """Neuer Handelstag: Tages-PnL und Kill-Switch zurücksetzen."""
        self.daily_realized_pnl_sol = 0.0
        self.halted = False

    # --- Entry-Seite ---------------------------------------------------------
    def can_enter(self, now: float | None = None) -> tuple[bool, str]:
        c = self.config
        if self.halted:
            return False, "Kill-Switch aktiv (Tagesverlust-Limit erreicht)"
        if len(self.positions) >= c.max_concurrent:
            return False, f"max. {c.max_concurrent} gleichzeitige Positionen"
        # Cash-Rechnung: Startbudget + realisierte PnL - in offenen Positionen
        # gebundenes Kapital. (Verkaufserlöse fließen ins Budget zurück.)
        committed = sum(p.cost_sol - p.realized_sol for p in self.positions.values())
        available = c.budget_sol + self.realized_pnl_sol - committed
        if available < c.position_sol:
            return False, f"Budget erschöpft (verfügbar {available:.3f} SOL)"
        return True, "ok"

    def open_position(self, mint: str, symbol: str, tokens: float, cost_sol: float, now: float | None = None) -> Position:
        now = time.time() if now is None else now
        pos = Position(mint=mint, symbol=symbol, tokens=tokens, cost_sol=cost_sol, entered_at=now)
        self.positions[mint] = pos
        self.spent_sol += cost_sol
        return pos

    # --- Exit-Seite ----------------------------------------------------------
    def check_exit(self, pos: Position, value_sol: float, creator_sold: bool, migrated: bool, now: float | None = None) -> ExitAction | None:
        c = self.config
        now = time.time() if now is None else now
        pnl = pos.pnl_pct(value_sol)
        pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl)
        held = now - pos.entered_at

        if self.halted:
            return ExitAction(ExitReason.KILL_SWITCH, 1.0)
        if creator_sold:
            return ExitAction(ExitReason.CREATOR_SOLD, 1.0)
        if migrated:
            if not c.hold_through_migration:
                return ExitAction(ExitReason.MIGRATION, 1.0)
            # Graduierte Runner: Trailing statt Sofort-Exit; großzügigere Zeit
            if pos.peak_pnl_pct - pnl >= c.trailing_stop_pct:
                return ExitAction(ExitReason.TRAILING_STOP, 1.0)
            if pnl <= c.stop_loss_pct:
                return ExitAction(ExitReason.STOP_LOSS, 1.0)
            if pos.state == PositionState.ENTERED and pnl >= c.derisk_at_pct:
                return ExitAction(ExitReason.TAKE_PROFIT, c.derisk_sell_fraction)
            if held > c.migrated_max_hold_seconds:
                return ExitAction(ExitReason.TIME_STOP, 1.0)
            return None
        if pnl <= c.stop_loss_pct:
            return ExitAction(ExitReason.STOP_LOSS, 1.0)
        if c.recycle_trigger_pct > 0:
            basis = pos.recycle_basis_sol if pos.recycle_basis_sol > 0 else pos.cost_sol
            remainder = value_sol - basis  # Restwert, der nach dem Bank-Verkauf drin bliebe
            if (value_sol >= basis * (1.0 + c.recycle_trigger_pct / 100.0)
                    and remainder >= c.recycle_min_value_sol):
                pos.recycle_basis_sol = remainder  # Gewinn wird neue Basis
                return ExitAction(ExitReason.RECYCLE, basis / value_sol)
        if pos.state == PositionState.ENTERED and pnl >= c.derisk_at_pct:
            return ExitAction(ExitReason.TAKE_PROFIT, c.derisk_sell_fraction)
        if pos.state == PositionState.DERISKED and pnl >= c.take_profit_pct:
            return ExitAction(ExitReason.TAKE_PROFIT, 1.0)
        if held > c.max_hold_seconds:
            return ExitAction(ExitReason.TIME_STOP, 1.0)
        if held > c.progress_deadline_seconds and pos.peak_pnl_pct < c.progress_min_pct:
            return ExitAction(ExitReason.TIME_STOP, 1.0)
        return None

    def record_sell(self, pos: Position, tokens_sold: float, sol_received: float) -> None:
        pos.tokens -= tokens_sold
        pos.realized_sol += sol_received
        if pos.tokens <= 1e-9:
            pos.state = PositionState.CLOSED
            pnl = pos.realized_sol - pos.cost_sol
            self.realized_pnl_sol += pnl
            self.daily_realized_pnl_sol += pnl
            del self.positions[pos.mint]
            if self.daily_realized_pnl_sol <= -self.config.daily_loss_stop_sol:
                self.halted = True
        elif pos.state == PositionState.ENTERED and pos.realized_sol >= pos.cost_sol:
            pos.state = PositionState.DERISKED

    def summary(self) -> dict:
        return {
            "open_positions": len(self.positions),
            "spent_sol": round(self.spent_sol, 4),
            "realized_pnl_sol": round(self.realized_pnl_sol, 4),
            "halted": self.halted,
        }
