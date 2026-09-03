"""Tests der Log-Auswertung."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import json

from memetrader.analyze import analyze_lines


def make_log():
    return [
        # Trade 1: Derisk (halb) + Take-Profit (Rest) -> Gewinner
        {"t": 100.0, "event": "entry", "mint": "M1", "symbol": "WIN", "sol": 0.05, "tokens": 1000},
        {"t": 200.0, "event": "exit", "mint": "M1", "symbol": "WIN", "reason": "take_profit", "fraction": 0.5, "sol_received": 0.055},
        {"t": 400.0, "event": "exit", "mint": "M1", "symbol": "WIN", "reason": "take_profit", "fraction": 1.0, "sol_received": 0.09},
        # Trade 2: Stop-Loss -> Verlierer
        {"t": 500.0, "event": "entry", "mint": "M2", "symbol": "LOSS", "sol": 0.05, "tokens": 1000},
        {"t": 560.0, "event": "exit", "mint": "M2", "symbol": "LOSS", "reason": "stop_loss", "fraction": 1.0, "sol_received": 0.031},
        # Trade 3: noch offen
        {"t": 600.0, "event": "entry", "mint": "M3", "symbol": "OPEN", "sol": 0.05, "tokens": 1000},
        # Blockierte Entries
        {"t": 610.0, "event": "entry_blocked", "mint": "M4", "why": "Kill-Switch aktiv"},
        {"t": 620.0, "event": "entry_blocked", "mint": "M5", "why": "max. 3 gleichzeitige Positionen"},
        {"t": 630.0, "event": "entry_blocked", "mint": "M6", "why": "max. 3 gleichzeitige Positionen"},
    ]


def test_analyze_reconstructs_trades():
    analysis = analyze_lines(json.dumps(e) for e in make_log())
    closed = analysis.closed_trades
    assert len(closed) == 2
    assert len(analysis.open_trades) == 1

    win = next(t for t in closed if t.mint == "M1")
    assert abs(win.pnl_sol - 0.095) < 1e-9  # 0.055 + 0.09 - 0.05... -> +0.095? nein: 0.145-0.05
    # Korrektur: proceeds 0.145, Kosten 0.05 -> +0.095
    assert win.hold_seconds == 300.0
    assert win.exit_reasons == ["take_profit", "take_profit"]

    loss = next(t for t in closed if t.mint == "M2")
    assert abs(loss.pnl_sol - (-0.019)) < 1e-9
    assert loss.exit_reasons == ["stop_loss"]


def test_analyze_counts_blocked_and_reports():
    analysis = analyze_lines(json.dumps(e) for e in make_log())
    assert analysis.blocked["max. 3 gleichzeitige Positionen"] == 2
    report = analysis.report()
    assert "Trefferquote: 1/2" in report
    assert "stop_loss" in report
    assert "Kill-Switch aktiv" in report
    assert "1 offen" in report


def test_analyze_tolerates_garbage_lines():
    lines = ["not json", "", json.dumps({"event": "entry", "mint": "M1", "symbol": "A", "sol": 0.05, "t": 1.0})]
    analysis = analyze_lines(lines)
    assert len(analysis.open_trades) == 1
