"""Autopilot: Der Bot trainiert IMMER weiter, wenn er nicht live handelt.

Betriebslogik:
- Solange KEIN Live-Prozess läuft (erkannt am Lockfile memetrader.live.lock),
  paper-tradet der Bot dauerhaft gegen die echten Live-Streams und lernt
  weiter (Journal, Selbst-Tuning, Claude-Gedächtnis).
- Startet ein Live-Prozess (run --live legt das Lockfile an), pausiert das
  Paper-Training automatisch und übernimmt wieder, sobald Live endet.
- Der LERNSTAND IST GETEILT UND PERSISTENT: tuning/journal/memory-Dateien
  überleben Neustarts; der Tuner lädt seinen Stand beim Start (load_state).
- Abstürze werden abgefangen: Log + Benachrichtigung + Neustart mit Backoff.
- Täglicher Bericht (UTC-Tageswechsel) über notify.py (Telegram/Webhook).

Start:  python -m memetrader autopilot [--budget-sol 1.0]
"""

from __future__ import annotations

import asyncio
import time
import traceback
from pathlib import Path

from .bot import Bot, BotConfig
from .notify import Notifier, build_daily_report

LIVE_LOCK = Path("memetrader.live.lock")


def live_lock_active(path: Path = LIVE_LOCK, stale_seconds: float = 6 * 3600) -> bool:
    """Live-Lock aktiv? Verwaiste Locks (älter als stale_seconds) zählen nicht."""
    try:
        age = time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return False
    return age < stale_seconds


class Autopilot:
    def __init__(self, config: BotConfig | None = None, notifier: Notifier | None = None,
                 lock_path: Path = LIVE_LOCK):
        self.config = config or BotConfig()
        self.notifier = notifier or Notifier.from_env()
        self.lock_path = lock_path
        self._last_report_day: int | None = None

    def _make_bot(self) -> Bot:
        bot = Bot(self.config)
        if bot.tuner.load_state():
            print(f"[autopilot] Lernstand geladen: {bot.tuner.state_summary()}")
        return bot

    def _maybe_daily_report(self, mode: str) -> None:
        day = int(time.time() // 86400)
        if self._last_report_day is None:
            self._last_report_day = day
            return
        if day != self._last_report_day:
            self._last_report_day = day
            report = build_daily_report(self.config.journal_path, self.config.log_path,
                                        self.config.tuning_path, mode=mode)
            self.notifier.send(report)

    async def run(self) -> None:
        channels = self.notifier.channels
        self.notifier.send(
            "memetrader Autopilot gestartet: Paper-Training läuft, solange kein "
            f"Live-Betrieb aktiv ist. Berichts-Kanäle: {channels or ['nur Konsole']}"
        )
        backoff = 5.0
        while True:
            if live_lock_active(self.lock_path):
                print("[autopilot] Live-Betrieb erkannt – Paper-Training pausiert.")
                while live_lock_active(self.lock_path):
                    self._maybe_daily_report(mode="live")
                    await asyncio.sleep(30)
                self.notifier.send("Live-Betrieb beendet – Paper-Training übernimmt wieder.")

            bot = self._make_bot()
            bot_task = asyncio.create_task(bot.run())
            try:
                while not bot_task.done():
                    self._maybe_daily_report(mode="paper")
                    if live_lock_active(self.lock_path):
                        bot_task.cancel()
                        break
                    await asyncio.sleep(15)
                if bot_task.done() and not bot_task.cancelled():
                    exc = bot_task.exception()
                    if exc is not None:
                        raise exc
                backoff = 5.0
            except asyncio.CancelledError:
                print("[autopilot] Paper-Bot gestoppt (Live-Übergabe).")
            except Exception as exc:
                print(f"[autopilot] Bot-Absturz: {exc}\n{traceback.format_exc(limit=3)}")
                self.notifier.send(f"memetrader: Paper-Bot abgestürzt ({type(exc).__name__}: {exc}) "
                                   f"– Neustart in {backoff:.0f}s. Lernstand bleibt erhalten.")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300.0)
            finally:
                if not bot_task.done():
                    bot_task.cancel()


def run_autopilot(budget_sol: float = 1.0, ml_model_path: str | None = None) -> None:
    config = BotConfig()
    config.risk.budget_sol = budget_sol
    if ml_model_path:
        config.ml_model_path = ml_model_path
    asyncio.run(Autopilot(config).run())
