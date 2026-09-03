# Fee-Ökonomie – wo im Memecoin-Markt an jedem Trade verdient wird

> Vertiefung zu [`data/fee-sources.json`](../data/fee-sources.json). Zahlen web-recherchiert und quellengeprüft im **September 2026** (DefiLlama, offizielle Docs, The Block, CoinDesk, Blockworks u. a.); Fee-Strukturen ändern sich häufig – vor Verwendung in Kalkulationen gegen die offiziellen Docs prüfen. Keine Finanz-/Rechtsberatung.

## 1. Die Fee-Landkarte (wer schneidet an einem Trade mit?)

Ein einziger Kauf eines frisch graduierten pump.fun-Coins berührt bis zu fünf Fee-Empfänger:

```
Trade 1 SOL
 ├─ Launchpad/DEX-Fee (0,30–1,25 % dynamisch)
 │   ├─ Protokoll     (pump.fun)
 │   ├─ Creator       (Coin-Ersteller, in SOL, claimbar)
 │   └─ LPs           (0,20 % konstant)
 ├─ Bot-/Terminal-Fee (0,5–1 % – Trojan, Axiom, PumpPortal …)
 │   └─ davon Referral-Anteile (bis 25–35 % an Werber)
 ├─ ggf. Integrator-Fee (Jupiter-Modell: eigene Fee, 20 % davon an Jupiter)
 ├─ Priority Fee / Jito-Tip (Netzwerk/Validator)
 └─ Netzwerk-Basisgebühr
```

Merksatz aus [`ai-und-memecoins.md`](ai-und-memecoins.md): Alle diese Empfänger verdienen **richtungsunabhängig** – das ist der verlässliche Teil des Marktes.

## 2. pump.fun im Detail: die Fee-Geschichte

| Phase | Curve-Fee | Creator-Anteil | Anmerkung |
|---|---|---|---|
| 2024 – Aug 2025 | 1,00 % | 0 | Alles ans Protokoll; Token-Erstellung seit Aug 2024 kostenlos (Deploy zahlt der Erstkäufer) |
| 12.05.2025 | 1,00 % | +0,05 % des Volumens | "Creator Revenue Sharing" – erstmals verdienen Ersteller laufend mit |
| **02.09.2025 "Project Ascend"** | **1,25 %** | **0,30 % (Curve)** | Dynamic Fees V1; Fee-Splitting auf bis zu 10 Wallets; Ownership-Transfer; 2+ Mio. USD Creator-Auszahlungen in den ersten 24 h |
| 2026 "Cashback Coins" | 1,25 % | wählbar | Deployer kann Creator-Fee unwiderruflich zu 100 % an die Trader umleiten; max. 1 nachträgliche Änderung |

**Graduation:** Curve komplett bei ~**85 SOL** (SOL-denominiert speichern – der USD-Wert "69k" floatet mit dem SOL-Kurs). Seit 20.03.2025 kostenlose Sofort-Migration zu PumpSwap (vorher Raydium + 6 SOL Gebühr).

### PumpSwap-Tier-Tabelle (dynamische Fees seit 02.09.2025)

Gesamt-Fee nach Market Cap (SOL-denominiert); LP konstant 0,20 %, Protokoll 0,05 % (Ausnahme Tier 1):

| Market Cap (SOL) | Gesamt | Creator | LP | Protokoll |
|---|---|---|---|---|
| 0–420 | 1,25 % | 0,30 % | 0,02 % | 0,93 % |
| 420–1.470 | 1,20 % | **0,95 %** | 0,20 % | 0,05 % |
| 1.470–2.460 | 1,15 % | 0,90 % | 0,20 % | 0,05 % |
| 2.460–3.440 | 1,10 % | 0,85 % | 0,20 % | 0,05 % |
| … stufenweise fallend … | | | | |
| ≥ ~98.240 | 0,30 % | 0,05 % | 0,20 % | 0,05 % |

Das Design ist bewusst: **Kleine Coins zahlen ihren Creators am meisten** (0,95 % im Sweet Spot nach Graduation) – der Anreiz, Coins zu pflegen statt zu verlassen. ⚠️ Tier-1-Split nur über Spiegel der offiziellen Tabelle belegt – vor Verwendung gegen pump.fun/docs/fees verifizieren.

**Claim-Mechanik:** Creator-Fees akkumulieren in SOL in einem On-Chain-Vault; Claim jederzeit via UI oder programmatisch (collect-creator-fee-Instruktion); kein Verfall. Verwaiste Coins: CTO-Teams können die Creator-Fee-Rechte per Formular übernehmen – d. h. auch **Community-Übernahmen haben seit 2025 eine Einnahmequelle**.

## 3. Die Konkurrenz-Splits im Vergleich

