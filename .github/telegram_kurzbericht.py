"""Ganz kurzer Telegram-Tagesbericht: Trades heute + Prozent + Serienstand.

Läuft als letzter Workflow-Schritt. Liest den frischen Bericht
(report/report.json) und die Serie (reports/paper-*.json, nur Läufe ab
30 Minuten Fenster) und druckt EINE Zeile auf stdout – der Workflow
schickt sie per Telegram-API an genau eine Chat-ID (TELEGRAM_CHAT_ID).

Sicherheit: Der Bot ist reine Einbahnstraße. Er liest niemals eingehende
Nachrichten (kein getUpdates, kein Polling) – niemand außer dem Besitzer
der hinterlegten Chat-ID bekommt je etwas zu sehen, und "benutzen" kann
ihn niemand.
"""

import glob
import json

heute = json.load(open("report/report.json"))
ref = heute["reference"]

equity = 1.0
laeufe = 0
for pfad in sorted(glob.glob("reports/paper-*.json")):
    d = json.load(open(pfad))
    if d.get("span_hours", 0) >= 0.5:
        equity *= 1.0 + d["reference"]["return_pct"] / 100.0
        laeufe += 1
serie = (equity - 1.0) * 100.0

print(f"🤖 Heute: {ref['closed']} Trades, {ref['return_pct']:+.2f} % "
      f"| Serie ({laeufe} Läufe): {serie:+.2f} %")
