"""Entry-Strategie: gefiltertes Curve-Momentum statt Block-0-Sniping.

Regeln abgeleitet aus docs/strategien.md (3.1), docs/filter-engine.md und den
Forschungs-Basisraten (filter-engine.md 6b). Alle Schwellen zentral in
StrategyConfig – kalibrieren, nicht raten.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .curve import CurveState


@dataclass
class StrategyConfig:
    # Beobachtungsfenster: die Sniper-/Bundle-Sekunden auslassen
    min_age_seconds: float = 45.0
    max_age_seconds: float = 45 * 60.0
    # Dev-Buy-Band (filter-features.json: dev_buy_share_pct – moderat ist ok,
    # 0 ist Spam-Muster, groß ist Dump-Setup). In SOL, da Events SOL liefern.
    min_dev_buy_sol: float = 0.05
    max_dev_buy_sol: float = 3.0
    # Nachfrage-Beweis
    min_unique_buyers: int = 10
    min_buys: int = 15
    max_sell_buy_ratio: float = 0.5  # sells/buys – Distribution-Frühwarnung
    # Curve-Band (strategien.md: Stall-Zone unten meiden, Graduation-Dump oben)
    min_fill_pct: float = 10.0
    max_fill_pct: float = 75.0
    # Aktivität: letzter Trade darf nicht zu lange her sein
    max_seconds_since_trade: float = 20.0
    # Dedupe: gleiches Symbol nur einmal pro Fenster handeln (Ticker-Kriege)
    symbol_dedupe_seconds: float = 3600.0
    # Mikrostruktur-Gates (Bundle-/Wash-Signaturen, filter-features.json);
    # greifen erst ab ausreichender Statistik. Baseline-Modus: Werte auf
    # 1.01 / 0.0 / 1.01 / 1.01 setzen = deaktiviert.
    max_burst_buyer_share: float = 0.60   # >60 % der Käufer in einem 60s-Fenster
    burst_window_seconds: float = 60.0
    min_buy_size_cv: float = 0.25         # Kaufgrößen zu uniform = Bot-Muster
    max_top3_buyer_share: float = 0.45    # Top-3-Käufer dominieren das Kauf-SOL
    max_roundtrip_share: float = 0.35     # Käufer, die auch verkaufen (Wash)


@dataclass
class Decision:
    enter: bool
    reasons: list[str] = field(default_factory=list)


class MomentumStrategy:
    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()
        self._symbol_seen: dict[str, tuple[float, str]] = {}  # SYMBOL -> (zeit, mint)

    def evaluate(self, state: CurveState, now: float | None = None) -> Decision:
        c = self.config
        now = time.time() if now is None else now
        reasons: list[str] = []
        age = now - state.created_at

        if state.migrated:
            reasons.append("bereits graduiert – Curve-Strategie nicht zuständig")
        if age < c.min_age_seconds:
            reasons.append(f"zu jung ({age:.0f}s < {c.min_age_seconds:.0f}s Sniper-Fenster)")
        if age > c.max_age_seconds:
            reasons.append("zu alt für Curve-Momentum")
        if state.creator_sold:
            reasons.append("Creator hat verkauft (Soft-Rug-Signal)")
        if not (c.min_dev_buy_sol <= state.dev_buy_sol <= c.max_dev_buy_sol):
            reasons.append(f"Dev-Buy außerhalb Band ({state.dev_buy_sol:.2f} SOL)")
        if len(state.unique_buyers) < c.min_unique_buyers:
            reasons.append(f"zu wenige Unique-Buyer ({len(state.unique_buyers)})")
        if state.buys < c.min_buys:
            reasons.append(f"zu wenige Käufe ({state.buys})")
        if state.buys and state.sells / state.buys > c.max_sell_buy_ratio:
            reasons.append(f"Verkaufsdruck hoch ({state.sells}/{state.buys})")
        if not (c.min_fill_pct <= state.fill_pct <= c.max_fill_pct):
            reasons.append(f"Curve-Füllung außerhalb Band ({state.fill_pct:.0f}%)")
        if state.last_trade_at and now - state.last_trade_at > c.max_seconds_since_trade:
            reasons.append("Momentum abgerissen (kein Trade zuletzt)")

        # Mikrostruktur-Gates (nur mit ausreichender Statistik) – und nur,
        # wenn nicht schon billige Checks abgelehnt haben (Performance:
        # burst_buyer_share ist O(n) und darf nicht pro Event für tote
        # Kandidaten laufen)
        if reasons:
            return Decision(enter=False, reasons=reasons)
        if len(state.unique_buyers) >= c.min_unique_buyers:
            burst = state.burst_buyer_share(c.burst_window_seconds)
            if burst > c.max_burst_buyer_share:
                reasons.append(f"Bundle-Signatur: {burst:.0%} der Käufer in einem "
                               f"{c.burst_window_seconds:.0f}s-Fenster")
            top3 = state.top_buyer_share(3)
            if top3 > c.max_top3_buyer_share:
                reasons.append(f"Käufer-Konzentration: Top-3 halten {top3:.0%} des Kauf-SOL")
            roundtrip = state.roundtrip_share()
            if roundtrip > c.max_roundtrip_share:
                reasons.append(f"Wash-Signatur: {roundtrip:.0%} der Käufer verkaufen auch")
        cv = state.buy_size_cv()
        if cv is not None and state.buys >= c.min_buys and cv < c.min_buy_size_cv:
            reasons.append(f"uniforme Kaufgrößen (CV {cv:.2f} – Bot-Muster)")

        symbol = (state.symbol or "").upper()
        if symbol:
            seen = self._symbol_seen.get(symbol)
            # Duplikat nur, wenn ein ANDERER Mint das Symbol belegt (Re-Evaluation
            # desselben Kandidaten, z. B. nach Claude-Vet, bleibt erlaubt)
            if seen is not None and seen[1] != state.mint and now - seen[0] < c.symbol_dedupe_seconds:
                reasons.append(f"Symbol-Duplikat '{symbol}' im Fenster (Ticker-Krieg)")

        if reasons:
            return Decision(enter=False, reasons=reasons)

        if symbol:
            self._symbol_seen[symbol] = (now, state.mint)
        return Decision(enter=True, reasons=["alle Entry-Kriterien erfüllt"])
