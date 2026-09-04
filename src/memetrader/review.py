"""Täglicher Strategie-Review: Ergebnisse ansehen, evidenzbasiert anpassen.

Disziplin (docs/forward-validierung.md): NICHT täglich an Parametern drehen –
das überanpasst an Rauschen und ruiniert das Konto. Dieser Review läuft
täglich, wertet Konto + Journal-Lektionen + A/B-Forward-Serie aus und gibt
eine EMPFEHLUNG mit vorregistrierter Evidenzregel zurück:

  Ein A/B-Arm wird nur dann als neuer Default empfohlen, wenn er über
  >= MIN_SERIES_DAYS Handelstage KUMULATIV vor der Referenz liegt UND sein
  Drawdown nicht schlechter ist. Sonst: HALTEN (nur dokumentieren).

Die Journal-Lektionen liefern zusätzlich einen Hinweis, WO das Problem liegt
(z. B. viele bad_entry -> Filter zu locker) – aber nur als Beobachtung, nicht
als automatische Änderung.
"""

from __future__ import annotations

import glob
import json
import time
from pathlib import Path

MIN_SERIES_DAYS = 14           # vorregistriert: so viele Handelstage vor Adoption
MIN_WINDOW_HOURS = 0.5         # kürzere Aufnahmen zählen nicht zur Serie
ARMS = ["density_cap", "recycle_ladder", "regime_gate", "insider_exit"]
ARM_LABEL = {"density_cap": "Dichte-Kappe", "recycle_ladder": "Recycle-Leiter",
             "regime_gate": "Regime-Gate", "insider_exit": "Insider-Exit"}


def _compound(returns_pct: list[float]) -> float:
    eq = 1.0
    for r in returns_pct:
        eq *= 1.0 + r / 100.0
    return (eq - 1.0) * 100.0


def load_series(reports_dir: str | Path) -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(Path(reports_dir) / "paper-*.json"))):
        try:
            d = json.loads(Path(p).read_text())
        except (ValueError, OSError):
            continue
        if d.get("span_hours", 0) >= MIN_WINDOW_HOURS and "reference" in d:
            out.append(d)
    return out


def series_verdict(series: list[dict]) -> dict:
    """Kumulative Arm-Performance + evidenzbasierte Empfehlung."""
    # nur Tage MIT Trades in der Referenz zählen als Handelstage
    active = [d for d in series if d["reference"].get("closed", 0) > 0
              or any(d.get(a, {}).get("closed", 0) > 0 for a in ARMS)]
    ref_cum = _compound([d["reference"]["return_pct"] for d in active])
    arms = {}
    for a in ARMS:
        rows = [d[a] for d in active if a in d]
        if not rows:
            continue
        arms[a] = {
            "cum_return_pct": round(_compound([r["return_pct"] for r in rows]), 2),
            "delta_vs_ref": round(_compound([r["return_pct"] for r in rows]) - ref_cum, 2),
            "avg_max_dd": round(sum(r["max_drawdown_pct"] for r in rows) / len(rows), 1),
        }
    ref_avg_dd = round(sum(d["reference"]["max_drawdown_pct"] for d in active) / len(active), 1) if active else 0.0

    recommendation = {"action": "hold", "arm": None,
                      "rationale": f"nur {len(active)} Handelstage (< {MIN_SERIES_DAYS}); Evidenz reicht nicht"}
    if len(active) >= MIN_SERIES_DAYS:
        # bester Arm, der Referenz schlägt UND Drawdown nicht verschlechtert
        cands = [(a, v) for a, v in arms.items()
                 if v["delta_vs_ref"] > 0 and v["avg_max_dd"] <= ref_avg_dd + 0.5]
        if cands:
            best = max(cands, key=lambda kv: kv[1]["delta_vs_ref"])
            recommendation = {
                "action": "adopt_arm", "arm": best[0],
                "rationale": (f"{ARM_LABEL[best[0]]} liegt über {len(active)} Handelstage "
                              f"{best[1]['delta_vs_ref']:+.2f} Punkte vor der Referenz "
                              f"bei Drawdown {best[1]['avg_max_dd']}% (Ref {ref_avg_dd}%)")}
        else:
            recommendation = {"action": "hold", "arm": None,
                              "rationale": f"{len(active)} Handelstage, aber kein Arm schlägt Referenz "
                                           f"bei gleichem/besserem Drawdown"}
    return {"trading_days": len(active), "ref_cum_return_pct": round(ref_cum, 2),
            "ref_avg_dd": ref_avg_dd, "arms": arms, "recommendation": recommendation}


