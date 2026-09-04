"""Kostenloser Trade-Recorder direkt von der Solana-Blockchain (RPC-Logs).

Hintergrund: PumpPortal hat Trade-Streams hinter einen bezahlten API-Key
gelegt (>=0,02 SOL). Die Daten selbst sind aber öffentlich – das
pump.fun-Programm emittiert Anchor-Events (CreateEvent/TradeEvent/
CompleteEvent) in den Transaktions-Logs, inklusive virtueller und realer
Reserven. Dieser Recorder abonniert die Logs des Programms über einen
Solana-RPC-Websocket (Standard: der öffentliche Mainnet-Endpunkt, ohne
Anmeldung) und übersetzt sie in exakt das Event-Format, das der Bot und
`memetrader replay`/`abtest` erwarten.

Grenzen: Öffentliche RPC-Endpunkte drosseln; bei Abwürgen verbindet der
Recorder mit Backoff neu (Lücken sind im Log sichtbar). Ein kostenloser
dedizierter Endpunkt (z. B. Helius-Free-Tier) lässt sich über die
Umgebungsvariable SOLANA_RPC_WS einsetzen.

Dekodierung: Anchor-Events = 8-Byte-Diskriminator (sha256("event:<Name>")[:8])
+ Borsh-Payload. Es werden nur die vorderen, stabilen Felder gelesen;
angehängte neue Felder (Fee-Infos etc.) stören nicht.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import struct
import time
from dataclasses import dataclass, field

PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUBLIC_RPC_WS = "wss://api.mainnet-beta.solana.com"
LAMPORTS = 1e9
TOKEN_DECIMALS = 1e6
# Startreserven der Bonding-Curve (Fallback, falls CreateEvent sie nicht trägt)
INITIAL_V_SOL = 30.0
INITIAL_V_TOKENS = 1_073_000_000.0

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw: bytes) -> str:
    num = int.from_bytes(raw, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = _B58_ALPHABET[rem] + out
    pad = 0
    for byte in raw:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + (out or "")


def _disc(name: str) -> bytes:
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


DISCRIMINATORS = {
    _disc("CreateEvent"): "create",
    _disc("TradeEvent"): "trade",
    _disc("CompleteEvent"): "complete",
}


class _Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def bytes(self, n: int) -> bytes:
        chunk = self.data[self.pos:self.pos + n]
        if len(chunk) < n:
            raise ValueError("Payload zu kurz")
        self.pos += n
        return chunk

    def pubkey(self) -> str:
        return b58encode(self.bytes(32))

    def u64(self) -> int:
        return struct.unpack("<Q", self.bytes(8))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.bytes(8))[0]

    def u8(self) -> int:
        return self.bytes(1)[0]

    def string(self) -> str:
        length = struct.unpack("<I", self.bytes(4))[0]
        if length > 10_000:
            raise ValueError("String-Länge unplausibel")
        return self.bytes(length).decode("utf-8", errors="replace")

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos


def decode_event(payload: bytes) -> dict | None:
    """Ein 'Program data:'-Payload -> geparstes Event oder None (fremdes Event)."""
    kind = DISCRIMINATORS.get(payload[:8])
    if kind is None:
        return None
    r = _Reader(payload[8:])
    try:
        if kind == "trade":
            mint = r.pubkey()
            sol = r.u64() / LAMPORTS
            tokens = r.u64() / TOKEN_DECIMALS
            is_buy = bool(r.u8())
            user = r.pubkey()
            r.i64()  # timestamp (wir nutzen Empfangszeit)
            v_sol = r.u64() / LAMPORTS
            v_tok = r.u64() / TOKEN_DECIMALS
            real_sol = r.u64() / LAMPORTS
            return {"kind": "trade", "mint": mint, "sol": sol, "tokens": tokens,
                    "is_buy": is_buy, "user": user, "v_sol": v_sol, "v_tok": v_tok,
                    "real_sol": real_sol}
        if kind == "create":
            name = r.string()
            symbol = r.string()
            uri = r.string()
            mint = r.pubkey()
            r.pubkey()  # bonding_curve
            user = r.pubkey()
            v_sol, v_tok = INITIAL_V_SOL, INITIAL_V_TOKENS
            # Neuere Layouts: creator(32) timestamp(8) vTok(8) vSol(8) ...
            if r.remaining >= 56:
                r.pubkey()
                r.i64()
                v_tok = r.u64() / TOKEN_DECIMALS
                v_sol = r.u64() / LAMPORTS
            return {"kind": "create", "mint": mint, "name": name, "symbol": symbol,
                    "uri": uri, "user": user, "v_sol": v_sol, "v_tok": v_tok}
        # complete
        r.pubkey()
        mint = r.pubkey()
        return {"kind": "complete", "mint": mint}
    except ValueError:
        return None


@dataclass
class RpcCore:
    """Netzfreie Übersetzung: eine Log-Notification -> Bot-Events (testbar)."""

    events_out: int = 0
    tx_counts: dict[str, int] = field(default_factory=dict)

    def on_notification(self, value: dict) -> list[dict]:
        if value.get("err") is not None:
            return []
        parsed: list[dict] = []
        for line in value.get("logs") or []:
            if not line.startswith("Program data: "):
                continue
            try:
                payload = base64.b64decode(line[14:])
            except Exception:
                continue
            event = decode_event(payload)
            if event is not None:
                parsed.append(event)

        out: list[dict] = []
        creates = {e["mint"]: e for e in parsed if e["kind"] == "create"}
        folded: set[int] = set()
        # Dev-Buy im selben Tx in das Create falten (wie realdata.iter_day_events)
        for i, e in enumerate(parsed):
            if e["kind"] == "trade" and e["is_buy"] and e["mint"] in creates:
                c = creates.pop(e["mint"])
                out.append({"txType": "create", "mint": c["mint"], "name": c["name"],
                            "symbol": c["symbol"], "uri": c["uri"],
                            "traderPublicKey": c["user"], "solAmount": e["sol"],
                            "vSolInBondingCurve": e["v_sol"],
                            "vTokensInBondingCurve": e["v_tok"]})
                folded.add(i)
        for c in creates.values():  # Creates ohne Dev-Buy
            out.append({"txType": "create", "mint": c["mint"], "name": c["name"],
                        "symbol": c["symbol"], "uri": c["uri"],
                        "traderPublicKey": c["user"], "solAmount": 0.0,
                        "vSolInBondingCurve": c["v_sol"],
                        "vTokensInBondingCurve": c["v_tok"]})
        for i, e in enumerate(parsed):
            if e["kind"] == "trade" and i not in folded:
                out.append({"txType": "buy" if e["is_buy"] else "sell",
                            "mint": e["mint"], "traderPublicKey": e["user"],
                            "solAmount": e["sol"], "tokenAmount": e["tokens"],
                            "vSolInBondingCurve": e["v_sol"],
                            "vTokensInBondingCurve": e["v_tok"]})
            elif e["kind"] == "complete":
                out.append({"txType": "migrate", "mint": e["mint"], "pool": "pump-amm"})
        for event in out:
            self.tx_counts[event["txType"]] = self.tx_counts.get(event["txType"], 0) + 1
        self.events_out += len(out)
        return out


def rpc_ws_url() -> str:
    return os.environ.get("SOLANA_RPC_WS", "").strip() or PUBLIC_RPC_WS


async def run_rpc_recorder(out_path: str, minutes: float, ws_url: str | None = None) -> int:
    import websockets

    ws_url = ws_url or rpc_ws_url()
    deadline = time.time() + minutes * 60.0
    core = RpcCore()
    subscribe = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
        "params": [{"mentions": [PUMP_PROGRAM]}, {"commitment": "confirmed"}],
    })
    reconnects = 0
    print(f"[rpc-record] Quelle: {ws_url}", flush=True)
    with open(out_path, "a") as fh:
        while time.time() < deadline:
            try:
                async with websockets.connect(ws_url, ping_interval=20,
                                              max_size=1 << 22) as ws:
                    await ws.send(subscribe)
                    while True:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            break
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 30.0))
                        except asyncio.TimeoutError:
                            continue
                        now = time.time()
                        try:
                            msg = json.loads(message)
                        except json.JSONDecodeError:
                            continue
                        if msg.get("method") != "logsNotification":
                            continue
                        value = msg.get("params", {}).get("result", {}).get("value", {})
                        for event in core.on_notification(value):
                            fh.write(json.dumps({**event, "_t": now}, ensure_ascii=False) + "\n")
                            if core.events_out % 2000 == 0:
                                fh.flush()
                                print(f"[rpc-record] {core.events_out} Events, "
                                      f"{(deadline - now) / 60:.0f} min verbleibend "
                                      f"({dict(core.tx_counts)})", flush=True)
            except (Exception,) as exc:
                if time.time() >= deadline:
                    break
                reconnects += 1
                print(f"[rpc-record] Verbindung verloren ({type(exc).__name__}: {exc}); "
                      f"Reconnect #{reconnects} in {min(2 * reconnects, 30)}s", flush=True)
                await asyncio.sleep(min(2.0 * reconnects, 30.0))
        fh.flush()
    print(f"[rpc-record] fertig: {core.events_out} Events -> {out_path}", flush=True)
    print(f"[rpc-record] Zusammensetzung: {dict(core.tx_counts)}  |  Reconnects: {reconnects}",
          flush=True)
    return core.events_out
