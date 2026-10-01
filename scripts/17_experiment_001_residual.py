#!/usr/bin/env python3
"""Step 17: Experiment 001 — market-residual model.

Target: residual = actual_margin - market_spread.
Compares training approaches on 2021-2022 VALIDATION only:
  A) fixed window: ridge trained once on 2018-2020
  B) expanding walk-forward: ridge retrained weekly on all strictly-earlier games
  C) recency-weighted expanding walk-forward (decay lambda chosen on validation)
Baselines: market-only (predicted residual = 0), V1 (ens_margin).

Pre-registered decision rule: the winner (lowest validation residual MAE) earns
ONE vault evaluation (2023-2025) only if its validation margin MAE
(market + predicted_residual) beats market-only margin MAE. Otherwise: null
result, no vault touch.

Writes experiments/experiment_001_market_residual/results.json + REPORT.md.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
EXP_DIR = os.path.join(REPO_ROOT, "experiments", "experiment_001_market_residual")

FEATURES = ["elo_diff", "off_epa_diff", "def_epa_diff", "off_pass_diff",
            "off_rush_diff", "def_pass_diff", "def_rush_diff",
            "sr_off_diff", "sr_def_diff", "rest_diff", "div_game", "week"]
ALPHA = 1.0  # fixed; no hyperparameter search (small NFL sample)
LAMBDA_GRID = [0.0025, 0.005, 0.01, 0.02, 0.04]  # per-week decay
ATS_T = 3.0


def fit_predict_ridge(train, pred, sample_weight=None):
    sc = StandardScaler()
    Xtr = sc.fit_transform(train[FEATURES].values)
    Xpr = sc.transform(pred[FEATURES].values)
    m = Ridge(alpha=ALPHA)
    m.fit(Xtr, train["residual"].values, sample_weight=sample_weight)
    return m.predict(Xpr)


def ats(pred_resid, market, actual, t=ATS_T):
    """Picks where |predicted residual| >= t (adjusted model edge vs market)."""
    sel = np.abs(pred_resid) >= t
    if sel.sum() == 0:
        return {"n": 0, "w": 0, "l": 0, "win_pct": None}
    side_home = pred_resid[sel] > 0
    win = np.where(side_home, actual[sel] > market[sel], actual[sel] < market[sel])
    push = actual[sel] == market[sel]
    win, push = win[~push], push[~push]
    n = len(win)
    w = int(win.sum())
    return {"n": n, "w": w, "l": n - w,
            "win_pct": round(w / n, 3) if n else None}


def metrics(df):
    """df has pred_resid, market_spread, actual_margin, v1_margin."""
    r = df["residual"].values
    pr = df["pred_resid"].values
    adj = df["market_spread"].values + pr
    act = df["actual_margin"].values
    mkt = df["market_spread"].values
    out = {
        "n": int(len(df)),
        "resid_mae": round(float(np.abs(r - pr).mean()), 3),
        "resid_rmse": round(float(np.sqrt(((r - pr) ** 2).mean())), 3),
        "margin_mae_adj": round(float(np.abs(act - adj).mean()), 3),
        "margin_mae_market": round(float(np.abs(act - mkt).mean()), 3),
        "corr_adj_actual": round(float(np.corrcoef(adj, act)[0, 1]), 3),
    }
    v1 = df.dropna(subset=["v1_margin"])
    out["margin_mae_v1"] = (round(float(np.abs(v1["actual_margin"] - v1["v1_margin"]).mean()), 3)
                            if len(v1) else None)
    if np.std(pr) > 1e-9:
        slope, icept = np.polyfit(pr, r, 1)
        out["calibration"] = {"slope": round(float(slope), 3),
                              "intercept": round(float(icept), 3)}
    else:
        out["calibration"] = {"slope": None, "intercept": None,
                              "note": "no variance in predictions"}
    out["ats_adj_at_3"] = ats(pr, mkt, act)
    if len(v1):
        e1 = (v1["v1_margin"] - v1["market_spread"]).values
        out["ats_v1_at_3"] = ats(e1, v1["market_spread"].values,
                                 v1["actual_margin"].values)
    return out


def expanding_predict(d, predict_mask, lam=None):
    """Weekly expanding walk-forward predictions for rows in predict_mask."""
    d = d.sort_values(["season", "week", "gameday"]).reset_index(drop=True)
    pred_idx = d.index[predict_mask].tolist()
    weeks = sorted(set((d.loc[i, "season"], d.loc[i, "week"]) for i in pred_idx))
    out = pd.Series(np.nan, index=d.index)
    for (s, w) in weeks:
        tr = d[((d["season"] < s) | ((d["season"] == s) & (d["week"] < w)))]
        pr = d[(d["season"] == s) & (d["week"] == w)]
        sw = None
        if lam is not None:
            ref = pr["gameday"].min()
            weeks_ago = (ref - tr["gameday"]).dt.days / 7.0
            sw = np.exp(-lam * weeks_ago.values)
        out.loc[pr.index] = fit_predict_ridge(tr, pr, sample_weight=sw)
    return out


def main():
    d = pd.read_parquet(f"{DATA}/experiments/games_features.parquet")
    d = d.sort_values(["season", "week", "gameday"]).reset_index(drop=True)
    val_m = d["season"].between(2021, 2022)
    vault_m = d["season"].between(2023, 2025)

    results = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "alpha": ALPHA, "features": FEATURES}

    # ---- Approach A: fixed window ----
    trA = d[d["season"].between(2018, 2020)]
    va = d[val_m].copy()
    va["pred_resid"] = fit_predict_ridge(trA, va)
    mA = metrics(va)

    # ---- Approach B: expanding walk-forward ----
    dB = d.copy()
    dB["pred_resid"] = expanding_predict(d, val_m, lam=None)
    mB = metrics(dB[val_m].copy())

    # ---- Approach C: recency-weighted expanding (lambda on validation) ----
    grid = {}
    for lam in LAMBDA_GRID:
        dC = d.copy()
        dC["pred_resid"] = expanding_predict(d, val_m, lam=lam)
        grid[str(lam)] = metrics(dC[val_m].copy())["resid_mae"]
    best_lam = min(grid, key=grid.get)
    dC = d.copy()
    dC["pred_resid"] = expanding_predict(d, val_m, lam=float(best_lam))
    mC = metrics(dC[val_m].copy())

    # ---- market-only baseline on validation ----
    va0 = va.copy()
    va0["pred_resid"] = 0.0
    mM = metrics(va0)

    results["validation_2021_2022"] = {
        "A_fixed_2018_2020": mA,
        "B_expanding": mB,
        f"C_recency_weighted_lambda_{best_lam}": mC,
        "lambda_grid_resid_mae": grid,
        "market_only": mM,
    }
    # by-season stability for each approach
    for name, frame in [("A", va), ("B", dB[val_m]), ("C", dC[val_m])]:
        for s in (2021, 2022):
            fs = frame[frame["season"] == s].copy()
            results["validation_2021_2022"][f"{name}_season_{s}"] = {
                "resid_mae": round(float(np.abs(fs["residual"] - fs["pred_resid"]).mean()), 3),
                "margin_mae_adj": round(float(np.abs(fs["actual_margin"] - (fs["market_spread"] + fs["pred_resid"])).mean()), 3),
                "margin_mae_market": round(float(np.abs(fs["actual_margin"] - fs["market_spread"]).mean()), 3),
                "n": int(len(fs)),
            }

    # ---- pre-registered decision ----
    cands = {"A": mA, "B": mB, "C": mC}
    winner = min(cands, key=lambda k: cands[k]["resid_mae"])
    w = cands[winner]
    eligible = w["margin_mae_adj"] < mM["margin_mae_market"]
    results["decision"] = {
        "rule": ("winner = lowest validation residual MAE; vault run only if "
                 "winner's validation margin MAE (market+pred_resid) < market-only margin MAE"),
        "winner": winner,
        "winner_resid_mae": w["resid_mae"],
        "winner_margin_mae_adj": w["margin_mae_adj"],
        "market_margin_mae": mM["margin_mae_market"],
        "vault_eligible": bool(eligible),
    }
    print("validation resid MAE:",
          {k: v["resid_mae"] for k, v in cands.items()},
          "| market margin MAE:", mM["margin_mae_market"])
    print("winner:", winner, "| vault eligible:", eligible)

    # ---- ONE vault run, locked methodology ----
    if eligible:
        dv = d.copy()
        if winner == "A":
            trA2 = d[d["season"].between(2018, 2020)]
            vv = d[vault_m].copy()
            vv["pred_resid"] = fit_predict_ridge(trA2, vv)
        elif winner == "B":
            dv["pred_resid"] = expanding_predict(d, vault_m, lam=None)
            vv = dv[vault_m].copy()
        else:
            dv["pred_resid"] = expanding_predict(d, vault_m, lam=float(best_lam))
            vv = dv[vault_m].copy()
        mv = metrics(vv)
        mv_season = {}
        for s in (2023, 2024, 2025):
            fs = vv[vv["season"] == s].copy()
            mv_season[str(s)] = {
                "resid_mae": round(float(np.abs(fs["residual"] - fs["pred_resid"]).mean()), 3),
                "margin_mae_adj": round(float(np.abs(fs["actual_margin"] - (fs["market_spread"] + fs["pred_resid"])).mean()), 3),
                "margin_mae_market": round(float(np.abs(fs["actual_margin"] - fs["market_spread"]).mean()), 3),
                "margin_mae_v1": round(float(np.abs(fs["actual_margin"] - fs["v1_margin"]).mean()), 3),
                "n": int(len(fs)),
            }
        results["vault_2023_2025"] = {"overall": mv, "by_season": mv_season,
                                      "note": ("Single locked evaluation. Vault was not "
                                               "used for any selection decision.")}
        print("vault margin MAE adj/market/v1:",
              mv["margin_mae_adj"], mv["margin_mae_market"], mv["margin_mae_v1"])
    else:
        results["vault_2023_2025"] = None
        print("NULL RESULT: no approach beat the market on validation. Vault untouched.")

    with open(f"{EXP_DIR}/results.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"wrote {EXP_DIR}/results.json")
    return results


if __name__ == "__main__":
    main()
