# Real-Test: Der Bot gegen echte historische Coins (Ergebnis: negativ)

> Ausgeführt am 03.09.2026. Getestet wurde die Entry-Pipeline des Bots gegen
> **echte** pump.fun-Coins mit **echten** Outcomes (MELT-Datensatz, 41.470
> graduierte Coins Dez 2024–März 2025; CC BY-NC). Methodik: `realtest.py`.
> Dieses Dokument hält bewusst ein NEGATIVES Ergebnis fest – es ist der
> wichtigste Befund des Projekts.

## Methodik (auf Sauberkeit gebaut)

- **Nur der chronologische Hold-out** (letzte 20 %, 8.295 Coins ≈ Feb/März
  2025) – auf diesen Coins wurde das ML-Modell nie trainiert.
- Alle Auswahl-Features **strikt kausal** (Ticker-Duplikate/Creator-Historie
  nur aus der Vergangenheit); Impersonations-Veto nur aus öffentlichem Wissen.
- Exits aus den realen Outcomes approximiert, als **Korridor** gerechnet:
  konservative Ordnung (Stop −35 % greift vor jedem Gewinn, sobald der Coin
  je ≤ 65 % des Einstiegs fiel) vs. optimistische Ordnung (TP-Leiter zuerst);
  4 % Roundtrip-Kosten. TP-Leiter: +175 % ab Endrendite ≥ 250 %.
- Schwellen-Kalibrierung ausschließlich auf dem Trainings-Teil; der Hold-out
  wurde genau einmal ausgewertet.

## Ergebnis

**Basisrate (jeden graduierten Coin kaufen):** −19,9 % pro Trade, 79 %
Stop-Quote, 13,7 % Winrate.

**Bot-Auswahl** (Impersonations-Veto + Ticker-Dedupe + ML-Gate 0,8 → 941 von
8.295 Coins, 11,3 %):

| Exit-Ordnung | Ø PnL/Trade | Winrate | PnL bei 0,05 SOL/Trade |
|---|---|---|---|
| konservativ | **−17,6 %** | 15,7 % | −8,27 SOL |
| optimistisch | **−16,5 %** | 16,3 % | −7,74 SOL |

Der Filter wirkt messbar (High-Risk-Anteil 84 % → 67,5 %, +2,3 Punkte
Erwartungswert gegenüber Basisrate) – **aber er dreht das Vorzeichen nicht.**

**Schwellen-Sweep (nur Train):** monoton besser mit strengerem Gate, aber
selbst die strengste Konfiguration (ML < 0,5) bleibt bei **−7,0 %** pro Trade.
Es existiert in diesem Auswahl-Pfad keine profitable Konfiguration.

**Drift live beobachtet:** Die auf Train beste Konfiguration (ML < 0,5)
selektiert im Hold-out-Zeitraum **null** Coins – die Score-Verteilung
verschiebt sich binnen Wochen. Das bestätigt empirisch die
Retraining-Pflicht aus [`filter-engine.md`](filter-engine.md) (4.5).

## Antwort auf die Frage "Was wäre aus 1 SOL geworden?"

In diesem realen Zeitraum, mit dieser Pipeline: **Der größte Teil des 1 SOL
wäre verloren gegangen.** Der Tages-Kill-Switch (−0,15 SOL) hätte den Verlust
gestreckt und gedeckelt, aber bei ~16 % Winrate und −17 % Erwartung pro Trade
nicht verhindert. Die +20 % aus der kalibrierten Simulation
([`backtest-simulation.md`](backtest-simulation.md)) haben den Realitätstest
damit NICHT bestanden – die Simulation war, wie dort bereits gewarnt, zu
freundlich.

## Was dieser Test NICHT prüfen konnte (offene Hypothese)

Ohne Trade-Streams blieben genau die Komponenten ungetestet, die den
eigentlichen Edge liefern sollen: Curve-Phasen-Timing (Einstieg bei
Nachfrage-Beweis statt "Kauf bei Graduation"), Mikrostruktur-Gates
(Burst/Top-3/Wash), Creator-Dump-Sofort-Exit und Zeit-Stops. Der Befund ist
also präzise: **"Metadaten-Auswahl allein hat keinen Edge" ist auf echten
Daten belegt; ob die Timing-/Mikrostruktur-Schicht einen liefert, ist offen
und nur mit Trade-Level-Daten prüfbar.**

## Nachtrag: erweiterte Policy-Suche (ebenfalls negativ)

Auf die Frage "geht es mit anderem Entscheidungsraum positiv?" wurde eine
Grid-Suche mit sauberem 60/20/20-Protokoll durchgeführt (Modelle nur auf den
ersten 60 % trainiert, Suche nur auf der Validierung, Hold-out unberührt):

- **Zweites Modell mit anderem Ziel:** statt Risiko-Vermeidung (P(high)) ein
  Gewinner-Sucher (P(Endrendite > +50 %), Basisrate 12,9 %).
