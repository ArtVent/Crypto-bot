"""Regel-Engine: K.-o.-Regeln und Risiko-Score.

Implementiert die K.-o.-Liste und die Score-Logik aus docs/filter-engine.md
(Abschnitt 3): harte DENY-Regeln zuerst, dann gewichtete WARN-Flags zu einem
0-100-Score. Schwellen sind bewusst zentral konfigurierbar (Thresholds), damit
sie gegen die eigene Outcome-Statistik kalibriert werden können.

Grundsatz: None = unbekannt. Sicherheitskritische Unbekannte (Authorities,
LP-Status bei relevanter Liquidität) werden als Warnung behandelt, nie als
"wird schon passen".
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RiskFlag, Severity, TokenReport, Verdict, VerdictResult


@dataclass
class Thresholds:
    top10_deny_pct: float = 30.0
    top10_warn_pct: float = 20.0
    insider_deny_pct: float = 30.0
    insider_warn_pct: float = 10.0
    lp_locked_min_pct: float = 90.0
    liquidity_min_usd: float = 10_000.0
    mc_liq_warn_ratio: float = 30.0
    mc_liq_deny_ratio: float = 100.0
    transfer_fee_warn_pct: float = 5.0
    sell_tax_deny_pct: float = 30.0
    sell_tax_warn_pct: float = 10.0
    creator_serial_deny: int = 10  # Launches ohne Erfolg
    external_score_warn: float = 60.0  # RugCheck score_normalised


DEFAULTS = Thresholds()


def _danger(code: str, msg: str, value: str | None = None) -> RiskFlag:
    return RiskFlag(code=code, severity=Severity.DANGER, message=msg, value=value)


def _warn(code: str, msg: str, value: str | None = None) -> RiskFlag:
    return RiskFlag(code=code, severity=Severity.WARN, message=msg, value=value)


def evaluate(report: TokenReport, t: Thresholds = DEFAULTS) -> VerdictResult:
    flags: list[RiskFlag] = []

    # --- K.-o.-Regeln (DENY) -------------------------------------------------
    if report.mint_authority_revoked is False:
        flags.append(_danger("mint_authority", "Mint-Authority aktiv – Supply kann nachgemintet werden"))
    if report.freeze_authority_revoked is False:
        flags.append(_danger("freeze_authority", "Freeze-Authority aktiv – Wallets können eingefroren werden"))
    if report.permanent_delegate:
        flags.append(_danger("permanent_delegate", "Token-2022 PermanentDelegate – fremde Token konfiszierbar"))
    if report.transfer_hook:
        flags.append(_danger("transfer_hook", "Token-2022 TransferHook – fremder Code im Transfer-Pfad"))
    if report.default_account_frozen:
        flags.append(_danger("default_frozen", "DefaultAccountState=Frozen – Käufer erhalten eingefrorene Token"))
    if report.is_honeypot:
        flags.append(_danger("honeypot", "Honeypot – Verkauf blockiert"))
    if report.sell_tax_pct is not None and report.sell_tax_pct >= t.sell_tax_deny_pct:
        flags.append(_danger("sell_tax", "Verkaufssteuer prohibitiv", f"{report.sell_tax_pct:.0f}%"))
    if report.external_rugged_flag:
        flags.append(_danger("rugged", "Provider markiert Token als gerugt"))

    if (
        report.lp_locked_pct is not None
        and report.lp_locked_pct < t.lp_locked_min_pct
        and (report.liquidity_usd or 0) > 0
    ):
        flags.append(
            _danger("lp_unlocked", "LP nicht ausreichend geburnt/gelockt", f"{report.lp_locked_pct:.0f}% gesichert")
        )

    if report.top10_holder_pct is not None and report.top10_holder_pct >= t.top10_deny_pct:
        flags.append(_danger("holder_concentration", "Top-10-Holder halten zu viel Supply", f"{report.top10_holder_pct:.0f}%"))

    if report.insider_networks_pct is not None and report.insider_networks_pct >= t.insider_deny_pct:
        flags.append(_danger("insider_networks", "Insider-Cluster halten zu viel Supply", f"{report.insider_networks_pct:.0f}%"))

    if (
        report.creator_prior_launches is not None
        and report.creator_prior_launches >= t.creator_serial_deny
        and (report.creator_prior_rugs or 0) > 0
    ):
        flags.append(
            _danger(
                "serial_creator",
                "Serien-Creator mit Rug-Historie",
                f"{report.creator_prior_launches} Launches, {report.creator_prior_rugs} Rugs",
            )
        )

    if (
        report.market_cap_usd is not None
        and report.liquidity_usd
        and report.market_cap_usd / report.liquidity_usd >= t.mc_liq_deny_ratio
    ):
        flags.append(
            _danger("mc_liq_ratio", "Market Cap zur Liquidität absurd", f"{report.market_cap_usd / report.liquidity_usd:.0f}x")
        )

    # --- Warn-Regeln ----------------------------------------------------------
    if report.mint_authority_revoked is None:
        flags.append(_warn("mint_authority_unknown", "Mint-Authority-Status unbekannt – vor Trade prüfen"))
    if report.metadata_mutable:
        flags.append(_warn("metadata_mutable", "Metadaten änderbar – Umbenennungs-/Impersonations-Risiko"))
    if report.transfer_fee_pct is not None and report.transfer_fee_pct >= t.transfer_fee_warn_pct:
        flags.append(_warn("transfer_fee", "Token-2022-Transfer-Fee hoch", f"{report.transfer_fee_pct:.1f}%"))
    if report.transfer_fee_upgradable:
        flags.append(_warn("transfer_fee_upgradable", "Transfer-Fee nachträglich erhöhbar"))
    if report.sell_tax_pct is not None and t.sell_tax_warn_pct <= report.sell_tax_pct < t.sell_tax_deny_pct:
        flags.append(_warn("sell_tax", "Verkaufssteuer erhöht", f"{report.sell_tax_pct:.0f}%"))
    if report.tax_modifiable:
        flags.append(_warn("tax_modifiable", "Taxes vom Owner änderbar (Tax-Switch-Risiko)"))
    if report.owner_can_blacklist:
        flags.append(_warn("blacklist", "Blacklist-Funktion vorhanden"))
    if report.trading_pausable:
        flags.append(_warn("pausable", "Handel pausierbar"))
    if report.is_proxy:
        flags.append(_warn("proxy", "Upgradebarer Proxy-Contract"))
    if report.is_mintable:
        flags.append(_warn("mintable", "Owner kann minten (EVM)"))
    if report.liquidity_usd is not None and report.liquidity_usd < t.liquidity_min_usd:
        flags.append(_warn("low_liquidity", "Liquidität sehr niedrig", f"${report.liquidity_usd:,.0f}"))
    if (
        report.top10_holder_pct is not None
        and t.top10_warn_pct <= report.top10_holder_pct < t.top10_deny_pct
    ):
        flags.append(_warn("holder_concentration", "Top-10-Holder-Anteil erhöht", f"{report.top10_holder_pct:.0f}%"))
    if (
        report.insider_networks_pct is not None
        and t.insider_warn_pct <= report.insider_networks_pct < t.insider_deny_pct
    ):
        flags.append(_warn("insider_networks", "Insider-Cluster erkannt", f"{report.insider_networks_pct:.0f}%"))
    if (
        report.market_cap_usd is not None
        and report.liquidity_usd
        and t.mc_liq_warn_ratio <= report.market_cap_usd / report.liquidity_usd < t.mc_liq_deny_ratio
    ):
        flags.append(
            _warn("mc_liq_ratio", "Market Cap/Liquidität gespannt", f"{report.market_cap_usd / report.liquidity_usd:.0f}x")
        )
    if (
        report.rugcheck_score_normalised is not None
        and report.rugcheck_score_normalised >= t.external_score_warn
    ):
        flags.append(_warn("external_score", "Externer Risiko-Score hoch", f"RugCheck {report.rugcheck_score_normalised:.0f}/100"))
    if (report.creator_prior_rugs or 0) > 0 and not any(f.code == "serial_creator" for f in flags):
        flags.append(_warn("creator_rug_history", "Creator hat Rug-Historie", f"{report.creator_prior_rugs} Rugs"))

    # Provider-Flags durchreichen (nur informativ, keine Doppel-Wertung)
    flags.extend(report.provider_flags)

    # --- Verdict + Score ------------------------------------------------------
    dangers = [f for f in flags if f.severity == Severity.DANGER]
    warns = [f for f in flags if f.severity == Severity.WARN]

    if dangers:
        verdict = Verdict.DENY
    elif len(warns) >= 3:
        verdict = Verdict.WARN
    elif warns:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.ALLOW

    score = min(100, len(dangers) * 40 + len(warns) * 10)
    return VerdictResult(address=report.address, chain=report.chain, verdict=verdict, score=score, flags=flags, report=report)
