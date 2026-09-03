# Memecoin-Trading-Strategien – Leitfaden

> Vertiefung zu [`data/strategies.json`](../data/strategies.json). Stand des Wissens: Anfang 2026. **Keine Finanzberatung.** Grundannahme dieses Dokuments: Der Memecoin-Markt ist ein Minus-Summen-Spiel nach Gebühren, in dem Insider, Sniper und Plattformen strukturell verdienen – ein Edge muss diese Gegenwind-Rechnung explizit schlagen, sonst existiert er nicht.

## 1. Marktstruktur verstehen (wer verdient hier eigentlich?)

Bevor man eine Strategie wählt, sollte klar sein, gegen wen man spielt:

1. **Plattformen** verdienen immer (pump.fun & Co.: Fees auf jeden Trade).
2. **Insider/Bundler** verdienen an der Informations- und Zeit-Asymmetrie des Launches.
3. **Sniper-Bots** verdienen an der Latenz-Asymmetrie der ersten Sekunden.
4. **KOLs** verdienen an der Aufmerksamkeits-Asymmetrie (sie senden, du empfängst).
5. **Retail** liefert netto die Verluste, aus denen 1–4 bezahlt werden.

Jede Strategie ist der Versuch, temporär aus Gruppe 5 in eine der Gruppen 2–4 zu wechseln – mit legalen Mitteln: Geschwindigkeit, Datenanalyse, Disziplin. Alles, was auf Täuschung basiert (Wash Trading, Bundling, koordinierte Pumps), ist Marktmanipulation, in vielen Jurisdiktionen strafbar und hier ausschließlich als Gegner-Verhalten dokumentiert (siehe [`data/scams.json`](../data/scams.json)).

## 2. Die vier Edge-Quellen

| Edge | Beispiele | Haltbarkeit |
|---|---|---|
| **Geschwindigkeit** | Launch-Sniping, News-zu-Token, Announcement-Trading | Kurz – Wettrüsten, Edge erodiert monatlich |
| **Information/Analyse** | Bundle-Erkennung, Smart-Money-Qualität, Wash-Filter | Mittel – solange die Analyse besser ist als der Durchschnitt |
| **Struktur/Mechanik** | Graduation-Muster, Funding-Harvesting, LP-Fees, Listing-Muster | Mittel – bekannte Muster werden gefadet, Mechanik bleibt |
| **Disziplin/Risiko** | Position Sizing, Exit-Regeln, Meta-Stop | Lang – der einzige Edge, der nicht wegarbitriert wird |

Faustregel: Ein Bot ohne Geschwindigkeits-Edge sollte gar nicht erst in den ersten 60 Sekunden eines Launches handeln.

## 3. Strategie-Familien im Detail

### 3.1 Lifecycle-Trading (das pump.fun-Spielbrett)

Der Launchpad-Lebenszyklus hat vier handelbare Phasen (Mechanik: [`pumpfun-mechanik.md`](pumpfun-mechanik.md)):

```
Launch ──► Curve-Phase ──► Graduation ──► DEX-Phase
  │             │               │              │
  Sniping   Momentum auf     Graduation-   Post-Grad-Dip,
  (Sek.)    der Kurve        Snipe         Trend/CTO
```

- **Phase 1 (Sekunden 0–60):** Reine Latenz-Arena. Ohne Co-located Infrastruktur, eigene RPC-Nodes und Jito-Bundles ist man hier Exit-Liquidität. Realistischer Ansatz für die meisten: diese Phase **auslassen**.
- **Phase 2 (Curve-Momentum):** Hier beginnt Analyse zu schlagen: Holder-Wachstumsrate, Käufer-Qualität (Wallet-Alter, Funding-Herkunft), Social-Echo. Ziel: Coins finden, die die Kurve *durchlaufen*, nicht nur anlaufen.
- **Phase 3 (Graduation):** Binäres Event mit bekanntem Muster – Pump in die Graduation, Dump danach. Weil es bekannt ist, wird es gefadet; die Kante liegt im Erkennen, *welche* Graduations organisch getragen sind (echte Holder vs. Bundle-Kulisse).
- **Phase 4 (DEX):** Ab hier gelten "normale" Trading-Regeln: Struktur, Volumen, Holder-Trends. Der Post-Graduation-Flush (Sniper raus) ist der erste sinnvolle Einstieg für alle ohne Speed-Edge.

