# KI & Memecoins – wie AI sniped, analysiert und Geld verdient

> Vertiefung zu [`data/ai-techniques.json`](../data/ai-techniques.json) und [`data/ai-agents.json`](../data/ai-agents.json). Stand des Wissens: Anfang 2026. Keine Finanzberatung. Manipulationstechniken werden hier ausschließlich zur Erkennung/Verteidigung beschrieben.

## 0. Die ehrliche Vorbemerkung

"AI sniped Memecoins und wird reich" ist zu 80 % Marketing-Mythos und zu 20 % Realität – und die 20 % sehen anders aus, als die Werbung suggeriert:

- **Sniping-Gewinne kommen primär aus Latenz und Infrastruktur**, nicht aus Intelligenz. Der "AI"-Anteil erfolgreicher Sniper ist meist ein Filter-Modell, das entscheidet, *welche* Launches man NICHT kauft.
- **Die verlässlichsten KI-Gewinner sind Plattformen und Infrastruktur-Agenten** (Fees pro Trade/Launch), nicht Trading-Agenten.
- **Die spektakulärsten "KI verdient Millionen"-Storys** (Truth Terminal/GOAT) liefen über Kultur und geschenkte Token – nicht über überlegenes Trading.

Wer das versteht, kann die echten Ansatzpunkte nutzen, statt "AI-Bots" zu kaufen, die vor allem für ihre Betreiber verdienen.

## 1. Die vier Rollen von KI im Memecoin-Markt

```
1. KI als TRADER      Sniper-Filter, Scoring, Sentiment, Execution   → dieser Bot
2. KI als AKTEUR      Agenten mit Publikum/Token (AIXBT, ToT)        → bewegen Märkte selbst
3. KI als INFRA       Deploy-/Analyse-Agenten (Clanker, Terminals)   → Fee-Geschäft
4. KI als WAFFE       Bot-Schwärme, Fake-Engagement, Köder           → Gegner-Wissen
```

## 2. Anatomie eines KI-Snipers (wie das technisch wirklich läuft)

Ein moderner Solana-Sniper ist eine Pipeline mit hartem Latenz-Budget – KI sitzt an genau einer Stelle:

```
┌──────────────┐   ~50–200 ms    ┌──────────────┐    ~10–100 ms   ┌──────────────┐
│ EVENT        │ ──────────────► │ SCORING      │ ──────────────► │ EXECUTION    │
│ Create-Event │                 │ (hier ist    │                 │ Tx bauen,    │
│ via Geyser/  │                 │ die "AI")    │                 │ Jito-Bundle, │
│ Websocket    │                 │ Filter+Score │                 │ landen       │
└──────────────┘                 └──────────────┘                 └──────────────┘
        gesamt: unter ~1 Sekunde vom Launch bis zur gelandeten Transaktion
```

**Schritt 1 – Event:** Der Bot abonniert Token-Erstellungen direkt am Programm (Geyser-Stream, PumpPortal-Websocket). Wer hier über Polling-APIs geht, hat schon verloren.

**Schritt 2 – Scoring (der KI-Kern):** In wenigen Millisekunden entscheidet ein Modell über Kauf/Skip. Realistische Feature-Menge zum Launch-Zeitpunkt:

| Feature-Gruppe | Beispiele | Warum prädiktiv |
|---|---|---|
| Creator | Wallet-Alter, Funding-Quelle, frühere Launches + deren Ausgang | Serien-Rugger sind Wiederholungstäter |
| Launch-Setup | Dev-Buy-Größe (absolut/relativ), Begleit-Käufe im selben Block | Bundle-Signatur = Dump-Setup |
| Metadaten | Namens-/Bild-Duplikate, Socials-Alter, Ticker-Kollisionen | Impersonation & Fließband-Launches |
| Kontext | Aktuelle Meta des Namens, Tageszeit, Launch-Frequenz der letzten Stunde | Meta-Fit und Markt-Sättigung |

Das Modell dahinter ist typischerweise **Gradient Boosting (XGBoost/LightGBM)** – nicht Deep Learning: tabellarische Features, kleine Latenz, ständiges Retraining. Ausgabe: Score + harte K.-o.-Flags.

**Schritt 3 – Execution:** Vorgebaute Transaktion, dynamischer Tip, Jito-Bundle. Hier entscheidet Infrastruktur (eigene Nodes, Standort), nicht KI.

**Wo das Geld herkommt:** Die Basisrate handelbarer Launches liegt bei ~1 %. Ein Sniper ohne Filter kauft 100 Launches, davon 99 Schrott – Totalverlust trotz Speed. Ein Filter, der die Trefferquote von 1 % auf 5–10 % hebt, dreht das Vorzeichen des Systems. **Der Erwartungswert wird im Scoring verdient, im Event-Layer nur nicht verloren.** Deshalb ist "AI-Sniping" präziser: *ML-gefiltertes* Sniping.

