"""Claude-Berater: periodische Strategie-Review des Journals durch Claude.

Rollenverteilung nach docs/ai-und-memecoins.md, Abschnitt 5.7 ("Guardrails in
Code, nicht im Prompt"): Claude ANALYSIERT und SCHLÄGT VOR – angewendet wird
ausschließlich innerhalb der AdaptiveTuner-Bounds, und nur wenn der Nutzer
--apply übergibt. Der Berater läuft nie im Trade-Pfad und hat keinerlei
Ausführungsrechte.

Benötigt: `pip install anthropic` und ANTHROPIC_API_KEY (oder ein per
`ant auth login` hinterlegtes Profil).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

ADVISOR_MODEL = "claude-opus-5"

TUNABLE_PARAMS = {
    # param -> (objekt, bounds-key) – Schnittmenge mit AdaptiveTuner.Bounds
    "stop_loss_pct": ("risk", "stop_loss_pct"),
    "take_profit_pct": ("risk", "take_profit_pct"),
    "progress_deadline_seconds": ("risk", "progress_deadline_seconds"),
    "min_fill_pct": ("strategy", "min_fill_pct"),
    "min_unique_buyers": ("strategy", "min_unique_buyers"),
}

SYSTEM_PROMPT = """Du bist der Strategie-Reviewer eines defensiven Memecoin-Paper-Trading-Bots.
Du bekommst: (1) aggregierte Journal-Statistiken abgeschlossener Trades inklusive
Lektions-Klassifikation, (2) die aktuell wirksamen Parameter, (3) die erlaubten
Parameter-Grenzen. Deine Aufgabe: Muster erkennen und konservative Anpassungen
vorschlagen – oder explizit KEINE, wenn die Evidenz dünn ist (weniger als ~15
abgeschlossene Trades ist fast immer zu dünn).

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt dieser Form:
{
  "analysis": "2-4 Sätze: das wichtigste Muster und seine wahrscheinlichste Ursache",
  "proposals": [
    {"param": "<einer der erlaubten Parameter>", "value": <Zahl innerhalb der Grenzen>,
     "reason": "1 Satz Begründung aus den Daten"}
  ],
  "warnings": ["optionale Hinweise, z.B. auf zu kleine Stichprobe oder Regime-Wechsel"]
}
Schlage nie Parameter außerhalb der Grenzen oder außerhalb der erlaubten Liste vor.
Bevorzuge wenige, gut begründete Änderungen gegenüber vielen spekulativen."""


@dataclass
class Proposal:
    param: str
    value: float
    reason: str


def summarize_journal(records: list[dict], effective_params: dict, bounds: dict) -> str:
    closed = [r for r in records if r.get("lesson")]
    lessons = Counter(r["lesson"] for r in closed)
    pnls = [r.get("pnl_sol") or 0.0 for r in closed]
    wins = [p for p in pnls if p > 0]
    by_lesson_pnl = {}
    for r in closed:
        by_lesson_pnl.setdefault(r["lesson"], []).append(r.get("pnl_sol") or 0.0)

    summary = {
        "n_closed_trades": len(closed),
        "total_pnl_sol": round(sum(pnls), 4),
        "win_rate": round(len(wins) / len(closed), 3) if closed else None,
        "lessons": dict(lessons),
        "pnl_per_lesson": {k: round(sum(v), 4) for k, v in by_lesson_pnl.items()},
        "entry_context_of_losers": [
            {k: r["context"].get(k) for k in ("fill_pct", "unique_buyers", "dev_buy_sol", "ml_risk")}
            for r in closed if (r.get("pnl_sol") or 0.0) < 0
        ][:15],
        "effective_params": effective_params,
        "allowed_bounds": bounds,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def ask_advisor(journal_summary: str) -> dict:
    """Fragt Claude nach einer Review. Wirft RuntimeError bei fehlender Einrichtung."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Berater benötigt das anthropic-SDK: pip install anthropic") from exc

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=ADVISOR_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": journal_summary}],
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(
            "Kein API-Zugang: ANTHROPIC_API_KEY setzen oder `ant auth login` ausführen"
        ) from exc

    text = next((b.text for b in response.content if b.type == "text"), "")
    return parse_advisor_response(text)


def parse_advisor_response(text: str) -> dict:
    """Extrahiert das JSON-Objekt aus der Antwort (tolerant gegen Umrahmung)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"Berater-Antwort ohne JSON: {text[:200]}")
    return json.loads(text[start:end + 1])


def apply_proposals(proposals: list[dict], tuner) -> list[str]:
    """Wendet Vorschläge NUR innerhalb der Tuner-Bounds auf die Configs an."""
    applied = []
    for p in proposals:
        param = p.get("param")
        if param not in TUNABLE_PARAMS:
            applied.append(f"ABGELEHNT {param}: nicht in der erlaubten Parameter-Liste")
            continue
        target_name, bound_key = TUNABLE_PARAMS[param]
        target = tuner.risk if target_name == "risk" else tuner.strategy
        lo, hi = getattr(tuner.bounds, bound_key)
        try:
            value = float(p.get("value"))
        except (TypeError, ValueError):
            applied.append(f"ABGELEHNT {param}: kein numerischer Wert")
            continue
        clamped = max(lo, min(hi, value))
        old = getattr(target, param)
        setattr(target, param, clamped)
        note = " (auf Grenze gekappt)" if clamped != value else ""
        applied.append(f"{param}: {old} -> {clamped}{note} – {p.get('reason', '')}")
    if applied:
        tuner._persist()
    return applied
