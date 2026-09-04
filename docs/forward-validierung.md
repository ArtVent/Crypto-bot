# Forward-Validierung: der Bot betreibt sich selbst

Stand: September 2026. Fortsetzung von `realtest-echte-daten.md` (Teil 5).

## Warum

Alle bisherigen Zahlen stammen aus Rückvergangenheit – und die vielversprechendste
Änderung (Bot-Dichte-Kappe `max_smart_buyers`, in-sample +20,1 % vs. +17,8 % bei
halbiertem Drawdown) trägt genau deshalb einen Vorbehalt: Ihre Schwelle wurde am
selben Tag gefunden, an dem sie getestet wurde. Die einzige ehrliche Antwort ist
**Vorwärts-Validierung auf Daten, die zum Zeitpunkt der Hypothese noch nicht
existierten**.

## Wie (Selbstbetrieb ohne lokalen Rechner)

Die Cloud-Sandbox erreicht keine Krypto-APIs – GitHub-Actions-Runner schon.
Deshalb läuft das Papertrading als Workflow (`.github/workflows/paper-trading.yml`):

1. `memetrader record` zeichnet ~45–50 Minuten des rohen PumpPortal-Streams
   als Replay-JSONL auf (`recorder.py`, kausale Subscribe-Logik, netzfrei getestet).
2. `memetrader abtest` spielt die Aufzeichnung **mehrfach lookahead-frei**
   durch den vollen Bot – identische Events, deterministisch, vorregistrierte
   Duelle: Referenz-Konfiguration vs. Dichte-Kappe (max. 7 kreditierte
   Wallets) vs. Recycle-Leiter (+100 %, Teil 6 in realtest-echte-daten.md:
   in-sample +22,5 % vs. +17,8 %).
3. Aufzeichnung, `report.json`/`report.md` und Journale werden als GitHub-Release
   (`paper-…`-Tag) veröffentlicht; optional geht eine Telegram-Zusammenfassung
   raus (Repo-Secrets `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`).

Gestartet wird per Änderung an `.github/paper-trigger` (die erste Zahl in der
Datei = Aufnahmedauer in Minuten). Eine tägliche Claude-Routine stößt den Lauf
an und trägt das Ergebnis des Vortags hier ein. Es fließt **kein echtes Geld**,
und es existieren **keine Keys** – reine Papier-Simulation auf Live-Daten.

Kostenrahmen: privates Repo = 2.000 kostenlose Actions-Minuten/Monat; der
tägliche 45-Minuten-Lauf braucht ~1.500. Ein öffentliches Repo hätte keine
Minutengrenze.

## Entscheidungsregel (vorab festgelegt)

Ein Kandidat (Dichte-Kappe, Recycle-Leiter) wird nur dann Default, wenn er
über **mindestens 14 frische Aufzeichnungen** kumulativ vor der Referenz
liegt UND sein Risikoprofil (Drawdown) nicht schlechter ist. Einzeltage
zählen nicht – Aufnahmefenster von ~45 Minuten sind verrauscht; maßgeblich
sind Summe und Verteilung über die Serie. Verliert ein Kandidat die Serie,
wird er verworfen und das steht dann genauso hier.

## Ergebnis-Serie

| Datum (UTC) | Fenster | Events | Referenz | Kappe | Leiter | Bemerkung |
|---|---|---|---|---|---|---|
| 2026-09-04 07:23 | 5 min | 56 | +0,00 % | +0,00 % | – | Validierungslauf der Pipeline (zu kurz für Trades – zählt nicht zur Serie) |
