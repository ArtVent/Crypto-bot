# pump.fun – Mechanik im Detail

> Stand des Wissens: Anfang 2026. Parameter (Fees, Schwellen) wurden von pump.fun mehrfach geändert – vor Bot-Implementierung immer gegen die aktuellen Docs/On-Chain-Programme verifizieren.

## Grundidee

pump.fun (Launch: Januar 2024, Solana) hat Token-Launches radikal standardisiert:

- Jeder erstellt für ein paar Cent einen SPL-Token mit **1 Milliarde Supply**.
- **Kein Presale, keine Team-Allocation** durch die Plattform (der Creator kann aber selbst sofort mitkaufen → "Dev Buy").
- Der gesamte Handel läuft anfangs über eine **Bonding Curve** – einen Smart Contract, der Preis und Liquidität deterministisch regelt. Es gibt in dieser Phase keinen klassischen LP-Pool und keine Orderbücher.

## Die Bonding Curve

- Konstantprodukt-Kurve mit virtuellen Reserven: Der Preis startet extrem niedrig (Market Cap wenige Tausend USD) und steigt mit jedem Kauf entlang der Kurve.
- Käufe zahlen SOL in die Kurve ein und bekommen Token heraus; Verkäufe umgekehrt. Der Contract ist immer Counterparty → **es gibt auf der Curve keine Honeypots im klassischen Sinn** (verkaufen geht immer), das Risiko ist der Preis, nicht die Verkaufbarkeit.
- **Mint- und Freeze-Authority sind revoked** – niemand kann nachminten oder Wallets einfrieren. Das nimmt zwei klassische Scam-Vektoren raus.
- Etwa **80 % des Supplys** liegen in der Kurve zum Verkauf, der Rest ist für die spätere DEX-Migration reserviert.

## Graduation ("Bonding")

- Ist die Kurve voll – historisch bei ca. **69.000–100.000 USD Market Cap** bzw. grob **~85 SOL** eingesammeltem SOL – "graduiert" der Token.
- Dann werden die reservierten Token + das SOL automatisch in einen DEX-Pool migriert und die **LP-Token geburnt** (Liquidität kann nicht abgezogen werden).
- **Bis März 2025**: Migration zu Raydium, mit 6 SOL Migrationsgebühr. **Seit März 2025**: kostenlose Migration in den hauseigenen DEX **PumpSwap**.
- Nur ein sehr kleiner Teil aller Launches (Größenordnung ~1 %) graduiert überhaupt. Graduation ist deshalb das wichtigste binäre Signal im pump.fun-Trading.

## Gebühren & Ökonomie

- **1 % Trading-Fee** auf Curve-Trades (Plattformeinnahme; pump.fun war damit zeitweise eines der umsatzstärksten Krypto-Protokolle überhaupt).
- **PumpSwap**: ~0,25 % Swap-Fee, aufgeteilt auf LPs/Protokoll/Creator.
- **Creator-Revenue-Sharing (seit 2025)**: Coin-Ersteller verdienen laufend an den Trading-Fees ihrer Coins mit. Motiv: Anreiz weg vom "einmal ruggen" hin zu "Coin am Leben halten". Prägte die ganze 2025er-Launchpad-Konkurrenz (Bags, Believe usw. werben mit besseren Creator-Splits).
- **PUMP-Token**: ICO im Juli 2025 (einer der größten ICOs aller Zeiten, ~500–600 Mio. USD in Minuten, FDV ~4 Mrd. USD), später Buyback-Programme aus Plattformeinnahmen.

## Typische Muster auf pump.fun (für Bot-Logik)

- **Dev Buy beim Launch**: Der Creator kauft im selben Bundle wie die Token-Erstellung. Moderater Dev-Buy ist normal; sehr großer Dev-Buy + frische Wallet = Dump-Setup.
- **Bundling**: Insider kaufen mit 5–50 Wallets im Launch-Block, um Verteilung vorzutäuschen. Erkennbar via Bubblemaps/GMGN-Bundle-Checks (gemeinsame Funding-Quelle der Wallets!).
- **Sniper-Bots**: Kaufen jede neue Coin-Erstellung in <1 s und verkaufen in die ersten organischen Käufe. Wer "beim Launch" kauft, ist fast immer deren Exit-Liquidität.
- **Curve-Stall**: Coins, die bei 30–60 % Curve-Füllung stagnieren, sterben meist; kurz vor Graduation (>90 %) entsteht oft ein Momentum-Push ("graduation snipe") und direkt nach Graduation häufig ein Dump der Curve-Käufer.
- **Re-Launches**: Gleiches Meme wird nach dem Tod x-mal neu deployed; Ticker sind nicht einzigartig! Immer über die Mint-Adresse identifizieren, nie über den Ticker.
- **Copytrading-Reflexivität**: Bekannte Wallets werden massenhaft kopiert; Smart-Money-Käufe wirken dadurch selbstverstärkend (und werden gezielt als Köder eingesetzt).

## Klone & Konkurrenz (Kontext)

| Plattform | Chain | Besonderheit |
|---|---|---|
| LetsBonk.fun | Solana | BONK-Ökosystem, Fees → BONK-Buybacks; überholte pump.fun Mitte 2025 zeitweise |
| Moonshot | Solana | DEX-Screener-Familie, Fiat-Onramp (Apple Pay), Normie-Fokus |
| Four.meme | BNB | PancakeSwap-Graduation, BNB-Meme-Wellen |
| SunPump | Tron | Justin-Sun-Push, Hype-Sommer 2024 |
| Believe | Solana | Launch per X-Reply, Creator-Coins |
| Clanker | Base | Token-Deploy per Farcaster-KI-Agent, direkt in Uniswap |

Details in `data/platforms.json`.

## Risiken & Kontroversen

- Klagen/Regulatorik: Sammelklagen in den USA (unregistrierte Securities-Vorwürfe), Sperre für UK-Nutzer nach FCA-Warnung (2024/2025).
- Livestream-Missbrauch (Ende 2024) → Feature-Abschaltung, moderierte Rückkehr 2025.
- Der Fair-Launch-Anspruch gilt nur für die Mechanik – **Information und Geschwindigkeit sind nicht fair verteilt** (Insider-Bundles, Sniper, KOL-Absprachen).