### 3.2 Flow-Following (Smart Money & KOLs)

Kernidee: Nicht den Coin analysieren, sondern die Käufer. Praktische Regeln:

- **Konfluenz schlägt Einzelsignal:** 3+ unabhängige Qualitäts-Wallets im selben Coin innerhalb kurzer Zeit ist ein deutlich besseres Signal als eine Star-Wallet.
- **Unabhängigkeit prüfen:** Wallets mit gemeinsamer Funding-Quelle sind EIN Akteur, keine Konfluenz (Bundle-Falle).
- **Rollierende Bewertung:** Wallet-Performance über die letzten N Trades bewerten, nicht Lifetime-PnL (Lucky Runner erkennen; Baiting-Wallets fliegen so automatisch raus).
- **Exit gehört zum Copy:** Wer Einstiege kopiert, aber Ausstiege verschläft, kopiert nur die Bags.

### 3.3 Rotation & Meta-Trading

Metas ([`data/metas.json`](../data/metas.json)) sind das Sektoren-Modell des Memecoin-Markts. Messbare Rotations-Indikatoren:

- **Launch-Anteil pro Meta:** Anteil neuer Launchpad-Token je Kategorie (Keyword-Klassifikation der Namen/Metadaten). Steigender Anteil = Meta zieht Erstellter an = Frühindikator.
- **Graduation-Quote pro Meta:** Welche Kategorie graduiert überdurchschnittlich? = Dort ist echtes Kaufinteresse.
- **Leader-Relativstärke:** Halten die 2–3 größten Coins der Meta ihre Hochs besser als der Gesamtmarkt?
- **Erschöpfungssignal:** Wenn die x-te Kopie des Meta-Leaders noch graduiert, ist die Meta meist im letzten Drittel.

### 3.4 Event-Trading

Wiederkehrende Event-Typen mit historischen Mustern (Beispiele in [`data/events.json`](../data/events.json)):

| Event-Typ | Typisches Muster | Fallstrick |
|---|---|---|
| CEX-Listing-Announcement | Spike auf Announcement, Abverkauf zum Handelsstart | Nur offizielle Feeds; Fakes |
| Virales Real-Life-Ereignis | Dutzende Klone, einer gewinnt; Stunden-Fenster | Den 'Winner' zu früh küren |
| Promi-Post/Launch | Sofort-Pump, Insider-Exit, oft -90 % in Tagen | Gehackte Accounts, Vesting-Lügen |
| Plattform-Events (ICO, neue Features) | Ökosystem-Coins profitieren mit | Sell the News |
| Makro-Schock | Memecoins fallen zuerst und am tiefsten | 'Dip kaufen' ohne Boden-Beweis |

### 3.5 Nicht-direktionale Ansätze (der ruhigere Weg)

Für Bots oft attraktiver als Richtungswetten, weil backtestbarer:

- **LP auf Meme-Paaren:** Fee-APR vs. Impermanent Loss; funktioniert in Seitwärts-Hype (hohes Volumen, kein Trend), stirbt im Kollaps. Range-Management ist der eigentliche Job.
- **Funding-Harvesting:** Spot long + Perp short auf gehypte Memes, kassiert überhitztes Funding. Risiken: Squeeze auf der Short-Seite, Funding-Flip.
- **Arbitrage:** Cross-Venue-Spreads sind real, aber die Konkurrenz ist professionell; ohne Top-Infrastruktur bleiben nur die Reste.

## 4. Risiko-Framework (der eigentliche Edge)

