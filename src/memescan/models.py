"""Datenmodelle der Filter-Engine.

TokenReport ist die provider-neutrale Zwischenschicht: Jeder Provider
(RugCheck, GoPlus, eigener RPC-Check) normalisiert seine Antwort in dieses
Modell; die Engine entscheidet ausschließlich auf dem Modell. Fehlende Werte
sind None ("unbekannt") und werden von den Regeln explizit behandelt –
unbekannt ist NICHT dasselbe wie sicher (docs/filter-engine.md, Abschnitt 4.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    DANGER = "danger"


class Verdict(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    DENY = "deny"


@dataclass
class RiskFlag:
    code: str
    severity: Severity
    message: str
    value: Optional[str] = None
    source: str = "memescan"


@dataclass
class TokenReport:
    """Provider-neutraler Prüfbericht eines Tokens."""

    address: str
    chain: str  # "solana" | "ethereum" | "base" | "bsc" | ...
    name: Optional[str] = None
    symbol: Optional[str] = None

    # Contract-Ebene (Solana: Authorities; EVM: Owner-Rechte)
    mint_authority_revoked: Optional[bool] = None
    freeze_authority_revoked: Optional[bool] = None
    metadata_mutable: Optional[bool] = None
    # Token-2022 / EVM-Sonderrechte
    permanent_delegate: Optional[bool] = None
    transfer_hook: Optional[bool] = None
    transfer_fee_pct: Optional[float] = None
    transfer_fee_upgradable: Optional[bool] = None
    default_account_frozen: Optional[bool] = None
    # EVM-spezifisch
    is_honeypot: Optional[bool] = None
    buy_tax_pct: Optional[float] = None
    sell_tax_pct: Optional[float] = None
    tax_modifiable: Optional[bool] = None
    owner_can_blacklist: Optional[bool] = None
    trading_pausable: Optional[bool] = None
    is_proxy: Optional[bool] = None
    is_mintable: Optional[bool] = None

    # Verteilung
    top10_holder_pct: Optional[float] = None  # bereinigt um LP/Burn/CEX soweit möglich
    insider_networks_pct: Optional[float] = None  # Supply-Anteil erkannter Insider-Ringe
    creator_holdings_pct: Optional[float] = None

    # Creator-Historie
    creator_prior_launches: Optional[int] = None
    creator_prior_rugs: Optional[int] = None

    # Liquidität
    liquidity_usd: Optional[float] = None
    lp_locked_pct: Optional[float] = None
    market_cap_usd: Optional[float] = None

    # Externe Scores (als Feature, nie als Entscheidung)
    rugcheck_score_normalised: Optional[float] = None  # 0-100, hoch = schlecht
    external_rugged_flag: Optional[bool] = None

    # Vom Provider mitgelieferte Roh-Risiken (durchgereicht)
    provider_flags: list[RiskFlag] = field(default_factory=list)

    sources: list[str] = field(default_factory=list)


@dataclass
class VerdictResult:
    address: str
    chain: str
    verdict: Verdict
    score: int  # 0 (sauber) .. 100 (maximal riskant), regelbasiert
    flags: list[RiskFlag]
    report: TokenReport

    def summary(self) -> str:
        lines = [
            f"{self.report.name or '?'} ({self.report.symbol or '?'}) [{self.chain}]",
            f"  Adresse : {self.address}",
            f"  Verdict : {self.verdict.value.upper()}  (Risiko-Score {self.score}/100)",
        ]
        if self.report.liquidity_usd is not None:
            lines.append(f"  Liquidität: ${self.report.liquidity_usd:,.0f}")
        for f in sorted(self.flags, key=lambda x: x.severity != Severity.DANGER):
            marker = {"danger": "!!", "warn": " !", "info": "  "}[f.severity.value]
            val = f" ({f.value})" if f.value else ""
            lines.append(f"  [{marker}] {f.code}: {f.message}{val}")
        if not self.flags:
            lines.append("  keine Auffälligkeiten in den geprüften Kriterien")
        lines.append(f"  Quellen : {', '.join(self.report.sources) or 'keine'}")
        return "\n".join(lines)
