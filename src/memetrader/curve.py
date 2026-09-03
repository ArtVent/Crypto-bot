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
            self.unique_buyers.add(trader)
        elif tx == "sell":
            self.sells += 1
            self.real_sol_in_curve -= sol
            if trader and trader == self.creator:
                self.creator_sold = True


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
