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

    p_replay = sub.add_parser("replay", help="Aufgezeichnete Events (JSONL) durch den Bot spielen")
    p_replay.add_argument("events_file")

    args = parser.parse_args(argv)

    from .bot import Bot, BotConfig

    if args.cmd == "run":
        config = BotConfig()
        config.risk.budget_sol = args.budget_sol
        config.risk.position_sol = args.position_sol
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
