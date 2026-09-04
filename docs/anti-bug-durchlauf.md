# Anti-Bug-Durchlauf (September 2026)

Vollständiger Korrektheits-Durchlauf über die Codebasis: drei parallele
Review-Pässe (Recorder/RPC, Risk/Bot/Wallet-Intelligence, Backtest/Abtest/
Funnel/Realdata), plus ein Live-Funnel an echten On-Chain-Daten und ein
Regressionstest gegen den historischen Handelstag.

## Wichtigster Befund: die „0 Trades" waren KEIN Bug

Ein 45-Minuten-Live-Lauf zeichnete 97.941 echte Events auf, der Bot handelte
aber 0-mal. Der Live-Funnel (`memetrader funnel`) an echten Daten zeigte die
echten Gründe: die Dev-Buy-Faltung funktioniert (nur 5 von 99 Coins ohne
Dev-Buy), und die Ablehnungen sind legitime Strategieregeln (Coin vor
Aufnahmebeginn gelauncht, zu jung, Creator hat verkauft, Verkaufsdruck).
Der Regressionstest bestätigt: derselbe Code macht auf dem historischen
Volltag weiter **58 Trades (+17,8 %)**. Fazit: Die Strategie ist selektiv
(~58 Trades/Tag ≈ 1–2 pro 45 Min), kurze Fenster handeln oft null. Das ist
korrektes Verhalten, kein Fehler.

## Behobene echte Bugs

| # | Datei | Bug | Fix |
|---|---|---|---|
| 1 | backtest.py | Max-Drawdown nur alle 5000 Events berechnet → **0 % bei kurzen Aufnahmen** (dem A/B-Fall) | Stichprobe alle 100 Events + am Ende; `equity()` ist O(offene Pos.) |
| 2 | backtest.py | Schluss-Liquidation umging das Journal → n_closed/Winrate/Lektionen ließen offene Positionen fallen (Bias zwischen Armen mit langer Haltezeit) | Liquidation über `journal.on_exit` |
| 3 | backtest.py / abtest.py | `return_pct` hardcodierte Basis 1.0 SOL → falsch bei anderem Budget | `BacktestResult.return_pct` nutzt `budget_sol` |
| 4 | backtest.py | Letzter (Teil-)Tag nie geflusht → `halted_days` zu niedrig, Equity-Kurve unvollständig | Flush nach der Schleife |
| 5 | bot.py | Kein Wiedereintritts-Schutz: gerade verkaufter Coin konnte im selben Event neu gekauft werden | `_maybe_enter` blockt bei offener Position, laufendem Vet, Post-Exit-Fenster oder `migrated` |
| 6 | bot.py | Verzögerter Claude-Vet-Entry übersprang die Intelligence-Gates (Markt im Vet-Fenster abgekühlt / Creator zum Spammer geworden) | Gates in `_intelligence_block` ausgelagert, beim Vet-Rücklauf erneut geprüft |
| 7 | risk.py | Recycle-Dust-Guard prüfte Gesamtwert statt Restwert (Doku sagte Restwert) | Guard auf `value - basis >= recycle_min_value_sol` |
| 8 | realdata.py | Mehrere Dev-Buys im selben Slot überschrieben statt summiert (Kaufvolumen verloren) | Summieren |
| 9 | realdata.py | Synthetisches migrate bei `t+0.5` konnte Monotonie brechen (heapq.merge setzt Sortierung voraus) | migrate beim selben `t` wie der auslösende Swap |
| 10 | rpcrecorder.py | Nicht-Dict-JSON-Frame löste vollen Reconnect (~2 s Lücke) statt Skip aus; Reconnect-Backoff nie zurückgesetzt; Milestone-Flush konnte verfehlt/mehrfach feuern | `isinstance`-Guard, Backoff-Reset nach stabilem Empfang, zählerbasierter Flush |
| 11 | recorder.py | Nicht-Dict-JSON-Frame löste Reconnect aus | `isinstance`-Guard |

## Ausdrücklich verifiziert KORREKT (kein Fehler)

- Recycle-Leiter-Mathematik (Basis raus, Rest als neue Basis), keine Endlos-Wiederholung
- Cash-/Budget-Buchhaltung (`committed`/`available`), kein Doppelzählen
- Kill-Switch-Tagesreset über Tagesgrenzen; Halbwertszeit-Decay 2^(-dt/HL); LRU-Kappung ohne Mutation-während-Iteration
- Entry-Gate-Vergleichsrichtungen (min `<`, max `>`, ml `>=`)
- Anchor-Diskriminatoren byte-genau gegen das echte pump.fun-IDL; Base58; Borsh-Offsets/Skalierung (Lamports/1e9, Token/1e6)
- Kein Lookahead; Overrides greifen; kein Zustands-Leak zwischen den A/B-Läufen; Equity-Formel sauber mark-to-market

## Dokumentiert (Verhalten beabsichtigt)

- Kill-Switch stellt offene Positionen glatt (nicht nur Entry-Sperre) – Kommentar präzisiert.
- Funnel misst nur das Strategie-Gate (Obergrenze) – als `note` im Output.
