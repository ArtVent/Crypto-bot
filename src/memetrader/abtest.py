"""Forward-Validierungs-A/B: Referenz vs. Bot-Dichte-Kappe auf einer Aufzeichnung.

Vorregistriertes Experiment (docs/realtest-echte-daten.md, Teil 5): Die Kappe
`max_smart_buyers` zeigte in-sample +20,1 % vs. +17,8 % bei halbiertem
Drawdown – die Schwelle stammt aber aus demselben Tag. Dieses Modul führt
GENAU dieses Duell auf frischen Aufzeichnungen aus (identische Events, beide
Läufe deterministisch) und schreibt einen maschinen- und menschenlesbaren
Bericht. Erst wenn die Kappe über mehrere frische Tage vorn liegt, wird sie
Default – nicht vorher.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .backtest import BacktestResult, run_backtest


def load_events(events_file: str | Path) -> list[tuple[float, dict]]:
    loaded: list[tuple[float, dict]] = []
    with open(events_file) as fh:
        for line in fh:
            if line.strip():
                record = json.loads(line)
                loaded.append((record.pop("_t"), record))
    loaded.sort(key=lambda e: e[0])
    return loaded


def _row(result: BacktestResult) -> dict:
    return {
        "final_equity_sol": round(result.final_equity_sol, 4),
        "return_pct": round(result.return_pct, 2),
        "entries": result.n_entries,
        "closed": result.n_closed,
        "win_rate": round(result.win_rate, 3) if result.win_rate is not None else None,
        "max_drawdown_pct": round(result.max_drawdown_pct, 1),
        "lessons": result.lessons,
    }


def run_abtest(events_file: str | Path, out_dir: str | Path,
               budget_sol: float = 1.0, max_smart_buyers: int = 7,
               recycle_trigger_pct: float = 100.0,
               min_market_heat: float = 3.0) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(events_file)
    if not events:
        raise ValueError(f"Aufzeichnung {events_file} enthält keine Events")
    span_hours = (events[-1][0] - events[0][0]) / 3600.0

    ref = run_backtest(events=events, workdir=out_dir / "ref", budget_sol=budget_sol,
                       ml_model=None, claude="stub")
    cap = run_backtest(events=events, workdir=out_dir / "cap", budget_sol=budget_sol,
                       ml_model=None, claude="stub",
                       bot_overrides={"max_smart_buyers": max_smart_buyers})
    ladder = run_backtest(events=events, workdir=out_dir / "ladder", budget_sol=budget_sol,
                          ml_model=None, claude="stub",
                          risk_overrides={"recycle_trigger_pct": recycle_trigger_pct})
    # Coldday-Erkennung: handeln nur, wenn der Markt Graduationen liefert.
    # Hinweis: Der Sensor startet bei Aufnahmebeginn leer – die ersten Minuten
    # eines Fensters sind für diesen Arm systematisch gesperrt (Warm-up);
    # auf wirklich kalten Aufnahmen bleibt er zu, und genau das ist sein Zweck.
    regime = run_backtest(events=events, workdir=out_dir / "regime", budget_sol=budget_sol,
                          ml_model=None, claude="stub",
                          bot_overrides={"min_market_heat": min_market_heat})

    report = {
        "recorded_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(events[0][0])),
        "span_hours": round(span_hours, 2),
        "n_events": len(events),
        "budget_sol": budget_sol,
        "max_smart_buyers": max_smart_buyers,
        "recycle_trigger_pct": recycle_trigger_pct,
        "min_market_heat": min_market_heat,
        "reference": _row(ref),
        "density_cap": _row(cap),
        "recycle_ladder": _row(ladder),
        "regime_gate": _row(regime),
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out_dir / "report.md").write_text(format_report(report))
    return report


def format_report(report: dict) -> str:
    ref, cap = report["reference"], report["density_cap"]
    ladder = report.get("recycle_ladder")
    regime = report.get("regime_gate")

    def line(name: str, row: dict) -> str:
        wr = f"{row['win_rate'] * 100:.0f}%" if row["win_rate"] is not None else "–"
        return (f"| {name} | {row['return_pct']:+.2f}% | {row['closed']} | "
                f"{wr} | {row['max_drawdown_pct']:.1f}% |")

    rows = [
        line("Referenz", ref),
        line(f"Dichte-Kappe (max. {report['max_smart_buyers']})", cap),
    ]
    deltas = [f"Kappe {cap['return_pct'] - ref['return_pct']:+.2f}"]
    if ladder is not None:
        rows.append(line(f"Recycle-Leiter (+{report['recycle_trigger_pct']:.0f}%)", ladder))
        deltas.append(f"Leiter {ladder['return_pct'] - ref['return_pct']:+.2f}")
    if regime is not None:
        rows.append(line(f"Regime-Gate (≥{report['min_market_heat']:.0f} Grads/h)", regime))
        deltas.append(f"Regime {regime['return_pct'] - ref['return_pct']:+.2f}")
    return "\n".join([
        "# Paper-Trading A/B-Bericht",
        "",
        f"Aufzeichnung ab {report['recorded_utc']} UTC, "
        f"{report['span_hours']:.1f} h, {report['n_events']} Events, "
        f"Start {report['budget_sol']} SOL (Paper).",
        "",
        "| Lauf | Ergebnis | Trades | Winrate | Max-DD |",
        "|---|---|---|---|---|",
        *rows,
        "",
        f"**Delta zur Referenz (Punkte): {', '.join(deltas)}.** Einzeltage sind "
        "verrauscht – zählen tut die Serie über mehrere frische Aufzeichnungen.",
    ]) + "\n"
