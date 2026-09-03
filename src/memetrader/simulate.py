"""Kalibrierter pump.fun-Markt-Simulator für Lookahead-freie Backtests.

WAS DAS IST – UND WAS NICHT: Dies ist KEINE historische Replay realer Trades
(dafür `memetrader record` + `backtest` auf der Aufzeichnung nutzen). Es ist
ein stochastischer Markt, kalibriert auf die recherchierten realen Basisraten
(docs/filter-engine.md 6b):
  ~62 % Insta-Tod, ~20 % langsames Ausbluten, ~9 % Bundle-Pump&Dump,
  ~4,5 % Creator-Rug, ~3,5 % organische Läufer, ~1 % Graduations.
Der Bot sieht ausschließlich den Event-Strom bis Zeitpunkt t – die Archetyp-
Zuordnung ist ihm unbekannt, Ergebnisse entstehen allein aus den Events.
Preise folgen exakt der Bonding-Curve-Mathematik (curve.py).

Grenzen der Aussagekraft: Ergebnisse zeigen das Verhalten des Systems unter
den kalibrierten Raten, nicht die reale PnL eines Kalenderzeitraums.
"""

from __future__ import annotations

import json
import random

V_SOL0 = 30.0
V_TOK0 = 1_073_000_000.0
GRADUATION_SOL = 85.0

ARCHETYPES = [
    ("instant_dead", 0.58),
    ("slow_bleed", 0.18),
    ("bundled_pump_dump", 0.05),
    ("stealth_bundle", 0.06),   # Bundle-Dump OHNE Creator-Verkaufssignal
    ("wash_trap", 0.04),        # gefälschte Käufer/Volumen, dann Dump
    ("creator_rug", 0.045),
    ("organic_runner", 0.035),
    ("graduation_runner", 0.01),
]

TOP_COINS = ["PEPE", "WIF", "BONK", "TRUMP", "DOGE", "MOODENG", "PNUT", "SPX"]
SYLLABLES = ["mo", "za", "ki", "lu", "pep", "dog", "cat", "flo", "gro", "sni",
             "bur", "tre", "wag", "yol", "chi", "pum", "nak", "ler", "vib", "zoo"]


class _SimToken:
    """Curve-Zustand + Wallet-Bestände eines simulierten Tokens."""

    def __init__(self, mint: str, rng: random.Random):
        self.mint = mint
        self.v_sol = V_SOL0
        self.v_tokens = V_TOK0
        self.k = V_SOL0 * V_TOK0
        self.real_sol = 0.0
        self.holdings: dict[str, float] = {}
        self.rng = rng
        self.migrated = False

    def buy(self, wallet: str, sol: float) -> dict:
        tokens = self.v_tokens - self.k / (self.v_sol + sol)
        self.v_sol += sol
        self.v_tokens = self.k / self.v_sol
        self.real_sol += sol
        self.holdings[wallet] = self.holdings.get(wallet, 0.0) + tokens
        return {"txType": "buy", "mint": self.mint, "traderPublicKey": wallet,
                "solAmount": sol, "vSolInBondingCurve": self.v_sol,
                "vTokensInBondingCurve": self.v_tokens}

    def sell(self, wallet: str, fraction: float) -> dict | None:
        tokens = self.holdings.get(wallet, 0.0) * fraction
        if tokens <= 0:
            return None
        sol_out = self.v_sol - self.k / (self.v_tokens + tokens)
        sol_out = min(sol_out, max(0.0, self.real_sol))
        self.v_tokens += tokens
        self.v_sol = self.k / self.v_tokens
        self.real_sol -= sol_out
        self.holdings[wallet] -= tokens
        return {"txType": "sell", "mint": self.mint, "traderPublicKey": wallet,
                "solAmount": sol_out, "vSolInBondingCurve": self.v_sol,
                "vTokensInBondingCurve": self.v_tokens}


def _name(rng: random.Random, impersonate: bool) -> tuple[str, str]:
    if impersonate:
        base = rng.choice(TOP_COINS)
        return base.title(), base
    name = "".join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 3)))
    return name.title(), name.upper()[: rng.randint(3, 6)]


