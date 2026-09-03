# Real-Test: Der Bot gegen echte historische Coins (Ergebnis: negativ)

> Ausgeführt am 03.09.2026. Getestet wurde die Entry-Pipeline des Bots gegen
> **echte** pump.fun-Coins mit **echten** Outcomes (MELT-Datensatz, 41.470
> graduierte Coins Dez 2024–März 2025; CC BY-NC). Methodik: `realtest.py`.
> Dieses Dokument hält bewusst ein NEGATIVES Ergebnis fest – es ist der
> wichtigste Befund des Projekts.

## Methodik (auf Sauberkeit gebaut)

- **Nur der chronologische Hold-out** (letzte 20 %, 8.295 Coins ≈ Feb/März
  2025) – auf diesen Coins wurde das ML-Modell nie trainiert.
- Alle Auswahl-Features **strikt kausal** (Ticker-Duplikate/Creator-Historie
  nur aus der Vergangenheit); Impersonations-Veto nur aus öffentlichem Wissen.
- Exits aus den realen Outcomes approximiert, als **Korridor** gerechnet:
  konservative Ordnung (Stop −35 % greift vor jedem Gewinn, sobald der Coin
  je ≤ 65 % des Einstiegs fiel) vs. optimistische Ordnung (TP-Leiter zuerst);
  4 % Roundtrip-Kosten. TP-Leiter: +175 % ab Endrendite ≥ 250 %.
- Schwellen-Kalibrierung ausschließlich auf dem Trainings-Teil; der Hold-out
  wurde genau einmal ausgewertet.

## Ergebnis

**Basisrate (jeden graduierten Coin kaufen):** −19,9 % pro Trade, 79 %
Stop-Quote, 13,7 % Winrate.

**Bot-Auswahl** (Impersonations-Veto + Ticker-Dedupe + ML-Gate 0,8 → 941 von
8.295 Coins, 11,3 %):

| Exit-Ordnung | Ø PnL/Trade | Winrate | PnL bei 0,05 SOL/Trade |
|---|---|---|---|
| konservativ | **−17,6 %** | 15,7 % | −8,27 SOL |
| optimistisch | **−16,5 %** | 16,3 % | −7,74 SOL |

Der Filter wirkt messbar (High-Risk-Anteil 84 % → 67,5 %, +2,3 Punkte
Erwartungswert gegenüber Basisrate) – **aber er dreht das Vorzeichen nicht.**

**Schwellen-Sweep (nur Train):** monoton besser mit strengerem Gate, aber
selbst die strengste Konfiguration (ML < 0,5) bleibt bei **−7,0 %** pro Trade.
Es existiert in diesem Auswahl-Pfad keine profitable Konfiguration.

**Drift live beobachtet:** Die auf Train beste Konfiguration (ML < 0,5)
selektiert im Hold-out-Zeitraum **null** Coins – die Score-Verteilung
verschiebt sich binnen Wochen. Das bestätigt empirisch die
Retraining-Pflicht aus [`filter-engine.md`](filter-engine.md) (4.5).

## Antwort auf die Frage "Was wäre aus 1 SOL geworden?"

In diesem realen Zeitraum, mit dieser Pipeline: **Der größte Teil des 1 SOL
wäre verloren gegangen.** Der Tages-Kill-Switch (−0,15 SOL) hätte den Verlust
gestreckt und gedeckelt, aber bei ~16 % Winrate und −17 % Erwartung pro Trade
nicht verhindert. Die +20 % aus der kalibrierten Simulation
([`backtest-simulation.md`](backtest-simulation.md)) haben den Realitätstest
damit NICHT bestanden – die Simulation war, wie dort bereits gewarnt, zu
freundlich.

## Was dieser Test NICHT prüfen konnte (offene Hypothese)

Ohne Trade-Streams blieben genau die Komponenten ungetestet, die den
eigentlichen Edge liefern sollen: Curve-Phasen-Timing (Einstieg bei
Nachfrage-Beweis statt "Kauf bei Graduation"), Mikrostruktur-Gates
(Burst/Top-3/Wash), Creator-Dump-Sofort-Exit und Zeit-Stops. Der Befund ist
also präzise: **"Metadaten-Auswahl allein hat keinen Edge" ist auf echten
Daten belegt; ob die Timing-/Mikrostruktur-Schicht einen liefert, ist offen
und nur mit Trade-Level-Daten prüfbar.**

## Konsequenzen

1. **Kein Live-Trading mit diesem Stand.** Die Beweislast liegt jetzt bei der
   Timing-Schicht – und die braucht echte Streams.
2. Realer Prüfweg: lokal `memescan watch`/`memetrader record` einige Wochen
   aufzeichnen, dann `memetrader backtest --events <aufzeichnung>` – derselbe
   Harness, echte Daten, voller Bot inklusive Mikrostruktur-Gates.
3. ML-Gate nur mit rollierendem Retraining betreiben (Drift-Befund).
4. Der Wert des heutigen Tages: Diese Erkenntnis hat 1 SOL gerettet, bevor er
   es auf die teure Art gelehrt hätte.
