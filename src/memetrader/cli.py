"""memetrader CLI.

  python -m memetrader run [--budget-sol 1.0] [--position-sol 0.05]
  python -m memetrader run --live --i-understand-the-risk   (Opt-in, Key lokal)
  python -m memetrader replay <events.jsonl>                (Backtest auf Aufzeichnung)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memetrader", description="Gefilterter pump.fun-Momentum-Bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Bot starten (Default: Paper-Trading)")
    p_run.add_argument("--budget-sol", type=float, default=1.0)
    p_run.add_argument("--position-sol", type=float, default=0.05)
    p_run.add_argument("--live", action="store_true", help="ECHTES Geld – nur mit --i-understand-the-risk")
    p_run.add_argument("--i-understand-the-risk", action="store_true")
    p_run.add_argument("--ml-model", default="models/mlfilter-melt.joblib",
                       help="Pfad zum ML-Risiko-Modell ('' = ohne ML-Gate)")
    p_run.add_argument("--ml-threshold", type=float, default=0.80)
    p_run.add_argument("--claude", action="store_true",
                       help="Live-Claude-Verbindung: Entry-Vets, Post-Mortems, Reviews (braucht ANTHROPIC_API_KEY)")

    p_replay = sub.add_parser("replay", help="Aufgezeichnete Events (JSONL) durch den Bot spielen")
    p_replay.add_argument("events_file")

    p_analyze = sub.add_parser("analyze", help="Entscheidungs-Log auswerten (PnL, Trefferquote, Exit-Gründe)")
    p_analyze.add_argument("log_file", nargs="?", default="memetrader.log.jsonl")

    p_bt = sub.add_parser("backtest", help="Lookahead-freier Backtest (simulierter Markt oder Aufzeichnung)")
    p_bt.add_argument("--days", type=float, default=60.0)
    p_bt.add_argument("--launches-per-day", type=int, default=400)
    p_bt.add_argument("--budget-sol", type=float, default=1.0)
    p_bt.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    p_bt.add_argument("--claude", choices=["stub", "live", "off"], default="stub")
    p_bt.add_argument("--events", help="JSONL echter aufgezeichneter Events statt Simulation")
    p_bt.add_argument("--workdir", default="backtest-runs")
    p_bt.add_argument("--baseline", action="store_true",
                      help="Mikrostruktur-Gates (Bundle/Wash) deaktivieren – für Vorher/Nachher-Vergleiche")

    p_brain = sub.add_parser("brain", help="Gelernten Zustand zeigen: Lektionen, Selbst-Tuning-Historie")
    p_brain.add_argument("--journal", default="memetrader.journal.jsonl")
    p_brain.add_argument("--tuning", default="memetrader.tuning.json")

    p_advise = sub.add_parser("advise", help="Claude-Review des Journals (Vorschläge; --apply wendet sie begrenzt an)")
    p_advise.add_argument("--journal", default="memetrader.journal.jsonl")
    p_advise.add_argument("--apply", action="store_true")

    args = parser.parse_args(argv)

    from .bot import Bot, BotConfig

    if args.cmd == "run":
        config = BotConfig()
        config.risk.budget_sol = args.budget_sol
        config.risk.position_sol = args.position_sol
        if args.ml_model:
            from pathlib import Path as _Path

            if _Path(args.ml_model).exists():
                config.ml_model_path = args.ml_model
                config.ml_risk_threshold = args.ml_threshold
            else:
                print(f"Hinweis: ML-Modell {args.ml_model} nicht gefunden – Bot läuft ohne ML-Gate.")
        if args.claude:
            try:
                import anthropic  # noqa: F401
            except ImportError:
                print("--claude benötigt das anthropic-SDK: pip install anthropic", file=sys.stderr)
                return 2
            config.claude_enabled = True
            print("Live-Claude-Verbindung aktiv: Entry-Vets, Post-Mortems und Reviews "
                  f"laufen über {__import__('memetrader.claude_link', fromlist=['CLAUDE_MODEL']).CLAUDE_MODEL}; "
                  "Gedächtnis: memetrader.memory.md")
        broker = None
        if args.live:
            if not args.i_understand_the_risk:
                print(
                    "Live-Modus verweigert: --i-understand-the-risk fehlt.\n"
                    "Vorher lesen: docs/strategien.md (Risiko), docs/fee-oekonomie.md (Kosten).\n"
                    "Erwartung laut eigener Datenbank: Die Mehrheit verliert. Erst Paper-Ergebnisse ansehen.",
                    file=sys.stderr,
                )
                return 2
            from .broker import LiveBroker

            broker = LiveBroker(max_position_sol=args.position_sol)
            print("LIVE-Modus. Positionsgröße", args.position_sol, "SOL. Kill-Switch:", config.risk.daily_loss_stop_sol, "SOL")
        try:
            asyncio.run(Bot(config, broker=broker).run())
        except KeyboardInterrupt:
            print("\nbeendet")
        return 0

    if args.cmd == "analyze":
        from .analyze import analyze_file

        print(analyze_file(args.log_file).report())
        return 0

    if args.cmd == "backtest":
        from statistics import mean, median

        from .backtest import run_backtest

        events = None
        if args.events:
            events = []
            with open(args.events) as fh:
                for line in fh:
                    if line.strip():
                        record = json.loads(line)
                        events.append((record.pop("_t"), record))
            events.sort(key=lambda e: e[0])
        results = []
        for seed in args.seeds:
            result = run_backtest(days=args.days, launches_per_day=args.launches_per_day,
                                  seed=seed, budget_sol=args.budget_sol,
                                  workdir=args.workdir, claude=args.claude, events=events,
                                  hardened_checks=not args.baseline)
            print(result.summary())
            results.append(result)
        finals = [r.final_equity_sol for r in results]
        print("\n=== Aggregat über Seeds ===")
        print(f"Endkapital: min {min(finals):.4f} / median {median(finals):.4f} / "
              f"mean {mean(finals):.4f} / max {max(finals):.4f} SOL (Start {args.budget_sol})")
        return 0

    if args.cmd == "brain":
        from collections import Counter
        from pathlib import Path as _Path

        from .journal import load_journal_records

        records = load_journal_records(args.journal)
        lessons = Counter(r.get("lesson") for r in records if r.get("lesson"))
        pnl = sum(r.get("pnl_sol") or 0.0 for r in records)
        print("=== memetrader Gehirn ===")
        print(f"Abgeschlossene Trades im Journal: {len(records)}  |  PnL: {pnl:+.4f} SOL")
        if lessons:
            print("Gelernte Lektionen:")
            for lesson, count in lessons.most_common():
                print(f"  {lesson:<26} {count:>3}x")
        tuning = _Path(args.tuning)
        if tuning.exists():
            state = json.loads(tuning.read_text())
            print("Wirksame (selbst-kalibrierte) Parameter:")
            for key, val in state.get("effective", {}).items():
                print(f"  {key:<26} {val}")
            print("Letzte Selbst-Anpassungen:")
            for adj in state.get("history", [])[-5:]:
                print(f"  {adj['param']}: {adj['old']} -> {adj['new']}  ({adj['reason']})")
        else:
            print("Noch keine Selbst-Anpassungen (memetrader.tuning.json fehlt).")
        return 0

    if args.cmd == "advise":
        from .adaptive import AdaptiveTuner, Bounds
        from .advisor import apply_proposals, ask_advisor, summarize_journal
        from .journal import load_journal_records
        from .risk import RiskConfig
        from .strategy import StrategyConfig

        records = load_journal_records(args.journal)
        if not records:
            print("Journal ist leer – erst Paper-Trading laufen lassen.")
            return 1
        strategy_cfg, risk_cfg = StrategyConfig(), RiskConfig()
        tuner = AdaptiveTuner(strategy_cfg, risk_cfg)
        effective = {"stop_loss_pct": risk_cfg.stop_loss_pct, "take_profit_pct": risk_cfg.take_profit_pct,
                     "progress_deadline_seconds": risk_cfg.progress_deadline_seconds,
                     "min_fill_pct": strategy_cfg.min_fill_pct, "min_unique_buyers": strategy_cfg.min_unique_buyers}
        bounds = {k: getattr(Bounds(), k) for k in
                  ("stop_loss_pct", "take_profit_pct", "progress_deadline_seconds", "min_fill_pct", "min_unique_buyers")}
        try:
            review = ask_advisor(summarize_journal(records, effective, bounds))
        except (RuntimeError, ValueError) as exc:
            print(f"Berater nicht verfügbar: {exc}", file=sys.stderr)
            return 2
        print("=== Claude-Review ===")
        print(review.get("analysis", ""))
        for warning in review.get("warnings", []):
            print(f"⚠ {warning}")
        proposals = review.get("proposals", [])
        if not proposals:
            print("Keine Änderungsvorschläge.")
            return 0
        for p in proposals:
            print(f"Vorschlag: {p.get('param')} -> {p.get('value')}  ({p.get('reason')})")
        if args.apply:
            for line in apply_proposals(proposals, tuner):
                print(f"  {line}")
            print("Angewendet (innerhalb der Bounds) und in memetrader.tuning.json persistiert.")
        else:
            print("(--apply zum begrenzten Übernehmen)")
        return 0

    if args.cmd == "replay":
        bot = Bot()
        t = 0.0
        with open(args.events_file) as fh:
            for line in fh:
                if not line.strip():
                    continue
                record = json.loads(line)
                t = record.get("_t", t + 1.0)
                bot.on_event(record, now=t)
        print(json.dumps(bot.risk.summary(), indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