# Socials-Wahrscheinlichkeiten je Archetyp (kalibriert an: Telegram-Link =>
# 8,9x Graduation-Rate, arXiv 2607.02823; Rugs tarnen sich oft mit Socials)
SOCIAL_PROBS = {
    "instant_dead": (0.08, 0.05, 0.10, 0.2),   # (twitter, website, telegram, desc_rich)
    "slow_bleed": (0.25, 0.15, 0.25, 0.4),
    "bundled_pump_dump": (0.35, 0.20, 0.30, 0.5),
    # Härtung: professionelle Fallen FÄLSCHEN gute Metadaten – gleiche
    # Socials-Qualität wie organische Läufer, das ML-Gate hilft hier nicht
    "stealth_bundle": (0.65, 0.45, 0.65, 0.8),
    "wash_trap": (0.65, 0.45, 0.65, 0.8),
    "creator_rug": (0.55, 0.35, 0.50, 0.7),
    "organic_runner": (0.65, 0.45, 0.65, 0.8),
    "graduation_runner": (0.80, 0.60, 0.85, 0.9),
}


def _meta_uri(archetype: str, name: str, rng: random.Random) -> str:
    p_tw, p_web, p_tg, p_desc = SOCIAL_PROBS[archetype]
    meta = {
        "description": (f"{name} community coin. "
                        + " ".join(rng.choice(SYLLABLES) for _ in range(rng.randint(8, 30)))
                        if rng.random() < p_desc else ""),
        "twitter": f"https://x.com/{name.lower()}" if rng.random() < p_tw else None,
        "website": f"https://{name.lower()}.xyz" if rng.random() < p_web else None,
        "telegram": f"https://t.me/{name.lower()}" if rng.random() < p_tg else None,
    }
    return "data:application/json," + json.dumps(meta)


