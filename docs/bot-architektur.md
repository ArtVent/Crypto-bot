# Bot-Architektur – wie ein Memecoin-Trading-Bot aufgebaut ist

> Referenz-Architektur und Praxiswissen für den Bau eines eigenen Bots (Fokus Solana, übertragbar auf EVM). Ergänzt [`strategien.md`](strategien.md) (was handeln) um das Wie. Stand des Wissens: Anfang 2026.

## 1. Referenz-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│  DATEN-LAYER                                                │
│  Websockets: neue Launches (PumpPortal), Trades, Wallets    │
│  Polling: DEX Screener/Birdeye (Preise, Trending)           │
│  Social: X/Telegram-Listener, Announcement-Feeds            │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  FILTER- & RISK-ENGINE (das Herzstück)                      │
│  Security-Checks: RugCheck/GoPlus, Authorities, LP-Status   │
│  Distribution: Bundle-/Cluster-Analyse, Holder-Konzentration│
│  Qualität: Wash-Filter, Social-Plausibilität, Dev-Historie  │
│  → K.-o.-Kriterien + Score                                  │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  STRATEGIE-LAYER                                            │
│  Signal → Entscheidung (Entry/Exit/Size) je Strategie-Modul │
│  Portfolio-Constraints (Exposure, Korrelation, Kill-Switch) │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  EXECUTION-LAYER                                            │
│  Routing (Jupiter/PumpPortal), Slippage, Priority Fees/Jito │
│  Tx-Simulation → Senden → Bestätigung → Retry-Logik         │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│  STATE & OPS                                                │
│  Positions-DB, PnL-Tracking, Logs/Alerts, Dashboards        │
│  Key-Management, Kill-Switch, Watchdogs                     │
└─────────────────────────────────────────────────────────────┘
```

## 2. Daten-Layer

- **RPC:** Öffentliche Endpoints reichen nicht (Rate Limits, Latenz). Standard: dedizierter Anbieter (Helius, Triton, QuickNode); für Sniping zusätzlich gRPC-/Geyser-Streams.
- **Launch-Events:** pump.fun-Creates/Trades via PumpPortal-Websocket oder eigenem Geyser-Abo auf die Programm-IDs; LetsBonk & Co. analog.
- **Markt-Daten:** DEX Screener API (Pairs, Trending – kostenlos, Minuten-Granularität), Birdeye (OHLCV, Holder – API-Key). Regel: Polling-Daten nur für langsame Strategien, Streams für alles unter Minuten-Horizont.
- **Wallet-Daten:** Helius Enhanced APIs/Webhooks für Wallet-Tracking (Copy-Trading, Dev-Monitoring).
- **Social:** Announcement-Feeds der Börsen (offizielle APIs/RSS), X-Listener für definierte Accounts. Social-Daten IMMER mit Ingest-Timestamp speichern (Backtest-Ehrlichkeit).

## 3. Filter- & Risk-Engine

Reihenfolge: billige Checks zuerst, teure nur für Überlebende (Latenz-Budget!).

1. **Instant-K.-o. (lokal, <10 ms):** Metadaten-Heuristiken (Name-Duplikate, URL im Namen), Blacklists (Dev-Wallets, Funding-Quellen), Token-Alter.
2. **On-Chain-Basics (1 RPC-Call):** Mint-/Freeze-Authority, Supply, größte Holder.
3. **API-Checks (100–500 ms):** RugCheck-Report, GoPlus (EVM), LP-Status.
4. **Tiefen-Analyse (Sekunden, asynchron):** Bundle-/Cluster-Erkennung über Funding-Graphen, Wash-Volumen-Schätzung, Dev-Historie über verbundene Wallets.

Ergebnis pro Token: `verdict` (deny/allow) + `score` + `flags[]` – als eigenes Modul mit eigener Datenbank, damit alle Strategien dieselbe Risiko-Sicht teilen. Die vollständigen Check-Kataloge: [`risiko-und-scam-checks.md`](risiko-und-scam-checks.md) und [`../data/scams.json`](../data/scams.json).

## 4. Execution-Layer (Solana-Spezifika)

- **Routing:** Auf der Bonding Curve direkt gegen das Launchpad-Programm (PumpPortal-API oder eigene Instruktionen); nach Graduation über Jupiter (bestes Routing) oder direkt gegen den Pool (weniger Hops = weniger Latenz).
- **Slippage:** Hart begrenzen (Curve-Phase z. B. 5–15 %, DEX-Phase 1–5 %). "Slippage hochdrehen bis es klappt" ist die Anfänger-Falle, die Sandwich-Bots füttert.
- **Priority Fees & Jito:** Compute-Unit-Preis dynamisch an Netzwerk-Last koppeln; für zeitkritische Trades Jito-Bundles (Tip statt Public Mempool) – reduziert Sandwich-Risiko und Fehl-Landungen.
- **Simulation:** Jede Transaktion vor dem Senden simulieren (`simulateTransaction`) und den Balance-Diff gegen die Erwartung prüfen – fängt Honeypots, kaputte Pools und eigene Bugs.
- **Bestätigung & Retry:** Auf `confirmed` warten, bei Expiry mit frischem Blockhash neu bauen; niemals blind identische Transaktionen nachfeuern (Doppelkauf-Klassiker).
- **EVM-Pendants:** Private Order Flow (Flashbots Protect), Gas-Strategie, `eth_call`-Simulation, Approval-Hygiene (exakte Beträge statt unbegrenzt).

## 5. Positions- & Risiko-Management im Code

- **Zustandsmaschine je Position:** `scouting → entered → derisked (Einsatz raus) → runner → closed` mit definierten Übergängen; kein Zustand außerhalb der Maschine.
- **Exits als Daemon:** Take-Profit-Leitern, Zeit-Stops und These-Stops laufen als eigener Prozess gegen Live-Preise – unabhängig vom Entry-Pfad (überlebt Crashes des Signal-Moduls).
- **Portfolio-Constraints:** Max. Positionen gleichzeitig, max. Exposure je Meta/Chain, Tages-Verlustlimit → Kill-Switch, der nur manuell wieder scharf geht.
- **PnL nach ECHTEN Kosten:** Fees, Priority Fees/Tips, Slippage gegen den Quote-Preis mitschreiben – die meisten "profitablen" Bots sterben in dieser Spalte.

## 6. Sicherheit des Bots selbst

- **Keys:** Nie im Code/Repo/ENV-Klartext auf Dauer; getrennte Hot-Wallet mit Wochenbudget, Nachschub manuell aus Cold Storage. Signier-Logik idealerweise in eigenem Prozess mit Policy (max. Betrag/Tx, Ziel-Whitelist).
- **Dependency-Risiko:** Trading-Bot-Repos und 'Sniper-Source-Code' sind ein etablierter Malware-Vektor – Dependencies pinnen und auditieren, fremden Code sandboxen (siehe Fake-Tools in [`../data/scams.json`](../data/scams.json)).
- **API-Hygiene:** Offizielle Domains hart codieren; Antworten validieren (ein manipulierter Preis-Feed = manipulierter Bot).
- **Adress-Disziplin:** Ziel-Adressen aus Konfiguration, nie aus Historie/Clipboard (Address Poisoning).

## 7. Test-Pipeline

1. **Unit-Ebene:** Filter-Engine gegen gelabelte Historie (bekannte Rugs müssen deny liefern, bekannte Runner allow) – die Fälle aus [`beruehmte-faelle.md`](beruehmte-faelle.md) sind ein guter Start-Testsatz.
2. **Replay-Backtest:** Aufgezeichnete Streams (Launches, Trades) durch den echten Bot-Code spielen; Fills konservativ modellieren (siehe Backtesting-Fallen in [`strategien.md`](strategien.md)).
3. **Paper-Trading:** Live-Signale, simulierte Orders, echte Latenz – mindestens Wochen, über verschiedene Markt-Regime.
4. **Devnet/Testnet:** Execution-Pfad (Signieren, Senden, Bestätigen) mit Spielgeld end-to-end testen.
5. **Live-Minimal:** Kleinste sinnvolle Größen, jede Diskrepanz zu Paper-Ergebnissen untersuchen, erst dann skalieren.

## 8. Betriebs-Realitäten

- **Latenz-Ehrlichkeit:** Heim-Server in Europa gegen Co-located Sniper in Frankfurt/NY zu snipen ist verlorene Zeit – Strategie an die eigene Infrastruktur-Stufe anpassen (Tabelle in [`strategien.md`](strategien.md), Abschnitt 6).
- **Degradation einplanen:** RPC-Ausfälle, API-Limits, Stream-Disconnects sind Normalbetrieb → Reconnect-Logik, Fallback-Endpoints, und im Zweifel: flat gehen statt blind weiterhandeln.
- **Beobachtbarkeit:** Jede Entscheidung (Signal, Score, Verdict, Order, Fill) strukturiert loggen – ohne das ist weder Debugging noch Strategie-Verbesserung möglich.
- **Edge-Verfall:** Jede funktionierende Memecoin-Strategie hat ein Verfallsdatum (Monate). Der Bot ist nie fertig; das Monitoring der eigenen Trefferquote ist das wichtigste Dashboard.

## 9. KI/ML-Erweiterung

Der wirksamste Ausbau dieser Architektur ist ein ML-Layer in der Filter-Engine (Rug-/Survival-Scoring statt reiner Regeln) plus NLP-Signale im Daten-Layer – nicht ein "KI-Trader" obendrauf. Fahrplan, Feature-Design, Angriffsflächen (Prompt-Injection, Sentiment-Vergiftung) und die Ökonomie dahinter: [`ai-und-memecoins.md`](ai-und-memecoins.md) sowie [`../data/ai-techniques.json`](../data/ai-techniques.json). Grundregel: LLMs klassifizieren und fassen zusammen; über Geld entscheiden Code-Policies.
