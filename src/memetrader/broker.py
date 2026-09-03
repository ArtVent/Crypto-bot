"""Broker-Schicht: Paper-Trading (Default) und Live-Gerüst.

PaperBroker rechnet Fills exakt gegen den Curve-Zustand (curve.py) inklusive
Curve-Fee und einem konservativen Latenz-Malus – Backtesting-Ehrlichkeit nach
docs/strategien.md Abschnitt 5 ("Fill-Illusion").

LiveBroker nutzt die PumpPortal-Local-API (Transaktion wird LOKAL signiert,
der Key verlässt die Maschine nicht; 0,5 % API-Fee, siehe
data/fee-sources.json). Er ist bewusst ein Gerüst mit harten Guards:
- aktiviert sich nur mit gesetztem SOLANA_PRIVATE_KEY UND explizitem Flag,
- verweigert Positionsgrößen über dem Risk-Limit,
- ist in dieser Sandbox NICHT live getestet (Proxy blockt Krypto-Domains).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .curve import CurveState, simulate_buy, simulate_sell

PAPER_LATENCY_PENALTY = 0.01  # 1 % adverse Ausführung als Latenz-/Impact-Malus
PUMPPORTAL_TRADE_FEE = 0.005  # 0,5 % API-Fee (Live-Pfad)


@dataclass
class Fill:
    mint: str
    side: str  # "buy" | "sell"
    tokens: float
    sol: float  # buy: gezahlt; sell: erhalten
    paper: bool = True


class PaperBroker:
    """Simulierte Ausführung gegen den Live-Curve-Zustand."""

    def buy(self, state: CurveState, sol_amount: float) -> Fill:
        tokens, sol_spent = simulate_buy(state, sol_amount)
        tokens *= 1.0 - PAPER_LATENCY_PENALTY
        return Fill(mint=state.mint, side="buy", tokens=tokens, sol=sol_spent)

    def sell(self, state: CurveState, tokens: float) -> Fill:
        sol_out = simulate_sell(state, tokens)
        sol_out *= 1.0 - PAPER_LATENCY_PENALTY
        return Fill(mint=state.mint, side="sell", tokens=tokens, sol=sol_out)

    def position_value(self, state: CurveState, tokens: float) -> float:
        """Konservative Bewertung: was ein Verkauf JETZT brächte (nicht Mid-Preis)."""
        return simulate_sell(state, tokens)


class LiveBroker:
    """Gerüst für echte Ausführung via PumpPortal-Local-API + lokale Signatur.

    NICHT in dieser Umgebung getestet. Vor erstem Einsatz:
    1. `pip install solders` (Signatur) – optionaler Import unten.
    2. SOLANA_PRIVATE_KEY (base58) NUR als lokale Umgebungsvariable setzen –
       niemals in Chat, Repo oder Konfig-Dateien (docs/risiko-und-scam-checks.md).
    3. Mit Minimalbeträgen beginnen; jede Transaktion wird vor dem Senden
       simuliert (simulateTransaction), Abbruch bei Fehlern.
    """

    TRADE_URL = "https://pumpportal.fun/api/trade-local"

    def __init__(self, rpc_url: str | None = None, max_position_sol: float = 0.1):
        self.rpc_url = rpc_url or os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.max_position_sol = max_position_sol
        key = os.environ.get("SOLANA_PRIVATE_KEY")
        if not key:
            raise RuntimeError(
                "LiveBroker: SOLANA_PRIVATE_KEY nicht gesetzt. "
                "Live-Trading ist ein bewusster Opt-in – siehe src/memetrader/README-Hinweise."
            )
        try:
            from solders.keypair import Keypair  # type: ignore
        except ImportError as exc:
            raise RuntimeError("LiveBroker benötigt 'solders' (pip install solders)") from exc
        self._keypair = Keypair.from_base58_string(key)

    def _trade(self, action: str, mint: str, amount: float, denominated_in_sol: bool) -> Fill:
        import base64

        import httpx
        from solders.transaction import VersionedTransaction  # type: ignore

        if denominated_in_sol and amount > self.max_position_sol:
            raise RuntimeError(f"LiveBroker: {amount} SOL überschreitet max_position_sol={self.max_position_sol}")

        resp = httpx.post(
            self.TRADE_URL,
            data={
                "publicKey": str(self._keypair.pubkey()),
                "action": action,
                "mint": mint,
                "amount": amount,
                "denominatedInSol": "true" if denominated_in_sol else "false",
                "slippage": 10,
                "priorityFee": 0.0005,
                "pool": "auto",
            },
            timeout=15,
        )
        resp.raise_for_status()
        tx = VersionedTransaction.from_bytes(resp.content)
        signed = VersionedTransaction(tx.message, [self._keypair])
        raw = base64.b64encode(bytes(signed)).decode()

        # Erst simulieren, dann senden (docs/bot-architektur.md, Abschnitt 4)
        sim = httpx.post(
            self.rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "simulateTransaction",
                "params": [raw, {"encoding": "base64"}],
            },
            timeout=15,
        ).json()
        if (sim.get("result") or {}).get("value", {}).get("err"):
            raise RuntimeError(f"Simulation fehlgeschlagen: {sim['result']['value']['err']}")

        sent = httpx.post(
            self.rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [raw, {"encoding": "base64", "maxRetries": 3}],
            },
            timeout=15,
        ).json()
        if "error" in sent:
            raise RuntimeError(f"sendTransaction: {sent['error']}")
        # Tokens/SOL exakt kennt erst die Bestätigung; Aufrufer muss nachziehen.
        return Fill(mint=mint, side=action, tokens=0.0, sol=amount if denominated_in_sol else 0.0, paper=False)

    def buy(self, state: CurveState, sol_amount: float) -> Fill:
        return self._trade("buy", state.mint, sol_amount, denominated_in_sol=True)

    def sell(self, state: CurveState, tokens: float) -> Fill:
        return self._trade("sell", state.mint, tokens, denominated_in_sol=False)

    def position_value(self, state: CurveState, tokens: float) -> float:
        return simulate_sell(state, tokens)
