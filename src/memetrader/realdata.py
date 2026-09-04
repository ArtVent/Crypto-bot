"""Konverter: echte pump.fun-Rohdaten (pumpfun-market-lab) -> Bot-Events.

Datenquelle: github.com/z17620794987-hub/pumpfun-market-lab – stündliche
Parquet-Dateien mit allen Bonding-Curve-Events eines Tages (event_type
create/swap, action buy/sell, user_wallet, token_creator, lamports_amount,
virtuelle/reale Reserven je Event). Lizenz: keine angegeben – Daten nur lokal
verwenden, nicht redistributieren.

Mapping auf das PumpPortal-Event-Format des Bots:
- create  -> txType=create (Dev-Buy: ein Buy des Creators im SELBEN Slot wird
  in das Create-Event gefaltet – on-chain sind Create+Erstkauf eine
  Transaktion, getrennte Zeilen im Datensatz)
- swap    -> txType=buy/sell, solAmount=lamports/1e9, vSol/vTokens aus den
  virtuellen Reserven
- Graduation gibt es im Datensatz nicht als Event -> synthetisches
  migrate-Event, sobald real_lamports_reserve >= 84 SOL (docs/pumpfun-mechanik.md).

Streng chronologisch (Datei-, Slot-, Zeilenreihenfolge); Generator, damit
3M+ Events nicht komplett im RAM liegen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

LAMPORTS = 1e9
TOKEN_DECIMALS = 1e6
GRADUATION_REAL_LAMPORTS = 84 * LAMPORTS


def _row_event(row) -> dict | None:
    v_sol = float(row.virtual_lamports_reserve) / LAMPORTS
    v_tok = float(row.virtual_token_reserve) / TOKEN_DECIMALS
    if row.event_type == "create":
        return {
            "txType": "create",
            "mint": row.token_mint,
            "traderPublicKey": row.token_creator,
            "name": row.name if isinstance(row.name, str) else "",
            "symbol": row.symbol if isinstance(row.symbol, str) else "",
            "uri": row.uri if isinstance(row.uri, str) else "",
            "solAmount": 0.0,
            "vSolInBondingCurve": v_sol,
            "vTokensInBondingCurve": v_tok,
        }
    if row.event_type == "swap" and row.action in ("buy", "sell"):
        return {
            "txType": row.action,
            "mint": row.token_mint,
            "traderPublicKey": row.user_wallet,
            "solAmount": float(row.lamports_amount or 0.0) / LAMPORTS,
            "vSolInBondingCurve": v_sol,
            "vTokensInBondingCurve": v_tok,
        }
    return None


def iter_day_events(data_dir: str | Path) -> Iterator[tuple[float, dict]]:
    import pandas as pd

    files = sorted(Path(data_dir).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"keine Parquet-Dateien in {data_dir}")

    graduated: set[str] = set()
    creators: dict[str, str] = {}

    for path in files:
        df = pd.read_parquet(path)
        df = df.sort_values(["slot_number"], kind="stable").reset_index(drop=True)

        pending_create: dict | None = None
        pending_slot: int | None = None
        pending_t: float = 0.0

        def flush():
            nonlocal pending_create
            if pending_create is not None:
                result = (pending_t, pending_create)
                pending_create = None
                return result
            return None

        for row in df.itertuples():
            event = _row_event(row)
            if event is None:
                continue
            t = float(row.timestamp)

            if event["txType"] == "create":
                out = flush()
                if out:
                    yield out
                creators[event["mint"]] = event["traderPublicKey"]
                pending_create, pending_slot, pending_t = event, int(row.slot_number), t
                continue

            # Dev-Buy im selben Slot in das Create falten
            if (
                pending_create is not None
                and event["mint"] == pending_create["mint"]
                and int(row.slot_number) == pending_slot
                and event["txType"] == "buy"
                and event["traderPublicKey"] == pending_create["traderPublicKey"]
            ):
                # Mehrere Creator-Buys im selben Slot summieren (Bundle), nicht
                # überschreiben; Reserven vom jeweils letzten (aktuellsten) Row.
                pending_create["solAmount"] += event["solAmount"]
                pending_create["vSolInBondingCurve"] = event["vSolInBondingCurve"]
                pending_create["vTokensInBondingCurve"] = event["vTokensInBondingCurve"]
                continue

            out = flush()
            if out:
                yield out
            yield (t, event)

            # Synthetische Graduation
            mint = event["mint"]
            if mint not in graduated and float(row.real_lamports_reserve) >= GRADUATION_REAL_LAMPORTS:
                graduated.add(mint)
                # gleicher Zeitstempel wie der auslösende Swap: hält die Ausgabe
                # monoton (heapq.merge im gemergten Strom setzt Sortierung voraus)
                yield (t, {"txType": "migrate", "mint": mint, "pool": "pump-amm"})

        out = flush()
        if out:
            yield out


def iter_amm_events(amm_dir: str | Path) -> Iterator[tuple[float, dict]]:
    """PumpSwap-AMM-Swaps als Bot-Events (pool='pump-amm').

    Reale Reserven dienen als Konstantprodukt-Basis für die Bewertung –
    PumpSwap ist ein x*y=k-AMM auf realen Reserven, simulate_sell darauf
    approximiert echte Verkaufserlöse.
    """
    import pandas as pd

    files = sorted(Path(amm_dir).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"keine Parquet-Dateien in {amm_dir}")
    for path in files:
        df = pd.read_parquet(path)
        df = df.sort_values(["slot_number"], kind="stable").reset_index(drop=True)
        for row in df.itertuples():
            if row.event_type != "swap" or row.action not in ("buy", "sell"):
                continue
            yield (float(row.timestamp), {
                "txType": row.action,
                "mint": row.token_mint,
                "pool": "pump-amm",
                "traderPublicKey": row.user_wallet,
                "solAmount": float(row.lamports_amount or 0) / LAMPORTS,
                "vSolInBondingCurve": float(row.real_lamports_reserve) / LAMPORTS,
                "vTokensInBondingCurve": float(row.real_token_reserve) / TOKEN_DECIMALS,
            })


def iter_merged_events(curve_dir: str | Path, amm_dir: str | Path) -> Iterator[tuple[float, dict]]:
    """Curve- und AMM-Strom chronologisch gemerged (heapq.merge auf t)."""
    import heapq

    return heapq.merge(iter_day_events(curve_dir), iter_amm_events(amm_dir), key=lambda e: e[0])
