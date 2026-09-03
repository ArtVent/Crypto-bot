"""Training des ML-Filters auf dem MELT-Datensatz (echte pump.fun-Historie).

Datensatz: git-disl/MELT (arXiv 2602.13480) – 41.470 graduierte pump.fun-Coins
(Dez 2024 – März 2025) mit Risiko-Labels. Lizenz: CC BY-NC 4.0 –
NUR für Forschung/persönliche Experimente; für kommerzielle Nutzung (SaaS)
auf eigenen Archiv-Daten (memescan watch/label) neu trainieren.

Ziel wie in docs/filter-engine.md 4.1: kein Preis-Orakel, sondern ein
Risiko-Gate – vorhergesagt wird P(label == 'high'), also
Kollaps-/Manipulations-Risiko. Der Bot nutzt das als zusätzliche
Ablehnungs-Regel: score > Schwelle -> kein Trade.

Methodik-Disziplin (docs/filter-engine.md 4.2/4.3):
- Nur Features, die ZUM LAUNCH-ZEITPUNKT verfügbar sind
  (Name/Symbol/Beschreibung/Socials aus den Token-Metadaten,
  Creator-Historie NUR aus früheren Launches, Uhrzeit).
- Chronologischer Train/Test-Split, niemals zufällig.
- Kalibrierter Klassifikator, damit die Schwelle als Wahrscheinlichkeit
  interpretierbar ist.

Aufruf:
  python -m memetrader.train_mlfilter --melt-dir /pfad/zu/MELT \
      --out models/mlfilter-melt.joblib
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

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


def build_dataset(melt_dir: Path) -> pd.DataFrame:
    labels = pd.read_csv(melt_dir / "data/label/label.csv")
    meta = pd.read_json(melt_dir / "data/memecoin/metadata.jsonl", lines=True)
    launches = pd.read_json(melt_dir / "data/memecoin/memecoin_list.jsonl", lines=True)

    launches["timestamp"] = pd.to_numeric(launches["timestamp"])
    launches = launches.sort_values("timestamp").reset_index(drop=True)

    # Creator-Historie & Symbol-Duplikate strikt kausal (nur frühere Events)
    creator_seen: dict[str, int] = defaultdict(int)
    creator_day_seen: dict[tuple, int] = defaultdict(int)
    symbol_seen: dict[str, int] = defaultdict(int)
    meta_by_addr = meta.set_index("address").to_dict("index")

    rows = []
    for launch in launches.itertuples():
        addr = launch.token_address
        m = meta_by_addr.get(addr, {})
        name = str(m.get("name") or "")
        symbol = str(m.get("symbol") or "")
        desc = str(m.get("description") or "")
        day = pd.Timestamp(launch.timestamp, unit="s").strftime("%Y-%m-%d")
        sym_key = symbol.upper()

        rows.append({
            "mint_address": addr,
            "timestamp": launch.timestamp,
            "has_twitter": int(bool(m.get("twitter"))),
            "has_website": int(bool(m.get("website"))),
            "has_telegram": int(bool(m.get("telegram"))),
            "n_socials": sum(bool(m.get(k)) for k in ("twitter", "website", "telegram")),
            "desc_len": len(desc),
            "desc_words": len(desc.split()),
            "desc_has_url": int(bool(re.search(r"https?://|www\.", desc))),
            "desc_all_caps_ratio": (sum(c.isupper() for c in desc) / len(desc)) if desc else 0.0,
            "name_len": len(name),
            "symbol_len": len(symbol),
            "symbol_is_upper": int(symbol.isupper()) if symbol else 0,
            "name_has_digit": int(any(c.isdigit() for c in name)),
            "name_entropy": _entropy(name),
            "symbol_dupes_before": symbol_seen[sym_key],
            "name_is_symbol": int(name.strip().upper() == sym_key),
            "creator_prior_launches": creator_seen[launch.creator],
            "creator_launch_same_day": creator_day_seen[(launch.creator, day)],
            "hour_utc": pd.Timestamp(launch.timestamp, unit="s").hour,
            "weekday": pd.Timestamp(launch.timestamp, unit="s").weekday(),
        })
        creator_seen[launch.creator] += 1
        creator_day_seen[(launch.creator, day)] += 1
        symbol_seen[sym_key] += 1

    df = pd.DataFrame(rows).merge(labels, on="mint_address", how="inner")
    df["y_high_risk"] = (df["label"] == "high").astype(int)
    return df.sort_values("timestamp").reset_index(drop=True)


def train(df: pd.DataFrame, test_fraction: float = 0.2, seed: int = 42):
    split = int(len(df) * (1 - test_fraction))
    train_df, test_df = df.iloc[:split], df.iloc[split:]
    X_tr, y_tr = train_df[FEATURES], train_df["y_high_risk"]
    X_te, y_te = test_df[FEATURES], test_df["y_high_risk"]

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=6,
        l2_regularization=1.0, random_state=seed,
    )
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, proba)
    base_rate = float(y_te.mean())

    # Operative Frage des Bots: Wenn ich nur Coins mit score < s handle,
    # wie stark sinkt die High-Risk-Quote im "Allow"-Topf, und wie viel bleibt übrig?
    operating_points = []
    for threshold in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9):
        allow = proba < threshold
        if allow.sum() == 0:
            continue
        operating_points.append({
            "threshold": threshold,
            "allow_share_pct": round(100 * float(allow.mean()), 1),
            "high_risk_in_allow_pct": round(100 * float(y_te[allow].mean()), 1),
        })

    metrics = {
        "n_train": len(train_df), "n_test": len(test_df),
        "test_base_rate_high_pct": round(100 * base_rate, 1),
        "roc_auc": round(float(auc), 4),
        "operating_points": operating_points,
        "feature_names": FEATURES,
    }
    return model, metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--melt-dir", required=True)
    parser.add_argument("--out", default="models/mlfilter-melt.joblib")
    parser.add_argument("--metrics-out", default="models/mlfilter-melt.metrics.json")
    args = parser.parse_args(argv)

    df = build_dataset(Path(args.melt_dir))
    print(f"Datensatz: {len(df)} gelabelte Launches, "
          f"{df['y_high_risk'].mean() * 100:.1f}% high-risk (Basisrate)")
    model, metrics = train(df)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "trained_on": "MELT (CC BY-NC 4.0)"}, out)
    Path(args.metrics_out).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Modell -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
