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

from .adaptive import AdaptiveTuner
from .broker import Fill, PaperBroker
from .curve import CurveState
from .journal import EntryContext, Journal
from .risk import PositionState, RiskConfig, RiskManager
from .strategy import MomentumStrategy, StrategyConfig
from .wallet_intel import CreatorBook, MarketRegime, WalletBook

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
    # Lern-Schicht: Journal + Selbst-Kalibrierung (journal.py / adaptive.py)
    journal_path: str = "memetrader.journal.jsonl"
    tuning_path: str = "memetrader.tuning.json"
    post_exit_watch_seconds: float = 600.0
    adaptive_enabled: bool = True
    # Live-Claude-Verbindung (claude_link.py): Entry-Vet, Post-Mortems, Reviews
    claude_enabled: bool = False
    claude_review_every_n_trades: int = 10
    memory_path: str = "memetrader.memory.md"
    # Wallet-/Creator-Intelligence & Regime-Gate (wallet_intel.py)
    block_serial_creators: bool = True    # Creator mit >=3 Launches, 0 Graduations
    min_smart_wallets: int = 0            # >0: Konfluenz-Gate (Smart-Buyer unter den Käufern)
    # >0: Bot-Dichte-Kappe. Auf heißen Tagen sind graduation-kreditierte Wallets
    # überwiegend Serien-Sniper-Bots; VIELE davon im Käuferfeld = Pile-in-Signatur
    # (In-Sample-Befund 2026-07-31, siehe docs/realtest-echte-daten.md Teil 5 –
    # Default aus, Forward-Validierung über Autopilot-Papertrading)
    max_smart_buyers: int = 0
    min_market_heat: float = 0.0          # >0: nur handeln bei >= X Graduationen/Stunde


