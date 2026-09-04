"""Roh-Event-Recorder: zeichnet den PumpPortal-Strom als Replay-JSONL auf.

Zweck (docs/realtest-echte-daten.md, Konsequenz 2): Die einzige belastbare
Validierung der Timing-Schicht sind frische Sekunden-Streams. Der Recorder
schreibt jedes Event mit `_t`-Zeitstempel – exakt das Format, das
`memetrader replay`, `memetrader backtest --events` und `memetrader abtest`
lesen. Aufnahme und Auswertung bleiben getrennt: erst aufzeichnen, dann
lookahead-frei replayen (auch mehrfach, für A/B auf identischen Daten).

Die Subscription-Logik ist netzfrei in RecorderCore gekapselt (testbar):
- create-Event  -> Trades dieses Mints abonnieren
- migrate-Event -> Mint abbestellen (Curve-Phase vorbei)
- regelmäßig    -> Mints älter als track_minutes abbestellen (Stream-Hygiene)
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
_UNSUB_BATCH = 50  # Keys je Unsubscribe-Nachricht


@dataclass
class RecorderCore:
    track_minutes: float = 90.0
    max_tracked: int = 5000
    prune_interval_seconds: float = 60.0
    _tracked: dict[str, float] = field(default_factory=dict)  # mint -> first_seen
    _last_prune: float = 0.0
    events_written: int = 0
    tx_counts: dict[str, int] = field(default_factory=dict)  # Beobachtbarkeit im Log

    def on_message(self, event: dict, now: float) -> tuple[str | None, list[str]]:
        """Liefert (JSONL-Zeile oder None, ausgehende WS-Nachrichten)."""
        outgoing: list[str] = []
        tx = event.get("txType")
        mint = event.get("mint")
        # Bestätigungen/Statusmeldungen ohne txType nicht aufzeichnen
        if not tx and not event.get("pool"):
            return None, outgoing

        if tx == "create" and mint and mint not in self._tracked:
            self._tracked[mint] = now
            outgoing.append(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
        elif (tx == "migrate" or event.get("pool") == "pump-amm") and mint in self._tracked:
            outgoing.append(json.dumps({"method": "unsubscribeTokenTrade", "keys": [mint]}))
            del self._tracked[mint]

        if now - self._last_prune >= self.prune_interval_seconds:
            outgoing += self._prune(now)
            self._last_prune = now

        self.events_written += 1
        kind = tx or event.get("pool") or "?"
        self.tx_counts[kind] = self.tx_counts.get(kind, 0) + 1
        return json.dumps({**event, "_t": now}, ensure_ascii=False), outgoing

    def _prune(self, now: float) -> list[str]:
        cutoff = now - self.track_minutes * 60.0
        stale = [m for m, t in self._tracked.items() if t < cutoff]
        if len(self._tracked) - len(stale) > self.max_tracked:  # Notbremse: älteste zuerst
            keep_overflow = sorted(self._tracked.items(), key=lambda kv: kv[1])
            stale = [m for m, _ in keep_overflow[: len(self._tracked) - self.max_tracked]]
        for mint in stale:
            self._tracked.pop(mint, None)
        return [
            json.dumps({"method": "unsubscribeTokenTrade", "keys": stale[i:i + _UNSUB_BATCH]})
            for i in range(0, len(stale), _UNSUB_BATCH)
        ]

    def resubscribe_messages(self) -> list[str]:
        """Nach Reconnect: alle noch beobachteten Mints erneut abonnieren."""
        mints = list(self._tracked)
        return [
            json.dumps({"method": "subscribeTokenTrade", "keys": mints[i:i + _UNSUB_BATCH]})
            for i in range(0, len(mints), _UNSUB_BATCH)
        ]


async def run_recorder(out_path: str, minutes: float, ws_url: str = PUMPPORTAL_WS) -> int:
    import websockets

    deadline = time.time() + minutes * 60.0
    core = RecorderCore()
    with open(out_path, "a") as fh:
        while time.time() < deadline:
            try:
                async with websockets.connect(ws_url, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    for msg in core.resubscribe_messages():
                        await ws.send(msg)
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
                            event = json.loads(message)
                        except json.JSONDecodeError:
                            continue
                        line, outgoing = core.on_message(event, now)
                        if line:
                            fh.write(line + "\n")
                            if core.events_written % 500 == 0:
                                fh.flush()
                                print(f"[record] {core.events_written} Events, "
                                      f"{len(core._tracked)} Mints beobachtet, "
                                      f"{(deadline - now) / 60:.0f} min verbleibend", flush=True)
                        for msg in outgoing:
                            await ws.send(msg)
            except (Exception,) as exc:  # Netz-/Protokollfehler: weiter bis Deadline
                if time.time() >= deadline:
                    break
                print(f"[record] Verbindung verloren ({type(exc).__name__}: {exc}); Reconnect in 2s", flush=True)
                await asyncio.sleep(2.0)
        fh.flush()
    print(f"[record] fertig: {core.events_written} Events -> {out_path}", flush=True)
    print(f"[record] Zusammensetzung: {dict(core.tx_counts)}", flush=True)
    return core.events_written
