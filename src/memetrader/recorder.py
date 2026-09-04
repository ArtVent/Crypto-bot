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
import os
import time
from dataclasses import dataclass, field

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
_UNSUB_BATCH = 50  # Keys je Unsubscribe-Nachricht


def ws_url_from_env(base: str = PUMPPORTAL_WS) -> str:
    """PumpPortal verlangt für Trade-Streams einen mit >=0,02 SOL aufgeladenen
    API-Key (Stand Sept. 2026). Key NUR als Umgebungsvariable/Secret – nie im
    Repo oder Chat; er kann das aufgeladene Guthaben handeln."""
    key = os.environ.get("PUMPPORTAL_API_KEY", "").strip()
    return f"{base}?api-key={key}" if key else base


@dataclass
class RecorderCore:
    track_minutes: float = 90.0
    max_tracked: int = 5000
    prune_interval_seconds: float = 60.0
    subscribe_flush_seconds: float = 2.0   # neue Mints gesammelt abonnieren
    subscribe_batch_max: int = 20
    status_log_max: int = 10               # erste Server-Statusmeldungen loggen
    _tracked: dict[str, float] = field(default_factory=dict)  # mint -> first_seen
    _pending_subs: list[str] = field(default_factory=list)
    _last_flush: float = 0.0
    _last_prune: float = 0.0
    _status_logged: int = 0
    events_written: int = 0
    tx_counts: dict[str, int] = field(default_factory=dict)  # Beobachtbarkeit im Log

    def on_message(self, event: dict, now: float) -> tuple[str | None, list[str]]:
        """Liefert (JSONL-Zeile oder None, ausgehende WS-Nachrichten)."""
        outgoing: list[str] = []
        tx = event.get("txType")
        mint = event.get("mint")
        # Bestätigungen/Fehler ohne txType: nicht aufzeichnen, aber SICHTBAR
        # machen – ein stilles Subscribe-Reject würde sonst nie auffallen
        if not tx and not event.get("pool"):
            self.tx_counts["status"] = self.tx_counts.get("status", 0) + 1
            if self._status_logged < self.status_log_max:
                self._status_logged += 1
                print(f"[record] Server-Status: {json.dumps(event, ensure_ascii=False)[:300]}",
                      flush=True)
            return None, self._flush_subs(now)

        if tx == "create" and mint and mint not in self._tracked:
            self._tracked[mint] = now
            self._pending_subs.append(mint)
        elif (tx == "migrate" or event.get("pool") == "pump-amm") and mint in self._tracked:
            outgoing.append(json.dumps({"method": "unsubscribeTokenTrade", "keys": [mint]}))
            del self._tracked[mint]

        outgoing += self._flush_subs(now)
        if now - self._last_prune >= self.prune_interval_seconds:
            outgoing += self._prune(now)
            self._last_prune = now

        self.events_written += 1
        kind = tx or event.get("pool") or "?"
        self.tx_counts[kind] = self.tx_counts.get(kind, 0) + 1
        return json.dumps({**event, "_t": now}, ensure_ascii=False), outgoing

    def _flush_subs(self, now: float) -> list[str]:
        """Gesammelte Mints als EINE Subscribe-Nachricht (Rate-Limit-Schutz)."""
        if not self._pending_subs:
            return []
        if len(self._pending_subs) < self.subscribe_batch_max and \
                now - self._last_flush < self.subscribe_flush_seconds:
            return []
        batch, self._pending_subs = self._pending_subs, []
        self._last_flush = now
        # inzwischen migrierte/geprunte Mints nicht mehr abonnieren
        batch = [m for m in batch if m in self._tracked]
        return [
            json.dumps({"method": "subscribeTokenTrade", "keys": batch[i:i + _UNSUB_BATCH]})
            for i in range(0, len(batch), _UNSUB_BATCH)
        ]

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


async def run_recorder(out_path: str, minutes: float, ws_url: str | None = None) -> int:
    import websockets

    ws_url = ws_url or ws_url_from_env()
    if "api-key" not in ws_url:
        print("[record] WARNUNG: kein PUMPPORTAL_API_KEY gesetzt – der Server "
              "liefert dann KEINE Trades (nur creates/migrations).", flush=True)
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
                            for msg in core._flush_subs(time.time()):
                                await ws.send(msg)
                            continue
                        now = time.time()
                        try:
                            event = json.loads(message)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(event, dict):
                            continue  # Fremd-Frame überspringen, nicht reconnecten
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
