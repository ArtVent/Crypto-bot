"""Tests der Regel-Engine: Die K.-o.-Liste aus docs/filter-engine.md muss greifen.

Testfälle nach dem Muster aus docs/bot-architektur.md, Abschnitt 7:
bekannte Scam-Konstellationen müssen DENY liefern, saubere Reports ALLOW.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memescan.engine import evaluate
from memescan.models import TokenReport, Verdict


def clean_report(**overrides) -> TokenReport:
    base = dict(
        address="TESTMINT",
        chain="solana",
        name="Testcoin",
        symbol="TEST",
        mint_authority_revoked=True,
        freeze_authority_revoked=True,
        metadata_mutable=False,
        top10_holder_pct=12.0,
        liquidity_usd=50_000.0,
        market_cap_usd=500_000.0,
        lp_locked_pct=100.0,
        rugcheck_score_normalised=5.0,
    )
    base.update(overrides)
    return TokenReport(**base)


def test_clean_token_allows():
    result = evaluate(clean_report())
    assert result.verdict == Verdict.ALLOW
    assert result.score == 0


def test_active_mint_authority_denies():
    result = evaluate(clean_report(mint_authority_revoked=False))
    assert result.verdict == Verdict.DENY
    assert any(f.code == "mint_authority" for f in result.flags)


def test_active_freeze_authority_denies():
    assert evaluate(clean_report(freeze_authority_revoked=False)).verdict == Verdict.DENY


def test_permanent_delegate_denies():
    # Token-2022 Burn-after-Buy-Muster (docs/filter-engine.md, 6b)
    assert evaluate(clean_report(permanent_delegate=True)).verdict == Verdict.DENY


def test_honeypot_denies():
    assert evaluate(clean_report(chain="ethereum", is_honeypot=True)).verdict == Verdict.DENY


def test_prohibitive_sell_tax_denies():
    assert evaluate(clean_report(chain="bsc", sell_tax_pct=95.0)).verdict == Verdict.DENY


def test_moderate_sell_tax_warns():
    result = evaluate(clean_report(chain="bsc", sell_tax_pct=12.0))
    assert result.verdict == Verdict.WARN
    assert any(f.code == "sell_tax" for f in result.flags)


def test_unlocked_lp_denies():
    assert evaluate(clean_report(lp_locked_pct=10.0)).verdict == Verdict.DENY


def test_holder_concentration_thresholds():
    assert evaluate(clean_report(top10_holder_pct=45.0)).verdict == Verdict.DENY
    assert evaluate(clean_report(top10_holder_pct=25.0)).verdict == Verdict.WARN
    assert evaluate(clean_report(top10_holder_pct=12.0)).verdict == Verdict.ALLOW


def test_mc_liquidity_ratio():
    # MC/Liq = 200 -> Preis-Illusion, DENY (docs/filter-engine.md K.-o. via Thresholds)
    assert evaluate(clean_report(market_cap_usd=10_000_000.0, liquidity_usd=50_000.0)).verdict == Verdict.DENY
    # MC/Liq = 40 -> WARN
    assert evaluate(clean_report(market_cap_usd=2_000_000.0, liquidity_usd=50_000.0)).verdict == Verdict.WARN


def test_serial_creator_denies():
    result = evaluate(clean_report(creator_prior_launches=25, creator_prior_rugs=3))
    assert result.verdict == Verdict.DENY
    assert any(f.code == "serial_creator" for f in result.flags)


def test_unknown_mint_authority_warns_not_allows():
    # Unbekannt darf NIE als sicher gelten (docs/filter-engine.md, Grundsatz)
    result = evaluate(clean_report(mint_authority_revoked=None))
    assert result.verdict == Verdict.WARN
    assert any(f.code == "mint_authority_unknown" for f in result.flags)


def test_rugged_flag_denies():
    assert evaluate(clean_report(external_rugged_flag=True)).verdict == Verdict.DENY
