"""Tests für Simulator und Backtest-Harness."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.backtest import StubClaudeWorker, run_backtest
from memetrader.mlfilter import fetch_token_metadata
from memetrader.risk import RiskConfig, RiskManager
from memetrader.simulate import generate_market


def test_market_generation_is_deterministic():
    a = generate_market(days=1, launches_per_day=50, seed=7)
    b = generate_market(days=1, launches_per_day=50, seed=7)
    assert len(a) == len(b) and a[0] == b[0] and a[-1] == b[-1]
    c = generate_market(days=1, launches_per_day=50, seed=8)
    assert len(c) != len(a) or c[0] != a[0]


def test_market_base_rates_roughly_calibrated():
    events = generate_market(days=2, launches_per_day=1000, seed=3)
    creates = sum(1 for _, e in events if e.get("txType") == "create")
    migrations = sum(1 for _, e in events if e.get("txType") == "migrate")
    assert creates == 2000
    # Graduation-Rate im Bereich der realen Basisraten (~0,2–2,5 %)
    assert 0.002 <= migrations / creates <= 0.025
    # Events sind chronologisch
    times = [t for t, _ in events]
    assert times == sorted(times)


def test_data_uri_metadata_parsing():
    meta = fetch_token_metadata('data:application/json,{"telegram": "https://t.me/x", "twitter": null}')
    assert meta["telegram"] == "https://t.me/x"
    assert fetch_token_metadata("data:application/json,kaputt") == {}
    assert fetch_token_metadata("sim://meta") == {}


def test_stub_vet_vetoes_impersonation():
    worker = StubClaudeWorker()
    worker.submit_vet("M1", {"name": "Pepe", "symbol": "PEPE"}, {})
    worker.submit_vet("M2", {"name": "Mozaki", "symbol": "MOZA"}, {})
    results = {p.mint: p for k, p in worker.drain() if k == "vet"}
    assert results["M1"].verdict == "veto"
    assert results["M2"].verdict == "ok"


def test_backtest_smoke_and_determinism(tmp_path):
    kwargs = dict(days=2.0, launches_per_day=150, budget_sol=1.0,
                  workdir=tmp_path, ml_model=None, claude="stub")
    r1 = run_backtest(seed=11, **kwargs)
    r2 = run_backtest(seed=11, **kwargs)
    assert r1.final_equity_sol == r2.final_equity_sol
    assert r1.n_closed == r2.n_closed
    # Budget-Deckel: Verlust kann nie das Startkapital übersteigen
    assert r1.final_equity_sol >= 0.0
    assert r1.launches == 300


def test_daily_killswitch_resets():
    rm = RiskManager(RiskConfig(daily_loss_stop_sol=0.03))
    pos = rm.open_position("M1", "X", 1000.0, 0.05, now=0.0)
    rm.record_sell(pos, 1000.0, 0.01)  # -0.04 -> halt
    assert rm.halted
    rm.reset_day()
    assert not rm.halted and rm.daily_realized_pnl_sol == 0.0
    assert rm.realized_pnl_sol < 0  # Gesamt-PnL bleibt erhalten
