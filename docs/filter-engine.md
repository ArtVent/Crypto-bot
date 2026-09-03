# Die Filter-Engine – Verlust-Vermeidung bis ins Detail

> Der tiefste technische Baustein dieses Repos: Wie man die Erkennungs-Schicht baut, die im Memecoin-Trading den Erwartungswert dreht. Ergänzt [`bot-architektur.md`](bot-architektur.md) (Abschnitt 3) und [`ai-und-memecoins.md`](ai-und-memecoins.md); der vollständige Feature-Katalog mit Schwellen steht in [`../data/filter-features.json`](../data/filter-features.json). Stand des Wissens: 2026.

## 1. Warum der Filter der Edge ist (die Mathematik)

Vereinfachtes Zahlenbeispiel mit realistischen Größenordnungen:

- Von allen Launchpad-Tokens graduiert nur eine niedrige einstellige Prozentzahl; der Rest ist nach Stunden wertlos.
- Annahme: Ein wertloser Kauf kostet im Schnitt −70 % (Rest-Exit vor Null), ein 'Runner' bringt im Schnitt +150 % (nach Fees/Slippage, gemischt aus kleinen und großen Gewinnern).
- **Ohne Filter** (1 % Trefferquote): EV pro Trade ≈ 0,01·150 % + 0,99·(−70 %) ≈ **−67 %**. Ruin, egal wie schnell man ist.
- **Mit Filter, der 90 % des Schrotts aussortiert und 80 % der Runner durchlässt**: Trefferquote ≈ 7,5 %, EV ≈ 0,075·150 % + 0,925·(−70 %) ≈ **−53 %** – immer noch negativ! 
- Erst die Kombination aus Filter UND asymmetrischem Exit-Management (Verluste bei −30/−40 % kappen, Gewinner laufen lassen) dreht das Vorzeichen: gleiche Trefferquote, Verlust je Niete −35 %, Gewinn je Treffer +300 % → EV ≈ **−9 %**; mit besserem Filter (Trefferquote 15 %) → **+15 %**.

Drei Konsequenzen, die das ganze Design bestimmen:

1. **Der Filter muss brutal selektiv sein** – lieber 95 % aller Chancen verpassen als 5 % mehr Schrott kaufen.
2. **Filter und Exit-Regeln sind EIN System** – ein Filter 'rettet' keine Strategie mit symmetrischen Exits.
3. **Jeder Prozentpunkt Filter-Qualität ist bares Geld** – deshalb lohnt hier der Engineering-Aufwand, nicht beim x-ten Entry-Signal.

## 2. Architektur: die vier Stufen im Latenz-Budget

Reihenfolge strikt von billig nach teuer; jede Stufe kann K.-o. geben (dann stoppt die Pipeline) oder Flags/Scores anreichern:

```
Stufe 0  INSTANT  (<10 ms, lokal)        Namens-/Ticker-Kollisionen, Blacklists,
                                          Dev-Buy aus dem Launch-Event, Same-Block-Käufer
Stufe 1  CHEAP    (~50–150 ms, 1–2 RPC)  Mint-/Freeze-Authority, Token-2022-Extensions,
                                          Top-Holder, LP-Status, Liquidität
Stufe 2  API      (~100–500 ms)          RugCheck-Report, GoPlus (EVM), Birdeye-Metriken
Stufe 3  DEEP     (Sekunden, asynchron)  Funding-Graph/Bundle-Analyse, Wash-Schätzung,
                                          Social-Qualität, Creator-Historie tief
```

Praktische Regeln:

- **Stufe 0–1 laufen synchron vor jedem Trade** – auch beim Sniping (das kostet 1–2 Blöcke; wer das nicht zahlen will, handelt ungefiltert und verliert langfristig).
- **Stufe 3 läuft asynchron weiter, NACH einem etwaigen Einstieg**: Ergebnisse können eine offene Position downgraden (→ Auto-Exit) statt nur Einstiege zu blocken.
- **Jedes Ergebnis wird gecacht und versioniert** (Token-Adresse → verdict, score, flags[], feature_vector, timestamp). Alle Strategien lesen dieselbe Risiko-Sicht; Re-Checks laufen ereignisgetrieben (Creator-Wallet bewegt sich → Re-Score).

## 3. Die K.-o.-Liste (regelbasiert, nicht verhandelbar)

Vor jedem ML steht die harte Deny-Liste. Sie fängt die Fälle, bei denen kein Score der Welt eine Ausnahme rechtfertigt (Details je Feature in [`filter-features.json`](../data/filter-features.json)):

