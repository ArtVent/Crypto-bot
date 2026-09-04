# Real-Test: Der Bot gegen echte historische Coins (Ergebnis: negativ)

> **Nachtrag 04.09.2026 (Anti-Bug-Durchlauf):** Die unten genannten ABSOLUTEN
> A/B-Zahlen (z. B. Referenz +17,84 %, Kappe +20,12 %, Leiter +22,47 %) wurden
> mit einem Wiedereintritts-Bug berechnet (der Bot kaufte gerade verkaufte
> Coins wieder nach). Nach der Korrektur ergibt derselbe Tag +57,0 % – ein
> nicht robuster Einzeltag-Wert (Tuner-Kaskade), KEIN Edge-Versprechen. Die
> relativen Aussagen bleiben richtungsgültig; Details in
> `docs/anti-bug-durchlauf.md`. Maßgeblich ist ab jetzt die Forward-Serie.

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

### Nachtrag Teil 2: A/B-Test "Halten durch die Migration" – verworfen

Die aus den Journal-Kontrafakten abgeleitete Hypothese (Migration-Exits
schneiden Gewinner ab -> halten + 30 % Trailing auf dem echten PumpSwap-AMM,
17,5 Mio. AMM-Events desselben Tages gemerged) wurde als kontrollierter
A/B-Test auf identischen Daten geprüft – und klar verworfen:

| Lauf (identische Daten, Curve+AMM) | Ergebnis |
|---|---|
| E: Halten + Trailing | **0,847 SOL (−15,3 %)**, 23 Trades |
| F: Sofort-Exit bei Migration (alt) | **1,178 SOL (+17,8 %)**, 58 Trades |

Gründe: Verkauf in die Graduation-Stärke ist der bessere Fill (nach der
Migration folgt oft der Dump, Trailing gibt 30 % her); gehaltene Positionen
blockieren bis zu 4 h die Concurrency-Slots (23 statt 58 Trades –
Opportunitätskosten). Lehre für die Lern-Schicht: Der Post-Exit-Peak im
Journal ist NICHT gleich abschöpfbarem Wert. Default zurück auf Sofort-Exit;
Mechanik bleibt als Option. Attribution der übrigen Differenz zum
+26,6-%-Lauf: neue Tuner-Bounds/Lockerung ≈ −4,5 Punkte (Tages-Rauschen,
mehr Entries inkl. mehr bad_entry), realistischere AMM-Preisung des
Graduation-Exits ≈ −4,3 Punkte – **+17,8 % ist damit die ehrlichste Zahl für
diesen Tag mit aktuellem Code.**

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

## Teil 5: Wallet-Intelligence-A/B – drei neue Gates auf dem realen Tag

Auf Nutzerwunsch ("neue Techniken") wurden drei rollierende, strikt kausale
Intelligence-Schichten gebaut (`wallet_intel.py`) und im kontrollierten A/B
auf dem vollen realen Tag (Teil 2, Curve + AMM gemerged) getestet – Referenz
ist der ehrliche F-Lauf mit **+17,84 %**:

| Variante | Ergebnis | Trades |
|---|---|---|
| F Referenz (ohne Gates) | +17,84 % | 58 |
| X Serial-Creator-Block (≥3 Launches, 0 Grads) | +17,84 % | 58 |
| Y X + Smart-Wallet-Konfluenz (min. 1) | +17,84 % | 58 |
| Z X + Regime-Gate (min. 3 Graduationen/h) | +17,84 % | 58 |

**Alle drei Läufe sind identisch zur Referenz – und das ist ein echter
Befund, kein Harness-Fehler** (verifiziert: die Overrides kamen im Bot an,
das Journal loggt `smart_buyers` je Entry): Auf diesem heißen Tag feuerte
keines der Gates ein einziges Mal. Serial-Spammer-Coins schaffen es gar
nicht erst durch die Momentum-Filter, der Markt fiel nie unter 3
Graduationen/Stunde, und **jeder** der 58 Trades hatte bereits ≥1
graduation-kreditierte Wallet unter den Käufern (Median ≈ 9, Spanne 1–29).

