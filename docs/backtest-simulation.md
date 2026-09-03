# Backtest-Bericht: 1 SOL über 60 Tage (kalibrierte Simulation)

> Ausgeführt am 03.09.2026 in der Entwicklungs-Session. **Dies ist KEINE Replay
> der realen letzten zwei Monate** – reale Trade-Streams für Juli–Sept 2026
> waren aus der Sandbox nicht abrufbar (Krypto-APIs geblockt, MELT-Rohdaten
> extern). Es ist ein Lookahead-freier Lauf des unveränderten Bots über einen
> stochastischen Markt, der auf die recherchierten realen Basisraten
> kalibriert ist ([`filter-engine.md`](filter-engine.md) 6b). Interpretation:
> Abschnitt "Was diese Zahlen bedeuten" – Pflichtlektüre vor jedem Schluss.

## Setup

- Start: 1,0 SOL · Positionsgröße 0,05 SOL · max. 3 parallel · Tages-Kill-Switch −0,15 SOL
- 60 simulierte Tage × 400 Launches/Tag (24.000 Launches je Seed), 5 Seeds
- Archetyp-Mix (kalibriert): 62 % Insta-Tod, 20 % Ausbluten, 9 % Bundle-Pump&Dump,
  4,5 % Creator-Rug, 3,5 % organische Läufer, 1 % Graduations; Socials je Archetyp
  gemäß Telegram-Graduation-Lift (8,9x) modelliert
- Voller Stack aktiv: Regel-Strategie, echtes MELT-ML-Gate (Schwelle 0,8),
  Lern-Schicht (Journal → Selbst-Tuning), Claude-Kanal als deterministischer
  Offline-Stub (gleiche Schnittstelle/Informationslage; ohne API-Key keine
  echten Claude-Calls möglich – mit Key: `--claude live`)
- Kein Lookahead by construction: Events streng chronologisch, Archetypen für
  den Bot unsichtbar, Fills exakt gegen Bonding-Curve-Mathematik inkl. Fees +
  Latenz-Malus

## Ergebnis

| Seed | Endkapital | Rendite | Trades | Winrate | Max DD |
|---|---|---|---|---|---|
| 1 | 1,136 SOL | +13,6 % | 14 | 71 % | 1,9 % |
| 2 | 1,200 SOL | +20,0 % | 19 | 63 % | 3,1 % |
| 3 | 1,290 SOL | +29,0 % | 23 | 74 % | 2,9 % |
| 4 | 1,315 SOL | +31,5 % | 24 | 71 % | 3,1 % |
| 5 | 1,069 SOL | +6,9 % | 19 | 53 % | 7,0 % |
| **Median** | **1,200 SOL** | **+20,0 %** | | | |

**Lern-Schicht sichtbar aktiv:** In 4 von 5 Seeds erkannte das Journal wiederholt
`impatient` (Zeit-Stop warf Positionen ab, die danach weiterliefen) und der
Selbst-Kalibrierer verlängerte den Progress-Deadline schrittweise von 480 s auf
das Bound-Maximum 900 s – exakt das vorgesehene Verhalten inkl. harter Grenze.
Häufigste Lektionen: `good_time_stop`, `good_creator_exit` (der
Creator-Dump-Sofort-Exit rettete viele Positionen), `impatient`.

## Was diese Zahlen bedeuten – und was nicht

1. **Die Maschinerie funktioniert:** Filter lassen von ~24.000 Launches nur
   ~25 Entries durch; Exits, Kill-Switch-Logik, Journal, Selbst-Tuning und
   Vet-Pfad arbeiten zusammen; kein Seed verlor Geld, Drawdowns blieben klein.
2. **Die +20 % Median sind eine OBERE Abschätzung unter freundlichen
   Annahmen, keine Prognose.** Der Simulator modelliert die harten Teile der
   Realität unvollständig: keine adaptiven Gegner, keine gefälschten
   Unique-Buyer (Wash-Wallets, die unsere Käuferzahl täuschen), Bundle-Fallen
   verraten sich hier oft durch sichtbare Creator-Verkäufe (real verkaufen
   Insider über nicht verknüpfte Wallets), Metadaten-Korrelationen sind
   sauberer als draußen, und Fills/MEV sind gnädig modelliert.
3. **Auffällig und ehrlich benannt:** 0 Stop-Loss-Lektionen und 0
   Kill-Switch-Tage heißt: Die gefährlichste reale Verlustquelle (Bundle-Dump
   ohne Creator-Signal) kam beim Bot kaum an – im echten Markt wird sie das.
   0 Vetos im Stub heißt: Impersonations-Fälle wurden schon von ML-Gate und
   Dedupe abgefangen, bevor der Vet sie sah.
4. **Der eigentliche Test steht noch aus:** `memetrader record` auf dem
   echten Stream laufen lassen und DENSELBEN Harness mit `--events` auf der
   Aufzeichnung ausführen – erst das ersetzt die Simulation durch Realität.

## Reproduktion

```bash
python -m memetrader backtest --days 60 --budget-sol 1.0 --seeds 1 2 3 4 5
# mit echtem Claude-Vet (API-Key nötig, langsam/kostenpflichtig):
python -m memetrader backtest --days 7 --seeds 1 --claude live
# auf echten Aufzeichnungen:
python -m memetrader backtest --events aufzeichnung.jsonl --seeds 1
```
