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
   in-sample +22,5 % vs. +17,8 %) vs. **Regime-Gate/Coldday-Erkennung**
   (≥3 Graduationen/Stunde, sonst kein Entry – der laut 2-Wochen-Rechnung
   größte Hebel: kalte Phasen kosten Köder ohne Fang, siehe Teil 3).
   Warm-up-Hinweis: Der Regime-Sensor startet bei Aufnahmebeginn leer; die
   ersten Minuten jedes Fensters sind für diesen Arm systematisch gesperrt.
   Auf wirklich kalten Aufnahmen handelt er gar nicht – genau das ist der
   Zweck, und die Serie misst, was das netto bringt.
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

**Datenquelle (seit Sept. 2026 zweigleisig):** PumpPortal liefert
Trade-Streams (`subscribeTokenTrade`) nur noch mit einem API-Key, der mit
mindestens 0,02 SOL aufgeladen ist – der kostenlose Feed enthält nur
Launches und Migrationen (Befund aus Diagnose-Lauf #4, Server-Statusmeldung
im Log). Deshalb liest der Recorder standardmäßig **kostenlos direkt von
der Solana-Blockchain** (`rpcrecorder.py`: `logsSubscribe` auf das
pump.fun-Programm, Anchor-Events mit Reserven dekodiert; öffentlicher
Mainnet-Endpunkt, ohne Anmeldung). `record --source auto` wählt PumpPortal
nur, wenn das Repo-Secret `PUMPPORTAL_API_KEY` existiert; ein eigener
RPC-Endpunkt (z. B. Helius-Free-Tier, falls der öffentliche drosselt) kommt
über das Secret `SOLANA_RPC_WS`. Falls je ein PumpPortal-Key genutzt wird:
nur als Secret, nur mit dem Minimum aufladen – er kann sein Guthaben
handeln.

## Entscheidungsregel (vorab festgelegt)

Ein Kandidat (Dichte-Kappe, Recycle-Leiter) wird nur dann Default, wenn er
über **mindestens 14 frische Aufzeichnungen** kumulativ vor der Referenz
liegt UND sein Risikoprofil (Drawdown) nicht schlechter ist. Einzeltage
zählen nicht – Aufnahmefenster von ~45 Minuten sind verrauscht; maßgeblich
sind Summe und Verteilung über die Serie. Verliert ein Kandidat die Serie,
wird er verworfen und das steht dann genauso hier.

## Ergebnis-Serie

Arme: Referenz · Kappe (Dichte) · Leiter (Recycle +100 %) · Regime (Coldday) ·
Insider (Insider-Exit ≤35 %).

| Datum (UTC) | Fenster | Events | Ref | Kappe | Leiter | Regime | Insider | Bemerkung |
|---|---|---|---|---|---|---|---|---|
| 2026-09-04 07:23 | 5 min | 56 | +0,00 % | +0,00 % | – | – | – | Pipeline-Validierung (zu kurz; PumpPortal ohne Trades – zählt nicht) |
| 2026-09-04 09:09 | 4 min | 7.378 | +0,00 % | +0,00 % | +0,00 % | – | – | Diagnose On-Chain-Quelle (voller Strom, 0 Reconnects; zu kurz – zählt nicht) |
| 2026-09-04 09:14 | 45 min | 97.941 | +0,00 % | +0,00 % | +0,00 % | – | – | Erstes volles 45-Min-Fenster. 0 Trades – kein Bug (Funnel + Regression 58 Trades). Selektiv ≈ 1–2/45 Min |
| 2026-09-04 10:18 | 8 min | 16.944 | +0,00 % | +0,00 % | +0,00 % | +0,00 % | – | Anti-Bug-Diagnose; Telegram-Zustellung verifiziert (zu kurz – zählt nicht) |