**Die eigentliche Erkenntnis steckt in der Verteilung:** Viele "smarte"
Wallets sind auf heißen Tagen kein Qualitäts-, sondern ein Dichte-Signal –
graduation-kreditierte Wallets sind überwiegend Serien-Sniper-Bots, die in
fast jeden Launch gehen. Journal-Analyse der 58 Trades:

| Gruppe | Winrate | PnL |
|---|---|---|
| < 8 kreditierte Wallets (n=19) | **58 %** | +0,190 SOL |
| ≥ 8 kreditierte Wallets (n=39) | 33 % | +0,086 SOL |

Der Effekt hält in beiden Tageshälften unabhängig (Split-Half-Check), das
Vorzeichen ist also stabil: **Ein Sniper-Pile-in (viele kreditierte Wallets
im Käuferfeld) senkt die Trefferquote.** Das Konfluenz-Gate "mindestens X
smarte Wallets" ist damit auf heißen Tagen genau falsch herum gedacht.

Konsequenz: Bot-Dichte-**Kappe** `max_smart_buyers` implementiert (Gegenteil
des Konfluenz-Gates) und in-sample auf demselben Tag getestet:

| Lauf | Ergebnis | Trades | Winrate | Max-DD |
|---|---|---|---|---|
| F Referenz | +17,84 % | 58 | 41 % | 23,1 % |
| **W Kappe (max. 7 kreditierte Wallets)** | **+20,12 %** | 21 | **67 %** | **12,9 %** |

Die Kappe blockte 3.789 Kandidaten und veränderte den Charakter des Tages:
kaum noch Graduation-Runner (1 statt 9 migration_exits – überfüllte Coins
graduieren eben oft), dafür enge Verluste (schlechtester Trade −0,02 SOL)
und hohe Trefferquote. **Ehrliche Einordnung:** Rendite-Vorsprung bei n=21
nicht belastbar (Top-3-Trades = 76 % des PnL; ohne den besten Trade ≈ +13 %),
und die Schwelle 8 stammt aus der Journal-Analyse desselben Tages
(in-sample). Belastbar ist die **Risiko-Verbesserung** (Drawdown halbiert,
Verluste gedeckelt) – genau das, was ein Dichte-Filter leisten soll.

**Entscheidungen (alle konservativ):**
- `block_serial_creators` bleibt als Default an – kostenlos, blockt ein
  dokumentiertes Scam-Muster, veränderte diesen Tag nicht.
- `min_smart_wallets` bleibt aus (Default 0): auf heißen Tagen wirkungslos
  bis kontraproduktiv.
- `min_market_heat` bleibt aus, ist aber als Schutz für kalte Regimes
  verfügbar (die Verlustwoche aus Teil 3 war ein kaltes Regime).
- `max_smart_buyers` bleibt trotz des guten In-Sample-Laufs aus: Die
  Schwelle stammt aus demselben Tag, an dem sie getestet wurde. Validierung
  erfolgt vorwärts im Autopilot-Papertraining auf frischen Daten, nicht
  durch Adoption rückgetesteter eigener Hypothesen. Der Lauf W ist der
  vorregistrierte Vergleichsmaßstab dafür.

## Teil 6: Teilverkaufs-Leiter ("Einsatz raus, Gewinn läuft")

Auf Nutzerwunsch gebaut: Sobald der Positionswert die aktuelle Basis um X %
übersteigt, wird genau die Basis verkauft; der Gewinn bleibt im Markt, wird
zur neuen Basis, und das wiederholt sich (`recycle_trigger_pct` in
`risk.py`). Kontrollierter A/B auf dem vollen realen Tag, drei Trigger:

