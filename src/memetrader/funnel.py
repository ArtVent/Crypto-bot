"""Entry-Funnel-Diagnose: WARUM handelt der Bot (nicht)?

Spielt eine Aufzeichnung durch dieselben Curve-/Strategie-Bausteine wie der
Bot und zählt, an welcher Regel Kandidaten scheitern. Zweck: Wenn ein
45-Minuten-Lauf mit zehntausenden Events 0 Trades macht, muss sichtbar sein,
ob die Daten das Entry-Profil einfach nie erfüllen (echtes Marktbild) oder
ob eine Aufnahme-/Formatlücke alles blockt (Bug).

Gezählt wird pro Kauf-Event die ERSTE gescheiterte Regel (decision.reasons[0]),
zusätzlich wie viele Mints jemals alle Kriterien erfüllt hätten. Rein lesend,
kein Handel, keine Seiteneffekte.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .curve import CurveState
from .strategy import MomentumStrategy


def _reason_key(reason: str) -> str:
    """Variable Teile (Zahlen) entfernen, damit Gründe aggregierbar sind."""
    return re.sub(r"[-+]?\d[\d.,]*", "N", reason)


def analyze_funnel(events_file: str | Path) -> dict:
    strategy = MomentumStrategy()
    curves: dict[str, CurveState] = {}
    symbol_counts: dict[str, int] = {}
    creator_counts: dict[str, int] = {}
    first_reason = Counter()
    would_enter_mints: set[str] = set()
    n_buy_events = 0

    with open(events_file) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            tx = e.get("txType")
            mint = e.get("mint")
            if not mint:
                continue
            now = float(e.get("_t", 0.0))

            if tx == "create":
                sym = (e.get("symbol") or "").upper()
                creator = e.get("traderPublicKey") or ""
                st = CurveState(
                    mint=mint, creator=creator, symbol=e.get("symbol") or "",
                    name=e.get("name") or "", uri=e.get("uri") or "",
                    v_sol=float(e.get("vSolInBondingCurve") or 0.0),
                    v_tokens=float(e.get("vTokensInBondingCurve") or 0.0),
                    created_at=now, dev_buy_sol=float(e.get("solAmount") or 0.0),
                    real_sol_in_curve=float(e.get("solAmount") or 0.0),
                )
                st.symbol_dupes_before = symbol_counts.get(sym, 0)
                st.creator_prior_launches = creator_counts.get(creator, 0)
                if sym:
                    symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
                if creator:
                    creator_counts[creator] = creator_counts.get(creator, 0) + 1
                curves[mint] = st
                continue

            st = curves.get(mint)
            if st is None:
                first_reason["kein Create in Aufnahme (Coin vor Start gelauncht)"] += 1
                continue
            if tx in ("buy", "sell"):
                st.apply_trade(e, now)
                if tx != "buy":
                    continue
                n_buy_events += 1
                decision = strategy.evaluate(st, now)
                if decision.enter:
                    would_enter_mints.add(mint)
                else:
                    first_reason[_reason_key(decision.reasons[0])] += 1
            elif tx == "migrate" or e.get("pool") == "pump-amm":
                st.migrated = True

    # Reifegrad der IM FENSTER geborenen Coins: wie weit kommen sie überhaupt?
    # Zeigt "nahe an min_buys=15" (Schwelle zu streng) vs "sterben bei 3" (kalter Markt).
    cfg = strategy.config
    peak_buys = sorted((s.buys for s in curves.values()), reverse=True)
    reached = lambda n: sum(1 for s in curves.values() if s.buys >= n)
    reached_buyers = lambda n: sum(1 for s in curves.values() if len(s.unique_buyers) >= n)
    maturity = {
        "max_buys_any_coin": peak_buys[0] if peak_buys else 0,
        "coins>=5_buys": reached(5),
        "coins>=10_buys": reached(10),
        f"coins>=min_buys({cfg.min_buys})": reached(cfg.min_buys),
        f"coins>=min_unique_buyers({cfg.min_unique_buyers})": reached_buyers(cfg.min_unique_buyers),
        "coins_meeting_both_demand_gates": sum(
            1 for s in curves.values()
            if s.buys >= cfg.min_buys and len(s.unique_buyers) >= cfg.min_unique_buyers),
    }

    return {
        "note": ("misst NUR das Strategie-Gate (Curve/Momentum); die nachgelagerten "
                 "Bot-Gates serial_creator/market_heat/smart_wallets/ML/Claude/risk "
                 "sind hier NICHT enthalten – mints_would_enter ist eine Obergrenze"),
        "mints_seen": len(curves),
        "buy_events": n_buy_events,
        "in_window_maturity": maturity,
        "mints_would_enter": len(would_enter_mints),
        "dev_buy_zero_mints": sum(1 for s in curves.values() if s.dev_buy_sol <= 0.0),
        "top_block_reasons": first_reason.most_common(12),
    }


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="memetrader funnel")
    p.add_argument("events_file")
    args = p.parse_args(argv)
    result = analyze_funnel(args.events_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