| Plattform | Trade-Fee | Creator bekommt | Besonderheit |
|---|---|---|---|
| pump.fun/PumpSwap | 0,30–1,25 % | 0,05–0,95 % (dynamisch) | Tier-System, Vault-Claims, Cashback-Option |
| LetsBonk (LaunchLab) | 1 % Curve | bis 0,1 %; "Bonk Classic" 2026: 0 % (0,30 % Fee, Rest in Liquidität) | Revenue-Verwendung mehrfach umgebaut: 50 % BONK-Burn → 35 % Burn + Staking/Marketing → ab Dez 2025: 51 % BNKK-Käufe |
| Bags | 2 % | 1 % Royalty, davon bis 90 % teilbar auf bis zu **100 Empfänger** (per X-/GitHub-/Kick-Handle benennbar) | Der Mechanismus für "Meme-Urheber verdient mit" |
| Zora (ab 15.09.2025) | 1 % | 0,5 % | + 0,2 % Market Contribution (auto-Liquidität), 0,2 % Plattform-Referral, 0,04 % Trade-Referral, 0,05 % Protokoll; Creator Coins vesten 50 % Supply über 5 Jahre |
| Believe (Meteora DBC) | 2 % | anfangs ~50 %, später 70 % der Fees | Peak 6,3 Mio. USD Tagesrevenue (Mai 2025) |
| Virtuals | 1 % | 70 % an Agent-Creator (seit 28.03.2025) | 30 % ans Agent Commerce Protocol |
| Clanker v4 | Pool-Fee konfigurierbar (MEV-Decay: Start bis 80 %!) | 80 % der Rewards (Default), bis 7 Empfänger | Clanker-Protokoll nimmt 20 % der LP-Fees |

Infrastruktur darunter: **Meteora DBC** (Basis von Believe, Bags & Co.) nimmt fix 20 % der Trading-Fee als Protokoll-Anteil; die restlichen 80 % teilen Launchpad-Partner und Creator per Konfiguration. **Anti-Sniper-Fees** sind Standard geworden: Meteora-DAMM-v2-Fee-Scheduler startet bei 50 % und fällt über 120 min auf 0,25 %; Clanker v4 analog mit parabolischem Decay – Sniping in Sekunde 1 wird über die Fee bestraft (relevant fürs eigene Sniping-Modell!).

## 4. Bot-, API- und Referral-Ökonomie

| Dienst | Fee | Referral-Modell |
|---|---|---|
| PumpPortal (Trade-API) | 0,5 %/Trade | – (Daten-Websocket kostenlos) |
| Trojan | 1 % (0,9 % mit Ref) | 25 % der Referee-Fees (35 % ab 10k USD Wochenvolumen) + Multi-Level 3,5/2,5/2/1 % |
| BonkBot | 1 % | 30/20/10 % (Monat 1/2/danach); Teil der Fees in BONK-Buybacks |
| Maestro | 1 % + 200 USD/Monat Premium | 25 % lifetime |
| Photon | 1 % flat | – |
| Axiom | 1 %, via Cashback bis ~0,75 % | 10 % Rabatt-Codes |
| GMGN | 0,75–1 % | mit Codes teils ~0,5 % |
| Jupiter Ultra | 5–10 bps Endnutzer | Integrator-Fees erlaubt; 20 % der Integrator-Fee an Jupiter (Legacy-API: bis 1 % Plattform-Fee, Jupiter behält 2,5 %) |

Zwei legale Verdienst-Schienen stecken hier drin: **(a) selbst Integrator werden** (eigenes Frontend/eigener Bot mit eigener Fee über Jupiter/PumpPortal-Muster) und **(b) Referral-Bäume** (dauerhafte Beteiligung am Volumen geworbener Trader – Trojans 5-Ebenen-Modell ist faktisch ein Affiliate-Geschäft).

## 5. Was ist MONATLICH realistisch? (die ehrliche Zahlenschau)

Recherchierte Ist-Zahlen (Sept 2026), von der Plattform bis zum Einzel-Creator:

| Akteur | Monatliche Größenordnung | Beleg |
|---|---|---|
| pump.fun (Protokoll) | Ø ~80 Mio. USD/Monat 2025 (971 Mio. Jahresumsatz); Spanne: 148 Mio. (Jan 2025) bis 31,8 Mio. (Jan 2026) | DefiLlama, Cointelegraph |
| PumpSwap (Fees gesamt) | ~87 Mio. USD/30 Tage, davon ~16 Mio. Protokoll-Revenue | DefiLlama Sept 2026 |
| LetsBonk | Peak >30 Mio. USD/Monat (Juli 2025); langfristig deutlich darunter (61 Mio. kumuliert über ~17 Monate) | CoinGecko, DefiLlama |
| Clanker (Deploy-Agent!) | Rekordwoche 8 Mio. USD Fees (Feb 2026) → Spitzenmonate ~20–30 Mio.; Ø-Protokoll-Revenue über Laufzeit ~0,7 Mio./Monat | KuCoin News, DefiLlama |
| **Alle pump.fun-Creator zusammen** | ~29 Mio. USD/Monat (>350 Mio. im Jahr bis Mitte 2026) | Yahoo Finance |
| **Top-Einzel-Creator** | Spitzentage 24k–123k USD/TAG (Top-25 nach Ascend-Start); TROLL-Creator kumuliert ~223k USD | CryptoSlate, SolanaFloor |
| **Median-Creator** | **nahe null** – die Verteilung ist extrem schief | CoinGecko-Lifespan-Daten |
| Bags-Creator gesamt | ~4 Mio. USD/Monat (40 Mio. über ~10 Monate) | BusinessWire |
| Bot-Betreiber (BonkBot) | ~0,5 Mio. USD/Monat (6,2 Mio. annualisiert) | DefiLlama |
| Bot-Betreiber (Trojan) | Lifetime ~23 Mrd. USD Volumen × ~1 % ≈ 230 Mio. Fees über ~2,5 Jahre → mehrere Mio./Monat | SolanaCompass |
| Believe (Peak) | 6,3 Mio. USD an EINEM Tag (Mai 2025) – Monate später Bruchteile | The Defiant |
| Sniper-Kollektiv (Studie) | >15.000 SOL Profit/Monat über ~4.600 deployer-nahe Sniper-Wallets → im Schnitt ~3–4 SOL (~500–800 USD)/Wallet – stark konzentriert auf wenige | Pine Analytics Apr 2025 |

