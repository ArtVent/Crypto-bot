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


def test_ws_url_from_env(monkeypatch):
    from memetrader.recorder import PUMPPORTAL_WS, ws_url_from_env

    monkeypatch.delenv("PUMPPORTAL_API_KEY", raising=False)
    assert ws_url_from_env() == PUMPPORTAL_WS
    monkeypatch.setenv("PUMPPORTAL_API_KEY", "k123")
    assert ws_url_from_env() == PUMPPORTAL_WS + "?api-key=k123"


# --- RPC-Recorder: Anchor-Event-Dekodierung (netzfrei) ------------------------

def _pack_trade(mint32, sol_lamports, is_buy, user32, v_sol, v_tok, real_sol=0):
    import hashlib, struct
    return (hashlib.sha256(b"event:TradeEvent").digest()[:8] + mint32
            + struct.pack("<Q", sol_lamports) + struct.pack("<Q", 5_000_000)
            + bytes([1 if is_buy else 0]) + user32 + struct.pack("<q", 1234)
            + struct.pack("<Q", v_sol) + struct.pack("<Q", v_tok)
            + struct.pack("<Q", real_sol) + struct.pack("<Q", 7)
            + b"extra-future-fields")  # angehängte neue Felder stören nicht


def _pack_create(name, symbol, mint32, user32):
    import hashlib, struct

    def s(x):
        raw = x.encode()
        return struct.pack("<I", len(raw)) + raw

    return (hashlib.sha256(b"event:CreateEvent").digest()[:8]
            + s(name) + s(symbol) + s("https://uri") + mint32 + b"\x02" * 32 + user32)


def test_rpc_core_decodes_and_folds_dev_buy():
    import base64

    from memetrader.rpcrecorder import RpcCore, b58encode

    mint, dev, buyer = b"\x03" * 32, b"\x04" * 32, b"\x05" * 32
    logs = [
        "Program 6EF8... invoke [1]",
        "Program data: " + base64.b64encode(_pack_create("Coin", "AAA", mint, dev)).decode(),
        "Program data: " + base64.b64encode(
            _pack_trade(mint, 2_000_000_000, True, dev, 32_000_000_000, 10**15)).decode(),
    ]
    events = RpcCore().on_notification({"err": None, "logs": logs})
    assert len(events) == 1  # Dev-Buy wurde ins Create gefaltet
    c = events[0]
    assert c["txType"] == "create" and c["symbol"] == "AAA"
    assert c["mint"] == b58encode(mint) and c["traderPublicKey"] == b58encode(dev)
    assert abs(c["solAmount"] - 2.0) < 1e-9 and abs(c["vSolInBondingCurve"] - 32.0) < 1e-9

    # Normaler Kauf eines Fremd-Wallets -> buy-Event mit Reserven
    logs2 = ["Program data: " + base64.b64encode(
        _pack_trade(mint, 500_000_000, True, buyer, 33_000_000_000, 10**15)).decode()]
    events2 = RpcCore().on_notification({"err": None, "logs": logs2})
    assert events2[0]["txType"] == "buy" and abs(events2[0]["solAmount"] - 0.5) < 1e-9

    # Fehlgeschlagene Tx wird ignoriert
    assert RpcCore().on_notification({"err": {"x": 1}, "logs": logs2}) == []


def test_rpc_core_complete_becomes_migrate():
    import base64
    import hashlib

    from memetrader.rpcrecorder import RpcCore, b58encode

    mint = b"\x06" * 32
    payload = (hashlib.sha256(b"event:CompleteEvent").digest()[:8]
               + b"\x07" * 32 + mint + b"\x08" * 32 + b"\x00" * 8)
    logs = ["Program data: " + base64.b64encode(payload).decode()]
    events = RpcCore().on_notification({"err": None, "logs": logs})
    assert events == [{"txType": "migrate", "mint": b58encode(mint), "pool": "pump-amm"}]