def _launch_events(mint: str, t0: float, archetype: str, rng: random.Random) -> list[tuple[float, dict]]:
    creator = f"dev_{mint}"
    impersonate = rng.random() < (0.25 if archetype in ("instant_dead", "bundled_pump_dump") else 0.02)
    name, symbol = _name(rng, impersonate)
    token = _SimToken(mint, rng)
    dev_buy = round(max(0.0, rng.lognormvariate(-0.7, 0.9)), 3)
    dev_buy = min(dev_buy, 6.0)
    events: list[tuple[float, dict]] = []

    create = {"txType": "create", "mint": mint, "traderPublicKey": creator,
              "name": name, "symbol": symbol, "uri": _meta_uri(archetype, name, rng),
              "solAmount": dev_buy, "vSolInBondingCurve": token.v_sol + dev_buy,
              "vTokensInBondingCurve": token.k / (token.v_sol + dev_buy)}
    if dev_buy > 0:
        token.buy(creator, dev_buy)
    events.append((t0, create))

    # Aktionen sammeln und erst chronologisch sortiert gegen die Curve rechnen:
    actions: list[tuple[float, str, str, float]] = []  # (t, wallet, kind, param)

    def act(t, wallet, kind, param=0.0):
        actions.append((t0 + t, wallet, kind, param))

    if archetype == "instant_dead":
        for i in range(rng.randint(0, 6)):
            act(rng.uniform(1, 120), f"w{i}", "buy", rng.uniform(0.01, 0.2))
        for i in range(rng.randint(0, 4)):
            act(rng.uniform(60, 300), f"w{i}", "sell", 1.0)
        if dev_buy > 0 and rng.random() < 0.6:
            act(rng.uniform(120, 600), creator, "sell", 1.0)

    elif archetype == "slow_bleed":
        n = rng.randint(8, 20)
        for i in range(n):
            act(rng.uniform(5, 2400), f"w{i}", "buy", rng.uniform(0.05, 0.4))
        for i in range(int(n * rng.uniform(0.4, 0.9))):
            act(rng.uniform(600, 5400), f"w{i}", "sell", rng.uniform(0.6, 1.0))
        if dev_buy > 0:
            act(rng.uniform(1800, 7200), creator, "sell", 1.0)

    elif archetype == "bundled_pump_dump":
        n = rng.randint(15, 35)
        burst = rng.uniform(20, 120)
        for i in range(n):
            act(rng.uniform(2, burst), f"b{i}", "buy", rng.uniform(0.3, 0.8))
        for i in range(rng.randint(2, 8)):  # wenige echte Nachläufer
            act(rng.uniform(burst, burst + 240), f"organic{i}", "buy", rng.uniform(0.05, 0.3))
        t_dump = rng.uniform(120, 600)
        for i in range(n):
            act(t_dump + rng.uniform(0, 90), f"b{i}", "sell", 1.0)
        if dev_buy > 0:
            act(t_dump + rng.uniform(0, 60), creator, "sell", 1.0)

    elif archetype == "stealth_bundle":
        # Bundle kauft schnell mit ähnlichen Größen; Creator verkauft NIE
        # (kein creator_sold-Rettungssignal); Dump über die Bundle-Wallets
        n = rng.randint(16, 35)
        burst = rng.uniform(30, 90)
        base_size = rng.uniform(0.35, 0.6)
        for i in range(n):
            act(rng.uniform(2, burst), f"sb{i}", "buy", base_size * rng.uniform(0.85, 1.15))
        for i in range(rng.randint(3, 9)):  # echte Nachläufer als Opfer
            act(rng.uniform(burst, burst + 300), f"victim{i}", "buy", rng.uniform(0.05, 0.4))
        t_dump = rng.uniform(180, 900)
        for i in range(n):
            act(t_dump + rng.uniform(0, 120), f"sb{i}", "sell", 1.0)

    elif archetype == "wash_trap":
        # Viele 'Käufer' sind Roundtrip-Wallets: kaufen und verkaufen zyklisch,
        # täuschen Aktivität/Unique-Buyer vor; am Ende koordinierter Dump
        n = rng.randint(14, 30)
        for i in range(n):
            t_in = rng.uniform(10, 900)
            act(t_in, f"ww{i}", "buy", rng.uniform(0.2, 0.7))
            act(t_in + rng.uniform(20, 180), f"ww{i}", "sell", rng.uniform(0.5, 0.9))
            act(t_in + rng.uniform(200, 500), f"ww{i}", "buy", rng.uniform(0.2, 0.7))
        for i in range(rng.randint(2, 6)):
            act(rng.uniform(300, 1200), f"victim{i}", "buy", rng.uniform(0.05, 0.4))
        t_dump = rng.uniform(900, 1800)
        for i in range(n):
            act(t_dump + rng.uniform(0, 150), f"ww{i}", "sell", 1.0)

    elif archetype == "creator_rug":
        n = rng.randint(15, 40)
        for i in range(n):
            act(rng.uniform(10, 1800), f"w{i}", "buy", rng.uniform(0.1, 0.7))
        t_rug = rng.uniform(600, 2400)
        act(t_rug, creator, "sell", 1.0)
        for i in range(int(n * 0.7)):  # Panik-Kaskade
            act(t_rug + rng.uniform(5, 300), f"w{i}", "sell", 1.0)

    elif archetype == "organic_runner":
        n = rng.randint(30, 120)
        horizon = rng.uniform(3600, 5 * 3600)
        for i in range(n):
            act(rng.uniform(10, horizon), f"w{i}", "buy", rng.uniform(0.1, 0.9))
        retrace = rng.random() < 0.7
        sell_share = rng.uniform(0.5, 0.85) if retrace else rng.uniform(0.15, 0.4)
        for i in range(int(n * sell_share)):
            act(rng.uniform(horizon * 0.4, horizon * 1.4), f"w{i}", "sell", rng.uniform(0.5, 1.0))

    elif archetype == "graduation_runner":
        n = rng.randint(80, 200)
        horizon = rng.uniform(3600, 4 * 3600)
        for i in range(n):
            # Beschleunigung Richtung Graduation
            t = horizon * (rng.random() ** 0.6)
            act(t, f"w{i}", "buy", rng.uniform(0.3, 1.2))
        for i in range(int(n * 0.25)):
            act(rng.uniform(horizon * 0.3, horizon), f"w{i}", "sell", rng.uniform(0.3, 0.8))

    actions.sort(key=lambda a: a[0])
    for t, wallet, kind, param in actions:
        if token.migrated:
            break
        if kind == "buy":
            events.append((t, token.buy(wallet, param)))
            if token.real_sol >= GRADUATION_SOL:
                token.migrated = True
                events.append((t + 1.0, {"txType": "migrate", "mint": mint, "pool": "pump-amm"}))
        else:
            sell_event = token.sell(wallet, param)
            if sell_event is not None:
                events.append((t, sell_event))
    return events


def generate_market(days: float, launches_per_day: int, seed: int) -> list[tuple[float, dict]]:
    """Erzeugt den chronologischen Event-Strom eines simulierten Zeitraums."""
    rng = random.Random(seed)
    names, weights = zip(*ARCHETYPES)
    events: list[tuple[float, dict]] = []
    total = int(days * launches_per_day)
    for i in range(total):
        t0 = rng.uniform(0, days * 86400.0)
        archetype = rng.choices(names, weights=weights, k=1)[0]
        events.extend(_launch_events(f"SIM{i:06d}", t0, archetype, rng))
    events.sort(key=lambda e: e[0])
    return events
