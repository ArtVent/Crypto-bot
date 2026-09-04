"""Telegram-Trade-Alert: eine Nachricht, WENN der Bot Trades gefunden hat.

Liest das Journal des Referenz-Arms (report/ref/bt_1.journal.jsonl – das ist
die Default-Konfiguration, also "der Bot") und baut eine kompakte Nachricht
mit einer Zeile je Trade. Gibt NICHTS aus, wenn keine Trades gefunden wurden
(dann sendet der Workflow auch nichts). Dank der End-Liquidation über das
Journal sind alle Entries eines Laufs hier als abgeschlossene Trades enthalten.

Einbahnstraße wie der Tagesbericht: nur senden, nie lesen.
"""

import json
import sys
from pathlib import Path

JOURNAL = Path("report/ref/bt_1.journal.jsonl")
MAX_LINES = 15  # sehr aktive Läufe nicht zur Roman-Nachricht werden lassen


def main() -> int:
    if not JOURNAL.exists():
        return 0
    trades = []
    for line in JOURNAL.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                trades.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not trades:
        return 0

    lines = [f"🎯 {len(trades)} Trade(s) gefunden (Paper, Referenz-Bot):"]
    for r in trades[:MAX_LINES]:
        cost = r.get("cost_sol") or 0.0
        pnl = r.get("pnl_sol")
        sym = (r.get("symbol") or r.get("mint", "")[:6]) or "?"
        if pnl is None or cost <= 0:
            lines.append(f"• {sym}: offen")
            continue
        pct = pnl / cost * 100.0
        mark = "🟢" if pnl > 0 else "🔴"
        lesson = r.get("lesson") or ""
        lines.append(f"{mark} {sym}  {pct:+.0f}%  ({lesson})")
    if len(trades) > MAX_LINES:
        lines.append(f"… und {len(trades) - MAX_LINES} weitere")

    total_pnl = sum((r.get("pnl_sol") or 0.0) for r in trades)
    lines.append(f"Σ {total_pnl:+.4f} SOL")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
