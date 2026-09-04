"""Tests für den Roh-Event-Recorder (netzfreie Logik) und das A/B-Kommando."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.abtest import format_report, run_abtest
from memetrader.recorder import RecorderCore
from tests.test_memetrader import SimCurve


def test_recorder_records_and_subscribes():
    core = RecorderCore()
    line, out = core.on_message({"txType": "create", "mint": "M1", "symbol": "AAA"}, now=100.0)
    assert json.loads(line)["_t"] == 100.0
    assert any("subscribeTokenTrade" in m and "M1" in m for m in out)
    # Statusmeldungen ohne txType werden nicht aufgezeichnet
    line, out = core.on_message({"message": "Successfully subscribed"}, now=101.0)
    assert line is None and out == []
    # Trades des Mints werden aufgezeichnet, ohne erneut zu abonnieren
    line, out = core.on_message({"txType": "buy", "mint": "M1", "solAmount": 0.1}, now=102.0)
    assert json.loads(line)["solAmount"] == 0.1 and out == []


def test_recorder_unsubscribes_on_migration_and_prunes_stale():
    core = RecorderCore(track_minutes=1.0, prune_interval_seconds=30.0)
    core.on_message({"txType": "create", "mint": "OLD"}, now=0.0)
    _, out = core.on_message({"txType": "migrate", "mint": "OLD"}, now=10.0)
    assert any("unsubscribeTokenTrade" in m and "OLD" in m for m in out)
    # Veralteter Mint fliegt beim Prune raus
    core.on_message({"txType": "create", "mint": "STALE"}, now=20.0)
    _, out = core.on_message({"txType": "create", "mint": "NEW"}, now=120.0)
    assert any("unsubscribeTokenTrade" in m and "STALE" in m for m in out)
    assert "STALE" not in core._tracked and "NEW" in core._tracked
    # Reconnect-Hilfe enthält die noch beobachteten Mints
    assert any("NEW" in m for m in core.resubscribe_messages())


def test_abtest_writes_reports(tmp_path):
    # Mini-Aufzeichnung: ein Coin mit ein paar Käufen (zu wenig für einen Entry)
    sim = SimCurve(mint="R1", creator="dev", symbol="REC")
    events = [dict(sim.create_event(), _t=1000.0)]
    for i in range(3):
        events.append(dict(sim.buy_event(0.2, f"w{i}"), _t=1001.0 + i))
    rec = tmp_path / "rec.jsonl"
    rec.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    report = run_abtest(rec, tmp_path / "out", budget_sol=1.0, max_smart_buyers=7)
    assert (tmp_path / "out" / "report.json").exists()
    assert report["n_events"] == 4 and report["max_smart_buyers"] == 7
    assert report["reference"]["closed"] == 0  # zu wenig Aktivität für einen Trade
    assert report["recycle_ladder"]["closed"] == 0 and report["recycle_trigger_pct"] == 100.0
    md = format_report(report)
    assert "Referenz" in md and "Dichte-Kappe" in md and "Recycle-Leiter" in md
    assert (tmp_path / "out" / "report.md").read_text() == md
