"""Bot-Orchestrierung: Streams -> Curve-Tracking -> Strategie -> Risk -> Broker.

Datenfluss (docs/bot-architektur.md):
  PumpPortal-Websocket (create + trades) -> CurveState je Mint
  -> MomentumStrategy.evaluate() für Kandidaten
  -> RiskManager.can_enter() -> Broker.buy()
  -> laufend RiskManager.check_exit() -> Broker.sell()

Jede Entscheidung wird als JSON-Zeile geloggt (Beobachtbarkeit, Abschnitt 8).
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import websockets

from .broker import Fill, PaperBroker
from .curve import CurveState
from .risk import PositionState, RiskConfig, RiskManager
from .strategy import MomentumStrategy, StrategyConfig

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
STATE_PRUNE_SECONDS = 90 * 60.0


@dataclass
class BotConfig:
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    log_path: str = "memetrader.log.jsonl"
    evaluate_every_seconds: float = 2.0
    # ML-Gate (optional): auf MELT trainiertes Risiko-Modell, siehe mlfilter.py
    ml_model_path: str | None = None
    ml_risk_threshold: float = 0.80


class Bot:
    def __init__(self, config: BotConfig | None = None, broker=None, ml_gate=None):
        self.config = config or BotConfig()
        self.broker = broker or PaperBroker()
        self.strategy = MomentumStrategy(self.config.strategy)
        self.risk = RiskManager(self.config.risk)
        self.curves: dict[str, CurveState] = {}
        self._log = Path(self.config.log_path)
        # Kausale Zähler für ML-Features (nur Vergangenheit, wie im Training)
        self.symbol_counts: dict[str, int] = {}
        self.creator_counts: dict[str, int] = {}
        self.ml_gate = ml_gate
        if self.ml_gate is None and self.config.ml_model_path:
            from .mlfilter import MLGate

            self.ml_gate = MLGate(self.config.ml_model_path)

    # --- Event-Verarbeitung (synchron, damit ohne Netz testbar) --------------
    def on_event(self, event: dict, now: float | None = None) -> list[Fill]:
        now = time.time() if now is None else now
        tx = event.get("txType")
        mint = event.get("mint")
        if not mint:
            return []

        if tx == "create":
            symbol = (event.get("symbol") or "").upper()
            creator = event.get("traderPublicKey") or ""
            state = CurveState(
                mint=mint,
                creator=creator,
                symbol=event.get("symbol") or "",
                name=event.get("name") or "",
                uri=event.get("uri") or "",
                v_sol=float(event.get("vSolInBondingCurve") or 0.0),
                v_tokens=float(event.get("vTokensInBondingCurve") or 0.0),
                created_at=now,
                dev_buy_sol=float(event.get("solAmount") or 0.0),
                real_sol_in_curve=float(event.get("solAmount") or 0.0),
            )
            # Zähler-Snapshot VOR dem Hochzählen = "wie viele davor" (kausal)
            state.symbol_dupes_before = self.symbol_counts.get(symbol, 0)
            state.creator_prior_launches = self.creator_counts.get(creator, 0)
            if symbol:
                self.symbol_counts[symbol] = self.symbol_counts.get(symbol, 0) + 1
            if creator:
                self.creator_counts[creator] = self.creator_counts.get(creator, 0) + 1
            self.curves[mint] = state
            return []

        state = self.curves.get(mint)
        if state is None:
            return []

        if tx in ("buy", "sell"):
            state.apply_trade(event, now)
        elif tx == "migrate" or event.get("pool") == "pump-amm":
            state.migrated = True

        fills = self._manage_position(state, now)
        fills += self._maybe_enter(state, now)
        return fills

    def _maybe_enter(self, state: CurveState, now: float) -> list[Fill]:
        if state.mint in self.risk.positions:
            return []
        decision = self.strategy.evaluate(state, now)
        if not decision.enter:
            return []
        if self.ml_gate is not None:
            risk_score = self.ml_gate.risk(
                state,
                symbol_dupes_before=state.symbol_dupes_before,
                creator_prior_launches=state.creator_prior_launches,
                now=now,
            )
            if risk_score >= self.config.ml_risk_threshold:
                self._write_log(
                    {"t": now, "event": "entry_blocked", "mint": state.mint,
                     "why": f"ml_risk {risk_score:.2f} >= {self.config.ml_risk_threshold}"}
                )
                return []
        ok, why = self.risk.can_enter(now)
        if not ok:
            self._write_log({"t": now, "event": "entry_blocked", "mint": state.mint, "why": why})
            return []
        fill = self.broker.buy(state, self.risk.config.position_sol)
        if fill.tokens <= 0:
            return []
        self.risk.open_position(state.mint, state.symbol, fill.tokens, fill.sol, now)
        self._write_log(
            {"t": now, "event": "entry", "mint": state.mint, "symbol": state.symbol,
             "sol": fill.sol, "tokens": fill.tokens, "fill_pct": round(state.fill_pct, 1),
             "unique_buyers": len(state.unique_buyers)}
        )
        return [fill]

    def _manage_position(self, state: CurveState, now: float) -> list[Fill]:
        pos = self.risk.positions.get(state.mint)
        if pos is None:
            return []
        value = self.broker.position_value(state, pos.tokens)
        action = self.risk.check_exit(pos, value, state.creator_sold, state.migrated, now)
        if action is None:
            return []
        tokens_to_sell = pos.tokens * action.sell_fraction
        fill = self.broker.sell(state, tokens_to_sell)
        self.risk.record_sell(pos, tokens_to_sell, fill.sol)
        self._write_log(
            {"t": now, "event": "exit", "mint": state.mint, "symbol": state.symbol,
             "reason": action.reason.value, "fraction": action.sell_fraction,
             "sol_received": fill.sol, "risk": self.risk.summary()}
        )
        return [fill]

    def prune(self, now: float) -> None:
        stale = [
            m for m, s in self.curves.items()
            if m not in self.risk.positions and now - s.created_at > STATE_PRUNE_SECONDS
        ]
        for m in stale:
            del self.curves[m]

    def _write_log(self, entry: dict) -> None:
        with self._log.open("a") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # --- Async-Hauptschleife --------------------------------------------------
    async def run(self) -> None:
        print(
            f"memetrader gestartet (Paper={isinstance(self.broker, PaperBroker)}). "
            f"Budget {self.risk.config.budget_sol} SOL, Position {self.risk.config.position_sol} SOL, "
            f"Kill-Switch bei -{self.risk.config.daily_loss_stop_sol} SOL."
        )
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(PUMPPORTAL_WS, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    backoff = 1.0
                    last_prune = time.time()
                    subscribed: set[str] = set()
                    async for message in ws:
                        event = json.loads(message)
                        # Trades neuer Mints abonnieren, sobald sie auftauchen
                        mint = event.get("mint")
                        if event.get("txType") == "create" and mint and mint not in subscribed:
                            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                            subscribed.add(mint)
                        for fill in self.on_event(event):
                            side = "KAUF " if fill.side == "buy" else "VERKAUF"
                            print(f"{side} {event.get('symbol', fill.mint[:8]):<10} {fill.sol:.4f} SOL  | {self.risk.summary()}")
                        now = time.time()
                        if now - last_prune > 300:
                            self.prune(now)
                            last_prune = now
                        if self.risk.halted and not self.risk.positions:
                            print("Kill-Switch aktiv und alle Positionen geschlossen – Bot stoppt.")
                            return
            except (websockets.WebSocketException, OSError) as exc:
                print(f"[bot] Verbindung verloren ({exc}); Reconnect in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)


def run_paper(budget_sol: float = 1.0) -> None:
    config = BotConfig()
    config.risk.budget_sol = budget_sol
    asyncio.run(Bot(config).run())
