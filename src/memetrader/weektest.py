"""3-Wochen-Test auf echten Pfaden: Auswahl + Exits über 44k reale Coins.

Datengrundlage: ian05012/solana-memecoin-dataset (MIT) – 44.460 Snapshots
frisch graduierter/trendender Solana-Memecoins (10.–30.06.2026) mit echten
Mikrostruktur-Features (sniper_count, bundler_ratio, top10_holder_pct,
flipper_ratio, unique_buyers, lp_burned_pct, mint/freeze-Status …) und
15-Minuten-OHLCV-Pfaden über ein 3-Tage-Fenster je Coin.

Was getestet wird: die K.-o.-Auswahl des Bots (Schwellen PRÄ-REGISTRIERT aus
data/filter-features.json – vor Sichtung dieses Datensatzes festgelegt, hier
NICHT getunt) plus die pfadbasierte Exit-Engine (Stop, Derisk, Trailing) als
chronologische Portfolio-Simulation mit Budget, Concurrency-Limit und
Tages-Kill-Switch.

Grenzen: Einstieg erst am Snapshot-Zeitpunkt (post-Graduation; Curve-Timing
ist hier NICHT abgebildet), 15-Minuten-Granularität (Intrabar konservativ:
Stop vor Gewinn), USD-Pfade (SOL/USD-Drift über <=3 Tage ignoriert),
GMGN-Auswahl-Bias des Datensatzes (Trending-Coins überrepräsentiert).
"""

from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path

import pandas as pd

FEES_ROUNDTRIP = 0.03  # PumpSwap-Fees + Slippage, konservativ

# Prä-registrierte K.-o.-Schwellen (data/filter-features.json / filter-engine.md).
# Achtung Datensatz-Einheiten: alle *_pct-/ratio-Felder sind 0-1-Ratios.
SELECTION = dict(
    require_mint_freeze_disabled=True,
    min_lp_burned_pct=0.90,
    max_top10_holder_pct=0.30,
    max_bundler_ratio=0.30,
    max_dev_remaining_pct=0.20,
    min_unique_buyers=10,
    max_flipper_ratio=0.35,     # Roundtrip-/Wash-Analog
    min_liquidity_usd=10_000.0,
)

EXITS = dict(
    stop_pct=-35.0,
    derisk_at_pct=100.0,
    trailing_stop_pct=30.0,
)


def select(df: pd.DataFrame) -> pd.Series:
    s = SELECTION
    mask = pd.Series(True, index=df.index)
    if s["require_mint_freeze_disabled"]:
        mask &= df["mint_disabled"].fillna(False) & df["freeze_disabled"].fillna(False)
    mask &= df["lp_burned_pct"].fillna(0) >= s["min_lp_burned_pct"]  # 0-1-Ratio
    mask &= df["top10_holder_pct"].fillna(100) <= s["max_top10_holder_pct"]
    mask &= df["bundler_ratio"].fillna(1) <= s["max_bundler_ratio"]
    mask &= df["dev_remaining_pct"].fillna(100) <= s["max_dev_remaining_pct"]
    mask &= df["unique_buyers"].fillna(0) >= s["min_unique_buyers"]
    mask &= df["flipper_ratio"].fillna(1) <= s["max_flipper_ratio"]
    mask &= df["liquidity_usd"].fillna(0) >= s["min_liquidity_usd"]
    return mask


def simulate_exit(entry_price: float, candles: pd.DataFrame) -> tuple[float, float]:
    """Pfad-Simulation: (PnL-Anteil, Exit-Zeit). Konservativ: Stop vor Gewinn."""
    stop_level = entry_price * (1 + EXITS["stop_pct"] / 100)
    derisk_level = entry_price * (1 + EXITS["derisk_at_pct"] / 100)
    derisked = False
    realized = 0.0
    open_fraction = 1.0
    peak = entry_price

    for candle in candles.itertuples():
        # 1) Stop zuerst (konservative Intrabar-Ordnung)
        if candle.low <= stop_level:
            realized += open_fraction * (EXITS["stop_pct"] / 100)
            return realized - FEES_ROUNDTRIP, candle.ts
        peak = max(peak, candle.high)
        # 2) Derisk: Hälfte bei +100 %
        if not derisked and candle.high >= derisk_level:
            realized += 0.5 * (EXITS["derisk_at_pct"] / 100)
            open_fraction = 0.5
            derisked = True
        # 3) Trailing auf den Rest (aktiv nach Derisk)
        if derisked:
            trail_level = peak * (1 - EXITS["trailing_stop_pct"] / 100)
            if candle.low <= trail_level:
                pnl_rest = (trail_level - entry_price) / entry_price
                realized += open_fraction * pnl_rest
                return realized - FEES_ROUNDTRIP, candle.ts
    # Fenster-Ende: Rest zum letzten Close
    last_close = float(candles.iloc[-1]["close"])
    realized += open_fraction * ((last_close - entry_price) / entry_price)
    return realized - FEES_ROUNDTRIP, float(candles.iloc[-1]["ts"])


