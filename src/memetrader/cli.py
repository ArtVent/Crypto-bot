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

    p_replay = sub.add_parser("replay", help="Aufgezeichnete Events (JSONL) durch den Bot spielen")
    p_replay.add_argument("events_file")

    p_analyze = sub.add_parser("analyze", help="Entscheidungs-Log auswerten (PnL, Trefferquote, Exit-Gründe)")
    p_analyze.add_argument("log_file", nargs="?", default="memetrader.log.jsonl")

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