| Lauf | Ergebnis | Trades | Winrate | Max-DD |
|---|---|---|---|---|
| F Referenz (ohne Leiter) | +17,84 % | 58 | 41 % | 23,1 % |
| Leiter +20 % | +8,58 % | 44 | 73 % | 10,5 % |
| Leiter +50 % | +2,88 % | 54 | 52 % | 19,4 % |
| **Leiter +100 %** | **+22,47 %** | 58 | 41 % | 21,7 % |

**Struktur des Befunds:** Ein früher Trigger räumt ~83 % der Position beim
ersten Zucken ab und kappt genau die Graduation-Runner, die den Tag tragen –
+20 % liefert die glatteste Kurve (WR 73 %, DD 10,5 %), aber halbiert den
Gewinn. Das bestätigt Teil 4 von der anderen Seite: **Der Edge lebt davon,
Gewinner laufen zu lassen.** Der späte Trigger (+100 %) ist in Stufe 1
identisch mit dem bestehenden Derisk – sein Mehrwert ist die *Wiederholung*:
Bei jedem weiteren Verdoppeln über der neuen Basis wird erneut gebankt,
wodurch Runner-Gewinne stufenweise gesichert werden statt komplett am
Trailing/Migrations-Exit zu hängen. +4,6 Punkte über der Referenz bei
leicht niedrigerem Drawdown.

**Einordnung und Entscheidung:** Die Wahl "+100 % ist am besten" ist eine
Auswahl auf demselben (inzwischen vielgenutzten) Testtag. Default bleibt
daher aus; die +100 %-Leiter läuft ab jetzt als **dritter Arm im täglichen
Forward-A/B** (`abtest`, docs/forward-validierung.md) und wird nur bei
kumulativem Serien-Vorsprung Default – dieselbe Regel wie für die
Dichte-Kappe.

**Nachtrag – dieselbe Leiter auf der echten Verlustwoche (Teil 3):** Auf
den Fingerprinter-Daten (6,7 Tage, kaltes Regime) verbessert die
+100 %-Leiter das Ergebnis von −36,9 % auf **−30,7 %** (Winrate 17→22 %,
Tiefstand 0,45→0,51 SOL) – gleiche Richtung wie am heißen Tag, aber die
Woche bleibt tief negativ. Der Befund beider Regime zusammen: **Die Leiter
verbessert die Exits konsistent um ~5–6 Punkte, aber das Vorzeichen einer
Periode bestimmt das Regime, nicht die Exit-Mechanik.** Hochgerechnet auf
14 Tage (geometrisch, Leiter-Konfiguration): nur kalte Tage ≈ 0,46 SOL;
Break-even braucht ~1 heißen Tag je ~3,7 kalte; hälftig heiß/kalt ≈
2,8 SOL; nur heiße Tage ≈ 17 SOL (Fantasie-Obergrenze, ein einzelner
Tag hochkompoundiert). Wie häufig heiße Tage wirklich sind, kann nur die
laufende Forward-Serie zeigen; der wirksamste Hebel laut dieser Rechnung
ist, kalte Regime gar nicht zu handeln (Regime-Gate `min_market_heat`,
vorhanden, Default aus, Forward-Kandidat).

## Konsequenzen

1. **Kein Live-Trading mit diesem Stand.** Die Beweislast liegt jetzt bei der
   Timing-Schicht – und die braucht echte Streams.
2. Realer Prüfweg: lokal `memescan watch`/`memetrader record` einige Wochen
   aufzeichnen, dann `memetrader backtest --events <aufzeichnung>` – derselbe
   Harness, echte Daten, voller Bot inklusive Mikrostruktur-Gates.
3. ML-Gate nur mit rollierendem Retraining betreiben (Drift-Befund).
4. Der Wert des heutigen Tages: Diese Erkenntnis hat 1 SOL gerettet, bevor er
   es auf die teure Art gelehrt hätte.
