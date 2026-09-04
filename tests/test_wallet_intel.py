"""Tests für Wallet-Intelligence, Creator-Gedächtnis und Regime-Gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.wallet_intel import CreatorBook, MarketRegime, WalletBook
from tests.test_memetrader import SimCurve, feed_healthy_curve, make_bot


def test_walletbook_credits_and_decay():
    book = WalletBook(half_life_seconds=3600.0)
    book.credit_graduation(["w1", "w2"], now=0.0)
    book.credit_graduation(["w1"], now=0.0)
    assert book.is_smart("w1", now=0.0)          # Score 2.0 >= 1.5
    assert not book.is_smart("w2", now=0.0)      # Score 1.0 < 1.5
    assert not book.is_smart("w1", now=3600.0)   # nach Halbwertszeit: 1.0 < 1.5
    assert book.smart_buyer_count({"w1", "w2", "wx"}, now=0.0) == 1


def test_walletbook_only_credits_first_k():
    book = WalletBook(early_buyer_credit_count=2)
    book.credit_graduation(["a", "b", "c", "d"], now=0.0)
    assert book._decayed("a", 0.0) == 1.0 and book._decayed("b", 0.0) == 1.0
    assert book._decayed("c", 0.0) == 0.0  # nicht unter den frühesten K


def test_creatorbook_serial_spammer():
    book = CreatorBook()
    for _ in range(3):
        book.record_launch("dev1")
    assert book.is_serial_spammer("dev1")
    book.record_graduation("dev1")
    assert not book.is_serial_spammer("dev1")   # eine Graduation rehabilitiert
    book.record_launch("dev2")
    assert not book.is_serial_spammer("dev2")   # zu wenig Historie


def test_market_regime_window():
    regime = MarketRegime(window_seconds=3600.0)
    for t in (0.0, 100.0, 200.0):
        regime.record_graduation(t)
    assert regime.graduations_per_hour(300.0) == 3
    assert regime.graduations_per_hour(3800.0) == 1  # nur t=200 noch im Fenster


# --- Bot-Integration ----------------------------------------------------------

def test_bot_blocks_live_serial_creator(tmp_path):
    bot = make_bot(tmp_path)
    # dev_serial launcht 3 Coins ohne Graduation
    for i in range(3):
        bot.on_event({"txType": "create", "mint": f"S{i}", "symbol": f"S{i}",
                      "traderPublicKey": "dev_serial"}, now=float(i))
    sim = SimCurve(mint="S_NEU", creator="dev_serial", symbol="NEU")
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "late"), now=max(t, 50.0))
    assert sim.mint not in bot.risk.positions
    assert "serial_creator_live" in (tmp_path / "log.jsonl").read_text()


def test_bot_credits_graduation_and_smart_gate(tmp_path):
    bot = make_bot(tmp_path)
    bot.config.min_smart_wallets = 1
    # Coin A graduiert -> frühe Käufer werden smart
    a = SimCurve(mint="A", creator="devA", symbol="AAA")
    bot.on_event(a.create_event(), now=0.0)
    for i in range(5):
        bot.on_event(a.buy_event(1.0, f"smartie{i}"), now=1.0 + i)
    bot.on_event({"txType": "migrate", "mint": "A", "pool": "pump-amm"}, now=10.0)
    bot.on_event({"txType": "migrate", "mint": "A", "pool": "pump-amm"}, now=11.0)  # idempotent
    assert bot.wallets.graduations_credited == 1
    # 2. Graduation -> smartie0 hat Score 2.0 und ist 'smart'
    b = SimCurve(mint="B", creator="devB", symbol="BBB")
    bot.on_event(b.create_event(), now=20.0)
    for i in range(3):
        bot.on_event(b.buy_event(1.0, f"smartie{i}"), now=21.0 + i)
    bot.on_event({"txType": "migrate", "mint": "B", "pool": "pump-amm"}, now=30.0)
    assert bot.wallets.is_smart("smartie0", now=31.0)

    # Kandidat OHNE Smart-Käufer wird geblockt ...
    c = SimCurve(mint="C", creator="devC", symbol="CCC")
    t = feed_healthy_curve(bot, c)
    bot.on_event(c.buy_event(0.5, "nobody"), now=max(t, 50.0) + 60)
    assert "C" not in bot.risk.positions
    assert "no_smart_wallets" in (tmp_path / "log.jsonl").read_text()
    # ... Kandidat MIT Smart-Käufer kommt durch
    d = SimCurve(mint="D", creator="devD", symbol="DDD")
    t = feed_healthy_curve(bot, d)
    bot.on_event(d.buy_event(0.6, "smartie0"), now=max(t, 50.0) + 120)
    bot.on_event(d.buy_event(0.5, "late"), now=max(t, 50.0) + 121)
    assert "D" in bot.risk.positions
