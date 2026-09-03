"""memescan CLI.

  python -m memescan check <adresse> [--chain solana|ethereum|base|bsc] [--json]
  python -m memescan watch [--db launches.db]
  python -m memescan label [--db launches.db] [--min-age-hours 24]
  python -m memescan stats [--db launches.db]
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys

import httpx

from . import archiver
from .engine import evaluate
from .models import Verdict
from .providers import (
    fetch_dexscreener_liquidity,
    fetch_goplus,
    fetch_rugcheck,
)

DEFAULT_DB = "launches.db"


def cmd_check(args: argparse.Namespace) -> int:
    try:
        if args.chain == "solana":
            report = fetch_rugcheck(args.address)
        else:
            report = fetch_goplus(args.address, args.chain)
        # Liquidität/MC ergänzen (für MC/Liq- und Low-Liquidity-Regeln)
        try:
            liq = fetch_dexscreener_liquidity(args.address)
            if liq.get("has_pair"):
                report.liquidity_usd = report.liquidity_usd or liq.get("liquidity_usd")
                report.market_cap_usd = report.market_cap_usd or liq.get("market_cap_usd")
                report.sources.append("dexscreener")
        except httpx.HTTPError:
            pass
    except httpx.HTTPError as exc:
        print(f"Fehler beim Abruf: {exc}", file=sys.stderr)
        return 2

    result = evaluate(report)
    if args.json:
        print(json.dumps(dataclasses.asdict(result), default=str, ensure_ascii=False, indent=2))
    else:
        print(result.summary())
    return 0 if result.verdict == Verdict.ALLOW else 1


def cmd_watch(args: argparse.Namespace) -> int:
    print(f"Archiviere alle neuen pump.fun-Launches nach {args.db} (Ctrl+C zum Beenden)")
    try:
        asyncio.run(archiver.watch(args.db, quiet=args.quiet))
    except KeyboardInterrupt:
        print("\nbeendet")
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    n = archiver.label_outcomes(args.db, min_age_hours=args.min_age_hours)
    print(f"{n} Launches gelabelt")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    print(json.dumps(archiver.stats(args.db), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memescan", description="Memecoin-Sicherheits-Scanner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Token prüfen")
    p_check.add_argument("address")
    p_check.add_argument("--chain", default="solana", choices=["solana", "ethereum", "base", "bsc"])
    p_check.add_argument("--json", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_watch = sub.add_parser("watch", help="Alle neuen Launches archivieren")
    p_watch.add_argument("--db", default=DEFAULT_DB)
    p_watch.add_argument("--quiet", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_label = sub.add_parser("label", help="Outcomes alter Launches labeln")
    p_label.add_argument("--db", default=DEFAULT_DB)
    p_label.add_argument("--min-age-hours", type=float, default=24.0)
    p_label.set_defaults(func=cmd_label)

    p_stats = sub.add_parser("stats", help="Archiv-Statistik")
    p_stats.add_argument("--db", default=DEFAULT_DB)
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
