"""Tests für memetrader: Curve-Mathe, Strategie, Risk-Engine, Bot-Lebenszyklus."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memetrader.bot import Bot, BotConfig
from memetrader.curve import CurveState, simulate_buy, simulate_sell
from memetrader.risk import ExitReason, PositionState, RiskConfig, RiskManager
from memetrader.strategy import MomentumStrategy, StrategyConfig

# pump.fun-typische virtuelle Startreserven
V_SOL0 = 30.0
V_TOK0 = 1_073_000_000.0


class SimCurve:
    """Simulierte Chain-Seite: erzeugt konsistente PumpPortal-Events."""

    def __init__(self, mint="MINT_SIM", creator="DEV", symbol="SIM"):
        self.mint, self.creator, self.symbol = mint, creator, symbol
        self.v_sol, self.v_tokens = V_SOL0, V_TOK0
        self.k = self.v_sol * self.v_tokens

    def create_event(self, dev_buy_sol=1.0):
        self.v_sol += dev_buy_sol
        self.v_tokens = self.k / self.v_sol
        return {
            "txType": "create", "mint": self.mint, "traderPublicKey": self.creator,
            "name": "Sim", "symbol": self.symbol, "solAmount": dev_buy_sol,
            "vSolInBondingCurve": self.v_sol, "vTokensInBondingCurve": self.v_tokens,
        }

    def buy_event(self, sol, trader):
        self.v_sol += sol
        self.v_tokens = self.k / self.v_sol
        return {
            "txType": "buy", "mint": self.mint, "traderPublicKey": trader, "solAmount": sol,
            "vSolInBondingCurve": self.v_sol, "vTokensInBondingCurve": self.v_tokens,
        }

    def sell_event(self, sol_out, trader):
        self.v_sol -= sol_out
        self.v_tokens = self.k / self.v_sol
        return {
            "txType": "sell", "mint": self.mint, "traderPublicKey": trader, "solAmount": sol_out,
            "vSolInBondingCurve": self.v_sol, "vTokensInBondingCurve": self.v_tokens,
        }


# --- Curve-Mathe -------------------------------------------------------------

def test_buy_sell_roundtrip_costs_fees():
    state = CurveState(mint="M", v_sol=V_SOL0, v_tokens=V_TOK0)
    tokens, spent = simulate_buy(state, 0.1)
    assert tokens > 0 and spent == 0.1
    sol_back = simulate_sell(state, tokens)
    assert 0.09 < sol_back < 0.1  # Fees kosten, aber kein Totalverlust


def test_price_rises_with_buys():
    sim = SimCurve()
    p0 = sim.v_sol / sim.v_tokens
    sim.buy_event(5.0, "w1")
    assert sim.v_sol / sim.v_tokens > p0


# --- Strategie ---------------------------------------------------------------

def good_state(now=100.0, **overrides):
    state = CurveState(
        mint="M", creator="DEV", symbol="GOOD", v_sol=45.0, v_tokens=V_SOL0 * V_TOK0 / 45.0,
        created_at=0.0, dev_buy_sol=1.0, real_sol_in_curve=15.0,
        buys=20, sells=2, last_trade_at=now - 1.0,
    )
    state.unique_buyers = {f"w{i}" for i in range(15)}
    for key, val in overrides.items():
        setattr(state, key, val)
    return state


def test_strategy_accepts_good_candidate():
    assert MomentumStrategy().evaluate(good_state(), now=100.0).enter


def test_strategy_rejects_sniper_window():
    decision = MomentumStrategy().evaluate(good_state(created_at=90.0), now=100.0)
    assert not decision.enter and any("zu jung" in r for r in decision.reasons)


def test_strategy_rejects_creator_sold():
    assert not MomentumStrategy().evaluate(good_state(creator_sold=True), now=100.0).enter


def test_strategy_rejects_oversized_dev_buy():
    assert not MomentumStrategy().evaluate(good_state(dev_buy_sol=10.0), now=100.0).enter


def test_strategy_symbol_dedupe():
    strat = MomentumStrategy()
    assert strat.evaluate(good_state(), now=100.0).enter
    dupe = good_state(mint="M2")
    decision = strat.evaluate(dupe, now=200.0)
    assert not decision.enter and any("Duplikat" in r for r in decision.reasons)


# --- Risk-Engine -------------------------------------------------------------

def test_stop_loss_and_killswitch():
    rm = RiskManager(RiskConfig(budget_sol=1.0, position_sol=0.05, daily_loss_stop_sol=0.03))
    pos = rm.open_position("M1", "X", tokens=1000.0, cost_sol=0.05, now=0.0)
    action = rm.check_exit(pos, value_sol=0.03, creator_sold=False, migrated=False, now=10.0)
    assert action and action.reason == ExitReason.STOP_LOSS
    rm.record_sell(pos, 1000.0, 0.03)  # -0.02 realisiert
    assert not rm.halted
    pos2 = rm.open_position("M2", "Y", tokens=1000.0, cost_sol=0.05, now=20.0)
    rm.record_sell(pos2, 1000.0, 0.03)  # kumuliert -0.04 <= -0.03
    assert rm.halted
    assert rm.can_enter()[0] is False


def test_derisk_then_full_take_profit():
    rm = RiskManager(RiskConfig(position_sol=0.05, derisk_at_pct=100.0, take_profit_pct=250.0))
    pos = rm.open_position("M1", "X", tokens=1000.0, cost_sol=0.05, now=0.0)
    action = rm.check_exit(pos, value_sol=0.11, creator_sold=False, migrated=False, now=10.0)
    assert action and action.reason == ExitReason.TAKE_PROFIT and action.sell_fraction == 0.5
    rm.record_sell(pos, 500.0, 0.055)
    assert pos.state == PositionState.DERISKED
    action = rm.check_exit(pos, value_sol=0.13, creator_sold=False, migrated=False, now=20.0)
    assert action and action.sell_fraction == 1.0


def test_time_stop_without_progress():
    rm = RiskManager(RiskConfig(progress_deadline_seconds=60.0, progress_min_pct=20.0))
    pos = rm.open_position("M1", "X", tokens=1000.0, cost_sol=0.05, now=0.0)
    action = rm.check_exit(pos, value_sol=0.052, creator_sold=False, migrated=False, now=120.0)
    assert action and action.reason == ExitReason.TIME_STOP


def test_max_concurrent_limit():
    rm = RiskManager(RiskConfig(budget_sol=1.0, position_sol=0.05, max_concurrent=2))
    rm.open_position("M1", "A", 1.0, 0.05)
    rm.open_position("M2", "B", 1.0, 0.05)
    assert rm.can_enter()[0] is False


# --- Bot-Integration ---------------------------------------------------------

def make_bot(tmp_path, **risk_overrides) -> Bot:
    config = BotConfig()
    config.log_path = str(tmp_path / "log.jsonl")
    config.strategy = StrategyConfig(min_age_seconds=45.0, min_unique_buyers=10, min_buys=15)
    for key, val in risk_overrides.items():
        setattr(config.risk, key, val)
    return Bot(config)


def feed_healthy_curve(bot: Bot, sim: SimCurve):
    bot.on_event(sim.create_event(dev_buy_sol=1.0), now=0.0)
    t = 5.0
    for i in range(20):  # 20 Käufe von 20 Wallets über ~40s, ~13 SOL netto
        bot.on_event(sim.buy_event(0.65, f"wallet{i}"), now=t)
        t += 2.0
    return t


def test_bot_enters_after_observation_window(tmp_path):
    bot = make_bot(tmp_path)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    assert sim.mint not in bot.risk.positions  # noch im Sniper-Fenster? nein: t≈45 – Einstieg passiert beim nächsten Event
    fills = bot.on_event(sim.buy_event(0.5, "wallet_late"), now=max(t, 50.0))
    assert sim.mint in bot.risk.positions
    assert any(f.side == "buy" for f in fills)


def test_bot_exits_on_creator_dump(tmp_path):
    bot = make_bot(tmp_path)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "wallet_late"), now=max(t, 50.0))
    assert sim.mint in bot.risk.positions
    fills = bot.on_event(sim.sell_event(2.0, "DEV"), now=60.0)  # Creator verkauft
    assert sim.mint not in bot.risk.positions
    assert any(f.side == "sell" for f in fills)


def test_bot_stop_loss_on_price_collapse(tmp_path):
    bot = make_bot(tmp_path)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "wallet_late"), now=max(t, 50.0))
    cost = bot.risk.positions[sim.mint].cost_sol
    # Fremde Wallets dumpen die Kurve weit unter den Einstieg
    fills = []
    for i in range(6):
        fills += bot.on_event(sim.sell_event(2.0, f"dumper{i}"), now=70.0 + i)
        if sim.mint not in bot.risk.positions:
            break
    assert sim.mint not in bot.risk.positions
    assert bot.risk.realized_pnl_sol < 0
    assert bot.risk.realized_pnl_sol > -cost  # Stop hat vor Totalverlust gegriffen


def test_bot_derisks_on_pump(tmp_path):
    bot = make_bot(tmp_path)
    sim = SimCurve()
    t = feed_healthy_curve(bot, sim)
    bot.on_event(sim.buy_event(0.5, "wallet_late"), now=max(t, 50.0))
    pos = bot.risk.positions[sim.mint]
    # Kräftiger Pump: Wert der Position verdoppelt sich
    for i in range(12):
        bot.on_event(sim.buy_event(4.0, f"pumper{i}"), now=55.0 + i)
        if pos.state == PositionState.DERISKED or sim.mint not in bot.risk.positions:
            break
    assert pos.realized_sol > 0  # Teilverkauf hat stattgefunden
