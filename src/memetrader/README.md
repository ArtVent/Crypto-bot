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

## Nutzung

```bash
# Paper-Trading (Default) – läuft gegen echte Live-Streams, handelt simuliert:
python -m memetrader run --budget-sol 1.0

# Backtest auf aufgezeichneten Events (JSONL, ein Event pro Zeile):
python -m memetrader replay events.jsonl

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
