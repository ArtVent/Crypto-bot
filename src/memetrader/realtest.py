"""Real-Test: die Entry-Pipeline des Bots gegen ECHTE historische Coins.

Datengrundlage: MELT (41.470 real graduierte pump.fun-Coins, Dez 2024–März
2025) mit realen Outcomes je Coin: min_ratio (tiefster Preis nach Graduation
relativ zum Startpreis) und return_ratio (Endrendite). Lizenz CC BY-NC 4.0 –
nur Forschung/persönliche Experimente.

Was hier getestet wird – und was nicht:
- GETESTET (real): die Auswahl-Entscheidung des Bots zum Launch-/Graduations-
  Zeitpunkt (ML-Gate, Impersonations-Veto, kausale Ticker-/Creator-Zähler)
  gegen das, was mit diesen realen Coins danach WIRKLICH passierte.
- ANGENÄHERT: die Exits. Es liegen nur Tiefpunkt und Endstand vor, nicht der
  Pfad. Konservative Ordnungs-Annahme: Der Stop zählt zuerst –
    min_ratio <= 0.65  -> Stop-Loss bei -35 % (auch wenn der Coin danach lief)
    return >= 2.5      -> TP-Leiter: 50 % bei +100 %, Rest bei +250 % => +175 %
    sonst              -> Endrendite (min_ratio > 0.65 impliziert Rendite > -35 %)
  Abzüglich 4 % Roundtrip-Kosten (Fees + Slippage) auf jeden Trade.
- NICHT GETESTET: Curve-Phase-Timing und Mikrostruktur-Gates (bräuchten
  Trade-Streams).
- SAUBERKEIT: Bewertet wird NUR der chronologische Hold-out (letzte 20 %),
  auf dem das ML-Modell nie trainiert wurde. Feature-Zähler sind strikt kausal.

Aufruf:  python -m memetrader.realtest --melt-dir /pfad/zu/MELT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from .simulate import TOP_COINS
from .train_mlfilter import FEATURES, build_dataset

ROUNDTRIP_COST = 0.04
STOP_PNL = -0.35
STOP_TRIGGER_RATIO = 0.65
TP_LADDER_TRIGGER = 2.5
TP_LADDER_PNL = 1.75


def approx_trade_pnl(min_ratio: float, return_ratio: float) -> float:
    """Konservative Exit-Approximation (Stop hat Vorrang vor Gewinnen)."""
    if min_ratio <= STOP_TRIGGER_RATIO:
        pnl = STOP_PNL
    elif return_ratio >= TP_LADDER_TRIGGER:
        pnl = TP_LADDER_PNL
    else:
        pnl = return_ratio
    return pnl - ROUNDTRIP_COST


def run_realtest(melt_dir: Path, model_path: Path, ml_threshold: float = 0.80,
                 position_sol: float = 0.05, test_fraction: float = 0.2) -> dict:
    df = build_dataset(melt_dir)
    labels = pd.read_csv(melt_dir / "data/label/label.csv")
    meta = pd.read_json(melt_dir / "data/memecoin/metadata.jsonl", lines=True)
    df = df.merge(meta[["address", "name", "symbol"]],
                  left_on="mint_address", right_on="address", how="left")

    # Chronologischer Hold-out: exakt derselbe Split wie im Training
    split = int(len(df) * (1 - test_fraction))
    test = df.iloc[split:].copy()

    bundle = joblib.load(model_path)
    test["ml_risk"] = bundle["model"].predict_proba(test[FEATURES])[:, 1]

    # Entry-Pipeline (alles zum Entscheidungszeitpunkt verfügbar):
    upper_name = test["name"].fillna("").str.upper()
    upper_sym = test["symbol"].fillna("").str.upper()
    vet_veto = upper_name.isin(TOP_COINS) | upper_sym.isin(TOP_COINS)
    dupe_block = test["symbol_dupes_before"] > 0  # Ticker-Krieg-Dedupe
    ml_block = test["ml_risk"] >= ml_threshold
    selected = test[~vet_veto & ~dupe_block & ~ml_block].copy()

    # Reale Outcomes -> approximierte Trade-PnL
    def pnl_stats(frame: pd.DataFrame) -> dict:
        pnls = [approx_trade_pnl(r.min_ratio, r.return_ratio) for r in frame.itertuples()]
        s = pd.Series(pnls)
        return {
            "n": len(s),
            "mean_pnl_pct": round(100 * s.mean(), 2) if len(s) else None,
            "median_pnl_pct": round(100 * s.median(), 2) if len(s) else None,
            "win_rate_pct": round(100 * (s > 0).mean(), 1) if len(s) else None,
            "stopped_out_pct": round(100 * (frame["min_ratio"] <= STOP_TRIGGER_RATIO).mean(), 1),
            "tp_ladder_pct": round(100 * ((frame["min_ratio"] > STOP_TRIGGER_RATIO)
                                          & (frame["return_ratio"] >= TP_LADDER_TRIGGER)).mean(), 1),
            "total_pnl_sol_at_position": round(float(s.sum()) * position_sol, 4),
            "high_risk_share_pct": round(100 * (frame["label"] == "high").mean(), 1),
        }

    result = {
        "test_period_coins": len(test),
        "selected_by_bot": len(selected),
        "selection_rate_pct": round(100 * len(selected) / len(test), 2),
        "blocked": {
            "impersonation_veto": int(vet_veto.sum()),
            "ticker_dedupe": int((dupe_block & ~vet_veto).sum()),
            "ml_gate": int((ml_block & ~vet_veto & ~dupe_block).sum()),
        },
        "bot_selection": pnl_stats(selected),
        "baseline_all_graduates": pnl_stats(test),
        "exit_model": {
            "stop": f"{STOP_PNL:.0%} sobald min_ratio <= {STOP_TRIGGER_RATIO}",
            "tp_ladder": f"+{TP_LADDER_PNL:.0%} ab Endrendite >= {TP_LADDER_TRIGGER:.0%}",
            "roundtrip_cost": f"{ROUNDTRIP_COST:.0%}",
            "ordering_assumption": "konservativ: Stop vor Gewinn",
        },
    }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--melt-dir", required=True)
    parser.add_argument("--model", default="models/mlfilter-melt.joblib")
    parser.add_argument("--ml-threshold", type=float, default=0.80)
    parser.add_argument("--position-sol", type=float, default=0.05)
    args = parser.parse_args(argv)

    result = run_realtest(Path(args.melt_dir), Path(args.model),
                          ml_threshold=args.ml_threshold, position_sol=args.position_sol)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