**Interpretation für die eigene Planung:**

1. **Plattform-/Infrastruktur-Skala (Mio./Monat)** ist real, aber Winner-take-most – erreichbar als Nischen-Klon (Clanker-Muster: 13 Mio. USD in 5 Monaten mit einem Deploy-Bot), nicht als Nachbau der Marktführer.
2. **Ein einzelnes KI-Creator-Studio** liegt realistisch zwischen **0 und niedrig vierstellig USD/Monat** als Fee-Sockel aus vielen kleinen Coins – mit Lotterie-Upside: EIN viraler Coin im 0,95-%-Tier mit 10 Mio. USD Monatsvolumen zahlt ~95k USD in dem Monat.
3. **Service-/SaaS-Modelle** (Sicherheits-API, Daten-Feeds, Bot-Entwicklung) skalieren wie normale Software: vierstellige MRR realistisch, fünfstellig mit Differenzierung ([`ai-geschaeftsmodelle.md`](ai-geschaeftsmodelle.md)).
4. **Referral-Einkommen** ist proportional zum geworbenen Volumen: 25 % Anteil an 1 % Fee = 2,5 bps des Referee-Volumens – 1 Mio. USD vermitteltes Monatsvolumen ≈ 250 USD/Monat, passiv.
5. **ML-Trading-PnL** hat keine seriöse öffentliche Monatszahl – die Sniper-Studie zeigt: kollektiv profitabel (87 % der Snipes im Plus), aber der Schnitt pro Wallet ist klein und die Gewinne konzentrieren sich auf die schnellste/bestinformierte Spitze.

## 6. Fee-Mathe fürs eigene Modell (Formeln)

- **Creator-Fee-Ertrag:** `Ertrag = Σ über Zeit (Volumen × Creator-Rate(Mcap-Tier))`. Wegen der Tiers ist der Ertrag NICHT linear im Volumen: Ein Coin, der lange im 420–1.470-SOL-Band pendelt, zahlt ~19x mehr pro Volumen-Dollar als einer über 98k SOL (0,95 % vs. 0,05 %).
- **LP-Ertrag (Meme-Pools):** `APR ≈ (Tagesvolumen/TVL) × LP-Fee-Anteil × 365 − IL`. Bei Volumen/TVL > 1 und 0,20 % LP-Anteil sind zweistellige Monats-Fee-Renditen möglich; die IL-Seite entscheidet (siehe Strategien).
- **Bot-Betreiber:** `Umsatz = Nutzer-Volumen × Fee − Infrastruktur`. Bei 1 % Fee ist 1 Mio. USD Tages-Nutzervolumen = 10k USD/Tag – erklärt, warum jedes Terminal um Volumen kämpft und Referral-Bäume so aggressiv sind.
- **Anti-Sniper-Decay einpreisen:** Auf Meteora-DAMM-v2-/Clanker-v4-Launches kostet ein Kauf in Minute 0 bis zu 50–80 % Fee – Sniping-EV-Rechnungen müssen die Fee-Kurve der Ziel-Plattform kennen.

## 7. Bekannte Quellen-Konflikte (im Zweifel neu verifizieren)

- PumpSwap Mai–Sept 2025: "0,05 % Creator on top" vs. "50 % des Protokoll-Revenues" – zwei Framings desselben Streams.
- LetsBonk-Split: Sekundärquellen (40/30/30) vs. offizielle Revenue-Seiten-Historie (maßgeblich).
- BonkBot-BONK-Burn-Anteil: 10 % vs. 20 % vs. "51 % der Q1-2025-Fees" – zeitabhängig, als Spanne führen.
- Meteora-Protokollanteil an LP-Fees: 5–20 % je Pool-Typ/Ära.
- GMGN-/Axiom-Sätze variieren je Tier/Quelle (0,5–1 %).
- pump.fun-Graduation: in SOL (~85) speichern, nicht in USD.