class Bot:
    def __init__(self, config: BotConfig | None = None, broker=None, ml_gate=None, claude_worker=None):
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
        # Lern-Schicht
        self.journal = Journal(self.config.journal_path, self.config.post_exit_watch_seconds)
        self.tuner = AdaptiveTuner(self.strategy.config, self.risk.config, self.config.tuning_path)
        self.tuner.bot_config = self.config  # erlaubt begrenzte ml_threshold-Anpassung
        # Live-Claude-Verbindung (optional; für Tests injizierbar)
        self.claude = claude_worker
        if self.claude is None and self.config.claude_enabled:
            from .claude_link import ClaudeLink, ClaudeWorker, Memory

            self.claude = ClaudeWorker(ClaudeLink(Memory(self.config.memory_path)))
        self._vet_waiting: dict[str, float | None] = {}  # mint -> ml_risk zum Vet-Zeitpunkt
        # Wallet-/Creator-Intelligence & Markt-Regime (alles rollierend & kausal)
        self.wallets = WalletBook()
        self.creators = CreatorBook()
        self.regime = MarketRegime()

    # --- Event-Verarbeitung (synchron, damit ohne Netz testbar) --------------
    def on_event(self, event: dict, now: float | None = None) -> list[Fill]:
        now = time.time() if now is None else now
        day = int(now // 86400)
        if getattr(self, "_current_day", None) != day:
            if getattr(self, "_current_day", None) is not None:
                self.risk.reset_day()
            self._current_day = day
        fills = self._process_claude_results(now)
        tx = event.get("txType")
        mint = event.get("mint")
        if not mint:
            return fills

        if tx == "create":
            self._finalize_lessons(now)
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
                self.creators.record_launch(creator)
            self.curves[mint] = state
            return fills

        state = self.curves.get(mint)
        if state is None:
            return fills

        if tx in ("buy", "sell"):
            state.apply_trade(event, now)
        elif (tx == "migrate" or event.get("pool") == "pump-amm") and not state.migrated:
            state.migrated = True
            # Kausale Credits ERST bei der Graduation: frühe Käufer, Creator, Regime
            self.wallets.credit_graduation(list(state.buy_sol_by_wallet.keys()), now)
            self.creators.record_graduation(state.creator)
            self.regime.record_graduation(now)

        # Post-Exit-Beobachtung: Wert der ehemaligen Position weiterverfolgen
        watched = self.journal.watching.get(mint)
        if watched is not None:
            self.journal.on_post_exit_value(mint, self.broker.position_value(state, watched.tokens))

        fills += self._manage_position(state, now)
        fills += self._maybe_enter(state, now)
        self._finalize_lessons(now)
        return fills

    def _process_claude_results(self, now: float) -> list[Fill]:
        """Verarbeitet asynchron eingetroffene Claude-Ergebnisse (Vets, Reviews, Notizen)."""
        if self.claude is None:
            return []
        fills: list[Fill] = []
        for kind, payload in self.claude.drain():
            if kind == "vet":
                risk_score = self._vet_waiting.pop(payload.mint, None)
                if payload.verdict == "veto":
                    self._write_log({"t": now, "event": "entry_blocked", "mint": payload.mint,
                                     "why": f"claude_veto: {payload.reason}"})
                    print(f"CLAUDE-VETO {payload.mint[:8]}: {payload.reason}")
                    continue
                if payload.verdict == "error":
                    self._write_log({"t": now, "event": "claude_vet_error", "mint": payload.mint,
                                     "why": payload.reason})
                state = self.curves.get(payload.mint)
                if state is None or payload.mint in self.risk.positions:
                    continue
                # Freigabe ist nur gültig, wenn die Lage JETZT noch stimmt
                decision = self.strategy.evaluate(state, now)
                ok, why = self.risk.can_enter(now)
                if decision.enter and ok:
                    fills += self._execute_entry(state, now, risk_score,
                                                 vet_note=payload.reason if payload.verdict == "ok" else None)
                else:
                    self._write_log({"t": now, "event": "entry_blocked", "mint": payload.mint,
                                     "why": "nach Claude-Vet nicht mehr gültig: "
                                            + (why if not ok else "; ".join(decision.reasons))})
            elif kind == "post_mortem":
                mint, note = payload
                if note:
                    self._write_log({"t": now, "event": "claude_memory", "mint": mint, "note": note})
                    print(f"CLAUDE-NOTIZ ({str(mint)[:8]}): {note}")
            elif kind == "review" and payload:
                from .advisor import apply_proposals

                applied = apply_proposals(payload.get("proposals", []), self.tuner)
                self._write_log({"t": now, "event": "claude_review",
                                 "analysis": payload.get("analysis", ""), "applied": applied})
                print(f"CLAUDE-REVIEW: {payload.get('analysis', '')}")
                for line in applied:
                    print(f"  {line}")
        return fills

    def _finalize_lessons(self, now: float) -> None:
        finalized = self.journal.finalize_due(now)
        if not finalized:
            return
        for record in finalized:
            self._write_log(
                {"t": now, "event": "lesson", "mint": record.mint, "symbol": record.symbol,
                 "lesson": record.lesson, "pnl_sol": record.pnl_sol,
                 "post_peak_value_sol": round(record.post_peak_value_sol, 6)}
            )
        if self.config.adaptive_enabled:
            adjustments = self.tuner.on_trades_finalized(self.journal.recent_lessons(), now)
            for adj in adjustments:
                self._write_log(
                    {"t": now, "event": "self_tune", "param": adj.param,
                     "old": adj.old, "new": adj.new, "reason": adj.reason}
                )
                print(f"SELBST-TUNING {adj.param}: {adj.old} -> {adj.new}  ({adj.reason})")
        if self.claude is not None:
            from dataclasses import asdict as _asdict

            GOOD_LESSONS = {"good_stop", "good_take_profit", "good_time_stop", "migration_exit"}
            for record in finalized:
                if record.lesson not in GOOD_LESSONS:
                    self.claude.submit_post_mortem(_asdict(record))
            n = len(self.journal.finalized)
            if n and n % self.config.claude_review_every_n_trades == 0:
                from collections import Counter as _Counter

                window = self.journal.finalized[-40:]
                summary = {
                    "n_closed_trades": len(window),
                    "total_pnl_sol": round(sum(r.pnl_sol or 0.0 for r in window), 4),
                    "lessons": dict(_Counter(r.lesson for r in window if r.lesson)),
                    "loser_contexts": [_asdict(r.context) for r in window if (r.pnl_sol or 0) < 0][:15],
                }
                effective = {
                    "stop_loss_pct": self.risk.config.stop_loss_pct,
                    "take_profit_pct": self.risk.config.take_profit_pct,
                    "progress_deadline_seconds": self.risk.config.progress_deadline_seconds,
                    "min_fill_pct": self.strategy.config.min_fill_pct,
                    "min_unique_buyers": self.strategy.config.min_unique_buyers,
                }
                bounds = {key: getattr(self.tuner.bounds, key) for key in effective}
                self.claude.submit_review(summary, effective, bounds)

    def _maybe_enter(self, state: CurveState, now: float) -> list[Fill]:
        if state.mint in self.risk.positions or state.mint in self._vet_waiting:
            return []
        decision = self.strategy.evaluate(state, now)
        if not decision.enter:
            return []
        # Intelligence-Gates (rollierend, kausal – siehe wallet_intel.py)
        if self.config.block_serial_creators and self.creators.is_serial_spammer(state.creator):
            self._write_log({"t": now, "event": "entry_blocked", "mint": state.mint,
                             "why": "serial_creator_live"})
            return []
        if self.config.min_market_heat > 0 and \
                self.regime.graduations_per_hour(now) < self.config.min_market_heat:
            self._write_log({"t": now, "event": "entry_blocked", "mint": state.mint,
                             "why": f"market_cold ({self.regime.graduations_per_hour(now):.0f} grads/h)"})
            return []
        smart_buyers = self.wallets.smart_buyer_count(state.unique_buyers, now)
        if self.config.min_smart_wallets > 0 and smart_buyers < self.config.min_smart_wallets:
            self._write_log({"t": now, "event": "entry_blocked", "mint": state.mint,
                             "why": f"no_smart_wallets ({smart_buyers})"})
            return []
        if self.config.max_smart_buyers > 0 and smart_buyers > self.config.max_smart_buyers:
            self._write_log({"t": now, "event": "entry_blocked", "mint": state.mint,
                             "why": f"bot_density ({smart_buyers} Serien-Sniper im Käuferfeld)"})
            return []
        risk_score = None
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
        # Live-Claude-Vet: zweite Meinung einholen, Entry kommt asynchron zurück
        if self.claude is not None:
            submitted = self.claude.submit_vet(
                state.mint,
                {"name": state.name, "symbol": state.symbol, "uri": state.uri},
                {"age_seconds": round(now - state.created_at, 1),
                 "fill_pct": round(state.fill_pct, 1),
                 "unique_buyers": len(state.unique_buyers),
                 "dev_buy_sol": state.dev_buy_sol,
                 "symbol_dupes_before": state.symbol_dupes_before,
                 "creator_prior_launches": state.creator_prior_launches,
                 "ml_risk": risk_score},
            )
            if submitted:
                self._vet_waiting[state.mint] = risk_score
                self._write_log({"t": now, "event": "vet_requested", "mint": state.mint,
                                 "symbol": state.symbol})
            return []
        return self._execute_entry(state, now, risk_score)

    def _execute_entry(self, state: CurveState, now: float, risk_score: float | None,
                       vet_note: str | None = None) -> list[Fill]:
        fill = self.broker.buy(state, self.risk.config.position_sol)
        if fill.tokens <= 0:
            return []
        self.risk.open_position(state.mint, state.symbol, fill.tokens, fill.sol, now)
        self.journal.on_entry(
            state.mint, state.symbol, fill.tokens, fill.sol,
            EntryContext(
                age_seconds=now - state.created_at,
                fill_pct=round(state.fill_pct, 1),
                unique_buyers=len(state.unique_buyers),
                buys=state.buys, sells=state.sells,
                dev_buy_sol=state.dev_buy_sol,
                symbol_dupes_before=state.symbol_dupes_before,
                creator_prior_launches=state.creator_prior_launches,
                ml_risk=round(risk_score, 3) if risk_score is not None else None,
                smart_buyers=self.wallets.smart_buyer_count(state.unique_buyers, now),
            ),
            now,
        )
        entry_log = {"t": now, "event": "entry", "mint": state.mint, "symbol": state.symbol,
                     "sol": fill.sol, "tokens": fill.tokens, "fill_pct": round(state.fill_pct, 1),
                     "unique_buyers": len(state.unique_buyers)}
        if vet_note:
            entry_log["claude_vet"] = vet_note
        self._write_log(entry_log)
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
        position_closed = state.mint not in self.risk.positions
        self.journal.on_exit(state.mint, action.reason.value, action.sell_fraction,
                             fill.sol, position_closed, now)
        if position_closed and self.config.adaptive_enabled:
            record = self.journal.watching.get(state.mint)
            if record is not None and record.pnl_sol is not None:
                self.tuner.on_trade_result(record.pnl_sol)
        self._write_log(
            {"t": now, "event": "exit", "mint": state.mint, "symbol": state.symbol,
             "reason": action.reason.value, "fraction": action.sell_fraction,
             "sol_received": fill.sol, "risk": self.risk.summary()}
        )
        return [fill]

    def prune(self, now: float) -> None:
        self._finalize_lessons(now)
        stale = [
            m for m, s in self.curves.items()
            if m not in self.risk.positions and m not in self.journal.watching
            and now - s.created_at > STATE_PRUNE_SECONDS
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
                        if self.risk.halted and not self.risk.positions and not getattr(self, "_halt_notified", False):
                            print("Kill-Switch aktiv – keine neuen Entries bis zum nächsten Handelstag.")
                            self._halt_notified = True
                        elif not self.risk.halted:
                            self._halt_notified = False
            except (websockets.WebSocketException, OSError) as exc:
                print(f"[bot] Verbindung verloren ({exc}); Reconnect in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)


def run_paper(budget_sol: float = 1.0) -> None:
    config = BotConfig()
    config.risk.budget_sol = budget_sol
    asyncio.run(Bot(config).run())
