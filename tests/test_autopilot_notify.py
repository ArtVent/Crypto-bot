"""Tests für Autopilot-Bausteine: Berichte, Persistenz, Live-Lock."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.adaptive import AdaptiveTuner
from memetrader.autopilot import live_lock_active
from memetrader.notify import Notifier, build_daily_report
from memetrader.risk import RiskConfig
from memetrader.strategy import StrategyConfig


def test_daily_report_aggregates(tmp_path):
    now = time.time()
    journal = tmp_path / "j.jsonl"
    journal.write_text("\n".join(json.dumps(r) for r in [
        {"closed_t": now - 3600, "pnl_sol": 0.08, "symbol": "WIN", "lesson": "good_trail"},
        {"closed_t": now - 7200, "pnl_sol": -0.02, "symbol": "LOSS", "lesson": "good_stop"},
        {"closed_t": now - 90000, "pnl_sol": 9.9, "symbol": "ALT", "lesson": "x"},  # >24h: raus
    ]))
    log = tmp_path / "l.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in [
        {"t": now - 100, "event": "entry", "mint": "M"},
        {"t": now - 90, "event": "entry_blocked", "mint": "M2", "why": "zu jung"},
        {"t": now - 80, "event": "self_tune", "param": "stop_loss_pct", "old": -35, "new": -30},
        {"t": now - 70, "event": "claude_memory", "note": "n"},
    ]))
    tuning = tmp_path / "t.json"
    tuning.write_text(json.dumps({"effective": {"stop_loss_pct": -30.0, "min_fill_pct": 15.0,
                                                "min_unique_buyers": 12, "position_sol": 0.05}}))

    report = build_daily_report(str(journal), str(log), str(tuning), mode="paper", now=now)
    assert "PAPER" in report
    assert "+0.0600 SOL" in report  # 0.08 - 0.02, Alt-Trade ausgeschlossen
    assert "Trades: 2" in report and "Winrate 50%" in report
    assert "Selbst-Tuning: 1" in report
    assert "Claude-Notizen: 1" in report
    assert "Stop -30.0%" in report


def test_notifier_uses_injected_sender():
    sent = []
    notifier = Notifier(sender=sent.append)
    assert notifier.send("hallo") == ["injected"]
    assert sent == ["hallo"]


def test_notifier_channels_from_config():
    assert Notifier().channels == []
    assert Notifier(telegram_token="t", telegram_chat_id="c").channels == ["telegram"]
    assert Notifier(webhook_url="https://x").channels == ["webhook"]


def test_live_lock_detection(tmp_path):
    lock = tmp_path / "live.lock"
    assert not live_lock_active(lock)
    lock.write_text("123")
    assert live_lock_active(lock)
    # Verwaister Lock (zu alt) zählt nicht
    import os
    old = time.time() - 7 * 3600
    os.utime(lock, (old, old))
    assert not live_lock_active(lock)


def test_tuner_state_roundtrip_persistence(tmp_path):
    path = tmp_path / "tuning.json"
    strat, risk = StrategyConfig(), RiskConfig(position_sol=0.05)
    tuner = AdaptiveTuner(strat, risk, path)
    # Zustand erzeugen: Verluste -> Skalierung runter; Anpassung -> persist
    for _ in range(3):
        tuner.on_trade_result(-0.02)
    tuner._persist()

    strat2, risk2 = StrategyConfig(), RiskConfig(position_sol=0.05)
    tuner2 = AdaptiveTuner(strat2, risk2, path)
    assert tuner2.load_state() is True
    assert risk2.position_sol == risk.position_sol  # Skalierung überlebt Neustart
    assert tuner2.consecutive_losses == 3


def test_tuner_load_state_clamps_to_bounds(tmp_path):
    path = tmp_path / "tuning.json"
    path.write_text(json.dumps({"effective": {"stop_loss_pct": -99.0, "min_unique_buyers": 500},
                                "position_scale": 0.01}))
    strat, risk = StrategyConfig(), RiskConfig()
    tuner = AdaptiveTuner(strat, risk, path)
    assert tuner.load_state() is True
    assert risk.stop_loss_pct == -50.0      # Bound, nicht -99
    assert strat.min_unique_buyers == 20    # Bound, nicht 500
    assert tuner.position_scale == 0.25     # Bound, nicht 0.01
