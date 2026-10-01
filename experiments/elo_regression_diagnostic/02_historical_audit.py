#!/usr/bin/env python3
"""ELO regression diagnostic — Part 2: historical early-season audit.

Walk-forward, vault-clean: test seasons 2019-2022 (2023-2025 NEVER touched).
For each offseason-regression setting, run production ELO mechanics from 2018,
predict pre-game ELO-implied home margin at weeks {1,2,3,4,6,8} via OLS
(home_margin ~ elo_diff) fit on strictly-prior seasons (per setting), report MAE.

READ-ONLY diagnostic. Touches nothing in production.
"""
import numpy as np
import pandas as pd
import importlib.util

spec = importlib.util.spec_from_file_location("r03", "/home/hatch/workspace/nfl-model/scripts/03_ratings.py")
r03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r03)

DATA = "/home/hatch/workspace/nfl-model/data"
OUT = "/home/hatch/workspace/nfl-model/experiments/elo_regression_diagnostic"

CHECKPOINTS = [1, 2, 3, 4, 6, 8]
LATER = list(range(9, 19))
TEST_SEASONS = [2019, 2020, 2021, 2022]
SETTINGS = {"regress_1_3": 1/3, "regress_1_2": 0.5, "regress_2_3": 2/3, "regress_full": 1.0}

sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
g = sched[(sched["home_score"].notna()) & (sched["season"] <= 2022)].copy()
g = g.sort_values(["season", "week"]).reset_index(drop=True)
g["home_margin"] = g["home_score"] - g["away_score"]


def run_elo_setting(games, regress):
    """Production ELO mechanics with a given offseason regression. Returns
    per-game pre-game elo_diff (no lookahead: weekly batching)."""
    elos, rows = {}, []
    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if week == 1:
            for t in list(elos.keys()):
                elos[t] = 1500.0 + (elos[t] - 1500.0) * (1 - regress)
        updates = {}
        for _, gg in grp.iterrows():
            h, a = gg["home_team"], gg["away_team"]
            he = elos.get(h, 1500.0); ae = elos.get(a, 1500.0)
            diff = he - ae + r03.HFA_ELO
            exp_h = 1.0 / (1.0 + 10 ** (-diff / 400.0))
            actual = 1.0 if gg["home_margin"] > 0 else (0.5 if gg["home_margin"] == 0 else 0.0)
            mm = r03.mov_multiplier(gg["home_margin"], diff)
            d = r03.K * mm * (actual - exp_h)
            updates[h] = updates.get(h, 0.0) + d
            updates[a] = updates.get(a, 0.0) - d
            rows.append({"season": season, "week": week, "game_id": gg["game_id"],
                         "elo_diff": he - ae, "home_margin": gg["home_margin"]})
        for t, d in updates.items():
            elos[t] = elos.get(t, 1500.0) + d
    return pd.DataFrame(rows)


def ols_fit_predict(train, test_x):
    X = np.column_stack([np.ones(len(train)), train["elo_diff"].values])
    y = train["home_margin"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta[0] + beta[1] * test_x


results = []
for name, regress in SETTINGS.items():
    edf = run_elo_setting(g, regress)
    for season in TEST_SEASONS:
        train = edf[edf["season"] < season]
        test = edf[edf["season"] == season].copy()
        test["pred"] = ols_fit_predict(train, test["elo_diff"].values)
        test["ae"] = (test["home_margin"] - test["pred"]).abs()
        for wk in CHECKPOINTS:
            sub = test[test["week"] == wk]
            results.append({"setting": name, "regress": regress, "season": season,
                            "checkpoint": f"week_{wk}", "n": len(sub),
                            "mae": sub["ae"].mean()})
        sub = test[test["week"].isin(LATER)]
        results.append({"setting": name, "regress": regress, "season": season,
                        "checkpoint": "weeks_9_18", "n": len(sub), "mae": sub["ae"].mean()})
        sub = test[test["week"].isin(CHECKPOINTS)]
        results.append({"setting": name, "regress": regress, "season": season,
                        "checkpoint": "early_pooled", "n": len(sub), "mae": sub["ae"].mean()})

res = pd.DataFrame(results)
res.to_csv(f"{OUT}/table_historical_regression_audit.csv", index=False)

# pooled across seasons (n-weighted)
pool = res.groupby(["setting", "regress", "checkpoint"]).apply(
    lambda d: pd.Series({"n": d["n"].sum(),
                         "mae": np.average(d["mae"], weights=d["n"])})).reset_index()
pool.to_csv(f"{OUT}/table_historical_regression_pooled.csv", index=False)

print("=== pooled MAE by setting x checkpoint (n-weighted) ===")
piv = pool.pivot(index="checkpoint", columns="setting", values="mae")
print(piv.round(3).to_string())
print("\n=== n per checkpoint ===")
print(pool.pivot(index="checkpoint", columns="setting", values="n").to_string())
print("\n=== by season: early_pooled ===")
print(res[res.checkpoint == "early_pooled"].pivot(index="season", columns="setting", values="mae").round(3).to_string())
print("\n=== by season: weeks_9_18 ===")
print(res[res.checkpoint == "weeks_9_18"].pivot(index="season", columns="setting", values="mae").round(3).to_string())