def journal_watch(journal_path: str | Path, last_n: int = 60) -> dict:
    """Häufigste Lektionen der letzten Trades – Hinweis, WO es hakt (nur Beobachtung)."""
    from collections import Counter
    p = Path(journal_path)
    if not p.exists():
        return {"n": 0, "lessons": {}}
    recs = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    recs = recs[-last_n:]
    lessons = Counter(r.get("lesson") for r in recs if r.get("lesson"))
    return {"n": len(recs), "lessons": dict(lessons.most_common())}


def append_history(history_path: str | Path, state: dict, budget_sol: float = 1.0) -> None:
    """Tages-Snapshot des Kontos anhängen (idempotent pro UTC-Tag)."""
    p = Path(history_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                if json.loads(line).get("date") == today:
                    return  # heute schon erfasst
            except json.JSONDecodeError:
                continue
    equity = budget_sol + state.get("realized_pnl_sol", 0.0)
    row = {"date": today, "equity_sol": round(equity, 6),
           "return_pct": round((equity / budget_sol - 1) * 100, 2),
           "total_entries": state.get("total_entries", 0),
           "day_entries": state.get("day_entries", 0)}
    with p.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def daily_review(state_path: str | Path, journal_path: str | Path,
                 reports_dir: str | Path, history_path: str | Path,
                 budget_sol: float = 1.0) -> dict:
    try:
        state = json.loads(Path(state_path).read_text())
    except (OSError, ValueError):
        state = {}
    append_history(history_path, state, budget_sol)
    equity = budget_sol + state.get("realized_pnl_sol", 0.0)
    return {
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "account": {"equity_sol": round(equity, 4),
                    "return_pct": round((equity / budget_sol - 1) * 100, 2),
                    "total_entries": state.get("total_entries", 0),
                    "sessions": state.get("sessions", 0)},
        "journal": journal_watch(journal_path),
        "ab_series": series_verdict(load_series(reports_dir)),
    }


def format_review(r: dict) -> str:
    acc, ab = r["account"], r["ab_series"]
    rec = ab["recommendation"]
    lines = [
        f"## Tages-Review {r['date']}",
        "",
        f"- **Konto:** {acc['equity_sol']} SOL ({acc['return_pct']:+.2f}% seit Start), "
        f"{acc['total_entries']} Trades gesamt, {acc['sessions']} Sessions.",
        f"- **Journal (letzte {r['journal']['n']}):** {r['journal']['lessons'] or 'keine Lektionen'}",
        f"- **A/B-Serie:** {ab['trading_days']} Handelstage, Referenz kumulativ "
        f"{ab['ref_cum_return_pct']:+.2f}% (Ø-DD {ab['ref_avg_dd']}%).",
    ]
    for a, v in ab["arms"].items():
        lines.append(f"  - {ARM_LABEL[a]}: kumulativ {v['cum_return_pct']:+.2f}% "
                     f"({v['delta_vs_ref']:+.2f} vs Ref), Ø-DD {v['avg_max_dd']}%")
    verb = {"hold": "HALTEN", "adopt_arm": "ANPASSEN"}.get(rec["action"], rec["action"])
    lines += ["", f"**Empfehlung: {verb}** – {rec['rationale']}."]
    if rec["action"] == "adopt_arm":
        lines.append(f"(Zu übernehmender Arm: `{rec['arm']}`.)")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="memetrader review")
    p.add_argument("--state", default="state/live-state.json")
    p.add_argument("--journal", default="state/live.journal.jsonl")
    p.add_argument("--reports", default="reports")
    p.add_argument("--history", default="state/equity-history.jsonl")
    p.add_argument("--json", action="store_true", help="Rohdaten als JSON ausgeben")
    args = p.parse_args(argv)
    r = daily_review(args.state, args.journal, args.reports, args.history)
    print(json.dumps(r, ensure_ascii=False, indent=2) if args.json else format_review(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
