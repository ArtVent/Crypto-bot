"""Trade-Journal: Kontext, Ausgang und LEKTION jedes Trades.

Das Journal ist das Gedächtnis des Bots. Für jeden geschlossenen Trade wird
der Markt noch eine Weile weiterbeobachtet (Post-Exit-Fenster), denn erst der
Kontrafakt macht aus einem Ergebnis eine Lektion:

  Stop gegriffen UND Coin fiel weiter        -> good_stop        (Regel bestätigt)
  Stop gegriffen UND Coin erholte sich       -> shaken_out       (Stop zu eng?)
  Zeit-Stop UND Coin lief danach             -> impatient        (zu ungeduldig?)
  Take-Profit UND Coin lief danach weit      -> sold_too_early   (Gewinner zu früh abgegeben)
  Creator-Exit UND Coin erholte sich         -> overreacted_creator_exit
  Schnell tief im Minus nach Entry           -> bad_entry        (Filter-Lücke)

Diese Lektionen sind die Eingabe des Selbst-Kalibrierers (adaptive.py) und
des optionalen Claude-Beraters (advisor.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class EntryContext:
    """Feature-Schnappschuss zum Einstiegszeitpunkt (für spätere Analyse)."""

    age_seconds: float = 0.0
    fill_pct: float = 0.0
    unique_buyers: int = 0
    buys: int = 0
    sells: int = 0
    dev_buy_sol: float = 0.0
    symbol_dupes_before: int = 0
    creator_prior_launches: int = 0
    ml_risk: float | None = None


@dataclass
class TradeRecord:
    mint: str
    symbol: str
    entered_t: float
    cost_sol: float
    tokens: float
    context: EntryContext = field(default_factory=EntryContext)
    exits: list[dict] = field(default_factory=list)  # {t, reason, fraction, sol}
    closed_t: float | None = None
    proceeds_sol: float = 0.0
    # Post-Exit-Beobachtung
    watch_until: float | None = None
    post_peak_value_sol: float = 0.0
    # Ergebnis
    lesson: str | None = None
    pnl_sol: float | None = None

    @property
    def last_exit_reason(self) -> str:
        return self.exits[-1]["reason"] if self.exits else "?"


# Schwellen der Lektions-Klassifikation (bewusst benannt und zentral)
RECOVERY_FACTOR = 1.0      # Post-Peak über Einstandskosten = "hätte sich erholt"
RUNNER_FACTOR = 1.5        # Post-Peak deutlich über Erlös = "lief danach weiter"
FAST_LOSS_SECONDS = 120.0  # Verlust-Exit so schnell = Entry-Problem, nicht Exit-Problem


def classify_lesson(record: TradeRecord) -> str:
    reason = record.last_exit_reason
    cost = record.cost_sol
    proceeds = record.proceeds_sol
    peak = record.post_peak_value_sol
    held = (record.closed_t or 0.0) - record.entered_t

    if reason == "stop_loss":
        if held <= FAST_LOSS_SECONDS:
            return "bad_entry"
        return "shaken_out" if peak > cost * RECOVERY_FACTOR else "good_stop"
    if reason == "time_stop":
        return "impatient" if peak > cost * RUNNER_FACTOR else "good_time_stop"
    if reason == "take_profit":
        return "sold_too_early" if peak > proceeds * RUNNER_FACTOR else "good_take_profit"
    if reason == "trailing_stop":
        return "sold_too_early" if peak > proceeds * RUNNER_FACTOR else "good_trail"
    if reason == "creator_sold":
        return "overreacted_creator_exit" if peak > cost * RECOVERY_FACTOR else "good_creator_exit"
    if reason == "migration":
        return "migration_exit"
    if reason == "kill_switch":
        return "kill_switch_exit"
    return "unclassified"


class Journal:
    """Hält offene Records im Speicher, schreibt finalisierte als JSONL."""

    def __init__(self, path: str | Path, post_exit_watch_seconds: float = 600.0):
        self.path = Path(path)
        self.post_exit_watch_seconds = post_exit_watch_seconds
        self.open: dict[str, TradeRecord] = {}
        self.watching: dict[str, TradeRecord] = {}
        self.finalized: list[TradeRecord] = []

    # --- Lebenszyklus ---------------------------------------------------------
    def on_entry(self, mint: str, symbol: str, tokens: float, cost_sol: float,
                 context: EntryContext, now: float) -> None:
        self.open[mint] = TradeRecord(
            mint=mint, symbol=symbol, entered_t=now, cost_sol=cost_sol,
            tokens=tokens, context=context,
        )

    def on_exit(self, mint: str, reason: str, fraction: float, sol_received: float,
                position_closed: bool, now: float) -> None:
        record = self.open.get(mint)
        if record is None:
            return
        record.exits.append({"t": now, "reason": reason, "fraction": fraction, "sol": sol_received})
        record.proceeds_sol += sol_received
        if position_closed:
            record.closed_t = now
            record.pnl_sol = record.proceeds_sol - record.cost_sol
            record.watch_until = now + self.post_exit_watch_seconds
            self.watching[mint] = self.open.pop(mint)

    def on_post_exit_value(self, mint: str, value_sol: float) -> None:
        """Wert der URSPRÜNGLICHEN Positionsgröße, falls man noch hielte."""
        record = self.watching.get(mint)
        if record is not None:
            record.post_peak_value_sol = max(record.post_peak_value_sol, value_sol)

    def finalize_due(self, now: float) -> list[TradeRecord]:
        done = [m for m, r in self.watching.items() if r.watch_until is not None and now >= r.watch_until]
        finalized = []
        for mint in done:
            record = self.watching.pop(mint)
            record.lesson = classify_lesson(record)
            self.finalized.append(record)
            self._persist(record)
            finalized.append(record)
        return finalized

    # --- Auswertung -----------------------------------------------------------
    def recent_lessons(self, n: int = 20) -> list[TradeRecord]:
        return self.finalized[-n:]

    def _persist(self, record: TradeRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_journal_records(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    records = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