def run(data_dir: Path, budget_sol: float = 1.0, position_sol: float = 0.05,
        max_concurrent: int = 3, daily_stop_sol: float = 0.15,
        selection_on: bool = True) -> dict:
    tokens = pd.read_parquet(data_dir / "tokens.parquet")
    ohlcv = pd.read_parquet(data_dir / "ohlcv.parquet")
    ohlcv = ohlcv.sort_values(["token_address", "ts"])
    candles_by_token = {k: v for k, v in ohlcv.groupby("token_address")}

    tokens = tokens.sort_values("captured_at").drop_duplicates("token_address", keep="first")
    mask = select(tokens) if selection_on else pd.Series(True, index=tokens.index)
    candidates = tokens[mask]

    cash = budget_sol
    equity_min = budget_sol
    open_positions: list[tuple[float, float]] = []  # heap: (exit_ts, pnl_sol)
    day = None
    daily_pnl = 0.0
    halted = False
    trades = []

    for row in candidates.itertuples():
        ts = pd.Timestamp(row.captured_at).timestamp() if not isinstance(row.captured_at, (int, float)) else float(row.captured_at)
        candles = candles_by_token.get(row.token_address)
        if candles is None or len(candles) < 2:
            continue
        candles = candles[candles["ts"] >= ts]
        if len(candles) < 2:
            continue

        # abgelaufene Positionen realisieren
        while open_positions and open_positions[0][0] <= ts:
            _, pnl_sol = heapq.heappop(open_positions)
            cash += position_sol + pnl_sol
            daily_pnl += pnl_sol

        d = int(ts // 86400)
        if d != day:
            day, daily_pnl, halted = d, 0.0, False
        if halted or daily_pnl <= -daily_stop_sol:
            halted = True
            continue
        if len(open_positions) >= max_concurrent or cash < position_sol:
            continue

        # Ausführbarer Einstieg: Open des ersten Candles NACH Snapshot
        # (price_at_capture kann veraltet sein – Schein-Gewinn-Artefakt)
        entry_price = float(candles.iloc[0]["open"])
        if entry_price <= 0:
            continue
        pnl_frac, exit_ts = simulate_exit(entry_price, candles)
        pnl_sol = position_sol * pnl_frac
        cash -= position_sol
        heapq.heappush(open_positions, (float(exit_ts), pnl_sol))
        trades.append(pnl_sol)
        open_value = sum(position_sol for _ in open_positions)  # konservativ: Einstand
        equity_min = min(equity_min, cash + open_value + sum(p for _, p in open_positions if p < 0))

    while open_positions:
        _, pnl_sol = heapq.heappop(open_positions)
        cash += position_sol + pnl_sol

    wins = [t for t in trades if t > 0]
    return {
        "candidates_total": int(len(tokens)),
        "selected": int(len(candidates)),
        "trades_executed": len(trades),
        "final_equity_sol": round(cash, 4),
        "return_pct": round((cash - budget_sol) / budget_sol * 100, 2),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else None,
        "avg_win_sol": round(sum(wins) / len(wins), 4) if wins else None,
        "avg_loss_sol": round(sum(t for t in trades if t <= 0) / max(1, len(trades) - len(wins)), 4),
        "worst_equity_sol": round(equity_min, 4),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--budget-sol", type=float, default=1.0)
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)

    print("=== Bot-Auswahl (prä-registrierte K.-o.-Schwellen) ===")
    print(json.dumps(run(data_dir, budget_sol=args.budget_sol, selection_on=True), indent=2))
    print("\n=== Baseline: OHNE Auswahl (jeden Kandidaten handeln) ===")
    print(json.dumps(run(data_dir, budget_sol=args.budget_sol, selection_on=False), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
