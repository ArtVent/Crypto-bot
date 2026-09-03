"""Provider-Clients: normalisieren externe APIs in das TokenReport-Modell.

Feld-Referenzen: data/detection-apis.json. Alle Clients sind bewusst tolerant
gegenüber fehlenden Feldern (None = unbekannt) und werfen nur bei
Transportfehlern. Externe Scores fließen als Feature ein, nie als Verdict
(docs/filter-engine.md, Abschnitt 6).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .models import RiskFlag, Severity, TokenReport

RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"
GOPLUS_BASE = "https://api.gopluslabs.io/api/v1"
DEXSCREENER_BASE = "https://api.dexscreener.com"

GOPLUS_CHAIN_IDS = {"ethereum": "1", "bsc": "56", "base": "8453"}

_TIMEOUT = httpx.Timeout(15.0)


def _pct(value: Any) -> Optional[float]:
    try:
        return float(value) * 100.0
    except (TypeError, ValueError):
        return None


def _bool01(value: Any) -> Optional[bool]:
    if value in ("1", 1, True):
        return True
    if value in ("0", 0, False):
        return False
    return None  # "" oder fehlend = unbekannt


def fetch_rugcheck(mint: str, client: httpx.Client | None = None) -> TokenReport:
    """Solana-Report via RugCheck /tokens/{mint}/report."""
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(f"{RUGCHECK_BASE}/tokens/{mint}/report")
        resp.raise_for_status()
        return parse_rugcheck(mint, resp.json())
    finally:
        if own:
            client.close()


def parse_rugcheck(mint: str, data: dict) -> TokenReport:
    meta = data.get("tokenMeta") or {}
    file_meta = data.get("fileMeta") or {}
    transfer_fee = data.get("transferFee") or {}

    # Top-10-Anteil: LP-/AMM-/Burn-Konten anhand knownAccounts aussortieren
    known = {addr: (info or {}).get("type", "") for addr, info in (data.get("knownAccounts") or {}).items()}
    skip_types = {"AMM", "LP", "BURN", "CEX"}
    holder_pcts = [
        h.get("pct", 0.0)
        for h in (data.get("topHolders") or [])
        if known.get(h.get("address", ""), "").upper() not in skip_types
    ]
    top10 = sum(sorted(holder_pcts, reverse=True)[:10]) if holder_pcts else None

    total_supply_insiders = sum(n.get("tokenAmount", 0) for n in (data.get("insiderNetworks") or []))
    insider_pct = None
    # insiderNetworks liefert absolute Mengen; ohne Supply-Kontext nur als Flag nutzen
    if data.get("graphInsidersDetected"):
        insider_pct = insider_pct  # Anteil unbekannt -> None lassen, Flag unten

    creator_tokens = data.get("creatorTokens") or []
    lp_locked = None
    liquidity = data.get("totalMarketLiquidity")
    markets = data.get("markets") or []
    if markets:
        lps = [((m.get("lp") or {}).get("lpLockedPct")) for m in markets]
        lps = [x for x in lps if x is not None]
        if lps:
            lp_locked = max(lps)

    provider_flags = [
        RiskFlag(
            code=f"rugcheck:{(r.get('name') or '?').lower().replace(' ', '_')}",
            severity=Severity.DANGER if r.get("level") == "danger" else Severity.WARN,
            message=r.get("description") or r.get("name") or "",
            source="rugcheck",
        )
        for r in (data.get("risks") or [])
        if r.get("level") in ("warn", "danger")
    ]
    if data.get("graphInsidersDetected"):
        provider_flags.append(
            RiskFlag(
                code="rugcheck:insider_graph",
                severity=Severity.WARN,
                message=f"Insider-Graph erkannt ({data.get('graphInsidersDetected')} Wallets, {total_supply_insiders} Token)",
                source="rugcheck",
            )
        )

    return TokenReport(
        address=mint,
        chain="solana",
        name=meta.get("name") or file_meta.get("name"),
        symbol=meta.get("symbol") or file_meta.get("symbol"),
        mint_authority_revoked=data.get("mintAuthority") is None if "mintAuthority" in data else None,
        freeze_authority_revoked=data.get("freezeAuthority") is None if "freezeAuthority" in data else None,
        metadata_mutable=meta.get("mutable"),
        transfer_fee_pct=transfer_fee.get("pct"),
        transfer_fee_upgradable=bool(transfer_fee.get("authority")) if transfer_fee else None,
        top10_holder_pct=top10,
        insider_networks_pct=insider_pct,
        creator_prior_launches=len(creator_tokens) or None,
        creator_prior_rugs=None,  # RugCheck liefert Historie, aber keine Rug-Zählung je Token
        liquidity_usd=liquidity,
        lp_locked_pct=lp_locked,
        rugcheck_score_normalised=data.get("score_normalised"),
        external_rugged_flag=data.get("rugged"),
        provider_flags=provider_flags,
        sources=["rugcheck"],
    )


def fetch_goplus(address: str, chain: str, client: httpx.Client | None = None) -> TokenReport:
    """EVM-Report via GoPlus token_security."""
    chain_id = GOPLUS_CHAIN_IDS.get(chain)
    if chain_id is None:
        raise ValueError(f"GoPlus: Chain '{chain}' nicht konfiguriert")
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(
            f"{GOPLUS_BASE}/token_security/{chain_id}", params={"contract_addresses": address}
        )
        resp.raise_for_status()
        payload = (resp.json().get("result") or {})
        data = payload.get(address.lower()) or payload.get(address) or {}
        return parse_goplus(address, chain, data)
    finally:
        if own:
            client.close()


def parse_goplus(address: str, chain: str, d: dict) -> TokenReport:
    holders = d.get("holders") or []
    top10 = sum(_pct(h.get("percent")) or 0.0 for h in holders[:10]) or None

    lp_holders = d.get("lp_holders") or []
    lp_locked = None
    if lp_holders:
        locked = sum(_pct(h.get("percent")) or 0.0 for h in lp_holders if _bool01(h.get("is_locked")))
        lp_locked = locked

    creator_rugs = None
    try:
        creator_rugs = int(d.get("honeypot_with_same_creator"))
    except (TypeError, ValueError):
        pass

    return TokenReport(
        address=address,
        chain=chain,
        name=d.get("token_name"),
        symbol=d.get("token_symbol"),
        is_honeypot=_bool01(d.get("is_honeypot")),
        buy_tax_pct=_pct(d.get("buy_tax")),
        sell_tax_pct=_pct(d.get("sell_tax")),
        tax_modifiable=_bool01(d.get("slippage_modifiable")),
        owner_can_blacklist=_bool01(d.get("is_blacklisted")),
        trading_pausable=_bool01(d.get("transfer_pausable")),
        is_proxy=_bool01(d.get("is_proxy")),
        is_mintable=_bool01(d.get("is_mintable")),
        top10_holder_pct=top10,
        lp_locked_pct=lp_locked,
        creator_prior_rugs=creator_rugs,
        creator_holdings_pct=_pct(d.get("creator_percent")),
        sources=["goplus"],
    )


def fetch_dexscreener_liquidity(address: str, client: httpx.Client | None = None) -> dict:
    """Liquidität/MC/Preis über DexScreener (kostenlos) – für Labeling und MC/Liq-Checks."""
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{address}")
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        if not pairs:
            return {"has_pair": False}
        best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0.0)
        return {
            "has_pair": True,
            "liquidity_usd": (best.get("liquidity") or {}).get("usd"),
            "market_cap_usd": best.get("marketCap") or best.get("fdv"),
            "price_usd": float(best["priceUsd"]) if best.get("priceUsd") else None,
            "volume_24h_usd": (best.get("volume") or {}).get("h24"),
            "dex": best.get("dexId"),
        }
    finally:
        if own:
            client.close()


def merge_reports(base: TokenReport, extra: TokenReport) -> TokenReport:
    """Füllt None-Felder von base mit Werten aus extra (base hat Vorrang)."""
    for field_name in base.__dataclass_fields__:
        if field_name in ("provider_flags", "sources"):
            continue
        if getattr(base, field_name) is None and getattr(extra, field_name) is not None:
            setattr(base, field_name, getattr(extra, field_name))
    base.provider_flags.extend(extra.provider_flags)
    base.sources.extend(s for s in extra.sources if s not in base.sources)
    return base
