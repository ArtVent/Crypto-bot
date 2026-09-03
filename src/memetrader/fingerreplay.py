"""Wochen-Replay auf dem Fingerprinter-Datensatz (eine echte Handelswoche).

Daten: willho/fingerprinter-dataset – 39.010 reale pump.fun-Launches,
03.–09.06.2026, 657k event-getriggerte Snapshots (Preis in SOL,
pump_magnitude = Vielfaches des Discovery-Preises, kumulative Wallets/Trades/
Volumen, Drawdown-/Deathbed-Events). Keine Lizenz angegeben -> nur lokale
Auswertung, Daten werden nicht redistribuiert.

Abbildung der Bot-Logik auf Event-Granularität:
- ENTRY = Momentum-Bestätigung wie im Curve-Bot: erster Snapshot mit
  pump_magnitude >= 2 im Beobachtungsfenster (45s–45min nach Discovery),
  plus Nachfrage-Beweis (unique_wallets, trade_count, Volumen) und
  Erst-Zyklus (keine Re-Pump-Zombies). Einstieg zum Snapshot-Preis
  (Event-Zeitpunkt = ausführbar), 3 % Roundtrip-Kosten.
- EXITS an jedem Folge-Snapshot: Stop -35 %, Derisk 50 % bei +100 %,
  danach Trailing 30 % unter Peak, Deathbed-Exit, Timeout 4 h,
  Datenende -> letzter Preis. (15-%-Move-Trigger geben die Granularität.)
- PORTFOLIO: 1 SOL Budget, 0,05 SOL je Position, max. 3 parallel,
  Tages-Kill-Switch -0,15 SOL, Cash-Rechnung chronologisch.

Bekannte Grenzen: Discovery-Auswahl des Quellsystems (~5,8k Launches/Tag,
nicht alle Creates), Event- statt Tick-Granularität, Fill zum Snapshot-Preis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

FEES_ROUNDTRIP = 0.03

ENTRY = dict(
    min_magnitude=2.0,
    min_age_s=45.0, max_age_s=45 * 60.0,
    min_unique_wallets=10, min_trades=15, min_volume_sol=5.0,
    max_cycle=1,
)
EXITS = dict(stop_pct=-35.0, derisk_at_pct=100.0, trailing_stop_pct=30.0,
             max_hold_s=4 * 3600.0)


class Position:
    __slots__ = ("mint", "entry_price", "entry_ts", "peak_pnl", "derisked", "realized_frac")

    def __init__(self, mint, price, ts):
        self.mint, self.entry_price, self.entry_ts = mint, price, ts
        self.peak_pnl, self.derisked, self.realized_frac = 0.0, False, 0.0

    def evaluate(self, price: float, ts: float, deathbed: bool) -> float | None:
        """Gibt Gesamt-PnL-Anteil zurück, wenn die Position schließt."""
        pnl = price / self.entry_price - 1.0
        self.peak_pnl = max(self.peak_pnl, pnl)
        open_frac = 0.5 if self.derisked else 1.0
        if deathbed or pnl <= EXITS["stop_pct"] / 100:
            return self.realized_frac + open_frac * max(pnl, -1.0) - FEES_ROUNDTRIP
        if not self.derisked and pnl >= EXITS["derisk_at_pct"] / 100:
            self.realized_frac += 0.5 * pnl
            self.derisked = True
            open_frac = 0.5
        if self.derisked and self.peak_pnl - pnl >= EXITS["trailing_stop_pct"] / 100 * (1 + self.peak_pnl):
            return self.realized_frac + open_frac * pnl - FEES_ROUNDTRIP
        if ts - self.entry_ts > EXITS["max_hold_s"]:
            return self.realized_frac + open_frac * pnl - FEES_ROUNDTRIP
        return None

    def force_close(self, price: float) -> float:
        pnl = price / self.entry_price - 1.0
        open_frac = 0.5 if self.derisked else 1.0
        return self.realized_frac + open_frac * pnl - FEES_ROUNDTRIP


def run(parquet: Path, budget_sol=1.0, position_sol=0.05, max_concurrent=3,
        daily_stop_sol=0.15, momentum_confirmation=True) -> dict:
    df = pd.read_parquet(parquet).sort_values("timestamp", kind="stable")
    df = df[df.current_price.notna() & (df.current_price > 0)]

    discovery_ts: dict[str, float] = {}
    positions: dict[str, Position] = {}
    done: set[str] = set()
    cash, day, daily_pnl, halted = budget_sol, None, 0.0, False
    trades: list[float] = []
    last_price: dict[str, float] = {}
    equity_min = budget_sol
    halted_days = 0

    for row in df.itertuples():
        ts = row.timestamp / 1000.0
        mint = row.mint
        price = float(row.current_price)
        last_price[mint] = price

        d = int(ts // 86400)
        if d != day:
            if halted:
                halted_days += 1
            day, daily_pnl, halted = d, 0.0, False

        if row.trigger_reason == "discovery":
            discovery_ts.setdefault(mint, ts)
            continue

        pos = positions.get(mint)
        if pos is not None:
            result = pos.evaluate(price, ts, bool(row.is_deathbed) or row.phase == "deathbed")
            if result is not None:
                pnl_sol = position_sol * result
                cash += position_sol + pnl_sol
                daily_pnl += pnl_sol
                trades.append(pnl_sol)
                del positions[mint]
                done.add(mint)
                if daily_pnl <= -daily_stop_sol:
                    halted = True
                equity_min = min(equity_min, cash + position_sol * len(positions)
                                 * (1 + EXITS["stop_pct"] / 100))
            continue

        if mint in done or halted or len(positions) >= max_concurrent or cash < position_sol:
            continue
        disco = discovery_ts.get(mint)
        if disco is None:
            continue
        age = ts - disco
        e = ENTRY
        if not (e["min_age_s"] <= age <= e["max_age_s"]):
            continue
        if momentum_confirmation and not (row.pump_magnitude or 0) >= e["min_magnitude"]:
            continue
        if (row.cycle_count or 1) > e["max_cycle"]:
            continue
        if (row.unique_wallets or 0) < e["min_unique_wallets"]:
            continue
        if (row.total_trade_count or 0) < e["min_trades"]:
            continue
        if (row.total_volume_sol or 0) < e["min_volume_sol"]:
            continue
        if bool(row.is_deathbed) or row.phase == "deathbed":
            continue
        positions[mint] = Position(mint, price, ts)
        cash -= position_sol

    for mint, pos in positions.items():
        result = pos.force_close(last_price.get(mint, pos.entry_price))
        cash += position_sol + position_sol * result
        trades.append(position_sol * result)

    wins = [t for t in trades if t > 0]
    return {
        "mints_total": int(df.mint.nunique()),
        "trades": len(trades),
        "final_equity_sol": round(cash, 4),
        "return_pct": round((cash - budget_sol) / budget_sol * 100, 2),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else None,
        "avg_win_sol": round(sum(wins) / len(wins), 4) if wins else None,
        "avg_loss_sol": round(sum(t for t in trades if t <= 0) / max(1, len(trades) - len(wins)), 4),
        "payoff_ratio": round(abs((sum(wins) / len(wins)) / (sum(t for t in trades if t <= 0)
                              / max(1, len(trades) - len(wins)))), 2) if wins and len(wins) < len(trades) else None,
        "halted_days": halted_days,
        "worst_equity_approx_sol": round(equity_min, 4),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", required=True)
    parser.add_argument("--budget-sol", type=float, default=1.0)
    args = parser.parse_args(argv)

    print("=== Bot-Regel: Momentum-Bestätigung (mag>=2) + Nachfrage-Beweis ===")
    print(json.dumps(run(Path(args.parquet), budget_sol=args.budget_sol,
                         momentum_confirmation=True), indent=2))
    print("\n=== Kontrolle: OHNE Momentum-Bestätigung (sonst identisch) ===")
    print(json.dumps(run(Path(args.parquet), budget_sol=args.budget_sol,
                         momentum_confirmation=False), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