## 3. Wo ML nachweislich Geld verdient (Ranking nach Realitätsgehalt)

1. **Verlust-Vermeidung durch Klassifikation** (Rug-Score, Bundle-Erkennung, Wash-Filter) – der mit Abstand größte, robusteste Effekt. Details: `ai-techniques.json` → filtering/graph.
2. **Execution-Ökonomie** (Fee-/Tip-Optimierung, Landungsraten) – klein pro Trade, groß über Frequenz.
3. **Aufmerksamkeits-Timing** (Sentiment-Velocity, News-zu-Token, Meta-Klassifikation) – echter Edge, aber im am stärksten manipulierten Datenkanal.
4. **Wallet-Intelligence fürs Copy-Trading** (Cluster statt Einzel-Wallets, rollierende Qualität) – funktioniert, bis die Ziel-Wallets es merken.
5. **Kurzfrist-Forecasting** – möglich, aber fragil; Regime-Wechsel fressen Modelle in Wochen.
6. **Autonome LLM-Trader** – Stand heute: Analyse-Skalierung ja, überlegene Entscheidungen nein.

## 4. KI als Markt-Akteur: Wie Agenten selbst Geld verdienen

Die AI-Agent-Meta (seit Oktober 2024, siehe [`data/metas.json`](../data/metas.json)) hat eigene Geschäftsmodelle hervorgebracht – sortiert nach Verlässlichkeit:

### 4.1 Fee-Infrastruktur (verlässlich)
**Clanker-Modell:** Der Agent deployt Token und kassiert dauerhaft einen Anteil der Pool-Fees jedes Tokens – richtungsunabhängig, skalierend mit Volumen. Millionen-Einnahmen binnen Monaten. Das ist das Launchpad-Geschäft in Agenten-Form; **Virtuals** hebt es auf Plattform-Ebene (Fee-Anteil an jedem Agenten-Token).

### 4.2 Der KI-KOL (skalierbar, reflexiv)
**AIXBT-Modell:** Content-Maschine mit Publikum + eigener Token + gated Zugang für Halter. Die Erwähnungen des Agenten bewegen Kurse, was das Publikum vergrößert, was den Token stützt. Monetarisierung: Token-Anteile des Betreiber-Umfelds, Fee-Beteiligungen, Zugangs-Gating.

### 4.3 Der Kultur-Agent (Lotterie)
**Truth-Terminal-Modell:** Agent erzeugt Mythologie → Community erstellt Token und *schenkt* sie dem Agenten → Wallet des Agenten wird durch Kurssteigerung Millionen wert. Nicht planbar, aber prägend: Es etablierte "der Agent hält eigenes Vermögen" als Legitimitäts-Signal.

### 4.4 Der Agenten-Token als Produkt (Mehrheit, meist wertlos)
Tausende Agenten mit Token, deren "KI" ein Chatbot-Wrapper ist – ökonomisch normale Memecoins mit Tech-Kostüm. Ihre Kurse folgen der Meta, nicht der Fähigkeit. Für die Bewertung gilt daher dieselbe Checkliste wie für jeden Memecoin ([`risiko-und-scam-checks.md`](risiko-und-scam-checks.md)) **plus**: Hat der Agent nachweisbare, laufende Einnahmen (Fees on-chain sichtbar) oder nur Output?

### Handelbare Konsequenzen für den Bot
- **Agent-Erwähnungen als Event-Typ** (AIXBT-Effekt): messbar, aber verfallend – und Ziel von Manipulation (Leute reverse-engineeren, welche Inputs Agenten zitieren).
- **Agent-Wallets als Copy-Kandidaten**: Agenten mit öffentlicher Wallet sind transparente Trader – aber ihre Käufe sind oft selbsterfüllend (Publikum kopiert), was Einstiege nach ihnen strukturell verschlechtert.
- **Fee-Flüsse als Fundamental-Signal**: On-chain sichtbare Einnahmen eines Agenten/einer Plattform sind das einzige "Fundamental-Datum" der Agenten-Token – automatisiert auswertbar.

## 5. Einen eigenen ML-Layer bauen (praktischer Fahrplan)

Aufbauend auf der Architektur in [`bot-architektur.md`](bot-architektur.md):

