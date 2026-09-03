"""Laufzeit-ML-Gate: bewertet Launches mit dem auf MELT trainierten Modell.

Das Gate ist eine ZUSÄTZLICHE Ablehnungs-Regel hinter der Regel-Strategie
(docs/filter-engine.md: externe/ML-Scores sind Features bzw. Filter, nie die
alleinige Entscheidung). Es sagt P(high risk) voraus; ab der konfigurierten
Schwelle wird der Entry blockiert.

Lizenz-Hinweis: models/mlfilter-melt.joblib wurde auf dem MELT-Datensatz
(CC BY-NC 4.0) trainiert – nur für Forschung/persönliche Experimente. Für
kommerzielle Nutzung mit train_mlfilter auf eigenen Archiv-Daten neu trainieren.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from typing import Optional

from .curve import CurveState

# Muss exakt der Trainings-Featureliste entsprechen (train_mlfilter.FEATURES)
FEATURES = [
    "has_twitter", "has_website", "has_telegram", "n_socials",
    "desc_len", "desc_words", "desc_has_url", "desc_all_caps_ratio",
    "name_len", "symbol_len", "symbol_is_upper", "name_has_digit",
    "name_entropy", "symbol_dupes_before", "name_is_symbol",
    "creator_prior_launches", "creator_launch_same_day",
    "hour_utc", "weekday",
]


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text.lower())
    total = len(text)
    return -sum(c / total * math.log2(c / total) for c in counts.values())


def extract_features(
    name: str,
    symbol: str,
    description: str = "",
    twitter: str | None = None,
    website: str | None = None,
    telegram: str | None = None,
    symbol_dupes_before: int = 0,
    creator_prior_launches: int = 0,
    creator_launch_same_day: int = 0,
    ts: float | None = None,
) -> dict:
    ts = time.time() if ts is None else ts
    tm = time.gmtime(ts)
    desc = description or ""
    sym = symbol or ""
    return {
        "has_twitter": int(bool(twitter)),
        "has_website": int(bool(website)),
        "has_telegram": int(bool(telegram)),
        "n_socials": sum(bool(x) for x in (twitter, website, telegram)),
        "desc_len": len(desc),
        "desc_words": len(desc.split()),
        "desc_has_url": int(bool(re.search(r"https?://|www\.", desc))),
        "desc_all_caps_ratio": (sum(c.isupper() for c in desc) / len(desc)) if desc else 0.0,
        "name_len": len(name or ""),
        "symbol_len": len(sym),
        "symbol_is_upper": int(sym.isupper()) if sym else 0,
        "name_has_digit": int(any(c.isdigit() for c in (name or ""))),
        "name_entropy": _entropy(name or ""),
        "symbol_dupes_before": symbol_dupes_before,
        "name_is_symbol": int((name or "").strip().upper() == sym.upper()),
        "creator_prior_launches": creator_prior_launches,
        "creator_launch_same_day": creator_launch_same_day,
        "hour_utc": tm.tm_hour,
        "weekday": tm.tm_wday,
    }


def fetch_token_metadata(uri: str, timeout: float = 5.0) -> dict:
    """Holt das Metadaten-JSON eines Tokens (IPFS-URI aus dem Create-Event).

    Tolerant: jeder Fehler liefert {} – das Gate rechnet dann ohne Socials.
    """
    if not uri or not uri.startswith("http"):
        return {}
    try:
        import httpx

        resp = httpx.get(uri, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class MLGate:
    """Lädt das trainierte Modell und bewertet CurveStates zur Entry-Zeit."""

    def __init__(self, model_path: str, fetch_metadata: bool = True):
        import joblib  # lazy: Bot bleibt ohne sklearn lauffähig

        bundle = joblib.load(model_path)
        self._model = bundle["model"]
        self._features = bundle["features"]
        if self._features != FEATURES:
            raise ValueError("Modell-Featureliste passt nicht zur Laufzeit-Extraktion – neu trainieren")
        self.fetch_metadata = fetch_metadata
        self._meta_cache: dict[str, dict] = {}

    def score_features(self, features: dict) -> float:
        row = [[features[name] for name in self._features]]
        return float(self._model.predict_proba(row)[0][1])

    def risk(
        self,
        state: CurveState,
        symbol_dupes_before: int = 0,
        creator_prior_launches: int = 0,
        creator_launch_same_day: int = 0,
        now: float | None = None,
    ) -> float:
        meta = self._meta_cache.get(state.mint)
        if meta is None:
            meta = fetch_token_metadata(getattr(state, "uri", "")) if self.fetch_metadata else {}
            self._meta_cache[state.mint] = meta
        features = extract_features(
            name=state.name,
            symbol=state.symbol,
            description=str(meta.get("description") or ""),
            twitter=meta.get("twitter"),
            website=meta.get("website"),
            telegram=meta.get("telegram"),
            symbol_dupes_before=symbol_dupes_before,
            creator_prior_launches=creator_prior_launches,
            creator_launch_same_day=creator_launch_same_day,
            ts=now if now is not None else state.created_at,
        )
        return self.score_features(features)
