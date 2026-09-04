"""Bonding-Curve-Zustand und -Mathematik (pump.fun-Modell).

Die Curve ist ein Konstantprodukt-AMM mit virtuellen Reserven; die
PumpPortal-Events liefern nach jedem Trade vSolInBondingCurve und
vTokensInBondingCurve (data/detection-apis.json). Damit lassen sich Preise
und Fills exakt nachrechnen – Grundlage des Paper-Brokers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Referenzwerte der pump.fun-Curve (docs/pumpfun-mechanik.md):
# ~85 SOL echte Einzahlung füllen die Kurve; Start-Marktcap ~30 SOL virtuell.
GRADUATION_REAL_SOL = 85.0
CURVE_FEE = 0.0125  # 1,25 % Curve-Fee seit Project Ascend (data/fee-sources.json)


@dataclass
class CurveState:
    """Live-Zustand einer Bonding Curve, gespeist aus Trade-Events."""

    mint: str
    creator: str = ""
    symbol: str = ""
    name: str = ""
    uri: str = ""
    v_sol: float = 0.0
    v_tokens: float = 0.0
    created_at: float = 0.0
    dev_buy_sol: float = 0.0
    real_sol_in_curve: float = 0.0  # Netto-SOL-Zufluss (Buy - Sell)
    buys: int = 0
    sells: int = 0
    unique_buyers: set[str] = field(default_factory=set)
    creator_sold: bool = False
    migrated: bool = False
    last_trade_at: float = 0.0
    # Kausale Kontext-Zähler (gesetzt vom Bot beim Create-Event)
    symbol_dupes_before: int = 0
    creator_prior_launches: int = 0
    # Mikrostruktur-Statistiken für Bundle-/Wash-Erkennung (filter-features.json)
    first_buy_times: list[float] = field(default_factory=list)
    buy_sol_by_wallet: dict[str, float] = field(default_factory=dict)
    sellers: set[str] = field(default_factory=set)
    early_buyers: list[str] = field(default_factory=list)  # Käufer-Wallets in Ankunftsreihenfolge (gekappt)
    _buy_n: int = 0
    _buy_sum: float = 0.0
    _buy_sumsq: float = 0.0

    @property
    def price_sol(self) -> float:
        """Preis in SOL pro Token."""
        if self.v_tokens <= 0:
            return 0.0
        return self.v_sol / self.v_tokens

    @property
    def fill_pct(self) -> float:
        """Grobe Curve-Füllung in % (netto eingezahltes SOL / Graduationsziel)."""
        return max(0.0, min(100.0, self.real_sol_in_curve / GRADUATION_REAL_SOL * 100.0))

    def apply_trade(self, event: dict, now: float) -> None:
        tx = event.get("txType")
        sol = float(event.get("solAmount") or 0.0)
        trader = event.get("traderPublicKey") or ""
        self.v_sol = float(event.get("vSolInBondingCurve") or self.v_sol)
        self.v_tokens = float(event.get("vTokensInBondingCurve") or self.v_tokens)
        self.last_trade_at = now
        if tx == "buy":
            self.buys += 1
            self.real_sol_in_curve += sol
            if trader not in self.unique_buyers:
                self.first_buy_times.append(now)
                if trader and len(self.early_buyers) < 50:
                    self.early_buyers.append(trader)  # frühe Käufer in Reihenfolge (Insider-Kandidaten)
            self.unique_buyers.add(trader)
            self.buy_sol_by_wallet[trader] = self.buy_sol_by_wallet.get(trader, 0.0) + sol
            self._buy_n += 1
            self._buy_sum += sol
            self._buy_sumsq += sol * sol
        elif tx == "sell":
            self.sells += 1
            self.real_sol_in_curve -= sol
            if trader:
                self.sellers.add(trader)
            if trader and trader == self.creator:
                self.creator_sold = True

    # --- Mikrostruktur-Metriken (Bundle-/Wash-Signaturen) ---------------------
    def burst_buyer_share(self, window_seconds: float = 60.0) -> float:
        """Max. Anteil der Unique-Buyer, deren Erstkauf in EIN Zeitfenster fällt."""
        times = self.first_buy_times
        n = len(times)
        if n == 0:
            return 0.0
        best, left = 1, 0
        for right in range(n):
            while times[right] - times[left] > window_seconds:
                left += 1
            best = max(best, right - left + 1)
        return best / n

    def buy_size_cv(self) -> float | None:
        """Variationskoeffizient der Kaufgrößen; Bots kaufen unnatürlich uniform."""
        if self._buy_n < 5 or self._buy_sum <= 0:
            return None
        mean = self._buy_sum / self._buy_n
        var = max(0.0, self._buy_sumsq / self._buy_n - mean * mean)
        return (var ** 0.5) / mean

    def top_buyer_share(self, k: int = 3) -> float:
        """Anteil des Kauf-SOL der k größten Käufer-Wallets."""
        if not self.buy_sol_by_wallet:
            return 0.0
        volumes = sorted(self.buy_sol_by_wallet.values(), reverse=True)
        total = sum(volumes)
        return sum(volumes[:k]) / total if total > 0 else 0.0

    def roundtrip_share(self) -> float:
        """Anteil der Käufer, die auch verkauft haben (Wash-/Churn-Signatur)."""
        if not self.unique_buyers:
            return 0.0
        return len(self.unique_buyers & self.sellers) / len(self.unique_buyers)

    def early_seller_share(self, k: int = 20) -> float:
        """Anteil der k FRÜHESTEN Käufer, die bereits verkauft haben.

        Zielt auf den einzigen realen Pre-Graduation-Rug-Mechanismus (Deep
        Research, docs/loser-filter-recherche.md): Insider/Sniper aus Block 0/1
        akkumulieren billig und dumpen auf die Nachzügler. Verkaufen die
        frühesten Käufer schon, ist das ihr Ausstieg – man kauft in ihren Dump.
        Kausal (nur bisher gesehene Käufe/Verkäufe), aus dem reinen Log-Strom."""
        early = self.early_buyers[:k]
        if not early:
            return 0.0
        return sum(1 for w in early if w in self.sellers) / len(early)


def simulate_buy(state: CurveState, sol_in: float, fee: float = CURVE_FEE) -> tuple[float, float]:
    """Simulierter Kauf: (erhaltene Tokens, effektiv gezahltes SOL inkl. Fee).

    Konstantprodukt: k = vSol * vTokens; tokens_out = vTokens - k/(vSol + sol_net).
    """
    if state.v_sol <= 0 or state.v_tokens <= 0 or sol_in <= 0:
        return 0.0, 0.0
    sol_net = sol_in * (1.0 - fee)
    k = state.v_sol * state.v_tokens
    tokens_out = state.v_tokens - k / (state.v_sol + sol_net)
    return tokens_out, sol_in


def simulate_sell(state: CurveState, tokens_in: float, fee: float = CURVE_FEE) -> float:
    """Simulierter Verkauf: erhaltenes SOL nach Fee."""
    if state.v_sol <= 0 or state.v_tokens <= 0 or tokens_in <= 0:
        return 0.0
    k = state.v_sol * state.v_tokens
    sol_out = state.v_sol - k / (state.v_tokens + tokens_in)
    return sol_out * (1.0 - fee)
