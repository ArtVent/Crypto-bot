"""Benachrichtigungen: Tages-Berichte über Training/Trades aufs Handy.

Kanäle (nach Verfügbarkeit, alle optional):
- Telegram-Bot: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID setzen.
  (BotFather -> Bot anlegen -> Token; Chat-ID z. B. via @userinfobot)
- Generischer Webhook: NOTIFY_WEBHOOK_URL (POST {"text": ...}) – für
  Discord/Slack/ntfy.sh o. ä.
- Konsole/Logdatei: immer.

Der Sicherheits-Grundsatz gilt auch hier: Berichte enthalten PnL und
Statistiken, niemals Keys oder Wallet-Adressen mit Guthaben-Kontext.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path


class Notifier:
    def __init__(self, telegram_token: str | None = None, telegram_chat_id: str | None = None,
                 webhook_url: str | None = None, sender=None):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
        self._sender = sender  # Test-Injection

    @classmethod
    def from_env(cls) -> "Notifier":
        return cls(
            telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
            webhook_url=os.environ.get("NOTIFY_WEBHOOK_URL"),
        )

    @property
    def channels(self) -> list[str]:
        out = []
        if self.telegram_token and self.telegram_chat_id:
            out.append("telegram")
        if self.webhook_url:
            out.append("webhook")
        return out

    def send(self, text: str) -> list[str]:
        """Sendet an alle konfigurierten Kanäle; gibt erfolgreiche zurück."""
        print(f"[notify] {text}")
        delivered = []
        if self._sender is not None:
            self._sender(text)
            return ["injected"]
        try:
            import httpx
        except ImportError:
            return delivered
        if self.telegram_token and self.telegram_chat_id:
            try:
                response = httpx.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={"chat_id": self.telegram_chat_id, "text": text,
                          "disable_web_page_preview": True},
                    timeout=15,
                )
                if response.status_code == 200:
                    delivered.append("telegram")
                else:
                    print(f"[notify] Telegram-Fehler {response.status_code}: {response.text[:120]}")
            except Exception as exc:
                print(f"[notify] Telegram nicht erreichbar: {exc}")
        if self.webhook_url:
            try:
                response = httpx.post(self.webhook_url, json={"text": text}, timeout=15)
                if 200 <= response.status_code < 300:
                    delivered.append("webhook")
            except Exception as exc:
                print(f"[notify] Webhook nicht erreichbar: {exc}")
        return delivered


def _load_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def build_daily_report(journal_path: str, log_path: str, tuning_path: str,
                       mode: str, since_hours: float = 24.0, now: float | None = None) -> str:
    """Baut den Tages-Bericht aus Journal + Entscheidungs-Log."""
    now = time.time() if now is None else now
    cutoff = now - since_hours * 3600

    records = [r for r in _load_jsonl(journal_path) if (r.get("closed_t") or 0) >= cutoff]
    log = [e for e in _load_jsonl(log_path) if (e.get("t") or 0) >= cutoff]

    pnl = sum(r.get("pnl_sol") or 0.0 for r in records)
    wins = [r for r in records if (r.get("pnl_sol") or 0) > 0]
    lessons = Counter(r.get("lesson") for r in records if r.get("lesson"))
    tunings = [e for e in log if e.get("event") == "self_tune"]
    memories = [e for e in log if e.get("event") == "claude_memory"]
    blocked = sum(1 for e in log if e.get("event") == "entry_blocked")
    entries = sum(1 for e in log if e.get("event") == "entry")

    lines = [
        f"memetrader Tagesbericht ({mode.upper()})",
        f"PnL (24h): {pnl:+.4f} SOL | Trades: {len(records)} "
        + (f"(Winrate {100 * len(wins) / len(records):.0f}%)" if records else ""),
        f"Entries: {entries} | vom Filter blockiert: {blocked}",
    ]
    if records:
        best = max(records, key=lambda r: r.get("pnl_sol") or 0)
        worst = min(records, key=lambda r: r.get("pnl_sol") or 0)
        lines.append(f"Bester: {best.get('symbol', '?')} {best.get('pnl_sol', 0):+.4f} | "
                     f"Schlechtester: {worst.get('symbol', '?')} {worst.get('pnl_sol', 0):+.4f}")
    if lessons:
        top = ", ".join(f"{k} x{v}" for k, v in lessons.most_common(4))
        lines.append(f"Lektionen: {top}")
    if tunings:
        lines.append(f"Selbst-Tuning: {len(tunings)} Anpassungen "
                     f"(zuletzt: {tunings[-1].get('param')} -> {tunings[-1].get('new')})")
    if memories:
        lines.append(f"Claude-Notizen: {len(memories)} neue")
    tuning_file = Path(tuning_path)
    if tuning_file.exists():
        try:
            state = json.loads(tuning_file.read_text())
            eff = state.get("effective", {})
            lines.append(f"Aktive Parameter: Stop {eff.get('stop_loss_pct')}% | "
                         f"Fill>={eff.get('min_fill_pct')}% | Buyer>={eff.get('min_unique_buyers')} | "
                         f"Position {eff.get('position_sol')} SOL")
        except json.JSONDecodeError:
            pass
    if not records and not entries:
        lines.append("Keine Trades im Zeitraum (Markt ruhig oder Filter streng).")
    return "\n".join(lines)
