# memescan – Sicherheits-Scanner & Launch-Archiver

Die erste lauffähige Umsetzung aus der Wissensdatenbank dieses Repos: das
**Security-Tooling-Geschäftsmodell** (Verlässlichkeit 5/5 in
[`../data/ai-business-models.json`](../data/ai-business-models.json)) plus der
**Daten-Grundstein** (Launch-Archiv als Trainingsdaten und Produkt).

## Was es tut

1. **`check`** – prüft einen Token defensiv gegen die K.-o.-Regeln aus
   [`../docs/filter-engine.md`](../docs/filter-engine.md): Authorities,
   Token-2022-Flags, Honeypot/Taxes (EVM via GoPlus), LP-Status,
   Holder-Konzentration, Creator-Historie, MC/Liquiditäts-Ratio → Verdict
   `ALLOW` / `WARN` / `DENY` mit Flags und Risiko-Score.
2. **`watch`** – archiviert **alle** neuen pump.fun-Launches (PumpPortal-
   Websocket, kostenlos) in SQLite – inklusive der toten 99 %, die jedes
   ML-Modell braucht ([`../docs/filter-engine.md`](../docs/filter-engine.md), 4.2).
3. **`label`** – labelt Launches nach 24 h mechanisch über DexScreener
   (`dead` / `survivor` / `graduated_pool`) → wachsender, gelabelter Datensatz.
4. **`stats`** – Archiv-Übersicht.

## Nutzung

```bash
pip install -e ".[dev]"          # oder: pip install httpx websockets

memescan check <MINT>                        # Solana (RugCheck + DexScreener)
memescan check <0x...> --chain base          # EVM (GoPlus)
memescan check <MINT> --json                 # maschinenlesbar

memescan watch --db launches.db              # Archiv-Daemon (Ctrl+C beendet)
memescan label --db launches.db              # Outcomes nachziehen (cron-tauglich)
memescan stats --db launches.db
```

Exit-Code: `0` = ALLOW, `1` = WARN/DENY, `2` = Abruf-Fehler — direkt in
Bot-Pipelines als Pre-Trade-Gate verwendbar.

## Tests

```bash
python3 -m pytest tests/ -q     # 18 Tests, ohne Netzwerk (Fixtures)
```

**Hinweis:** Die Cloud-Sandbox, in der dieses Paket entstand, blockt die
Krypto-API-Domains (Proxy-403) – Live-Abrufe wurden dort nicht getestet.
Parser und Regel-Engine sind über Fixtures getestet; den ersten Live-Lauf
(`memescan check`, `memescan watch`) bitte lokal machen und Abweichungen der
API-Schemata gegen [`../data/detection-apis.json`](../data/detection-apis.json)
prüfen.

## Architektur

```
providers.py   RugCheck / GoPlus / DexScreener → TokenReport (normalisiert)
engine.py      K.-o.-Regeln + Score (Thresholds zentral, kalibrierbar)
archiver.py    PumpPortal-Websocket → SQLite; Outcome-Labeler
cli.py         check / watch / label / stats
```

Design-Grundsätze (aus der Doku): `None` = unbekannt ≠ sicher; externe Scores
sind Features, nie die Entscheidung; Schwellen zentral kalibrierbar; das
Archiv ist vollständig oder wertlos.

## Ausbau-Fahrplan (→ Monetarisierung)

1. Archiv einige Wochen laufen lassen → eigene Basisraten statt Literaturwerte.
2. Bundle-Basistest ergänzen (Same-Slot-Käufer aus dem Trade-Stream).
3. Gradient-Boosting-Klassifikator auf dem gelabelten Archiv
   ([`../docs/filter-engine.md`](../docs/filter-engine.md), Abschnitt 4).
4. Produktisierung: HTTP-API (FastAPI) + Telegram-Bot vor `evaluate()` –
   Freemium-Modell wie in
   [`../docs/ai-geschaeftsmodelle.md`](../docs/ai-geschaeftsmodelle.md), Abschnitt 4.
   Ethik-Leitplanken von dort gelten: kein Pay-to-Pass, Fehlerraten offenlegen,
   Scores als Risiko-Indikator framen, nie als Freigabe.
