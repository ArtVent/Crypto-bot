"""Wallet-Intelligence: rollierende Smart-Wallet-Erkennung aus dem Live-Strom.

Technik aus data/ai-techniques.json (Wallet-Intelligence, 'proven') und
docs/strategien.md 3.2 (Flow-Following): Wallets, die wiederholt FRÜH in
später graduierende Coins einsteigen, sind ein Qualitätssignal. Alles strikt
kausal: Credits entstehen erst, WENN eine Graduation passiert, und zählen nur
für Käufe, die davor lagen; die Konfluenz-Prüfung eines Kandidaten nutzt
ausschließlich bereits vergebene Credits.

Verwendung im Bot:
- Bei jeder Migration: die frühesten K Käufer des Coins erhalten einen Credit
  (mit Zeitstempel; Credits verfallen mit Halbwertszeit).
- Entry-Signal: smart_buyer_count(state) = Anzahl Käufer des Kandidaten mit
  Score >= min_score. Optionales Gate: strategy.min_smart_wallets.

Baiting-Schutz (docs/ai-und-memecoins.md, Abschnitt 6): Scores verfallen,
Credits gibt es nur für Graduations (teuer zu faken), und das Signal ist ein
Gate unter vielen, nie Allein-Grund.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class WalletBook:
    half_life_seconds: float = 24 * 3600.0
    early_buyer_credit_count: int = 25   # die frühesten K Käufer werden kreditiert
    min_score: float = 1.5               # Score-Schwelle für 'smart'
    max_wallets: int = 50_000
    # wallet -> (score, letzter_credit_t)
    _scores: dict[str, tuple[float, float]] = field(default_factory=dict)
    graduations_credited: int = 0

    def _decayed(self, wallet: str, now: float) -> float:
        entry = self._scores.get(wallet)
        if entry is None:
            return 0.0
        score, t = entry
        return score * math.exp(-(now - t) * math.log(2) / self.half_life_seconds)

    def credit_graduation(self, early_buyers: list[str], now: float) -> None:
        """Frühe Käufer eines graduierenden Coins kreditieren (kausal: erst jetzt)."""
        self.graduations_credited += 1
        for wallet in early_buyers[: self.early_buyer_credit_count]:
            self._scores[wallet] = (self._decayed(wallet, now) + 1.0, now)
        if len(self._scores) > self.max_wallets:
            # LRU-artige Kappung: älteste Credits raus
            for wallet, _ in sorted(self._scores.items(), key=lambda kv: kv[1][1])[
                : len(self._scores) - self.max_wallets
            ]:
                del self._scores[wallet]

    def is_smart(self, wallet: str, now: float) -> bool:
        return self._decayed(wallet, now) >= self.min_score

    def smart_buyer_count(self, buyers, now: float) -> int:
        return sum(1 for w in buyers if self.is_smart(w, now))

    def stats(self) -> dict:
        return {"wallets_tracked": len(self._scores),
                "graduations_credited": self.graduations_credited}


@dataclass
class CreatorBook:
    """Rollierendes Creator-Gedächtnis: Launches vs. Graduations je Wallet."""

    _launches: dict[str, int] = field(default_factory=dict)
    _graduations: dict[str, int] = field(default_factory=dict)
    serial_block_launches: int = 3   # ab so vielen Launches ohne Graduation: blocken

    def record_launch(self, creator: str) -> None:
        if creator:
            self._launches[creator] = self._launches.get(creator, 0) + 1

    def record_graduation(self, creator: str) -> None:
        if creator:
            self._graduations[creator] = self._graduations.get(creator, 0) + 1

    def is_serial_spammer(self, creator: str) -> bool:
        launches = self._launches.get(creator, 0)
        return launches >= self.serial_block_launches and self._graduations.get(creator, 0) == 0

    def stats(self) -> dict:
        blocked = sum(1 for c in self._launches if self.is_serial_spammer(c))
        return {"creators_tracked": len(self._launches), "serial_spammers": blocked}


@dataclass
class MarketRegime:
    """Markt-Hitze-Sensor: Graduationen pro Stunde als Regime-Signal
    (docs/strategien.md 4: Regime-Filter; metas.json: Launch-/Grad-Raten als Sensor)."""

    window_seconds: float = 3600.0
    _events: list[float] = field(default_factory=list)

    def record_graduation(self, now: float) -> None:
        self._events.append(now)
        cutoff = now - self.window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.pop(0)

    def graduations_per_hour(self, now: float) -> float:
        cutoff = now - self.window_seconds
        return float(sum(1 for t in self._events if t >= cutoff))
