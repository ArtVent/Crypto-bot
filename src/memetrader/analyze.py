"""Log-Auswertung: rekonstruiert aus memetrader.log.jsonl, wie der Bot handelt.

Grundlage des Kalibrier-Loops (docs/strategien.md, Abschnitt 5): PnL nach
Kosten, Trefferquote, Exit-Gründe und blockierte Entries zeigen, welche Regel
Geld rettet und welche Rendite kostet – Schwellen werden gegen diese Zahlen
angepasst, nicht nach Gefühl.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Trade:
    mint: str
    symbol: str
    entered_t: float
    cost_sol: float
    proceeds_sol: float = 0.0
    closed_t: float | None = None
    exit_reasons: list[str] = field(default_factory=list)

    @property
    def closed(self) -> bool:
        return self.closed_t is not None

    @property
    def pnl_sol(self) -> float:
        return self.proceeds_sol - self.cost_sol

    @property
    def pnl_pct(self) -> float:
        return self.pnl_sol / self.cost_sol * 100.0 if self.cost_sol else 0.0

    @property
    def hold_seconds(self) -> float | None:
        return None if self.closed_t is None else self.closed_t - self.entered_t


@dataclass
class Analysis:
    trades: list[Trade]
    blocked: Counter
    open_trades: list[Trade]

    @property
    def closed_trades(self) -> list[Trade]:
        return [t for t in self.trades if t.closed]

    def report(self) -> str:
        closed = self.closed_trades
        lines = ["=== memetrader Log-Auswertung ==="]
        lines.append(f"Positionen: {len(closed)} geschlossen, {len(self.open_trades)} offen")
        if closed:
            wins = [t for t in closed if t.pnl_sol > 0]
            total = sum(t.pnl_sol for t in closed)
            best = max(closed, key=lambda t: t.pnl_sol)
            worst = min(closed, key=lambda t: t.pnl_sol)
            holds = [t.hold_seconds for t in closed if t.hold_seconds is not None]
            lines += [
                f"PnL gesamt: {total:+.4f} SOL  (Kosten: {sum(t.cost_sol for t in closed):.4f} SOL eingesetzt)",
                f"Trefferquote: {len(wins)}/{len(closed)} ({len(wins) / len(closed) * 100:.0f}%)",
                f"Ø PnL je Trade: {total / len(closed):+.4f} SOL   Ø Haltezeit: {sum(holds) / len(holds) / 60:.1f} min" if holds else "",
                f"Bester : {best.symbol or best.mint[:8]} {best.pnl_sol:+.4f} SOL ({best.pnl_pct:+.0f}%)",
                f"Schlechtester: {worst.symbol or worst.mint[:8]} {worst.pnl_sol:+.4f} SOL ({worst.pnl_pct:+.0f}%)",
                "Exit-Gründe:",
            ]
            reason_counts = Counter(r for t in closed for r in t.exit_reasons)
            reason_pnl: dict[str, float] = {}
            for t in closed:
                # PnL dem letzten (schließenden) Grund zuordnen
                reason_pnl[t.exit_reasons[-1]] = reason_pnl.get(t.exit_reasons[-1], 0.0) + t.pnl_sol
            for reason, count in reason_counts.most_common():
                pnl = reason_pnl.get(reason)
                pnl_txt = f"  (PnL der damit geschlossenen: {pnl:+.4f} SOL)" if pnl is not None else ""
                lines.append(f"  {reason:<14} {count:>3}x{pnl_txt}")
        if self.blocked:
            lines.append("Blockierte Entries (was der Filter aussortiert hat):")
            for why, count in self.blocked.most_common(10):
                lines.append(f"  {count:>4}x {why}")
        return "\n".join(l for l in lines if l)


def analyze_lines(lines) -> Analysis:
    trades: dict[str, Trade] = {}
    finished: list[Trade] = []
    blocked: Counter = Counter()

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        event = entry.get("event")
        mint = entry.get("mint", "")
        if event == "entry":
            trades[mint] = Trade(
                mint=mint,
                symbol=entry.get("symbol", ""),
                entered_t=float(entry.get("t", 0.0)),
                cost_sol=float(entry.get("sol", 0.0)),
            )
        elif event == "exit" and mint in trades:
            trade = trades[mint]
            trade.proceeds_sol += float(entry.get("sol_received", 0.0))
            trade.exit_reasons.append(entry.get("reason", "?"))
            if float(entry.get("fraction", 0.0)) >= 1.0:
                trade.closed_t = float(entry.get("t", 0.0))
                finished.append(trades.pop(mint))
        elif event == "entry_blocked":
            blocked[entry.get("why", "?")] += 1

    return Analysis(trades=finished + list(trades.values()), blocked=blocked, open_trades=list(trades.values()))


def analyze_file(path: str | Path) -> Analysis:
    with Path(path).open() as fh:
        return analyze_lines(fh)