- **Exit-Grid:** Stop ∈ {−20 %, −35 %, −50 %} × Gewinn-Cap ∈ {+100 %, +250 %,
  +500 %}, konservative Ordnung, 4 % Kosten.
- **Auswahl-Grid:** Risiko-Schwellen, Gewinner-Quantile (q90/q95/q98), Kombis.

**Ergebnis: keine der Konfigurationen erreicht ein positives Mittel.**
Bestwert −10,1 % pro Trade (Stop −20 %, Cap +500 %, Gewinner-q90; Winrate
7,7 %); strenge Risiko-Auswahlen selektieren spät im Zeitraum kaum noch Coins
(Drift). Muster: engerer Stop > weiter Stop, hoher Cap > niedriger Cap – aber
die Decke bleibt klar unter null.

**Präzisierte Schlussfolgerung:** Der Edge liegt – falls er existiert – NICHT
in der Frage "welchen graduierten Coin wähle ich anhand von Launch-Metadaten".
Endpunkt-Daten können zudem strukturell nicht testen, was der Bot eigentlich
tut (Minuten-Timing, Zeit-Stops, Mikrostruktur-Gates): Diese Hypothese bleibt
offen und braucht Trade-Streams. Konsistent mit der Fee-Ökonomie-Analyse
([`fee-oekonomie.md`](fee-oekonomie.md)): Verlässlich positiv sind in diesem
Markt die Fee-/Tooling-Seiten, nicht die Richtungswette.

## Teil 2: Voll-Replay auf echten Trade-Streams (ein realer Handelstag)

Über eine Dataset-Recherche wurde ein GitHub-Repo mit **einem kompletten Tag
roher pump.fun-Bonding-Curve-Events** gefunden (31.07.2026, 3,34 Mio. Events
inkl. virtueller Reserven je Trade – `pumpfun-market-lab`, keine Lizenz
angegeben, nur lokal verwendet). Damit war erstmals der **komplette Bot**
lookahead-frei auf echten Trades replaybar: Curve-Timing, Mikrostruktur-Gates,
Exits, Lern-Schicht (`realdata.py`-Konverter, ML-Gate offline deaktiviert,
Claude-Kanal als Stub).

**Der Replay fand zuerst einen echten Bug:** Die Budget-Prüfung behandelte
Verkaufserlöse als verbraucht (Umsatz- statt Kapital-Deckel) – der Bot fror
nach ~29 Entries ein. Nach dem Fix (korrekte Cash-Rechnung, Regressionstest):

| Lauf | Ergebnis (Start 1,0 SOL) |
|---|---|
| **Voller Tag, Lernen an** | **1,2661 SOL (+26,6 %)**, 51 Trades, Winrate 37 %, Max-DD 20,5 % |
| Stunden 0–11 (Lernphase) | +11,0 % |
| Walk-Forward: Stunden 12–23 mit H1-Lernstand | +15,6 % (DD nur 4,2 %) |
| Kontrolle: Stunden 12–23 mit Defaults | +22,4 % |

**Gewinn-Struktur (glaubwürdig asymmetrisch, kein Einzeltreffer):** 32 kleine
Verluste (Ø −0,011 SOL) gegen 19 größere Gewinne (Ø +0,035 SOL), Payoff-Ratio
3,1; Haupttreiber sind Graduation-Runner (migration_exit), Top-3-Trades ≈ 69 %
des PnL bei ähnlich großen Einzelbeiträgen.

**Ehrliche Einordnung:**
1. **n = 1 Tag.** Ein profitabler Realtag belegt, dass die Timing-Schicht
   funktionieren KANN – nicht, dass der Edge über Wochen trägt. Teil 1 dieses
   Dokuments zeigt, wie brutal Monats-Basisraten sein können.
2. **Fill-Modell bleibt freundlich** (Post-Trade-Kurs + 1 % Malus): reale
   Fills kämpfen mit MEV, Fehlversuchen, Priority-Fees.
3. **Lern-Befund:** Die H1-Selbstverschärfung (Käufer ≥ 30, Füllung ≥ 35 %)
   unterlag den Defaults auf H2 (+15,6 % vs. +22,4 %) – der Tuner optimiert
   Verlust-Vermeidung ohne Opportunitätskosten. Konkreter Verbesserungspunkt.
4. Der Befund aus Teil 1 bleibt gültig: Der Edge liegt im **Timing**, nicht
   in der Metadaten-Auswahl.

**Nächster Schritt vor jedem Live-Gedanken:** mehr echte Tage – lokal Streams
aufzeichnen (`memetrader record`) und denselben Replay über Wochen fahren;
erst eine positive Wochen-Serie auf frischen Daten trägt Beweislast.

## Teil 3: Eine echte Handelswoche (Fingerprinter, 03.–09.06.2026)

