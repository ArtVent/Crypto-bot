# Memecoin-Datenbank

Strukturierte Wissensdatenbank zu Memecoins, Launch-Plattformen und dem Ökosystem drumherum – als maschinenlesbare JSON-Dateien für den Bot plus vertiefende Doku unter [`../docs/`](../docs/).

## Dateien

| Datei | Inhalt |
|---|---|
| [`memecoins.json`](memecoins.json) | Bekannte Memecoins: Name, Ticker, Chain, Startjahr, Kategorie, Hintergrund |
| [`platforms.json`](platforms.json) | Launch-Plattformen (pump.fun, LetsBonk, Moonshot, Four.meme, …): Mechanik, Graduation, Fees, Marktposition |
| [`dexes-and-aggregators.json`](dexes-and-aggregators.json) | DEXe & Aggregatoren (Raydium, PumpSwap, Jupiter, Uniswap, …) |
| [`tools.json`](tools.json) | Screener, Security-Checks, Trading-Bots, APIs (DEX Screener, RugCheck, GMGN, Helius, …) |

## Doku (`../docs/`)

| Datei | Inhalt |
|---|---|
| [`memecoin-grundlagen.md`](../docs/memecoin-grundlagen.md) | Was Memecoins sind, Markt-Wellen, Lebenszyklus, Kennzahlen, Signal-Checkliste |
| [`pumpfun-mechanik.md`](../docs/pumpfun-mechanik.md) | Bonding Curve, Graduation, Fees, typische Muster auf pump.fun |
| [`risiko-und-scam-checks.md`](../docs/risiko-und-scam-checks.md) | Scam-Typen, automatisierbare Pre-Trade-Checks, Red Flags, Bot-Sicherheit |
| [`glossar.md`](../docs/glossar.md) | Szene-Begriffe von "Ape" bis "Whale" |

## Konventionen

- **JSON-Format**: Jede Datei hat einen `_meta`-Block (Beschreibung + Felddefinitionen) und darunter das eigentliche Array. Feldnamen englisch (code-freundlich), Beschreibungstexte deutsch.
- **Keine Contract-Adressen**: bewusst weggelassen, um Verwechslungen mit Fake-Token auszuschließen. Adressen immer live über verifizierte Quellen auflösen (CoinGecko, Jupiter Strict List, DEX Screener).
- **Keine Live-Marktdaten**: Preise/Market Caps veralten in Minuten und gehören nicht in statische Dateien – dafür APIs nutzen (DEX Screener, Birdeye, CoinGecko; siehe `tools.json`).
- **Stand**: Wissensstand ca. Anfang 2026. Fees, Graduation-Schwellen und Marktpositionen ändern sich schnell → vor Verwendung in Handelslogik gegen offizielle Docs prüfen.

## Beispiel: Daten im Bot laden (Python)

```python
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"

memecoins = json.loads((DATA / "memecoins.json").read_text())["memecoins"]
platforms = json.loads((DATA / "platforms.json").read_text())["platforms"]

solana_coins = [c for c in memecoins if "Solana" in c["chain"]]
```

## Disclaimer

Reine Wissens-/Recherchesammlung, **keine Finanzberatung**. Memecoins sind Totalverlust-Territorium; die überwältigende Mehrheit aller Launchpad-Token geht gegen null.
