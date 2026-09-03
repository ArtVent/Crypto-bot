"""Launch-Archiver: zeichnet ALLE pump.fun-Launches auf und labelt Outcomes.

Das Archiv (SQLite) ist bewusst vollständig – auch die toten 99 % – denn es
ist die Trainingsdaten-Grundlage der ML-Stufe und laut Recherche der Engpass
aller Rug-Klassifikations-Projekte (docs/filter-engine.md, Abschnitt 4.2;
docs/ai-geschaeftsmodelle.md: Daten-Geschäft).

Quelle: PumpPortal-Data-Websocket (kostenlos), Event-Felder siehe
data/detection-apis.json. Labeling: DexScreener-Abfrage nach Ablauf des
Label-Horizonts (existiert ein Pair? Liquidität? => grobe Outcome-Klasse).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import httpx
import websockets

from .providers import fetch_dexscreener_liquidity

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS launches (
    mint TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    name TEXT,
    symbol TEXT,
    creator TEXT,
    initial_buy_tokens REAL,
    initial_buy_sol REAL,
    market_cap_sol REAL,
    uri TEXT,
    raw JSON,
    -- Outcome-Label (docs/filter-engine.md 4.1), gesetzt vom Labeler:
    label TEXT,             -- dead | survivor | graduated_pool | unknown
    labeled_at REAL,
    label_liquidity_usd REAL,
    label_volume24_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_launches_unlabeled ON launches (labeled_at) WHERE labeled_at IS NULL;
"""


def open_db(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def record_launch(conn: sqlite3.Connection, event: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO launches
           (mint, created_at, name, symbol, creator, initial_buy_tokens,
            initial_buy_sol, market_cap_sol, uri, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            event.get("mint"),
            time.time(),
            event.get("name"),
            event.get("symbol"),
            event.get("traderPublicKey"),
            event.get("initialBuy"),
            event.get("solAmount"),
            event.get("marketCapSol"),
            event.get("uri"),
            json.dumps(event),
        ),
    )
    conn.commit()


async def watch(db_path: str | Path, quiet: bool = False) -> None:
    """Lauscht auf neue Token und archiviert jeden Launch. Läuft bis Ctrl+C."""
    conn = open_db(db_path)
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(PUMPPORTAL_WS, ping_interval=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                backoff = 1.0
                async for message in ws:
                    event = json.loads(message)
                    if event.get("txType") != "create":
                        continue
                    record_launch(conn, event)
                    if not quiet:
                        print(
                            f"+ {event.get('symbol', '?'):<10} {event.get('mint', '?')}"
                            f"  dev-buy {event.get('solAmount', 0):.2f} SOL"
                        )
        except (websockets.WebSocketException, OSError) as exc:
            print(f"[archiver] Verbindung verloren ({exc}); Reconnect in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def label_outcomes(db_path: str | Path, min_age_hours: float = 24.0, limit: int = 200) -> int:
    """Labelt Launches, die alt genug sind: existiert 24 h später ein handelbares Pair?

    Grobe, mechanische Label-Definitionen (verfeinerbar):
      dead            – kein DexScreener-Pair (nie graduiert oder Liquidität weg)
      graduated_pool  – Pair vorhanden mit >= 1.000 USD Liquidität
      survivor        – Pair vorhanden, aber < 1.000 USD Liquidität (Randfall)
    """
    conn = open_db(db_path)
    cutoff = time.time() - min_age_hours * 3600
    rows = conn.execute(
        "SELECT mint FROM launches WHERE labeled_at IS NULL AND created_at < ? LIMIT ?",
        (cutoff, limit),
    ).fetchall()
    labeled = 0
    with httpx.Client(timeout=15.0) as client:
        for (mint,) in rows:
            try:
                info = fetch_dexscreener_liquidity(mint, client)
            except httpx.HTTPError:
                continue  # nächster Lauf versucht es erneut
            if not info.get("has_pair"):
                label, liq, vol = "dead", None, None
            else:
                liq = info.get("liquidity_usd") or 0.0
                vol = info.get("volume_24h_usd")
                label = "graduated_pool" if liq >= 1000 else "survivor"
            conn.execute(
                "UPDATE launches SET label=?, labeled_at=?, label_liquidity_usd=?, label_volume24_usd=? WHERE mint=?",
                (label, time.time(), liq, vol, mint),
            )
            labeled += 1
            time.sleep(0.4)  # DexScreener-Rate-Limit respektieren
    conn.commit()
    return labeled


def stats(db_path: str | Path) -> dict:
    conn = open_db(db_path)
    total = conn.execute("SELECT COUNT(*) FROM launches").fetchone()[0]
    by_label = dict(
        conn.execute(
            "SELECT COALESCE(label,'unlabeled'), COUNT(*) FROM launches GROUP BY label"
        ).fetchall()
    )
    return {"total": total, "by_label": by_label}
