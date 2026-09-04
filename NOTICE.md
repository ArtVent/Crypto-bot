# Attribution / Drittanbieter-Daten

## MELT-Datensatz (Modell-Training)

`models/mlfilter-melt.joblib` wurde auf dem **MELT**-Datensatz trainiert:

> MELT: Memecoin Launch Time dataset — lizenziert unter
> **Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0)**.

Bedingungen, die daraus für dieses Repository folgen:
- **Namensnennung** (hiermit erfüllt).
- **Nicht-kommerziell:** Das mitgelieferte Modell darf nur für Forschung /
  persönliche, nicht-kommerzielle Experimente (Paper-Trading) verwendet
  werden. Für kommerzielle Nutzung (Trading mit echtem Geld zur
  Gewinnerzielung) muss das Modell mit `train_mlfilter.py` auf **eigenen**
  Archiv-Daten neu trainiert werden; das MELT-basierte Modell ist dann zu
  entfernen. Siehe Hinweis im Docstring von `src/memetrader/mlfilter.py`.

## Verwendete Live-Datenquellen (Laufzeit, nicht im Repo gespeichert)

- pump.fun-Programm-Logs über öffentliche Solana-RPC-Endpunkte
  (`logsSubscribe`) – öffentliche On-Chain-Daten.
- Optionaler PumpPortal-Datenstrom (nur mit eigenem API-Key).

Datensätze ohne freie Lizenz (pumpfun-market-lab, fingerprinter u. a.) wurden
ausschließlich lokal zur Auswertung genutzt und sind **nicht** Teil dieses
Repositories.
