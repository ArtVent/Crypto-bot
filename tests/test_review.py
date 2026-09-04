"""Tests für den täglichen Strategie-Review, v. a. die Evidenzregel."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.review import (append_history, daily_review, series_verdict)


def _report(insider_ret, ref_ret=1.0, closed=5, dd_ins=5.0, dd_ref=10.0):
    arm = lambda ret, dd: {"return_pct": ret, "closed": closed, "win_rate": 0.5,
                           "max_drawdown_pct": dd, "final_equity_sol": 1 + ret / 100}
    return {"span_hours": 0.75, "reference": arm(ref_ret, dd_ref),
            "density_cap": arm(ref_ret, dd_ref), "recycle_ladder": arm(ref_ret, dd_ref),
            "regime_gate": arm(ref_ret, dd_ref), "insider_exit": arm(insider_ret, dd_ins)}


def test_holds_below_min_days():
    series = [_report(insider_ret=3.0) for _ in range(5)]  # Insider besser, aber nur 5 Tage
    v = series_verdict(series)
    assert v["recommendation"]["action"] == "hold" and "reicht nicht" in v["recommendation"]["rationale"]


def test_adopts_with_enough_evidence():
    series = [_report(insider_ret=3.0) for _ in range(14)]  # 14 Tage, Insider klar vorn, DD besser
    v = series_verdict(series)
    assert v["recommendation"]["action"] == "adopt_arm"
    assert v["recommendation"]["arm"] == "insider_exit"


def test_holds_when_no_arm_beats_ref_even_with_days():
    series = [_report(insider_ret=0.5) for _ in range(20)]  # alle gleich/schlechter als Ref
    v = series_verdict(series)
    assert v["recommendation"]["action"] == "hold"


def test_daily_review_writes_history_idempotent(tmp_path):
    state = tmp_path / "live-state.json"
    state.write_text(json.dumps({"realized_pnl_sol": 0.1, "total_entries": 7, "sessions": 2}))
    hist = tmp_path / "hist.jsonl"
    r1 = daily_review(state, tmp_path / "nojournal.jsonl", tmp_path / "noreports", hist)
    r2 = daily_review(state, tmp_path / "nojournal.jsonl", tmp_path / "noreports", hist)
    assert r1["account"]["equity_sol"] == 1.1
    assert len(hist.read_text().splitlines()) == 1  # zweiter Lauf am selben Tag hängt nicht doppelt an
