"""Backtest-Harness: spielt Event-Ströme LOOKAHEAD-FREI durch den echten Bot.

Quellen: simulierter Markt (simulate.py) oder echte Aufzeichnungen (JSONL mit
_t-Zeitstempel je Event). Der Bot-Code ist identisch mit dem Live-Betrieb –
inklusive ML-Gate, Lern-Schicht und Claude-Kanal. Kein Lookahead by
construction: Events werden streng chronologisch gefüttert; der Bot kennt
weder Archetypen noch Zukunft.

Claude-Kanal im Backtest: Ohne ANTHROPIC_API_KEY läuft ein deterministischer
OFFLINE-STUB mit identischer Schnittstelle und identischer Informationslage
(nur Metadaten + öffentliches Wissen, z. B. bekannte Top-Ticker – kein
Orakel-Zugriff auf Archetypen). Mit Key kann derselbe Backtest die echte API
nutzen (claude='live' – langsam und kostenpflichtig, für Stichproben gedacht).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .bot import Bot, BotConfig
from .claude_link import VetResult
from .risk import RiskConfig
from .simulate import TOP_COINS, generate_market
from .strategy import StrategyConfig


class StubClaudeWorker:
    """Deterministischer Offline-Ersatz des ClaudeWorker (gleiche Schnittstelle).

    Vet-Politik auf Basis öffentlich verfügbarer Information: Veto bei
    Impersonation bekannter Top-Ticker. Post-Mortems/Reviews werden gezählt,
    aber nicht generiert (das leistet nur die echte API).
    """

    def __init__(self):
        self._queue: list[tuple] = []
        self._pending: set[str] = set()
        self.stats = Counter()

    def submit_vet(self, mint, token_meta, entry_context):
        if mint in self._pending:
            return False
        self._pending.add(mint)
        self.stats["vets"] += 1
        symbol = (token_meta.get("symbol") or "").upper()
        name = (token_meta.get("name") or "").upper()
        if symbol in TOP_COINS or name in TOP_COINS:
            self.stats["vetoes"] += 1
            result = VetResult(mint=mint, verdict="veto",
                               reason=f"Impersonation von '{symbol or name}'", confidence=0.9)
        else:
            result = VetResult(mint=mint, verdict="ok", reason="unauffällig", confidence=0.2)
        self._queue.append(("vet", result))
        return True

    def submit_post_mortem(self, record_dict):
        self.stats["post_mortems"] += 1

    def submit_review(self, summary, effective, bounds):
        self.stats["reviews"] += 1

    def drain(self):
        out, self._queue = self._queue, []
        for kind, payload in out:
            if kind == "vet":
                self._pending.discard(payload.mint)
        return out


@dataclass
class BacktestResult:
    seed: int
    days: float
    launches: int
    final_equity_sol: float
    realized_pnl_sol: float
    liquidation_sol: float
    n_entries: int
    n_closed: int
    win_rate: float | None
    max_drawdown_pct: float
    lessons: dict = field(default_factory=dict)
    self_tuning_events: int = 0
    vet_stats: dict = field(default_factory=dict)
    daily_equity: list = field(default_factory=list)
    halted_days: int = 0

    def summary(self) -> str:
        lines = [
            f"Seed {self.seed}: 1.0000 SOL -> {self.final_equity_sol:.4f} SOL "
            f"({(self.final_equity_sol - 1.0) * 100:+.1f}%)",
            f"  Trades: {self.n_closed} geschlossen ({self.n_entries} Entries), "
            f"Winrate {self.win_rate * 100:.0f}%" if self.win_rate is not None else
            f"  Trades: {self.n_closed}",
            f"  Max Drawdown: {self.max_drawdown_pct:.1f}%  |  Kill-Switch-Tage: {self.halted_days}",
            f"  Vets: {self.vet_stats.get('vets', 0)} (davon {self.vet_stats.get('vetoes', 0)} Vetos)"
            f"  |  Selbst-Tuning-Events: {self.self_tuning_events}",
            f"  Lektionen: {dict(sorted(self.lessons.items(), key=lambda x: -x[1]))}",
        ]
        return "\n".join(lines)


def run_backtest(
    days: float = 60.0,
    launches_per_day: int = 400,
    seed: int = 1,
    budget_sol: float = 1.0,
    workdir: str | Path = ".",
    ml_model: str | None = "models/mlfilter-melt.joblib",
    claude: str = "stub",  # "stub" | "live" | "off"
    events: list | None = None,
    hardened_checks: bool = True,
) -> BacktestResult:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    config = BotConfig()
    config.risk = RiskConfig(budget_sol=budget_sol)
    config.strategy = StrategyConfig()
    if not hardened_checks:  # Baseline: Mikrostruktur-Gates deaktiviert
        config.strategy.max_burst_buyer_share = 1.01
        config.strategy.min_buy_size_cv = 0.0
        config.strategy.max_top3_buyer_share = 1.01
        config.strategy.max_roundtrip_share = 1.01
    config.log_path = str(workdir / f"bt_{seed}.log.jsonl")
    config.journal_path = str(workdir / f"bt_{seed}.journal.jsonl")
    config.tuning_path = str(workdir / f"bt_{seed}.tuning.json")
    config.memory_path = str(workdir / f"bt_{seed}.memory.md")
    for path in (config.log_path, config.journal_path):
        Path(path).unlink(missing_ok=True)

    ml_gate = None
    if ml_model and Path(ml_model).exists():
        from .mlfilter import MLGate

        ml_gate = MLGate(ml_model, fetch_metadata=False)

    worker = None
    if claude == "stub":
        worker = StubClaudeWorker()
    elif claude == "live":
        from .claude_link import ClaudeLink, ClaudeWorker, Memory

        worker = ClaudeWorker(ClaudeLink(Memory(config.memory_path)))

    bot = Bot(config, ml_gate=ml_gate, claude_worker=worker)

    if events is None:
        events = generate_market(days, launches_per_day, seed)
    n_launches = sum(1 for _, e in events if e.get("txType") == "create")

    equity_curve: list[tuple[float, float]] = []
    peak = budget_sol
    max_dd = 0.0
    halted_days = 0
    last_day = -1
    was_halted_today = False

    # Equity = Budget + realisierte PnL + (aktueller Verkaufswert offener Positionen
    #          - deren noch nicht zurückgeflossene Kosten)
    def equity(now: float) -> float:
        open_value = 0.0
        open_cost_outstanding = 0.0
        for mint, pos in bot.risk.positions.items():
            state = bot.curves.get(mint)
            if state is not None:
                open_value += bot.broker.position_value(state, pos.tokens)
            open_cost_outstanding += pos.cost_sol - pos.realized_sol
        return budget_sol + bot.risk.realized_pnl_sol + open_value - open_cost_outstanding

    for t, event in events:
        day = int(t // 86400)
        if day != last_day:
            if last_day >= 0:
                equity_curve.append((last_day, round(equity(t), 4)))
                if was_halted_today:
                    halted_days += 1
            last_day = day
            was_halted_today = False
        bot.on_event(event, now=t)
        if bot.risk.halted:
            was_halted_today = True
        eq = equity(t)
        peak = max(peak, eq)
        if peak > 0:
            max_dd = max(max_dd, (peak - eq) / peak * 100.0)

    # Restpositionen zum letzten Kurs liquidieren (konservativ: Verkaufswert)
    end_t = events[-1][0] if events else 0.0
    liquidation = 0.0
    for mint, pos in list(bot.risk.positions.items()):
        state = bot.curves.get(mint)
        value = bot.broker.position_value(state, pos.tokens) if state else 0.0
        liquidation += value
        bot.risk.record_sell(pos, pos.tokens, value)
    bot.journal.finalize_due(end_t + 10 * 600.0)

    final_equity = budget_sol + bot.risk.realized_pnl_sol
    closed = bot.journal.finalized
    wins = [r for r in closed if (r.pnl_sol or 0) > 0]
    log_text = Path(config.log_path).read_text() if Path(config.log_path).exists() else ""

    return BacktestResult(
        seed=seed, days=days, launches=n_launches,
        final_equity_sol=round(final_equity, 4),
        realized_pnl_sol=round(bot.risk.realized_pnl_sol, 4),
        liquidation_sol=round(liquidation, 4),
        n_entries=log_text.count('"event": "entry"'),
        n_closed=len(closed),
        win_rate=round(len(wins) / len(closed), 3) if closed else None,
        max_drawdown_pct=round(max_dd, 1),
        lessons=dict(Counter(r.lesson for r in closed if r.lesson)),
        self_tuning_events=log_text.count('"event": "self_tune"'),
        vet_stats=dict(worker.stats) if isinstance(worker, StubClaudeWorker) else {},
        daily_equity=equity_curve,
        halted_days=halted_days,
    )


def run_seeds(seeds: list[int], **kwargs) -> list[BacktestResult]:
    return [run_backtest(seed=s, **kwargs) for s in seeds]