### Position Sizing

- **Totalverlust-Prämisse:** Jede Micro-Cap-Position kann auf 0 gehen – Positionsgröße = Betrag, dessen Totalverlust egal ist. Praxis-Anker: 0,25–1 % des Trading-Kapitals pro Trench-Trade, wenige Prozent für etablierte Memes.
- **Kelly mit Bremse:** Selbst wenn man Trefferquote/Payoff schätzt: maximal Fraktions-Kelly (¼) fahren – die Schätzfehler in diesem Markt sind riesig.
- **Korrelations-Deckel:** 10 Meme-Positionen sind im Crash EINE Position. Gesamt-Exposure gegen das Meme-Beta begrenzen, nicht nur je Coin.

### Exits

- **Vor dem Entry definiert**, mechanisch ausgeführt – in illiquiden Coins existiert "ich schau dann mal" nicht.
- **Gestaffelte Take-Profits** (z. B. Einsatz raus bei 2x, Rest in Tranchen) schlagen Alles-oder-nichts psychologisch und praktisch.
- **Stop-Loss-Realität:** In illiquiden Pools sind Stops Slippage-Maschinen; Alternative: Positionsgröße als impliziter Stop + Zeit-Stops (Exit nach N Stunden ohne These-Bestätigung).
- **These-Stop:** Der Grund des Einstiegs (Meta läuft, Wallet X drin, Event frisch) ist weg → Position ist weg, egal wo der Preis steht.

### Meta-Regeln fürs System

- **Kill-Switch:** Tages-/Wochen-Verlustlimit, das den Bot hart stoppt.
- **Regime-Filter:** In Makro-Risk-off (BTC/SOL-Trend gebrochen) Neueinstiege aussetzen – Memecoins haben dann negative Erwartungswerte quer durch alle Strategien.
- **Kapazitäts-Ehrlichkeit:** Strategien, die mit 1k USD funktionieren, sterben oft bei 50k (eigener Market Impact in Micro-Caps).

## 5. Backtesting- und Auswertungs-Fallen

- **Survivorship Bias:** Wer nur graduierte/gelistete Coins in der Historie hat, testet auf den 1 % Gewinnern. Der Datensatz braucht die toten 99 %.
- **Fill-Illusion:** Historische Preise ≠ erzielbare Fills. Slippage, Priority Fees und MEV müssen modelliert werden – beim Sniping entscheidet der Block, nicht der Minutenchart.
- **Look-Ahead über Social-Daten:** "Coin war auf TikTok viral" ist rückblickend leicht, in Echtzeit schwer – Signale nur mit Timestamp der tatsächlichen Verfügbarkeit testen.
- **Metriken:** Statt nur PnL: Trefferquote, Payoff-Ratio, Max Drawdown, PnL nach Fees/Slippage, PnL pro Strategie-Familie getrennt. Eine profitable Familie subventioniert sonst unbemerkt drei defizitäre.
- **Out-of-Sample-Pflicht:** Der Markt von 2024 ist nicht der von 2026 – Strategien auf Zeiträumen validieren, die sie nicht gesehen haben, und live erst mit Minimalgröße.

## 6. Zuordnung Strategie ↔ Bot-Ausbaustufe

| Ausbaustufe | Realistisch handelbar |
|---|---|
| Stufe 1: Polling-Bot (DEX-Screener-API, Minuten-Takt) | Blue-Chip-Dips, DCA/Grid, Meta-Rotation, Listing-Reaktion |
| Stufe 2: Websocket-Bot (Echtzeit-Streams, Sekunden) | Trending-Momentum, Copy-Trading, Graduation-Trading, Post-Grad-Dip |
| Stufe 3: Infrastruktur-Bot (eigene RPCs, Jito, <1 s) | Launch-Sniping, Arbitrage, Event-Latenz-Spiele |

Details zur technischen Umsetzung: [`bot-architektur.md`](bot-architektur.md).
