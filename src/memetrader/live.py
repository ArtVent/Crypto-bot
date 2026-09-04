"""Durchgehender Live-Paper-Bot auf der kostenlosen On-Chain-Quelle.

Warum: Der Record-then-Replay-Ansatz (45-min-Fenster) handelt kaum, weil ein
Coin im Fenster geboren werden UND ausreifen muss – am Fensterrand geht fast
alles verloren. Ein durchgehend laufender Bot fängt Coins von Geburt an und
hält sie durch ihren Lebenszyklus, genau wie der historische Volltag (58
Trades). Dieser Modul treibt den echten Bot live aus dem RPC-Log-Strom
(rpcrecorder-Dekodierung), sendet bei jedem Entry sofort einen Telegram-Alert
und persistiert den Kontostand, damit verkettete Sessions dasselbe
1-SOL-Papierkonto fortführen (GitHub-Runner haben ein Zeitlimit; mehrere
Sessions bilden zusammen den Dauerbetrieb).

Zustand über Sessions:
- Lernstand (Tuner) lädt/schreibt sich selbst über tuning_path.
- Journal wird angehängt (tuning_path/journal_path als committete Dateien).
- live-state.json trägt realisierte PnL + Session-Zähler; offene Positionen
  werden am Session-Ende glattgestellt, damit jede Session flach startet/endet.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .bot import Bot, BotConfig
from .notify import Notifier
from .rpcrecorder import PUMP_PROGRAM, RpcCore, rpc_ws_url


@dataclass
class LiveState:
    realized_pnl_sol: float = 0.0
    sessions: int = 0
    total_entries: int = 0

    @classmethod
    def load(cls, path: Path) -> "LiveState":
        try:
            d = json.loads(Path(path).read_text())
            return cls(realized_pnl_sol=float(d.get("realized_pnl_sol", 0.0)),
                       sessions=int(d.get("sessions", 0)),
                       total_entries=int(d.get("total_entries", 0)))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            return cls()

    def save(self, path: Path, budget_sol: float) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({
            "realized_pnl_sol": round(self.realized_pnl_sol, 6),
            "equity_sol": round(budget_sol + self.realized_pnl_sol, 6),
            "sessions": self.sessions,
            "total_entries": self.total_entries,
            "updated_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
        }, indent=2))


def _entry_alert(event: dict, fill, bot: Bot) -> str:
    sym = event.get("symbol") or fill.mint[:8]
    return (f"🟢 KAUF {sym}  {fill.sol:.4f} SOL\n"
            f"Konto: {bot.risk.summary().get('realized_pnl_sol', 0):+.4f} SOL realisiert, "
            f"{len(bot.risk.positions)} offen")


def liquidate_open(bot: Bot, now: float) -> float:
    """Offene Positionen zum letzten Kurs glattstellen (über das Journal),
    damit die Session flach endet und realized_pnl den Stand trägt."""
    liquidation = 0.0
    for mint, pos in list(bot.risk.positions.items()):
        state = bot.curves.get(mint)
        value = bot.broker.position_value(state, pos.tokens) if state else 0.0
        liquidation += value
        bot.risk.record_sell(pos, pos.tokens, value)
        bot.journal.on_exit(mint, "session_end", 1.0, value, True, now)
    bot.journal.finalize_due(now + 10 * 600.0)
    return liquidation


async def run_live(config: BotConfig, run_seconds: float, notifier: Notifier | None = None,
                   state_path: str = "state/live-state.json", save_every: float = 120.0,
                   ws_url: str | None = None) -> LiveState:
    import websockets

    notifier = notifier or Notifier.from_env()
    ws_url = ws_url or rpc_ws_url()
    state = LiveState.load(Path(state_path))
    bot = Bot(config)
    if bot.tuner.load_state():
        print(f"[live] Lernstand geladen: {bot.tuner.state_summary()}", flush=True)
    # Kontostand aus vorheriger Session fortführen
    bot.risk.realized_pnl_sol = state.realized_pnl_sol

    subscribe = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                            "params": [{"mentions": [PUMP_PROGRAM]}, {"commitment": "confirmed"}]})
    core = RpcCore()
    deadline = time.time() + run_seconds
    last_save = last_prune = time.time()
    entries_this_session = 0
    print(f"[live] Start: Budget {config.risk.budget_sol} SOL, fortgeführte PnL "
          f"{state.realized_pnl_sol:+.4f}, Quelle {ws_url}, Laufzeit {run_seconds/60:.0f} min", flush=True)

    while time.time() < deadline:
        try:
            async with websockets.connect(ws_url, ping_interval=20, max_size=1 << 22) as ws:
                await ws.send(subscribe)
                while time.time() < deadline:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        continue
                    now = time.time()
                    try:
                        msg = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(msg, dict) or msg.get("method") != "logsNotification":
                        continue
                    value = msg.get("params", {}).get("result", {}).get("value", {})
                    for event in core.on_notification(value):
                        for fill in bot.on_event(event, now):
                            if fill.side == "buy":
                                entries_this_session += 1
                                state.total_entries += 1
                                msg_text = _entry_alert(event, fill, bot)
                                print(msg_text, flush=True)
                                notifier.send(msg_text)
                    if now - last_prune > 300:
                        bot.prune(now)
                        last_prune = now
                    if now - last_save > save_every:
                        state.realized_pnl_sol = bot.risk.realized_pnl_sol
                        state.save(Path(state_path), config.risk.budget_sol)
                        last_save = now
        except (Exception,) as exc:  # Netzfehler: bis Deadline weiterversuchen
            if time.time() >= deadline:
                break
            print(f"[live] Verbindung verloren ({type(exc).__name__}: {exc}); Reconnect in 3s", flush=True)
            await asyncio.sleep(3.0)

    liquidate_open(bot, time.time())
    state.realized_pnl_sol = bot.risk.realized_pnl_sol
    state.sessions += 1
    state.save(Path(state_path), config.risk.budget_sol)
    equity = config.risk.budget_sol + state.realized_pnl_sol
    summary = (f"⏱ Session #{state.sessions} beendet: {entries_this_session} Entries. "
               f"Konto {equity:.4f} SOL ({(equity/config.risk.budget_sol-1)*100:+.2f}% seit Start, "
               f"{state.total_entries} Entries gesamt).")
    print(summary, flush=True)
    notifier.send(summary)
    return state
