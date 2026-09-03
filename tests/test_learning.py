"""Tests der Lern-Schicht: Lektionen, Selbst-Kalibrierung, Berater-Guards, Bot-Loop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.adaptive import AdaptiveTuner
from memetrader.advisor import apply_proposals, parse_advisor_response
from memetrader.journal import EntryContext, Journal, TradeRecord, classify_lesson
from memetrader.risk import RiskConfig
from memetrader.strategy import StrategyConfig
from tests.test_memetrader import SimCurve, feed_healthy_curve, make_bot


def record(reason, cost=0.05, proceeds=0.03, peak=0.0, held=300.0):
    r = TradeRecord(mint="M", symbol="X", entered_t=0.0, cost_sol=cost, tokens=1000.0)
    r.exits = [{"t": held, "reason": reason, "fraction": 1.0, "sol": proceeds}]
    r.proceeds_sol = proceeds
    r.closed_t = held
    r.post_peak_value_sol = peak
    r.pnl_sol = proceeds - cost
    return r


# --- Lektions-Klassifikation --------------------------------------------------

def test_good_stop_vs_shaken_out():
    assert classify_lesson(record("stop_loss", peak=0.01)) == "good_stop"
    assert classify_lesson(record("stop_loss", peak=0.08)) == "shaken_out"


def test_fast_loss_is_bad_entry():
    assert classify_lesson(record("stop_loss", peak=0.01, held=60.0)) == "bad_entry"


def test_impatient_and_sold_too_early():
    assert classify_lesson(record("time_stop", proceeds=0.05, peak=0.09)) == "impatient"
    assert classify_lesson(record("time_stop", proceeds=0.05, peak=0.05)) == "good_time_stop"
    assert classify_lesson(record("take_profit", proceeds=0.12, peak=0.30)) == "sold_too_early"
    assert classify_lesson(record("take_profit", proceeds=0.12, peak=0.13)) == "good_take_profit"


def test_creator_exit_lessons():
    assert classify_lesson(record("creator_sold", peak=0.09)) == "overreacted_creator_exit"
    assert classify_lesson(record("creator_sold", peak=0.01)) == "good_creator_exit"


# --- Journal-Lebenszyklus -----------------------------------------------------

def test_journal_lifecycle_and_persistence(tmp_path):
    journal = Journal(tmp_path / "j.jsonl", post_exit_watch_seconds=100.0)
    journal.on_entry("M1", "X", 1000.0, 0.05, EntryContext(fill_pct=20.0), now=0.0)
    journal.on_exit("M1", "stop_loss", 1.0, 0.03, position_closed=True, now=300.0)
    assert "M1" in journal.watching
    journal.on_post_exit_value("M1", 0.02)
    journal.on_post_exit_value("M1", 0.09)  # Erholung -> shaken_out
    assert journal.finalize_due(now=350.0) == []  # Fenster noch offen
    done = journal.finalize_due(now=401.0)
    assert len(done) == 1 and done[0].lesson == "shaken_out"
    assert (tmp_path / "j.jsonl").exists()


# --- Selbst-Kalibrierung ------------------------------------------------------

def make_tuner():
    return AdaptiveTuner(StrategyConfig(), RiskConfig(), state_path="/dev/null")


def finalized(lesson, n, **kw):
    out = []
    for _ in range(n):
        r = record({"shaken_out": "stop_loss", "impatient": "time_stop",
                    "sold_too_early": "take_profit", "bad_entry": "stop_loss",
                    "good_stop": "stop_loss"}[lesson], **kw)
        r.lesson = lesson
        out.append(r)
    return out


def test_tuner_widens_stop_on_shakeouts_bounded(tmp_path):
    tuner = AdaptiveTuner(StrategyConfig(), RiskConfig(), tmp_path / "t.json")
    old = tuner.risk.stop_loss_pct
    adjustments = tuner.on_trades_finalized(finalized("shaken_out", 4), now=1.0)
    assert tuner.risk.stop_loss_pct == old - 5.0
    assert adjustments and adjustments[0].param == "stop_loss_pct"
    # Bound: nie unter -50
    for _ in range(20):
        tuner.on_trades_finalized(finalized("shaken_out", 4), now=2.0)
    assert tuner.risk.stop_loss_pct >= -50.0


def test_tuner_needs_evidence(tmp_path):
    tuner = AdaptiveTuner(StrategyConfig(), RiskConfig(), tmp_path / "t.json")
    old = tuner.risk.stop_loss_pct
    tuner.on_trades_finalized(finalized("shaken_out", 2), now=1.0)  # < MIN_EVIDENCE
    assert tuner.risk.stop_loss_pct == old


def test_tuner_tightens_entry_on_bad_entries(tmp_path):
    tuner = AdaptiveTuner(StrategyConfig(), RiskConfig(), tmp_path / "t.json")
    tuner.on_trades_finalized(finalized("bad_entry", 3, held=60.0), now=1.0)
    assert tuner.strategy.min_fill_pct == 15.0
    assert tuner.strategy.min_unique_buyers == 13


def test_drawdown_scaling_and_recovery(tmp_path):
    import pytest

    tuner = AdaptiveTuner(StrategyConfig(), RiskConfig(position_sol=0.05), tmp_path / "t.json")
    for _ in range(3):
        tuner.on_trade_result(-0.02)
    assert tuner.risk.position_sol == pytest.approx(0.05 * 0.75)
    for _ in range(2):
        tuner.on_trade_result(-0.02)
    assert tuner.risk.position_sol == pytest.approx(0.05 * 0.5)
    for _ in range(4):
        tuner.on_trade_result(+0.03)
    assert tuner.risk.position_sol == pytest.approx(0.05)  # wieder voll


# --- Berater-Guards -----------------------------------------------------------

def test_advisor_parse_and_bounded_apply(tmp_path):
    review = parse_advisor_response(
        'Hier die Analyse: {"analysis": "ok", "proposals": ['
        '{"param": "stop_loss_pct", "value": -99, "reason": "extrem"},'
        '{"param": "budget_sol", "value": 100, "reason": "boese"},'
        '{"param": "take_profit_pct", "value": 300, "reason": "laufen lassen"}]}'
    )
    tuner = AdaptiveTuner(StrategyConfig(), RiskConfig(), tmp_path / "t.json")
    lines = apply_proposals(review["proposals"], tuner)
    assert tuner.risk.stop_loss_pct == -50.0  # auf Bound gekappt, nicht -99
    assert tuner.risk.take_profit_pct == 300.0
    assert any("ABGELEHNT budget_sol" in l for l in lines)  # nicht in erlaubter Liste


# --- Bot-Integration: kompletter Lern-Loop ------------------------------------

def learn_bot(tmp_path):
    bot = make_bot(tmp_path)
    bot.config.journal_path = str(tmp_path / "journal.jsonl")
    bot.config.tuning_path = str(tmp_path / "tuning.json")
    from memetrader.journal import Journal as J

    bot.journal = J(bot.config.journal_path, post_exit_watch_seconds=120.0)
    bot.tuner.state_path = Path(bot.config.tuning_path)
    return bot


def test_bot_full_learning_loop_shaken_out(tmp_path):
    bot = learn_bot(tmp_path)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "late"), now=max(t, 50.0))
    assert sim.mint in bot.risk.positions
    # Crash weit unter Stop (langsam genug, dass es kein bad_entry ist)
    for i in range(6):
        bot.on_event(sim.sell_event(2.0, f"dumper{i}"), now=400.0 + i)
        if sim.mint not in bot.risk.positions:
            break
    assert sim.mint in bot.journal.watching
    # Erholung im Post-Exit-Fenster -> shaken_out
    for i in range(10):
        bot.on_event(sim.buy_event(3.0, f"rebuyer{i}"), now=410.0 + i)
    # Fenster ablaufen lassen (Event auf anderem Mint triggert finalize)
    other = SimCurve(mint="OTHER", symbol="OTH")
    bot.on_event(other.create_event(), now=700.0)
    records = bot.journal.finalized
    assert len(records) == 1
    assert records[0].lesson == "shaken_out"
    assert records[0].context.unique_buyers >= 10  # Entry-Kontext gespeichert
    log = (tmp_path / "log.jsonl").read_text()
    assert '"lesson"' in log


def test_trailing_and_hold_through_migration(tmp_path):
    from memetrader.risk import ExitReason, RiskConfig, RiskManager

    rm = RiskManager(RiskConfig(hold_through_migration=True, trailing_stop_pct=30.0))
    pos = rm.open_position("M1", "X", 1000.0, 0.05, now=0.0)
    # Migriert + im Plus: KEIN Sofort-Exit mehr
    assert rm.check_exit(pos, value_sol=0.08, creator_sold=False, migrated=True, now=100.0) is None
    # Peak +100 %, dann Rückfall auf +60 % -> Trailing (40 Punkte unter Peak)
    rm.check_exit(pos, value_sol=0.10, creator_sold=False, migrated=True, now=200.0)
    action = rm.check_exit(pos, value_sol=0.08, creator_sold=False, migrated=True, now=300.0)
    assert action and action.reason == ExitReason.TRAILING_STOP


def test_tuner_loosens_when_clean(tmp_path):
    from memetrader.adaptive import AdaptiveTuner
    from memetrader.risk import RiskConfig
    from memetrader.strategy import StrategyConfig

    strat = StrategyConfig(min_fill_pct=20.0, min_unique_buyers=16)
    tuner = AdaptiveTuner(strat, RiskConfig(), tmp_path / "t.json")
    window = []
    for _ in range(9):
        r = record("stop_loss", peak=0.01)
        r.lesson = "good_stop"
        window.append(r)
    tuner.on_trades_finalized(window, now=1.0)
    assert strat.min_fill_pct == 17.5
    assert strat.min_unique_buyers == 14
