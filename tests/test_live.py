"""Tests für den durchgehenden Live-Modus (netzfrei: nur Zustandslogik)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.live import LiveState, liquidate_open
from tests.test_memetrader import SimCurve, feed_healthy_curve, make_bot


def test_livestate_roundtrip_and_carry(tmp_path):
    p = tmp_path / "live-state.json"
    LiveState(realized_pnl_sol=0.1234, sessions=2, total_entries=9).save(p, budget_sol=1.0)
    s = LiveState.load(p)
    assert abs(s.realized_pnl_sol - 0.1234) < 1e-9 and s.sessions == 2 and s.total_entries == 9
    # fehlende Datei -> Nullzustand
    assert LiveState.load(tmp_path / "missing.json").realized_pnl_sol == 0.0


def test_liquidate_open_flattens_into_realized(tmp_path):
    bot = make_bot(tmp_path)
    sim = SimCurve(mint="LQ", creator="dev", symbol="LQ")
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "late"), now=max(t, 50.0))
    assert "LQ" in bot.risk.positions
    pnl_before = bot.risk.realized_pnl_sol
    liq = liquidate_open(bot, now=max(t, 50.0) + 5)
    assert "LQ" not in bot.risk.positions            # flach nach Session-Ende
    assert liq > 0 and bot.risk.realized_pnl_sol != pnl_before
    assert any(r.mint == "LQ" for r in bot.journal.finalized)  # im Journal erfasst


def test_evening_report_and_new_state_fields(tmp_path):
    from memetrader.live import LiveState, evening_report
    p = tmp_path / "s.json"
    st = LiveState(realized_pnl_sol=0.25, sessions=3, total_entries=12,
                   last_report_day=2026250, day_start_realized=0.2, day_entries=4)
    st.save(p, budget_sol=1.0)
    r = LiveState.load(p)
    assert r.last_report_day == 2026250 and r.day_entries == 4 and abs(r.day_start_realized - 0.2) < 1e-9
    txt = evening_report(r, budget_sol=1.0)
    assert "Abendbericht" in txt and "4 Trades heute" in txt and "+25.00%" in txt
    # Tages-PnL = realized - day_start = 0.25 - 0.2 = +0.05
    assert "+0.0500 SOL heute" in txt
