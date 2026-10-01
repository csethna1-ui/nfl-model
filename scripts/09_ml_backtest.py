#!/usr/bin/env python3
"""Step 9: Moneyline value backtest.

Converts the walk-forward model spread predictions into win probabilities via
a calibrated normal CDF, compares against vig-removed market moneylines, and
bets where the model's probability edge exceeds a threshold.

Threshold is tuned on validation (2021-2022), evaluated on test (2023-2025).
Flat 1u risk per bet. Ties = stake refunded.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
W = {"elo": 0.4, "epa": 0.5, "gbm": 0.1}


def american_to_prob(o):
    return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)


def american_payout(o):
    """profit per 1u risked on a win"""
    return o / 100.0 if o > 0 else 100.0 / -o


def run(df, sigma, thresh, dogs_only=False):
    w = l = 0
    profit = 0.0
    risked = 0.0
    dog_bets = 0
    for _, g in df.iterrows():
        p_home = norm.cdf(g["model_spread"] / sigma)
        qh = american_to_prob(g["home_moneyline"])
        qa = american_to_prob(g["away_moneyline"])
        m_home = qh / (qh + qa)
        e_home = p_home - m_home
        e_away = (1 - p_home) - (1 - m_home)
        cands = []
        if e_home >= thresh:
            cands.append(("home", e_home, g["home_moneyline"]))
        if e_away >= thresh:
            cands.append(("away", e_away, g["away_moneyline"]))
        if dogs_only:
            cands = [c for c in cands if c[2] > 0]
        if not cands:
            continue
        side, edge, odds = max(cands, key=lambda c: c[1])
        if odds > 0:
            dog_bets += 1
        hm = g["home_margin"]
        if hm == 0:
            continue  # tie: refund, no risk counted
        won = (hm > 0 and side == "home") or (hm < 0 and side == "away")
        risked += 1.0
        if won:
            w += 1
            profit += american_payout(odds)
        else:
            l += 1
            profit -= 1.0
    n = w + l
    return {"n": n, "w": w, "l": l, "wr": w / n if n else 0,
            "roi": profit / risked if risked else 0,
            "profit": profit, "dog_share": dog_bets / n if n else 0}


def main():
    d = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    d = d[d["season"] >= 2021].copy()
    d["model_spread"] = (W["elo"] * d["pred_elo"] + W["epa"] * d["pred_epa_m"]
                         + W["gbm"] * d["pred_gbm_m"])
    s = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    d = d.merge(s[["game_id", "away_moneyline", "home_moneyline"]], on="game_id")
    d = d[d["away_moneyline"].notna() & d["home_margin"].notna()].copy()
    print("games with ML + walk-forward preds:", len(d))

    val = d[d["season"] <= 2022]
    test = d[d["season"] >= 2023]
    sigma = (val["home_margin"] - val["model_spread"]).std()
    print(f"calibrated sigma (2021-2022 residuals): {sigma:.2f}")

    print("\n=== validation 2021-2022: threshold sweep (all sides) ===")
    best = None
    for t in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        r = run(val, sigma, t)
        print(f"thresh {t:.2f}: n={r['n']:4d} {r['w']}-{r['l']} "
              f"({r['wr']*100:.1f}%) ROI {r['roi']*100:+.1f}% dog_share {r['dog_share']*100:.0f}%")
        if best is None or r["roi"] > best[1]:
            best = (t, r["roi"])
    print("\n=== validation 2021-2022: threshold sweep (underdogs only) ===")
    best_dog = None
    for t in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        r = run(val, sigma, t, dogs_only=True)
        print(f"thresh {t:.2f}: n={r['n']:4d} {r['w']}-{r['l']} "
              f"({r['wr']*100:.1f}%) ROI {r['roi']*100:+.1f}%")
        if best_dog is None or r["roi"] > best_dog[1]:
            best_dog = (t, r["roi"])

    print(f"\n>>> selected: all-sides thresh={best[0]:.2f}, dogs-only thresh={best_dog[0]:.2f}")
    print("\n=== TEST 2023-2025 ===")
    r_all = run(test, sigma, best[0])
    r_dog = run(test, sigma, best_dog[0], dogs_only=True)
    for name, r in [("all sides", r_all), ("underdogs only", r_dog)]:
        se = np.sqrt(r["wr"] * (1 - r["wr"]) / r["n"]) if r["n"] else 0
        print(f"{name}: n={r['n']} {r['w']}-{r['l']} ({r['wr']*100:.1f}% +/- {se*100:.1f}) "
              f"ROI {r['roi']*100:+.1f}% profit {r['profit']:+.1f}u")


if __name__ == "__main__":
    main()
