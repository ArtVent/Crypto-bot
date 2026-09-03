"""Parser-Tests mit Fixture-Daten (kein Netzwerk in Tests)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memescan.engine import evaluate
from memescan.models import Verdict
from memescan.providers import parse_goplus, parse_rugcheck

RUGCHECK_SCAM_FIXTURE = {
    "mintAuthority": "SomeAuthorityPubkey111111111111111111111111",
    "freezeAuthority": None,
    "tokenMeta": {"name": "FakeCoin", "symbol": "FAKE", "mutable": True},
    "score_normalised": 78,
    "rugged": False,
    "totalMarketLiquidity": 900.0,
    "topHolders": [
        {"address": "A1", "pct": 22.0},
        {"address": "A2", "pct": 15.0},
        {"address": "LP1", "pct": 40.0},
    ],
    "knownAccounts": {"LP1": {"name": "Raydium Pool", "type": "AMM"}},
    "markets": [{"lp": {"lpLockedPct": 0.0}}],
    "creatorTokens": [{"mint": "m1"}, {"mint": "m2"}, {"mint": "m3"}],
    "risks": [
        {"name": "Mint Authority still enabled", "description": "Tokens can be minted", "level": "danger", "score": 5000},
        {"name": "Low Liquidity", "description": "Low amount of liquidity", "level": "warn", "score": 500},
    ],
    "transferFee": {"pct": 0, "maxAmount": 0, "authority": None},
}

GOPLUS_HONEYPOT_FIXTURE = {
    "token_name": "HoneyTrap",
    "token_symbol": "HONEY",
    "is_honeypot": "1",
    "buy_tax": "0.05",
    "sell_tax": "0.99",
    "slippage_modifiable": "1",
    "transfer_pausable": "0",
    "is_proxy": "",
    "is_mintable": "0",
    "honeypot_with_same_creator": "4",
    "holders": [{"percent": "0.30", "is_locked": "0"}, {"percent": "0.10", "is_locked": "0"}],
    "lp_holders": [{"percent": "1.0", "is_locked": "0"}],
}


def test_rugcheck_parser_maps_fields():
    report = parse_rugcheck("MINT1", RUGCHECK_SCAM_FIXTURE)
    assert report.mint_authority_revoked is False  # Authority gesetzt
    assert report.freeze_authority_revoked is True  # explizit null
    assert report.metadata_mutable is True
    # LP-Konto (AMM) fliegt aus der Top-10-Rechnung raus
    assert report.top10_holder_pct == 37.0
    assert report.lp_locked_pct == 0.0
    assert report.creator_prior_launches == 3
    assert report.rugcheck_score_normalised == 78
    assert any(f.source == "rugcheck" for f in report.provider_flags)


def test_rugcheck_scam_fixture_denies():
    result = evaluate(parse_rugcheck("MINT1", RUGCHECK_SCAM_FIXTURE))
    assert result.verdict == Verdict.DENY
    codes = {f.code for f in result.flags}
    assert "mint_authority" in codes
    assert "holder_concentration" in codes
    assert "lp_unlocked" in codes


def test_goplus_parser_maps_fields():
    report = parse_goplus("0xdead", "bsc", GOPLUS_HONEYPOT_FIXTURE)
    assert report.is_honeypot is True
    assert report.sell_tax_pct == 99.0
    assert report.tax_modifiable is True
    assert report.is_proxy is None  # "" = unbekannt, nicht False
    assert report.creator_prior_rugs == 4
    assert report.top10_holder_pct == 40.0


def test_goplus_honeypot_fixture_denies():
    result = evaluate(parse_goplus("0xdead", "bsc", GOPLUS_HONEYPOT_FIXTURE))
    assert result.verdict == Verdict.DENY
    codes = {f.code for f in result.flags}
    assert "honeypot" in codes
    assert "sell_tax" in codes


def test_archiver_roundtrip(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from memescan import archiver

    db = tmp_path / "test.db"
    conn = archiver.open_db(db)
    archiver.record_launch(
        conn,
        {
            "mint": "MINT_X",
            "txType": "create",
            "name": "Testy",
            "symbol": "TSTY",
            "traderPublicKey": "DEV1",
            "initialBuy": 1000000.0,
            "solAmount": 2.5,
            "marketCapSol": 30.0,
            "uri": "https://example/meta.json",
        },
    )
    # Duplikat wird ignoriert
    archiver.record_launch(conn, {"mint": "MINT_X", "txType": "create"})
    s = archiver.stats(db)
    assert s["total"] == 1
    assert s["by_label"] == {"unlabeled": 1}