| # | Check | Grund |
|---|---|---|
| 1 | Mint- oder Freeze-Authority aktiv | Supply-/Freeze-Exploit möglich |
| 2 | Token-2022: PermanentDelegate gesetzt | Fremde Token konfiszierbar |
| 3 | Token-2022: unbekannter TransferHook | Beliebiger Code im Transfer-Pfad (Honeypot-Vektor) |
| 4 | LP weder geburnt noch gelockt (manuelle Pools) | Hard-Rug jederzeit |
| 5 | Bereinigte Top-10-Holder > ~30 % | Dump-Übermacht |
| 6 | Bundle-Funding-Überlappung > ~30 % der Early-Buyer | Ein Akteur spielt viele |
| 7 | Creator-Wallet auf eigener Rug-Blacklist / Serien-Launcher ohne Erfolge | Wiederholungstäter |
| 8 | Exakter Name+Bild-Match zu etabliertem Coin | Impersonation |
| 9 | Wash-Anteil > ~60 % des Volumens | Alle Marktsignale des Coins sind Fiktion |
| 10 | EVM: Honeypot-/Tax-/Proxy-Flags (Kauf-Verkaufs-Simulation fehlgeschlagen) | Klassische Contract-Fallen |

Wichtig: Schwellen (~) sind Startwerte – kalibriert werden sie an der eigenen Outcome-Statistik (Abschnitt 5), und sie werden bewusst NICHT öffentlich exakt dokumentiert, wenn der Bot live ist (Gegner testen gegen bekannte Grenzen).

## 4. Der ML-Layer über den Regeln

### 4.1 Was das Modell vorhersagt

Nicht "geht der Coin hoch?", sondern **Überlebens-/Qualitätsklassen** in festen Horizonten – das ist lernbar, Preisziele sind es kaum:

- `dead_1h` – praktisch kein Handel mehr nach 1 h
- `rug` – Insider-Exit-Muster (Cluster-Dump, LP-Ereignis) egal wann
- `survivor_24h` – handelbar mit realer Liquidität nach 24 h
- `graduated` – Curve abgeschlossen
- `runner` – graduiert UND hat Nach-Graduation-Hoch deutlich über Graduation-Preis

Ein Multi-Klassen-Modell (oder mehrere binäre) auf diesen Labels; die Strategie-Layer übersetzen dann selbst: Sniping braucht P(dead_1h) niedrig, Graduation-Trading P(graduated) hoch, Dip-Buying P(rug) niedrig.

### 4.2 Labeling-Regeln (der unterschätzte Teil)

- **Jedes Label braucht eine mechanische Definition** (z. B. rug = Creator-Cluster verkauft > X % innerhalb Y min UND Preis −Z %; nicht "sah aus wie ein Rug"). Uneindeutige Fälle bekommen ein `ambiguous`-Label und fliegen aus dem Training statt es zu verschmutzen.
- **Zeitpunkt-Disziplin:** Der Feature-Vektor wird exakt zum Entscheidungszeitpunkt eingefroren (t=Launch für Sniping-Modelle; t=Graduation für Dip-Modelle – das sind ZWEI Datensätze, nicht einer).
- **Vollständigkeit:** Alle Launches archivieren, auch die, die der Bot nie angefasst hätte – sonst lernt das Modell die eigene Vorauswahl statt den Markt.

### 4.3 Training & Modellwahl

- **Gradient Boosting (LightGBM/XGBoost)** als Arbeitspferd: tabellarische Features, Millisekunden-Inferenz, robuste Handhabung fehlender Werte (Stufe-3-Features sind zum Sniping-Zeitpunkt oft noch NULL – das Modell muss mit 'noch unbekannt' umgehen, Missing ≠ 0!).
- **Chronologische Splits, niemals zufällig**: Train Woche 1–8, Validation 9–10, Test 11–12; zusätzlich Purging (keine Label-Horizonte, die in den Test hineinragen).
- **Klassen-Gewichte nach ökonomischen Kosten**, nicht nach Häufigkeit: ein als sicher eingestufter Rug kostet real z. B. 10× so viel wie ein verpasster Runner an Opportunität – die Kostenmatrix gehört ins Training (sample weights) und in die Schwellenwahl.
- **Kalibrierung** (isotonic/Platt) am Ende: Die Scores werden als Wahrscheinlichkeiten in Positionsgrößen übersetzt – unkalibrierte Scores machen das Sizing kaputt.

### 4.4 Evaluation, die zählt

Ranking der Metriken nach Aussagekraft:

1. **Simulierter PnL auf dem Test-Zeitraum** mit konservativem Fill-Modell – die einzige Metrik, die am Ende zählt.
2. **Precision bei fixierter niedriger Alarm-Quote** (z. B. Precision@top-5 %-Scores): misst, ob die besten Kandidaten wirklich gut sind.
3. **Recall der Rug-Klasse bei fixer False-Positive-Rate**: Wie viel Schaden rutscht durch?
4. AUC/F1 nur als Debug-Werte – sie belohnen Verbesserungen in irrelevanten Score-Regionen.

Dazu **Slice-Analyse**: Metriken getrennt je Meta, Tageszeit, Launchpad und Marktphase – ein Modell, das nur in der Trainings-Meta funktioniert, ist beim nächsten Rotationswechsel wertlos.

### 4.5 Drift & Gegner-Adaption (Betriebsmodus)

