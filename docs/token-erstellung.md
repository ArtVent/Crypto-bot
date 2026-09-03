# Token-Erstellung – wie Memecoins technisch entstehen

> Vertiefung zu [`data/token-creation.json`](../data/token-creation.json). Zweck: verstehen, wie Launches gebaut sind, um sie als Trader/Bot **bewerten** zu können – und was einen seriösen von einem extraktiven Launch unterscheidet. Stand des Wissens: Anfang 2026.
>
> **Rechtlicher Rahmen in Kürze:** Einen Token zu erstellen ist in den meisten Ländern legal. Illegal bzw. haftungsträchtig sind die Begleitpraktiken: Täuschung über Verteilung/Absichten, Wash Trading, koordinierte Pumps, unkennzeichnete bezahlte Promotion, und je nach Ausgestaltung Wertpapier-/Prospektpflichten (SEC/BaFin/MiCA). Wer launcht, launcht mit Klarnamen-Risiko gegenüber Regulatoren – Anonymität on-chain ist forensisch brüchig.

## 1. Was ein Token technisch IST

### Solana (SPL)

Ein SPL-Token besteht aus:

- **Mint-Account:** definiert Supply, Decimals und zwei kritische Rechte:
  - `mintAuthority` – darf neue Token erzeugen. **Muss für einen vertrauenswürdigen Memecoin revoked (null) sein.**
  - `freezeAuthority` – darf Token-Accounts einfrieren. **Ebenfalls revoked = Standard.**
- **Metadaten** (Metaplex-Standard): Name, Symbol, Bild/URI. Wichtig: Metadaten können `mutable` sein – ein Token, dessen Name/Bild nachträglich änderbar ist, kann "umlackiert" werden.
- **Token-Accounts** der Halter (Associated Token Accounts).

Erstellung: über CLI/SDKs (`spl-token`, Metaplex) in Minuten möglich; Kosten wenige USD (Rent + Transaktionen). Handelbar wird der Token erst durch einen **Liquiditätspool** (Raydium/Meteora/Orca), den der Ersteller mit eigenem SOL + Token befüllt.

### EVM (ERC-20)

Ein ERC-20 ist ein Smart Contract – und damit beliebig programmierbar. Der Standard definiert nur die Schnittstelle (transfer, approve, balanceOf); alles andere ist Ersteller-Entscheidung:

- Fixe vs. mintbare Supply, Owner-Rechte, Taxes, Blacklists, Pausierbarkeit, Upgradebarkeit (Proxy).
- Seriöser Standard: auditierter Basis-Code (z. B. OpenZeppelin), **fixe Supply, keine Owner-Sonderrechte, Ownership renounced, Code auf dem Explorer verifiziert**.
- Handelbar durch einen Uniswap-/PancakeSwap-Pool; die LP-Token des Pools gehören dem Ersteller, bis er sie **burnt oder lockt** – der zentrale Vertrauenspunkt jedes manuellen EVM-Launches.

### Launchpads (pump.fun-Modell)

Launchpads nehmen dem Ersteller fast alle Entscheidungen ab – und Käufern damit fast alle *Contract*-Risiken:

- Supply fix (1 Mrd.), Authorities revoked, Bonding Curve statt manuellem Pool, automatische Migration + LP-Burn bei Graduation.
- Übrig bleibt als Risikofläche: **Verteilung** (Dev-Buy, Bundles), **Verhalten** (Dump, Abandonment) und **Identität** (wer steckt dahinter?).
- Deshalb gilt für Bots: Bei Launchpad-Token Distribution-Analyse priorisieren, bei manuellen Deploys Contract-Analyse (siehe [`risiko-und-scam-checks.md`](risiko-und-scam-checks.md)).

## 2. Anatomie eines Launches (was alles VOR dem ersten Trade passiert)

Ein typischer geplanter Launch (nicht Stealth) hat diese Bausteine – jede Zeile ist ein Prüfpunkt für Außenstehende:

1. **Konzept/Meme:** Name, Ticker, Bild. Prüfpunkt: IP-Risiko (CHILLGUY-Copyright-Fall), Verwechselbarkeit, Meta-Fit.
2. **Supply-Plan:** Wer bekommt was? Fair Launch (100 % Curve/Pool) vs. Allokationen (Team, 'Marketing', Airdrop). Prüfpunkt: Jede Allokation ist potenzieller Verkaufsdruck; Vesting nur so gut wie seine On-Chain-Durchsetzung.
3. **Liquiditäts-Plan:** Wie viel Startliquidität, wer stellt sie, was passiert mit den LP-Token? Prüfpunkt: Burn/Lock-Nachweis; einseitige Liquiditätskonstruktionen (LIBRA-Muster) sind ein Alarmzeichen.
4. **Deploy:** Launchpad oder manuell (siehe oben).
5. **Distribution/Marketing:** Socials, KOL-Deals, Listings (DEX-Screener-Profil, CoinGecko-Antrag). Prüfpunkt: Bezahlte Promotion ohne Kennzeichnung ist in vielen Ländern illegal und ein Charakter-Signal.
6. **Launch-Moment:** Stealth vs. angekündigt. Angekündigte Launches werden gesnipet; deshalb kaufen manche Teams selbst im ersten Block mit ("Dev-Buy") – moderat ist das Selbstschutz, exzessiv ist es ein Bundle.

## 3. Woran man einen seriös aufgesetzten Launch erkennt

Checkliste aus Käufer-/Bot-Sicht – je mehr Punkte erfüllt, desto geringer das *strukturelle* Risiko (über den Preis sagt das nichts):

- [ ] Mint- und Freeze-Authority revoked (Solana) / keine Owner-Sonderrechte, renounced (EVM)
- [ ] Metadaten immutable; Contract-Code verifiziert (EVM)
- [ ] LP geburnt oder langfristig gelockt, Nachweis on-chain verlinkt
- [ ] Supply-Verteilung offengelegt und on-chain nachvollziehbar; Team-Anteile mit echtem (contract-enforced) Vesting
- [ ] Kein signifikantes Launch-Bundling (Cluster-Analyse unauffällig)
- [ ] Dev-Wallet-Historie sauber (keine Serien-Rugs unter derselben Funding-Quelle)
- [ ] Socials älter als der Coin; Team erreichbar; keine gekauften Follower-Kulissen
- [ ] Keine Presale-/Vorkasse-Konstruktion ohne Escrow
- [ ] Promotion gekennzeichnet; keine Fake-Partnerschafts-Claims

## 4. Ökonomie eines Launches (warum 99 % scheitern)

- **Angebots-Flut:** Zehntausende Launches pro Tag konkurrieren um ein endliches Aufmerksamkeits-Budget. Der Median-Launch bekommt nie mehr als eine Handvoll Käufer.
- **Reflexivität rückwärts:** Ohne frühe Käufer keine Kurve, ohne Kurve kein Chart, ohne Chart keine Käufer.
- **Graduation als Filter:** Nur grob ~1 % der pump.fun-Launches erreichen den DEX; von denen stirbt wiederum die Mehrheit in der ersten Woche.
- **Creator-Fee-Ära (seit 2025):** Fee-Sharing gibt Erstellern erstmals einen Anreiz, Coins zu *pflegen* statt zu ruggen – strukturell die wichtigste Anreiz-Änderung seit Launchpad-Erfindung. Für die Bewertung heißt das: Creator mit laufenden Fee-Einnahmen und Reputation verhalten sich messbar anders als Wegwerf-Wallets.
- **Der ehrliche Kern:** Ein Memecoin "gelingt", wenn er zum Schelling-Punkt einer Community wird. Das ist Kultur-Arbeit über Monate (BONK, WIF, SPX) – nicht Deploy-Technik.

## 5. Warnhinweise für eigene Experimente

Wer selbst (z. B. zu Lernzwecken auf Devnet/Testnet) Token deployt:

- **Devnet/Testnet zuerst:** Alle Mechaniken (Mint, Authorities, Pools) lassen sich ohne echtes Geld auf Solana-Devnet bzw. EVM-Testnets durchspielen – für Bot-Tests ohnehin der richtige Ort.
- **Mainnet-Launch = öffentliches Handeln mit echten Gegenparteien:** Ab dem ersten echten Käufer trägt man Verantwortung (und Haftungsrisiken) gegenüber realen Menschen. "Nur ein Test" existiert auf Mainnet nicht.
- **Steuern/Compliance:** Fee-Einnahmen und Trading-Gewinne sind steuerpflichtig; je nach Land können Registrierungs-/Prospektpflichten greifen (EU: MiCA).