Auf der Suche nach Wochen-Daten wurde ein dritter Real-Datensatz erschlossen:
willho/fingerprinter-dataset (pg_dump, lokal restauriert) – **39.010 reale
Launches über 6,7 zusammenhängende Tage**, 657k event-getriggerte Snapshots
(Preis in SOL, 15-%-Move-/Drawdown-/Deathbed-Trigger, kumulative Wallets/
Trades/Volumen). Replay: `fingerreplay.py` – Bot-Logik auf Event-Granularität
(Entry bei bestätigtem 2x-Momentum im 45s–45min-Fenster + Nachfrage-Beweis,
asymmetrische Exits, volle Portfolio-Rechnung, 3 % Kosten).

| Variante | Ergebnis (1 SOL Start) | Trades | Winrate |
|---|---|---|---|
| Bot-Regel (Momentum-Bestätigung) | **0,631 SOL (−36,9 %)** | 46 | 17,4 % |
| Kontrolle ohne Bestätigung | 0,568 SOL (−43,3 %) | 53 | 15,1 % |

**Einordnung:** Die Momentum-Bestätigung verbessert messbar (+6,4 Punkte),
aber die Woche endet klar negativ; der Kill-Switch griff an 2 von 7 Tagen.
Wichtige Unterschiede zum profitablen Juli-Tag: gröbere Granularität
(Events statt Sekunden-Trades), keine Mikrostruktur-Gates möglich (keine
Wallet-Level-Daten -> Bundle-/Wash-Checks inaktiv), anderes Markt-Regime,
Discovery-Auswahl des Quellsystems (~5,8k/Tag). Das Gesamtbild über alle
Real-Zeiträume: je feiner die Zeitauflösung, desto besser das Ergebnis –
was ZWEI Lesarten zulässt (Edge lebt im Sekunden-Timing UND/ODER feinere
Simulation = freundlichere Fills). Beide mahnen zum selben Schluss:

**Kein grünes Licht für echtes SOL.** Ein profitabler Tag + eine negative
Woche + drei negative Grob-Studien = die Beweislast liegt weiter bei
mehrwöchigen Sekunden-Daten (lokale Aufzeichnung), nicht beim Kapital.

## Teil 4: 8 weitere echte Tage – Entry-Qualität isoliert (q33wx-Datensatz)

Vierter unabhängiger Real-Zeitraum: q33wx/pumpfun-pumpswap-market-data –
**69.855 reale Launches, 16.–27.07.2026**, mit Sekunden-Snapshots bei t=60s
(Trades, Netto-SOL, Unique-Buyer, Dev-Share) und Endpunkt-Outcomes
(peak_mult, final_mult, secs_to_peak, rugged). Ergänzend bestätigte die
Recherche: mehr Roh-Trade-Tage existieren auf GitHub nicht; mehrwöchige
Per-Trade-Archive gibt es nur auf (hier geblockten) Diensten wie
replay.pumpapi.io – lokal für den Nutzer abrufbar.

Studie: Bot-Entry-Regel bei t=60s (Buyer>=10, Trades>=15, Netto>=3 SOL,
Dev<=10 %) gegen reale Outcomes, Entry-Preis über die Curve-Formel korrigiert
(wer nach Traktion kauft, kauft höher), Endpunkt-Exit-Klammer wie Teil 1:

| | Ø PnL (kons./optim.) | Winrate |
|---|---|---|
| Alle 69.855 Launches | −12,9 % / −12,0 % | 6–7 % |
| Bot-Auswahl @60s (10,2 %) | **−32,6 % / −32,3 %** | ~4 % |

**Zwei getrennte Erkenntnisse:** (1) Der Sicherheitszweck funktioniert –
Rug-Quote in der Auswahl 2,1 % vs. 9,4 % Basis. (2) Als *Rendite*-Signal ist
"Traktion bei 60s kaufen" unter Endpunkt-Exits sogar schlechter als der
Durchschnitt: Der Peak liegt bei diesen Coins häufig in/kurz nach der ersten
Minute (secs_to_peak), man kauft das lokale Hoch der Sniper-Welle. Wichtige
Einschränkung: Endpunkt-Daten können die echten schnellen Exits des Bots
(Zeit-Stopps nach Minuten, Trailing) nicht abbilden – dieselbe Auswahl kann
mit reaktiven Exits anders abschneiden (vgl. Teil 2). Die Aussage ist also
präzise: **Der Entry allein trägt keinen Edge; wenn es einen gibt, entsteht
er im Zusammenspiel mit schnellen Exits – und genau das braucht
Sekunden-Streams zur Validierung.**

## Konsequenzen

1. **Kein Live-Trading mit diesem Stand.** Die Beweislast liegt jetzt bei der
   Timing-Schicht – und die braucht echte Streams.
2. Realer Prüfweg: lokal `memescan watch`/`memetrader record` einige Wochen
   aufzeichnen, dann `memetrader backtest --events <aufzeichnung>` – derselbe
   Harness, echte Daten, voller Bot inklusive Mikrostruktur-Gates.
3. ML-Gate nur mit rollierendem Retraining betreiben (Drift-Befund).
4. Der Wert des heutigen Tages: Diese Erkenntnis hat 1 SOL gerettet, bevor er
   es auf die teure Art gelehrt hätte.