- **Wöchentliches Retraining** auf rollierendem Fenster (z. B. letzte 8–12 Wochen) als Standard-Zyklus; zusätzlich Trigger-Retraining, wenn Live-Precision unter Alarmschwelle fällt.
- **Feature-Importance-Monitoring:** Kippt die Wichtigkeit eines Features abrupt, hat die Gegenseite adaptiert (z. B. Dev-Buys werden plötzlich klein gehalten und über Bundles ersetzt) → Feature-Familie erweitern.
- **Champion/Challenger:** Neues Modell läuft erst im Schatten-Modus (Scores loggen, nicht handeln) gegen das Live-Modell; Wechsel nur bei signifikant besserem simulierten PnL.
- **Private Zusatz-Features als Burggraben:** Öffentliche Checks (RugCheck-Flags etc.) sind allen bekannt und werden von Scammern getestet – die dauerhafte Kante liegt in eigenen Features aus dem eigenen Archiv (Creator-Historie, Funding-Graph-Fingerprints).

## 5. Detektions-Algorithmen im Detail

### 5.1 Bundle-Erkennung (Funding-Graph)

```
1. Sammle Käufer der Blöcke 0..N (N≈3) nach Launch → Kandidaten-Set
2. Für jede Wallet: verfolge Erstausstattung rückwärts (max. K Hops, K≈3):
   - direkter Transfer von Wallet X → Kante (wallet, X)
   - CEX-Withdraw: gruppiere nach Börse + Zeitfenster (Withdraw-Batches
     derselben Quelle landen zeitlich gehäuft)
3. Baue Graph, finde Zusammenhangskomponenten
4. bundle_score = Supply-Anteil der größten Komponente unter den Early-Buyern
5. Zusatz-Evidenz: identische Kaufgrößen, gleiche Priority-Fee-Signatur,
   Wallets alle jünger als 48 h, sequentielle Erstellung
```

Fallstricke: CEX-Hops zerschneiden den Graph (deshalb Zeitfenster-Heuristik), legitime Airdrop-Empfänger können wie Cluster aussehen (Whitelist bekannter Verteilungen), und die Analyse ist teuer → asynchron in Stufe 3, Ergebnis wirkt als Positions-Downgrade.

### 5.2 Wash-Erkennung (drei unabhängige Tests, Mehrheitsentscheid)

1. **Konzentrationstest:** Anteil des Volumens der Top-5-Trader-Wallets; > ~60 % = verdächtig.
2. **Uniformitätstest:** Varianz der Trade-Größen und Inter-Trade-Zeiten; Bots erzeugen unnatürlich regelmäßige Muster (organischer Flow ist bursty und größen-heterogen).
3. **Zirkularitätstest:** Kauf- und Verkaufsvolumen derselben Wallets im kurzen Fenster (Selbst-Überschneidung), inkl. 1-Hop-Nachbarwallets.

Ausgabe ist ein Wash-Anteil-Schätzer, der ALLE volumenbasierten Signale des Bots bereinigt (`wash_adjusted_volume`) – nicht nur ein Flag.

### 5.3 Soft-Rug-Frühwarnung (Laufzeit)

Ereignisgetriebene Überwachung jeder offenen Position: Creator-Cluster-Verkäufe, Transfers an CEX-Deposits/frische Wallets, LP-Bewegungen bei nicht geburnten Pools, Downgrade durch nachgezogene Stufe-3-Ergebnisse. Jeder Trigger mappt auf eine definierte Aktion (Alarm / Teil-Exit / Voll-Exit) – im Code, nicht im Ermessen.

## 6. Externe Checks als Input (nicht als Ersatz)

RugCheck, GoPlus, SolSniffer & Co. sind wertvolle Stufe-2-Inputs: schnell, breit, gepflegt. Aber sie sind öffentlich (Scammer testen dagegen), generisch (kennen die eigene Strategie nicht) und gelegentlich falsch. Regel: **Externe Scores sind Features im eigenen Modell, niemals die Entscheidung.** Zusätzlich jeden externen Feed auf Plausibilität überwachen (Anomalie-Erkennung, Kreuzvergleich) – ein manipulierter oder ausgefallener Feed darf den Bot höchstens vorsichtiger machen, nie mutiger.

## 7. Minimal-Ausbau für den Einstieg

Wer nicht alles auf einmal baut, nimmt diese Reihenfolge – jede Stufe ist allein schon PnL-relevant:

1. K.-o.-Regeln 1–5 + 8 (nur RPC + lokaler Index) → blockt die schlimmsten Fälle.
2. RugCheck-/GoPlus-Anbindung (Stufe 2) → breite Abdeckung geschenkt.
3. Launch-Archiv aufbauen (ALLE Launches + Outcomes) → die Daten-Grundlage für alles Weitere.
4. Wash- und Bundle-Basistests (5.1/5.2 in einfacher Form).
5. Erst jetzt ML: Gradient-Boosting-Klassifikator auf dem eigenen Archiv, Schatten-Modus, dann live.
