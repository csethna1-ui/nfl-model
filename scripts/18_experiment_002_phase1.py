#!/usr/bin/env python3
"""Experiment 002, Phase 1: diagnostic decomposition of V1's margin-prediction error.

DIAGNOSIS ONLY. No model fitting, no threshold tuning, no filter selection.
Validation period 2021-2022. The 2023-2025 vault is never loaded.
Primary metrics: margin MAE, RMSE, calibration, V1 vs market. NOT ATS.
"""
import json
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
OUT = os.path.join(REPO_ROOT, "experiments", "experiment_002_v1_error_analysis")

g = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
v = g[g["season"].isin([2021, 2022])].copy().reset_index(drop=True)
assert len(v) == 569, len(v)
assert v["ens_margin"].notna().all()

v["edge"] = v["ens_margin"] - v["spread_line"]
v["err_v1"] = (v["ens_margin"] - v["home_margin"]).abs()
v["err_mkt"] = (v["spread_line"] - v["home_margin"]).abs()
v["bet_home"] = v["edge"] > 0
v["ae"] = v["edge"].abs()

# model disagreement: spread across the three ensemble components
comp = v[["pred_elo", "pred_epa_m", "pred_gbm_m"]].values
v["disagree"] = comp.std(axis=1)
v["disagree_bin"] = pd.qcut(v["disagree"], 3, labels=["low", "med", "high"])

v["rest_bin"] = np.where(v["rest_diff"] < 0, "disadvantage",
                 np.where(v["rest_diff"] > 0, "advantage", "neutral"))
v["phase"] = pd.cut(v["week"], [0, 4, 9, 14, 18, 99],
                    labels=["w1-4", "w5-9", "w10-14", "w15-18", "playoffs"])
v["edge_bin"] = pd.cut(v["ae"], [0, 1, 2, 3, 4, 99],
                       labels=["0-1", "1-2", "2-3", "3-4", "4+"])
v["div_bin"] = np.where(v["div_game"], "division", "non-division")
v["side_bin"] = np.where(v["bet_home"], "home", "away")


def calib_slope(df):
    if len(df) < 30:
        return None
    x = df["ens_margin"].values
    if x.std() < 1e-9:
        return None
    return round(float(np.polyfit(x, df["home_margin"].values, 1)[0]), 3)


def summarize(df, name):
    n = len(df)
    return {
        "n": n,
        "v1_mae": round(float(df["err_v1"].mean()), 3),
        "mkt_mae": round(float(df["err_mkt"].mean()), 3),
        "v1_minus_mkt": round(float((df["err_v1"] - df["err_mkt"]).mean()), 3),
        "v1_rmse": round(float(np.sqrt((df["ens_margin"] - df["home_margin"]).pow(2).mean())), 3),
        "mkt_rmse": round(float(np.sqrt((df["spread_line"] - df["home_margin"]).pow(2).mean())), 3),
        "calib_slope": calib_slope(df),
    }


def by(df, col):
    return {str(k): summarize(dd, k) for k, dd in df.groupby(col, observed=True)}


reg = v[v["game_type"] == "REG"]
result = {
    "scope": "validation 2021-2022, n=569 (REG 543, playoffs 26); frozen V1 outputs only",
    "overall": summarize(v, "all"),
    "by_season": by(v, "season"),
    "by_week": by(reg, "week"),
    "by_edge_bucket": by(v, "edge_bin"),
    "by_side": by(v, "side_bin"),
    "by_division": by(v, "div_bin"),
    "by_rest": by(v, "rest_bin"),
    "by_phase": by(v, "phase"),
    "by_disagreement": by(v, "disagree_bin"),
    "components": {
        c: summarize(v.assign(ens_margin=v[c], err_v1=(v[c] - v["home_margin"]).abs()), c)
        for c in ["pred_elo", "pred_epa_m", "pred_gbm_m"]
    },
    "note": ("Components evaluated as standalone margin predictors vs market. "
             "Disagreement = std across (pred_elo, pred_epa_m, pred_gbm_m), terciled. "
             "Diagnosis only: no filter selection, no threshold tuning."),
}

with open(f"{OUT}/phase1_decomposition.json", "w") as f:
    json.dump(result, f, indent=1)
print(f"wrote {OUT}/phase1_decomposition.json")

# compact console table
rows = [("ALL", result["overall"])]
for sec in ["by_season", "by_side", "by_division", "by_rest", "by_phase",
            "by_disagreement", "by_edge_bucket"]:
    for k, s in result[sec].items():
        rows.append((f"{sec[3:]}:{k}", s))
print(f"{'bucket':22s} {'n':>4s} {'v1':>7s} {'mkt':>7s} {'v1-mkt':>7s} {'rmse_v1':>8s} {'slope':>6s}")
for name, s in rows:
    print(f"{name:22s} {s['n']:4d} {s['v1_mae']:7.3f} {s['mkt_mae']:7.3f} "
          f"{s['v1_minus_mkt']:+7.3f} {s['v1_rmse']:8.3f} {str(s['calib_slope']):>6s}")
print("\ncomponents as standalone predictors:")
for c, s in result["components"].items():
    print(f"  {c:12s} n={s['n']} v1_mae={s['v1_mae']:.3f} mkt_mae={s['mkt_mae']:.3f} "
          f"diff={s['v1_minus_mkt']:+.3f} slope={s['calib_slope']}")
