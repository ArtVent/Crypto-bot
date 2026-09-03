# Memecoin-Datenbank

Strukturierte Wissensdatenbank zu Memecoins, Launch-Plattformen, Strategien, Scams und dem Ökosystem drumherum – als maschinenlesbare JSON-Dateien für den Bot plus vertiefende Doku unter [`../docs/`](../docs/).

## Daten (`data/`)

| Datei | Inhalt |
|---|---|
| [`memecoins.json`](memecoins.json) | Bekannte Memecoins: Name, Ticker, Chain, Startjahr, Kategorie, Hintergrund |
| [`platforms.json`](platforms.json) | Launch-Plattformen (pump.fun, LetsBonk, Moonshot, Four.meme, …): Mechanik, Graduation, Fees, Marktposition |
| [`strategies.json`](strategies.json) | Trading-Strategien: Mechanik, Signale, Risiken, Automatisierbarkeit, passende Tools |
| [`scams.json`](scams.json) | Scam-/Manipulations-Taxonomie mit Red Flags und automatisierbarer Erkennung (Verteidigungs-Perspektive) |
| [`ai-techniques.json`](ai-techniques.json) | KI-/ML-Techniken im Trading: was sie tun, wie sie Geld verdienen, wo ihre Grenzen liegen |
| [`ai-agents.json`](ai-agents.json) | AI-Agenten-Ökosystem (Truth Terminal, AIXBT, Clanker, ElizaOS, …) mit Einnahmemodellen |
| [`metas.json`](metas.json) | Narrative/Metas (Dog, AI, PolitiFi, …) mit Hochphasen, Leadern und Lektionen |
| [`events.json`](events.json) | Timeline prägender Ereignisse der Memecoin-Geschichte (2013 – Ende 2025) |
| [`chains.json`](chains.json) | Chain-Profile aus Memecoin-Sicht: Launch-/Trade-Infrastruktur, Kosten, Charakter |
| [`token-creation.json`](token-creation.json) | Wege der Token-Erstellung und was jeder Deploy-Weg für Käufer/Bots bedeutet |
| [`dexes-and-aggregators.json`](dexes-and-aggregators.json) | DEXe & Aggregatoren (Raydium, PumpSwap, Jupiter, Uniswap, …) |
| [`tools.json`](tools.json) | Screener, Security-Checks, Trading-Bots, APIs (DEX Screener, RugCheck, GMGN, Helius, …) |

## Doku (`../docs/`)

| Datei | Inhalt |
|---|---|
| [`memecoin-grundlagen.md`](../docs/memecoin-grundlagen.md) | Was Memecoins sind, Markt-Wellen, Lebenszyklus, Kennzahlen, Signal-Checkliste |
| [`pumpfun-mechanik.md`](../docs/pumpfun-mechanik.md) | Bonding Curve, Graduation, Fees, typische Muster auf pump.fun |
| [`strategien.md`](../docs/strategien.md) | Strategie-Leitfaden: Edge-Quellen, Strategie-Familien, Risiko-Framework, Backtesting-Fallen |
| [`ai-und-memecoins.md`](../docs/ai-und-memecoins.md) | KI & Memecoins: Anatomie eines KI-Snipers, wo ML wirklich verdient, Agenten-Geschäftsmodelle, Angriffe auf KI-Trader |
| [`risiko-und-scam-checks.md`](../docs/risiko-und-scam-checks.md) | Scam-Typen, automatisierbare Pre-Trade-Checks, Red Flags, Bot-Sicherheit |
| [`beruehmte-faelle.md`](../docs/beruehmte-faelle.md) | Fallstudien: SQUID, BALD, HAWK, TRUMP, LIBRA & Co. – mit Lektionen für Filter |
| [`token-erstellung.md`](../docs/token-erstellung.md) | Wie Token technisch entstehen, Anatomie eines Launches, Seriositäts-Checkliste, Rechtliches |
| [`bot-architektur.md`](../docs/bot-architektur.md) | Referenz-Architektur eines Memecoin-Bots: Daten, Filter-Engine, Execution, Testing, Betrieb |
| [`glossar.md`](../docs/glossar.md) | Szene-Begriffe von "Ape" bis "Whale" |

## Konventionen

- **JSON-Format**: Jede Datei hat einen `_meta`-Block (Beschreibung + Felddefinitionen) und darunter das eigentliche Array. Feldnamen englisch (code-freundlich), Beschreibungstexte deutsch.
- **Keine Contract-Adressen**: bewusst weggelassen, um Verwechslungen mit Fake-Token auszuschließen. Adressen immer live über verifizierte Quellen auflösen (CoinGecko, Jupiter Strict List, DEX Screener).
- **Keine Live-Marktdaten**: Preise/Market Caps veralten in Minuten und gehören nicht in statische Dateien – dafür APIs nutzen (DEX Screener, Birdeye, CoinGecko; siehe `tools.json`).
- **Scam-Wissen ist Verteidigungs-Wissen**: `scams.json` und die Fall-Doku dokumentieren Manipulationsmuster zur Erkennung – nicht zur Anwendung; vieles davon ist strafbar.
- **Stand**: Wissensstand ca. Anfang 2026. Fees, Graduation-Schwellen und Marktpositionen ändern sich schnell → vor Verwendung in Handelslogik gegen offizielle Docs prüfen.

## Beispiel: Daten im Bot laden (Python)

```python
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"

def load(name: str, key: str) -> list[dict]:
    return json.loads((DATA / f"{name}.json").read_text())[key]

memecoins = load("memecoins", "memecoins")
strategies = load("strategies", "strategies")
scams = load("scams", "scams")

solana_coins = [c for c in memecoins if "Solana" in c["chain"]]
sniping = [s for s in strategies if s["family"] == "sniping"]
contract_scams = [s for s in scams if s["category"] == "contract"]
```

## Disclaimer

Reine Wissens-/Recherchesammlung, **keine Finanzberatung**. Memecoins sind Totalverlust-Territorium; die überwältigende Mehrheit aller Launchpad-Token geht gegen null.
