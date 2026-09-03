# Risiko- & Scam-Checks für Memecoins

> Zweck: Checkliste/Wissensbasis für automatisierte Sicherheits-Checks im Bot. Stand des Wissens: Anfang 2026. Kein Check garantiert Sicherheit – Memecoins sind auch ohne Scam hochriskant.

## Die wichtigsten Scam-Typen

| Scam | Mechanik | Erkennung |
|---|---|---|
| **Rug Pull (LP-Abzug)** | Dev zieht die Liquidität aus dem Pool → Preis ≈ 0 | LP-Token geburnt/gelockt? (Launchpad-Graduations burnen die LP automatisch) |
| **Soft Rug / Slow Rug** | Dev/Insider verkaufen Bestände langsam in die Nachfrage | Dev-Wallet & verbundene Wallets tracken; stetige Outflows bei stagnierendem Preis |
| **Honeypot** | Contract erlaubt Kaufen, aber nicht Verkaufen (EVM-typisch) | Kauf+Verkauf simulieren (Honeypot.is, GoPlus); auf Bonding Curves kein Thema |
| **Mint-Exploit** | Dev kann Supply nachminten und dumpen | Mint-Authority muss revoked sein (Solana) / kein mint() für Owner (EVM) |
| **Freeze/Blacklist** | Wallets werden am Verkauf gehindert | Freeze-Authority revoked? (Solana); Blacklist-/Pause-Funktionen im EVM-Contract? |
| **Tax-Scam** | Verkaufssteuer wird nachträglich auf z. B. 99 % gesetzt | Sind Taxes veränderbar? Owner renounced? (EVM) |
| **Bundling / Insider-Launch** | Dev kauft beim Launch mit vielen Wallets, täuscht Verteilung vor | Bundle-Analyse (GMGN, Bubblemaps): gemeinsame Funding-Quelle, Käufe im selben Block |
| **Fake-Token / Impersonation** | Kopie eines bekannten Coins/Tickers mit anderer Adresse | Nur per Mint-/Contract-Adresse identifizieren, gegen CoinGecko/Jupiter-Strict-List abgleichen |
| **Wash Trading / Fake Volume** | Bots erzeugen Volumen & Trending-Platzierung | Volumen vs. einzigartige Wallets; viele Trades gleicher Größe/Frequenz |
| **KOL-Pump & Dump** | Influencer callen gegen Bezahlung vorab gekaufte Coins | Wallet des KOL-Umfelds prüfen; "call" nach bereits gelaufenem Chart = Exit-Liquidität |
| **CEX-Listing-Fakes** | Gefälschte Listing-Ankündigungen | Nur offizielle Exchange-Kanäle als Quelle akzeptieren |

## Automatisierbare Checkliste (Pre-Trade)

### Solana

1. **Mint-Authority == null** und **Freeze-Authority == null** (RPC: `getAccountInfo` auf den Mint).
2. **LP-Status**: Pool von Launchpad-Graduation (LP geburnt) oder LP-Lock nachweisbar?
3. **Holder-Verteilung**: Top-10-Holder (ohne LP-, Burn- und CEX-Adressen) < ~25–30 % des Supplys.
4. **Bundle-Check**: Wurden >N Wallets im Launch-Block aus derselben Quelle gefundet? (RugCheck-/GMGN-API)
5. **Dev-Historie**: Hat die Creator-Wallet frühere Rugs? (RugCheck "creator history")
6. **Liquidität absolut**: z. B. min. 10–20k USD, und MC/Liquidity-Ratio nicht absurd (>30 = Warnung).
7. **Token-Alter & Kurvenstand**: frisch gelauncht + noch auf der Curve = maximales Risiko-Segment.
8. **Metadaten**: Socials vorhanden? Kopierte Bilder/Namen bekannter Coins? (Impersonation-Flag)

### EVM (Ethereum/Base/BNB)

1. **GoPlus-/Honeypot-Check**: is_honeypot, buy/sell_tax, cannot_sell_all, transfer_pausable, is_blacklisted.
2. **Ownership renounced** oder Owner-Funktionen (setTax, blacklist, mint, pause) vorhanden?
3. **Verified Source Code** auf dem Explorer? Proxy-Contract (upgradebar = Risiko)?
4. **LP-Lock/Burn** prüfen (Unicrypt, Team.Finance o. ä.).
5. **Simulation**: Test-Buy + Test-Sell via eth_call/Tenderly vor echtem Einstieg.

## Verhaltens-Red-Flags (Laufzeit-Monitoring)

- Dev-/Insider-Wallets transferieren Token auf frische Wallets oder CEX-Deposits.
- Liquidität sinkt schleichend (LP-Withdrawals bei nicht geburnter LP).
- Trending-Platzierung ohne organisches Social-Echo (gekauftes Trending/Volumen).
- Plötzlicher Tausch der Socials/Website, Umbenennung des Projekts.
- Airdrops unbekannter Token in die eigene Wallet: nie interagieren (Dust-/Phishing-Angriff).

## Betriebs-/Bot-Sicherheit (eigene Infrastruktur)

- **Private Keys**: nie im Code/Repo; getrennte Hot-Wallet mit begrenztem Kapital für den Bot.
- **Telegram-Bots** (Trojan, BonkBot & Co.) verwalten Keys serverseitig → Totalverlust-Risiko bei Kompromittierung einkalkulieren.
- **Slippage & MEV**: enge Slippage-Limits; auf Solana Priority Fees/Jito-Tips statt blindem Slippage-Erhöhen; Sandwich-Schutz nutzen.
- **Simulieren vor Senden**: Transaktionen erst simulieren (Solana: `simulateTransaction`).
- **Fake-APIs/Phishing**: Nur offizielle Endpoints/Domains; Typosquatting-Domains sind im Memecoin-Umfeld Standard-Angriff.
- **Positionsgrößen**: Memecoin-Positionen als Totalverlust-Budget dimensionieren; >90 % aller Launchpad-Coins gehen gegen 0.

## Faustregeln

- Ticker sind nichts, Adressen sind alles.
- Wenn der Einstieg sich anfühlt wie "zu spät" – ist er es meistens; wenn er sich anfühlt wie "ganz früh" – bist du Exit-Liquidität der Sniper.
- Jeder Check ist umgehbar; Scammer optimieren gegen genau diese Checklisten. Scores (RugCheck & Co.) sind Filter, keine Freigaben.
