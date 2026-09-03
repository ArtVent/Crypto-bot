# memetrader – gefilterter Momentum-Bot (das 1-SOL-Experiment)

Autonomer Trading-Bot für pump.fun-Curve-Coins, gebaut nach den Regeln der
eigenen Wissensdatenbank. **Startet immer im Paper-Modus** (echte Live-Daten,
simulierte Fills); Live-Trading ist ein doppelter Opt-in.

## Ehrliche Erwartung zuerst

Aus der eigenen Datenbank ([`../../docs/strategien.md`](../../docs/strategien.md),
[`../../docs/filter-engine.md`](../../docs/filter-engine.md)): Die Mehrheit der
Teilnehmer verliert; Block-0-Sniping von Heim-Infrastruktur ist strukturell
verloren; ~99 % der Launches sterben. Dieses Programm ist ein **Experiment mit
Verlust-Deckel** – Ziel ist, aus 1 SOL mit Disziplin mehr zu machen, Erwartung
ist, dass es auch scheitern kann. Der Kill-Switch begrenzt den Schaden
(Default: −0,15 SOL/Tag, dann Stopp).

## Strategie (bewusst KEIN Block-0-Sniper)

1. **Beobachtungsfenster**: Coins jünger als 45 s werden ignoriert – dort
   fressen sich Sniper und Bundler gegenseitig (docs/strategien.md 3.1).
2. **Entry nur bei Nachfrage-Beweis**: ≥10 Unique-Buyer, ≥15 Käufe,
   Dev-Buy im gesunden Band (0,05–3 SOL), Curve-Füllung 10–75 %,
   Verkaufsdruck niedrig, Momentum intakt, kein Symbol-Duplikat (Ticker-Kriege),
   Creator hat nicht verkauft.
3. **Asymmetrische Exits**: harter Stop −35 %; bei +100 % die Hälfte verkaufen
   (Einsatz raus = "derisked"); Rest-Ziel +250 %; Zeit-Stop (8 min ohne +20 %,
   max. 20 min); Sofort-Exit bei Creator-Verkauf oder Migration.
4. **Risk-Engine**: 0,05 SOL pro Position, max. 3 gleichzeitig,
   Tages-Kill-Switch, Budget-Deckel – alles in `RiskConfig` kalibrierbar.

## ML-Filter – trainiert auf echten Trades

`models/mlfilter-melt.joblib` ist ein auf **41.470 echten pump.fun-Coins**
(MELT-Forschungsdatensatz, Dez 2024–März 2025) trainiertes Risiko-Modell:
HistGradientBoosting auf 19 Launch-Zeitpunkt-Features (Socials, Beschreibung,
Namens-/Ticker-Eigenschaften, Ticker-Duplikate, Creator-Historie, Uhrzeit) –
mit strikt chronologischem Split und kausaler Feature-Konstruktion
(Creator-/Duplikat-Zähler nur aus der Vergangenheit).

**Ergebnisse (ehrlich):** ROC-AUC **0,72** auf 8.295 Holdout-Coins.
Basisrate 84 % high-risk; der Bot nutzt das Modell als Gate bei Schwelle 0,80:
nur ~15 % der Coins passieren, darin sinkt die High-Risk-Quote auf **68 %**.
Das ist eine echte, messbare Risiko-Reduktion – und trotzdem bleibt die
Mehrheit auch der gefilterten Coins riskant. Der ML-Filter ersetzt weder die
Regel-Strategie noch das Risk-Management, er ergänzt sie.

**Wichtigstes gelerntes Feature:** `symbol_dupes_before` (Ticker-Duplikate) –
die empirische Bestätigung der Dedupe-Regel aus der Strategie; danach
Socials-Anzahl und Beschreibungsqualität.

**Lizenz:** Der MELT-Datensatz ist CC BY-NC 4.0 → dieses Modell nur für
Forschung/persönliche Experimente. Für den kommerziellen Pfad (SaaS) mit
`python -m memetrader.train_mlfilter` auf den eigenen Archiv-Daten
(`memescan watch`/`label`) neu trainieren – die Pipeline ist identisch.

## Lern-Schicht – der Bot lernt aus seinen Fehlern

Drei Bausteine machen aus dem Regel-Bot ein selbst-korrigierendes System:

