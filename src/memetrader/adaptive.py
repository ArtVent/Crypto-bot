"""Selbst-Kalibrierung: übersetzt Journal-Lektionen in begrenzte Parameter-Anpassungen.

Prinzipien (docs/filter-engine.md 4.5, docs/strategien.md 4):
- Jede Anpassung ist BEGRENZT (harte Min/Max-Clamps) – der Bot kann sich
  nachjustieren, aber nie aus seinem Sicherheitsrahmen heraus 'lernen'.
- Jede Anpassung braucht MEHRFACH-EVIDENZ (Mindestanzahl gleicher Lektionen
  im Rolling-Fenster), nie einen Einzelfall.
- Jede Anpassung wird mit Begründung geloggt und persistiert – nachvollziehbar
  in `memetrader brain`.
- Drawdown-Bewusstsein: Nach Verlust-Serien wird die Positionsgröße reduziert
  (Vorsicht lernen), nach Erholung wieder normalisiert.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .journal import TradeRecord
from .risk import RiskConfig
from .strategy import StrategyConfig


@dataclass
class Bounds:
    stop_loss_pct: tuple[float, float] = (-50.0, -20.0)
    take_profit_pct: tuple[float, float] = (150.0, 400.0)
    progress_deadline_seconds: tuple[float, float] = (4 * 60.0, 15 * 60.0)
    # Real-Day-Walk-Forward-Befund: Über-Verschärfung (35 %/30 Käufer) kostete
    # mehr Rendite als sie Verluste sparte -> engere Ober-Grenzen
    min_fill_pct: tuple[float, float] = (10.0, 25.0)
    min_unique_buyers: tuple[float, float] = (10.0, 20.0)
    ml_risk_threshold: tuple[float, float] = (0.60, 0.90)
    position_scale: tuple[float, float] = (0.25, 1.0)


@dataclass
class Adjustment:
    t: float
    param: str
    old: float
    new: float
    reason: str


class AdaptiveTuner:
    WINDOW = 20          # Rolling-Fenster finalisierter Trades
    MIN_EVIDENCE = 3     # Mindestanzahl gleicher Lektionen für eine Anpassung

    def __init__(
        self,
        strategy: StrategyConfig,
        risk: RiskConfig,
        state_path: str | Path = "memetrader.tuning.json",
        bounds: Bounds | None = None,
    ):
        self.strategy = strategy
        self.risk = risk
        self.bounds = bounds or Bounds()
        self.state_path = Path(state_path)
        self.history: list[Adjustment] = []
        self.consecutive_losses = 0
        self.wins_since_scaleup = 0
        self.position_scale = 1.0
        self.base_position_sol = risk.position_sol

    # --- Kern: aus Lektionen lernen -------------------------------------------
    def on_trades_finalized(self, recent: list[TradeRecord], now: float | None = None) -> list[Adjustment]:
        now = time.time() if now is None else now
        window = recent[-self.WINDOW:]
        lessons = Counter(r.lesson for r in window if r.lesson)
        made: list[Adjustment] = []

        def clamp(value: float, key: str) -> float:
            lo, hi = getattr(self.bounds, key)
            return max(lo, min(hi, value))

        def adjust(obj, param: str, new_value: float, bound_key: str, reason: str):
            old = getattr(obj, param)
            new_value = clamp(new_value, bound_key)
            if abs(new_value - old) < 1e-9:
                return
            setattr(obj, param, new_value)
            adj = Adjustment(t=now, param=param, old=old, new=new_value, reason=reason)
            self.history.append(adj)
            made.append(adj)

        # Stop-Kalibrierung: rausgeschüttelt vs. bestätigt
        if lessons["shaken_out"] >= self.MIN_EVIDENCE and lessons["shaken_out"] > lessons["good_stop"]:
            adjust(self.risk, "stop_loss_pct", self.risk.stop_loss_pct - 5.0, "stop_loss_pct",
                   f"{lessons['shaken_out']}x shaken_out im Fenster – Stop etwas weiter")
        elif lessons["good_stop"] >= 2 * self.MIN_EVIDENCE and lessons["shaken_out"] == 0:
            adjust(self.risk, "stop_loss_pct", self.risk.stop_loss_pct + 2.5, "stop_loss_pct",
                   f"{lessons['good_stop']}x good_stop ohne shaken_out – Stop etwas enger")

        # Geduld-Kalibrierung
        if lessons["impatient"] >= self.MIN_EVIDENCE:
            adjust(self.risk, "progress_deadline_seconds",
                   self.risk.progress_deadline_seconds + 120.0, "progress_deadline_seconds",
                   f"{lessons['impatient']}x impatient – Zeit-Stop verlängert")

        # Gewinner-Kalibrierung
        if lessons["sold_too_early"] >= self.MIN_EVIDENCE:
            adjust(self.risk, "take_profit_pct", self.risk.take_profit_pct + 50.0, "take_profit_pct",
                   f"{lessons['sold_too_early']}x sold_too_early – Rest-Ziel erhöht")

        # Entry-Kalibrierung: bad_entry = Filter-Lücke -> strenger werden
        if lessons["bad_entry"] >= self.MIN_EVIDENCE:
            adjust(self.strategy, "min_fill_pct", self.strategy.min_fill_pct + 5.0, "min_fill_pct",
                   f"{lessons['bad_entry']}x bad_entry – Curve-Mindestfüllung erhöht")
            adjust(self.strategy, "min_unique_buyers", self.strategy.min_unique_buyers + 3, "min_unique_buyers",
                   f"{lessons['bad_entry']}x bad_entry – mehr Nachfrage-Beweis verlangt")
        # Opportunitätskosten-Gegenspieler (Walk-Forward-Befund): läuft es
        # sauber (keine bad_entries, überwiegend gute Exits), Filter wieder
        # Richtung Default lockern – Über-Verschärfung kostet Rendite
        good_lessons = sum(lessons[k] for k in
                           ("good_stop", "good_take_profit", "good_time_stop", "good_trail", "good_creator_exit"))
        if len(window) >= 8 and lessons["bad_entry"] == 0 and good_lessons >= len(window) * 0.5:
            if self.strategy.min_fill_pct > 10.0:
                adjust(self.strategy, "min_fill_pct", self.strategy.min_fill_pct - 2.5, "min_fill_pct",
                       "0x bad_entry bei sauberem Fenster – Entry-Filter gelockert (Opportunitätskosten)")
            if self.strategy.min_unique_buyers > 10:
                adjust(self.strategy, "min_unique_buyers", self.strategy.min_unique_buyers - 2, "min_unique_buyers",
                       "0x bad_entry bei sauberem Fenster – Entry-Filter gelockert (Opportunitätskosten)")

        # ML-Gate-Kalibrierung: Verlierer hatten höheres ml_risk als Gewinner?
        losers = [r for r in window if (r.pnl_sol or 0) < 0 and r.context.ml_risk is not None]
        winners = [r for r in window if (r.pnl_sol or 0) > 0 and r.context.ml_risk is not None]
        if len(losers) >= self.MIN_EVIDENCE and len(winners) >= self.MIN_EVIDENCE:
            avg_l = sum(r.context.ml_risk for r in losers) / len(losers)
            avg_w = sum(r.context.ml_risk for r in winners) / len(winners)
            if avg_l - avg_w > 0.05:
                # ml_risk_threshold lebt in BotConfig; via Callback-Attribut (gesetzt vom Bot)
                if hasattr(self, "bot_config"):
                    adjust(self.bot_config, "ml_risk_threshold",
                           self.bot_config.ml_risk_threshold - 0.02, "ml_risk_threshold",
                           f"Verlierer ml_risk Ø {avg_l:.2f} vs. Gewinner {avg_w:.2f} – Gate strenger")

        if made:
            self._persist()
        return made

    # --- Drawdown-bewusste Positionsgröße -------------------------------------
    def on_trade_result(self, pnl_sol: float) -> None:
        if pnl_sol < 0:
            self.consecutive_losses += 1
            self.wins_since_scaleup = 0
        else:
            self.consecutive_losses = 0
            self.wins_since_scaleup += 1

        lo, hi = self.bounds.position_scale
        if self.consecutive_losses >= 5:
            self.position_scale = max(lo, 0.5)
        elif self.consecutive_losses >= 3:
            self.position_scale = max(lo, 0.75)
        elif self.wins_since_scaleup >= 2:
            self.position_scale = min(hi, self.position_scale + 0.25)
        self.risk.position_sol = round(self.base_position_sol * self.position_scale, 6)

    # --- Persistenz -------------------------------------------------------------
    def _persist(self) -> None:
        state = {
            "position_scale": self.position_scale,
            "consecutive_losses": self.consecutive_losses,
            "effective": {
                "stop_loss_pct": self.risk.stop_loss_pct,
                "take_profit_pct": self.risk.take_profit_pct,
                "progress_deadline_seconds": self.risk.progress_deadline_seconds,
                "position_sol": self.risk.position_sol,
                "min_fill_pct": self.strategy.min_fill_pct,
                "min_unique_buyers": self.strategy.min_unique_buyers,
            },
            "history": [vars(a) for a in self.history[-50:]],
        }
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    def load_state(self) -> bool:
        """Lädt persistierten Lernstand (Parameter innerhalb der Bounds,
        Positions-Skalierung) – damit Lernen Neustarts überlebt."""
        if not self.state_path.exists():
            return False
        try:
            state = json.loads(self.state_path.read_text())
        except (json.JSONDecodeError, OSError):
            return False

        def clamp(value, key):
            lo, hi = getattr(self.bounds, key)
            return max(lo, min(hi, float(value)))

        eff = state.get("effective", {})
        if "stop_loss_pct" in eff:
            self.risk.stop_loss_pct = clamp(eff["stop_loss_pct"], "stop_loss_pct")
        if "take_profit_pct" in eff:
            self.risk.take_profit_pct = clamp(eff["take_profit_pct"], "take_profit_pct")
        if "progress_deadline_seconds" in eff:
            self.risk.progress_deadline_seconds = clamp(eff["progress_deadline_seconds"], "progress_deadline_seconds")
        if "min_fill_pct" in eff:
            self.strategy.min_fill_pct = clamp(eff["min_fill_pct"], "min_fill_pct")
        if "min_unique_buyers" in eff:
            self.strategy.min_unique_buyers = int(clamp(eff["min_unique_buyers"], "min_unique_buyers"))
        lo, hi = self.bounds.position_scale
        self.position_scale = max(lo, min(hi, float(state.get("position_scale", 1.0))))
        self.consecutive_losses = int(state.get("consecutive_losses", 0))
        self.risk.position_sol = round(self.base_position_sol * self.position_scale, 6)
        return True

    def state_summary(self) -> dict:
        return {
            "position_scale": self.position_scale,
            "consecutive_losses": self.consecutive_losses,
            "adjustments_made": len(self.history),
            "last_adjustments": [vars(a) for a in self.history[-5:]],
        }