1. **Daten sammeln, bevor irgendwas modelliert wird:** Alle Launches (nicht nur Gewinner!) mit vollem Feature-Satz zum Launch-Zeitpunkt aufzeichnen + Ausgang nach 1h/24h/7d als Label (tot / gerugt / graduiert / gelaufen). Ohne die toten 99 % ist jedes Modell Survivorship-Müll.
2. **Baseline vor ML:** Erst die regelbasierten K.-o.-Checks (RugCheck-Flags, Bundle-Schwellen) messen. Ein ML-Modell muss DIESE Baseline schlagen, nicht Zufall.
3. **Modell klein halten:** Gradient Boosting auf tabellarischen Features; Metrik: Präzision bei niedriger False-Positive-Rate und **PnL-gewichtete** Evaluation (ein übersehener Runner kostet mehr als zehn korrekt gefilterte Rugs – asymmetrische Kosten einbauen).
4. **Zeitliche Sauberkeit:** Train/Test strikt chronologisch splitten; Features nur aus Daten, die zum Entscheidungszeitpunkt real verfügbar waren (Ingest-Timestamps!).
5. **Drift als Normalzustand:** Wöchentliches Retraining einplanen; Feature-Wichtigkeiten überwachen – wenn ein Feature plötzlich 'kippt', hat die Gegenseite adaptiert.
6. **LLMs gezielt einsetzen:** Meta-Klassifikation, Metadaten-Anreicherung und Social-Zusammenfassungen (billige Modelle für die Masse, große für Kandidaten) – nicht für die Kauf-Entscheidung selbst.
7. **Guardrails in Code, nicht im Prompt:** Positions-Limits, Whitelists, Kill-Switch liegen außerhalb jeder KI-Komponente. Ein LLM darf vorschlagen, nie allein ausführen (Freysa-Lektion: Prompts sind sozial durchbrechbar).

## 6. Angriffe auf KI-Trader (Verteidigungs-Wissen)

Wer KI-Signale nutzt, erbt deren Angriffsfläche – die Gegenseite weiß, wie Bots lesen:

| Angriff | Mechanik | Verteidigung |
|---|---|---|
| **Sentiment-Vergiftung** | Bot-Schwärme/KI-Texte erzeugen 'organisches' Echo für einen Insider-Coin | Bot-Erkennung, Account-Qualität gewichten, Social nie als Allein-Signal |
| **Filter-Reverse-Engineering** | Scammer bauen Launches, die bekannte Scores/Checks exakt bestehen | Eigene (nicht öffentliche) Zusatz-Features; Verhaltens-Monitoring nach Entry |
| **Copy-Baiting** | Ziel-Wallets kaufen sichtbar klein, dumpen über Cluster | Konfluenz unabhängiger Wallets, Cluster-Check des Ziel-Coins |
| **Prompt-Injection** | Köder-Posts/Metadaten enthalten Instruktionen für LLM-Agenten ('ignore previous…', gefälschte 'offizielle' Anweisungen) | LLM-Inputs als Daten behandeln, nie als Befehle; Aktionen nur über Code-Policies |
| **Feed-Manipulation** | Gefälschte API-Antworten/Preise füttern den Bot | Mehrquellen-Kreuzvergleich, Anomalie-Erkennung, Domain-Pinning |
| **Agenten-Impersonation** | Fake-AIXBT-Accounts/-Token, 'offizielle Agent-Coins' | Kanonische Account-/Adress-Whitelists |

## 7. Ökonomie-Übersicht: Wer verdient im 'KI × Memecoin'-Feld wirklich?

| Akteur | Einnahmequelle | Verlässlichkeit |
|---|---|---|
| Launchpads & Agenten-Plattformen | Fees pro Trade/Launch | Sehr hoch – verdienen immer |
| Infrastruktur (RPC, Geyser, APIs) | Abos der Bot-Betreiber | Sehr hoch |
| Deploy-/Infra-Agenten (Clanker-Typ) | Fee-Anteile deployter Token | Hoch |
| Bot-Anbieter (Telegram/Terminals) | Nutzer-Trading-Fees | Hoch – unabhängig vom Nutzer-PnL |
| KI-KOL-Agenten & Betreiber | Token + Zugang + Reichweite | Mittel – reflexiv, Meta-abhängig |
| Professionelle Sniper-Teams | ML-Filter + Latenz + Disziplin | Mittel – realer, erodierender Edge |
| Käufer von 'AI-Bots' & Agent-Token-Retail | – | Netto-Verlierer als Gruppe |

Die Rangfolge ist kein Zufall: **Je näher an der Fee-Quelle und je weiter weg von der Richtungs-Wette, desto verlässlicher das Geschäft.** Für den eigenen Bot heißt das: ML dort einsetzen, wo es Kosten senkt und Verluste vermeidet – das ist der Teil des 'AI-Traums', der reproduzierbar ist.

Wie man aus dieser Erkenntnis legale, ethisch saubere Geschäftsmodelle baut – vom KI-Creator-Studio mit Fee-Einnahmen über Sicherheits-SaaS bis zum Daten-Geschäft – steht ausführlich in [`ai-geschaeftsmodelle.md`](ai-geschaeftsmodelle.md) und [`../data/ai-business-models.json`](../data/ai-business-models.json).