**1. Trade-Journal mit Kontrafakt (`journal.py`):** Nach jedem geschlossenen
Trade beobachtet der Bot den Coin noch 10 Minuten weiter – erst der Vergleich
"was wäre passiert, hätte ich gehalten?" macht aus dem Ergebnis eine Lektion:
`good_stop` / `shaken_out` (Stop zu eng), `impatient` (Zeit-Stop zu früh),
`sold_too_early`, `bad_entry` (schneller Verlust = Filter-Lücke),
`overreacted_creator_exit` u. a. Jede Lektion landet mit vollem
Entry-Kontext (Curve-Füllung, Käuferzahl, ML-Score, …) in
`memetrader.journal.jsonl`.

**2. Selbst-Kalibrierung (`adaptive.py`):** Häufen sich Lektionen (>= 3 gleiche
im 20-Trade-Fenster), passt der Bot seine Parameter an – Stop weiter/enger,
Zeit-Stop länger, Entry-Filter strenger, ML-Schwelle nachgezogen. Alles mit
harten Grenzen (Stop nie unter −50 %, ML-Schwelle nie unter 0,6 usw.),
Mehrfach-Evidenz-Pflicht und geloggter Begründung. Dazu Drawdown-Bewusstsein:
Nach 3 Verlusten in Folge handelt er mit 75 % Größe, nach 5 mit 50 % – und
arbeitet sich mit Gewinnen zurück. Der Bot kann sich justieren, aber nie aus
seinem Sicherheitsrahmen "herauslernen".

**3. Live-Claude-Verbindung (`claude_link.py`):** Mit `--claude` läuft Claude
(Modell `claude-opus-5`) als echter Co-Pilot IM Bot-Betrieb, über drei Kanäle,
alle asynchron in Worker-Threads (der Trade-Loop blockiert nie):

- **Entry-Vet:** Kandidaten, die alle Regel-/ML-Gates bestanden haben, gehen
  mit Metadaten und Kontext an Claude; bei klaren Scam-/Impersonations-Mustern
  (Confidence >= 0,7 – im Code erzwungen, nicht im Prompt) wird der Entry
  vetot. Die Freigabe wird beim Eintreffen re-validiert (hat der Creator
  inzwischen verkauft, gilt sie nicht mehr). Advisory-Prinzip: API-Timeout
  oder -Fehler bedeutet KEIN Veto – der Bot hängt nie an der API-Verfügbarkeit.
- **Post-Mortems:** Jede lehrreiche Lektion destilliert Claude in eine kurze
  Erkenntnis, die in `memetrader.memory.md` landet – ein von Claude kuratiertes
  Langzeit-Gedächtnis, das künftige Vets und Reviews als Kontext erhalten.
- **Reviews:** Alle N Trades (Default 10) analysiert Claude Journal +
  Gedächtnis und schlägt Anpassungen vor, die automatisch, aber NUR innerhalb
  der AdaptiveTuner-Bounds angewendet werden.

Sicherheits-Invarianten: Claude signiert nie Transaktionen; Token-Metadaten
werden in den Prompts explizit als angreifer-kontrollierte Daten behandelt
(Prompt-Injection-Muster aus data/scams.json); alle Anwendungen laufen durch
Code-Grenzen (Guardrails in Code, nicht im Prompt – die Freysa-Lektion).
Benötigt `pip install anthropic` + `ANTHROPIC_API_KEY`; Kosten grob:
ein Vet ~1–2k Tokens, bei Dutzenden Vets/Tag einstellige USD-Beträge.
`memetrader advise` bleibt als Offline-Variante ohne laufenden Bot.

Einblick in den gelernten Zustand:

```bash
python -m memetrader brain     # Lektionen, wirksame Parameter, Tuning-Historie
python -m memetrader advise    # Claude-Review (--apply übernimmt begrenzt)
```

## Nutzung

