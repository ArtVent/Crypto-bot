# Crypto-bot

## memescan – Sicherheits-Scanner & Launch-Archiver

Lauffähiger Code auf Basis der Datenbank: Token-Checks (RugCheck/GoPlus/eigene Regeln → ALLOW/WARN/DENY), pump.fun-Launch-Archiv und Outcome-Labeling. Setup und Nutzung: [`src/README.md`](src/README.md)

```bash
pip install -e . && memescan check <MINT>
```

## memetrader – gefilterter Momentum-Bot (1-SOL-Experiment)

Autonomer pump.fun-Bot nach den Regeln der Datenbank: Beobachtungsfenster statt Block-0-Sniping, Entry nur bei Nachfrage-Beweis, asymmetrische Exits, Kill-Switch. **Default: Paper-Trading**; Live nur als doppelter Opt-in mit lokalem Key. Details und ehrliche Erwartung: [`src/memetrader/README.md`](src/memetrader/README.md)

```bash
memetrader run --budget-sol 1.0        # Paper-Modus gegen Live-Daten
```

## Memecoin-Datenbank

Dieses Repo enthält eine umfangreiche, strukturierte Wissensdatenbank zu Memecoins und ihrem Ökosystem:

### `data/` – maschinenlesbare JSON-Daten

[Memecoins](data/memecoins.json) · [Launch-Plattformen](data/platforms.json) · [Strategien](data/strategies.json) · [Scam-Taxonomie](data/scams.json) · [KI-Techniken](data/ai-techniques.json) · [AI-Agenten](data/ai-agents.json) · [KI-Geschäftsmodelle](data/ai-business-models.json) · [Filter-Features](data/filter-features.json) · [Detektions-APIs](data/detection-apis.json) · [Fee-Quellen](data/fee-sources.json) · [Metas/Narrative](data/metas.json) · [Event-Timeline](data/events.json) · [Chain-Profile](data/chains.json) · [Token-Erstellung](data/token-creation.json) · [DEXe & Aggregatoren](data/dexes-and-aggregators.json) · [Tools & APIs](data/tools.json)

Details und Lade-Beispiele: [`data/README.md`](data/README.md)

### `docs/` – Hintergrund-Doku

[Memecoin-Grundlagen](docs/memecoin-grundlagen.md) · [pump.fun-Mechanik](docs/pumpfun-mechanik.md) · [Strategien-Leitfaden](docs/strategien.md) · [KI & Memecoins](docs/ai-und-memecoins.md) · [KI-Geschäftsmodelle](docs/ai-geschaeftsmodelle.md) · [Filter-Engine](docs/filter-engine.md) · [Fee-Ökonomie](docs/fee-oekonomie.md) · [Risiko- & Scam-Checks](docs/risiko-und-scam-checks.md) · [Berühmte Fälle](docs/beruehmte-faelle.md) · [Token-Erstellung](docs/token-erstellung.md) · [Bot-Architektur](docs/bot-architektur.md) · [Glossar](docs/glossar.md)

> Wissensstand ca. Anfang 2026, ohne Gewähr. Keine Finanzberatung; Scam-Dokumentation dient ausschließlich der Erkennung und Verteidigung.
