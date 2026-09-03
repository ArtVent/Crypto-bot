"""Tests für das ML-Gate: Feature-Parität, Modell-Scoring, Bot-Integration."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.mlfilter import FEATURES, extract_features
from tests.test_memetrader import SimCurve, feed_healthy_curve, make_bot

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "mlfilter-melt.joblib"


def test_extract_features_matches_training_schema():
    features = extract_features(
        name="Testcoin", symbol="TEST", description="A very chill coin http://x.io",
        twitter="https://x.com/t", telegram=None, website=None,
        symbol_dupes_before=3, creator_prior_launches=2, ts=1_700_000_000.0,
    )
    assert list(features.keys()) == FEATURES
    assert features["n_socials"] == 1
    assert features["desc_has_url"] == 1
    assert features["symbol_dupes_before"] == 3
    assert features["name_is_symbol"] == 0


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="trainiertes Modell nicht vorhanden")
def test_real_model_scores_probability():
    pytest.importorskip("joblib")
    pytest.importorskip("sklearn")
    from memetrader.mlfilter import MLGate

    gate = MLGate(str(MODEL_PATH), fetch_metadata=False)
    features = extract_features(name="Coin", symbol="COIN", ts=1_700_000_000.0)
    score = gate.score_features(features)
    assert 0.0 <= score <= 1.0
    # Determinismus
    assert gate.score_features(features) == score


class StubGate:
    def __init__(self, score: float):
        self._score = score
        self.calls = 0

    def risk(self, state, **kwargs) -> float:
        self.calls += 1
        return self._score


def _bot_with_gate(tmp_path, score: float):
    bot = make_bot(tmp_path)
    bot.ml_gate = StubGate(score)
    bot.config.ml_risk_threshold = 0.80
    return bot


def test_bot_blocks_entry_on_high_ml_risk(tmp_path):
    bot = _bot_with_gate(tmp_path, score=0.95)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "late"), now=max(t, 50.0))
    assert sim.mint not in bot.risk.positions
    assert bot.ml_gate.calls >= 1
    log = (tmp_path / "log.jsonl").read_text()
    assert "ml_risk" in log


def test_bot_enters_on_low_ml_risk(tmp_path):
    bot = _bot_with_gate(tmp_path, score=0.10)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "late"), now=max(t, 50.0))
    assert sim.mint in bot.risk.positions


def test_bot_tracks_causal_counters(tmp_path):
    bot = make_bot(tmp_path)
    first = SimCurve(mint="MA", symbol="DOGE", creator="DEV1")
    second = SimCurve(mint="MB", symbol="DOGE", creator="DEV1")
    bot.on_event(first.create_event(), now=0.0)
    bot.on_event(second.create_event(), now=1.0)
    assert bot.curves["MA"].symbol_dupes_before == 0
    assert bot.curves["MB"].symbol_dupes_before == 1
    assert bot.curves["MB"].creator_prior_launches == 1