```bash
# Paper-Trading (Default) – läuft gegen echte Live-Streams, handelt simuliert;
# das ML-Gate ist automatisch aktiv, wenn models/mlfilter-melt.joblib existiert:
python -m memetrader run --budget-sol 1.0
python -m memetrader run --ml-threshold 0.75   # strengeres Gate
python -m memetrader run --ml-model ""         # ohne ML-Gate
python -m memetrader run --claude              # + Live-Claude: Vets, Post-Mortems, Reviews

# ML-Modell neu trainieren (MELT oder eigene Archiv-Daten):
python -m memetrader.train_mlfilter --melt-dir /pfad/zu/MELT --out models/mlfilter-melt.joblib

# Backtest auf aufgezeichneten Events (JSONL, ein Event pro Zeile):
python -m memetrader replay events.jsonl

# Entscheidungs-Log auswerten (PnL, Trefferquote, Exit-Gründe, Filter-Wirkung):
python -m memetrader analyze memetrader.log.jsonl

# Lookahead-freier Backtest: 60 Tage simulierter, basisraten-kalibrierter Markt
# (oder --events <aufzeichnung.jsonl> für echte aufgezeichnete Streams,
#  oder --real-dir <parquet-verzeichnis> für rohe pump.fun-Tagesdaten):
python -m memetrader backtest --days 60 --budget-sol 1.0 --seeds 1 2 3 4 5

# DAUERBETRIEB: Paper-Training läuft IMMER, wenn kein Live-Prozess aktiv ist
# (run --live pausiert es automatisch via Lockfile); Lernstand persistiert,
# Abstürze werden neu gestartet, täglicher Bericht geht raus:
python -m memetrader autopilot --budget-sol 1.0

# Tagesberichte aufs Handy (Telegram): Bot bei @BotFather anlegen ->
# Token kopieren; eigene Chat-ID z. B. via @userinfobot; dann:
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="123456789"
python -m memetrader notify-test          # Kanal prüfen
# Alternativ/zusätzlich: NOTIFY_WEBHOOK_URL für Discord/Slack/ntfy.sh

# Live (erst nach überzeugenden Paper-Wochen!):
#   1. pip install solders
#   2. export SOLANA_PRIVATE_KEY=...   # NUR lokal – nie in Chat/Repo/Cloud!
#   3. export SOLANA_RPC_URL=...       # eigener RPC empfohlen (Helius o. ä.)
python -m memetrader run --live --i-understand-the-risk --position-sol 0.05
```

Jede Entscheidung landet als JSON-Zeile in `memetrader.log.jsonl`
(Entries, Exits mit Grund, blockierte Einstiege) – die Grundlage, um die
Schwellen gegen echte Ergebnisse zu kalibrieren, statt zu raten.

## Sicherheit

- **Der Private Key verlässt nie deine Maschine**: Live-Pfad nutzt die
  PumpPortal-Local-API (Transaktion wird lokal signiert), jede Transaktion
  wird vor dem Senden simuliert, Positionsgrößen sind hart gedeckelt.
- Diese Cloud-Sandbox blockt Krypto-Domains (Proxy-403): Der Live-Pfad ist
  hier **ungetestet** und als Gerüst markiert – erster echter Lauf lokal,
  mit Minimalbeträgen. Die Logik (Curve-Mathe, Strategie, Risk, Lebenszyklen)
  ist über 15 Tests mit synthetischen Event-Strömen abgedeckt.
- Kosten pro Trade im Live-Betrieb: 1,25 % Curve-Fee + 0,5 % PumpPortal +
  Priority Fee (siehe [`../../docs/fee-oekonomie.md`](../../docs/fee-oekonomie.md)) –
  bei 0,05-SOL-Positionen sind das ~2 % Hürde pro Roundtrip. Der Filter muss
  das erst einmal verdienen.

## Empfohlener Ablauf für das 1-SOL-Experiment

1. `memescan watch` parallel laufen lassen (Launch-Archiv → Kalibrierdaten).
2. `memetrader run` im Paper-Modus mindestens 1–2 Wochen; Log auswerten:
   Trefferquote, PnL nach Fees, welche Exits greifen.
3. Schwellen anpassen (StrategyConfig/RiskConfig), erneut Paper.
4. Erst wenn Paper über Wochen netto positiv NACH Fees ist: Live mit 0,02–0,05
   SOL Positionen. Wenn nicht: Das Experiment hat trotzdem geliefert – nämlich
   den Beweis, welche Variante NICHT funktioniert, ohne das SOL zu verbrennen.
