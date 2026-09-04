# Verlierer-Coins aussortieren: Deep Research + ehrliches Urteil

Auftrag: den Bot so erweitern, dass er Verlierer-Coins anhand einer
„abgleichenden Datenbank" bewertet und gar nicht erst kauft. Bedingung des
Nutzers: **nur wenn das Sinn macht.** Dieses Dokument hält das Ergebnis von
zwei Deep-Research-Pässen und einem Validierungsversuch fest.

## Kurzurteil

**Die wörtliche Idee — eine Reputations-/Blacklist-Datenbank von Erstellern
oder Coins, gegen die neue Launches abgeglichen werden — trägt auf pump.fun
kaum.** Grund (beide Recherchen unabhängig, plus Basisraten): Serien-Rugger
nehmen **pro Coin eine frische Wallet**, sodass „frühere Launches dieser
Wallet" fast immer 0 ist. Eine Deployer-Adress-Blacklist läuft damit ins
Leere. Wir **bauen sie daher nicht** als Rendite-Filter.

Was stattdessen dem eigentlichen Ziel dient (keine Verlierer kaufen) und
kausal, kostenlos und validierbar ist: den **einzigen realen
Pre-Graduation-Rug-Mechanismus** direkt im Trade-Verlauf erkennen — Insider/
Sniper aus Block 0/1 akkumulieren billig und dumpen auf die Nachzügler.
Dafür wurde ein neues Gate gebaut (`early_seller_share`) und als A/B-Arm
validiert (siehe unten).

## Warum die Reputations-DB nicht trägt (Belege)

- **Basisrate.** ~98,7 % aller pump.fun-Token sind P&D/Rug; Graduation-Rate
  0,2–1,4 % (fallend). „Verlierer" ist der Default – der Bot sucht die
  seltene Ausnahme, nicht „kein Rug".
- **Prädiktive Obergrenze moderat.** Größte Studie („Catching the Rug",
  6,4 Mio. Token): reine Trade-Features der ersten 5 Minuten erreichen
  MCC ≈ 0,36–0,39 – realer, aber begrenzter Edge; Einzel-Features selten
  AUC > 0,7.
- **Contract-Security-Checks sind pre-graduation wertlos.** Mint-/
  Freeze-Authority sind bei pump.fun standardmäßig revoked, LP ist
  protokoll-verwaltet. Honeypot/LP-Lock/Transfer-Tax-Checks (RugCheck/GoPlus-
  Kern) diskriminieren hier nicht.
- **Fresh-Wallet-Problem.** Deployer-**Adresse** als Schlüssel ist de facto
  wertlos; nur **Funding-Cluster** (wer finanziert die Deployer) trägt Signal
  – der braucht aber pro-Wallet-RPC-Funding-Lookups (Latenz), ist
  verschleiert (Multi-Hop/Mixer) und mit unseren Daten nicht validierbar.
- **Validierung nicht möglich mit vorhandenen Daten.** MELT (unser einziger
  gelabelter Datensatz mit Ersteller-Feld) trägt in `creator` für **alle**
  46.139 Coins **dieselbe** Platzhalter-Adresse – echte Ersteller-Identität
  fehlt. Eine Reputations-DB ließe sich damit weder seeden noch ehrlich
  prüfen. Ohne Validierbarkeit bauen wir sie nicht.

## Was tatsächlich trägt (umgesetzt)

Neues Gate **Insider-Exit** (`curve.early_seller_share`, `strategy.
max_early_seller_share`): Anteil der frühesten K Käufer, die bereits wieder
verkauft haben. Verkaufen die Block-0/1-Käufer schon, kauft man in ihren
Dump. Kausal (nur bisher gesehene Trades), aus dem reinen Log-Strom, nicht
gamebar über frische Wallets (es misst Verhalten, nicht Identität).
Default AUS – wird nur nach A/B-Beleg Default.

**A/B-Ergebnis (historischer Tag):** _läuft – wird nach Abschluss ergänzt._

Weitere bereits vorhandene, evidenzkonforme Gates (Deep Research bestätigt
sie als richtig): Burst-Buyer-Anteil (Bundle), Kaufgrößen-CV (Bot-
Uniformität), Top-3-Käufer-Konzentration, Wash/Roundtrip, Dev-Buy-Band,
Sell/Buy-Verhältnis. Der bestehende ML-Metadaten-Filter (Socials, Namen-
Entropie, Timing) bleibt als schwaches Zusatzsignal.

## Frei nutzbare Datenquellen für eine ECHTE Reputations-DB (Zukunft)

Falls wir später eine belastbare Bad-Actor-DB bauen wollen, braucht es
echte, gelabelte Solana-Deployer-Daten. Frei gefunden:

| Quelle | Lizenz | Inhalt |
|---|---|---|
| SolRPDS (github.com/DeFiLabX/SolRPDS) | CC BY 4.0 | 22.195 Rug-Tokens, Deployer/LP-Aktivität 2021–2024 |
| MemeChain (zenodo 18246856) | CC BY 4.0 | 34.988 Meme-Coins, Metadaten + Logos (Fingerprinting) |
| crypto-wallet-address-labels | MIT | 210k+ Multichain-Labels inkl. Scam |
| Dune Pumpfun Deployer Records | frei (Queries) | Self-Buys/Sniper/Deployer-PnL selbst berechnen |

Der tragfähige Kern wäre **Funding-Cluster-Reputation** + **Metadaten-/
URI-Fingerprinting** (nicht Deployer-Adresse), mit Hub-Allowlist (CEX/Bridge
ausschließen), Wilson-/Bayes-Prior gegen „1 Launch → 100 % Rug", Zeit-Decay
und strikt point-in-time (nur Fakten mit slot < Kaufslot). Das ist ein
eigenes, größeres Projekt und lohnt erst mit echten Labels – nicht jetzt.

## Quellen

- Catching the Rug — arxiv.org/abs/2608.20271
- MemeTrans — arxiv.org/abs/2602.13480
- LROO (leakage-resistant) — arxiv.org/abs/2603.11324
- Survival Analysis 832k Launches — arxiv.org/abs/2607.02823
- Serial Scammers / Attack of the Clones — arxiv.org/abs/2412.10993
- Pine Analytics (Block-0-Sniper) — chaincatcher.com/en/article/2185070
- RugCheck-Methodik, Bubblemaps Bundle-vs-Cluster, GoPlus AML (Zusatzdienste)
