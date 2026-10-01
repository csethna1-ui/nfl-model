#!/usr/bin/env python3
"""Step 4: Walk-forward backtest.
Components: (a) ELO->margin linear, (b) EPA->margin/total linear, (c) gradient-boosted
regressors on efficiency differentials. Ensemble weights tuned on 2021-2022 validation.
All features for a game use only data through the prior week (ratings are pre-computed
walk-forward in 03_ratings.py). XGBoost trains on expanding window of past games only.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")

try:
    from xgboost import XGBRegressor
    GBM = "xgboost"
except ImportError:
    from sklearn.ensemble import HistGradientBoostingRegressor
    GBM = "sklearn-hgbr"
print("GBM backend:", GBM, flush=True)

MARGIN_FEATS = ["elo_diff",
    "off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
    "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff",
    "rest_diff", "div_game", "week"]
TOTAL_FEATS = ["off_epa_sum", "def_epa_sum", "off_pass_sum", "off_rush_sum",
    "def_pass_sum", "def_rush_sum", "sr_off_sum", "sr_def_sum",
    "rest_diff", "div_game", "week"]

def add_features(d):
    d = d.copy()
    d["off_epa_diff"] = d["home_off_epa"] - d["away_off_epa"]
    d["def_epa_diff"] = d["home_def_epa"] - d["away_def_epa"]
    d["off_pass_diff"] = d["home_off_pass_epa"] - d["away_off_pass_epa"]
    d["off_rush_diff"] = d["home_off_rush_epa"] - d["away_off_rush_epa"]
    d["def_pass_diff"] = d["home_def_pass_epa"] - d["away_def_pass_epa"]
    d["def_rush_diff"] = d["home_def_rush_epa"] - d["away_def_rush_epa"]
    d["sr_off_diff"] = d["home_off_sr"] - d["away_off_sr"]
    d["sr_def_diff"] = d["home_def_sr"] - d["away_def_sr"]
    d["off_epa_sum"] = d["home_off_epa"] + d["away_off_epa"]
    d["def_epa_sum"] = d["home_def_epa"] + d["away_def_epa"]
    d["off_pass_sum"] = d["home_off_pass_epa"] + d["away_off_pass_epa"]
    d["off_rush_sum"] = d["home_off_rush_epa"] + d["away_off_rush_epa"]
    d["def_pass_sum"] = d["home_def_pass_epa"] + d["away_def_pass_epa"]
    d["def_rush_sum"] = d["home_def_rush_epa"] + d["away_def_rush_epa"]
    d["sr_off_sum"] = d["home_off_sr"] + d["away_off_sr"]
    d["sr_def_sum"] = d["home_def_sr"] + d["away_def_sr"]
    d["rest_diff"] = d["home_rest"] - d["away_rest"]
    return d

def make_gbm():
    if GBM == "xgboost":
        return XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                            random_state=42, n_jobs=4)
    else:
        return HistGradientBoostingRegressor(max_iter=200, max_depth=3,
                            learning_rate=0.05, l2_regularization=1.0, random_state=42)

def main():
    d = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
    d = add_features(d).sort_values(["season", "week"]).reset_index(drop=True)
    train = d[d["season"] <= 2020]
    print("train games 2018-2020:", len(train), flush=True)

    # (a) ELO -> margin, fit on train
    lr_elo = LinearRegression().fit(train[["elo_diff"]], train["home_margin"])
    print(f"ELO->margin: margin = {lr_elo.intercept_:.2f} + {lr_elo.coef_[0]:.4f}*elo_diff")
    # (b) EPA -> margin / total, fit on train
    epa_m_feats = ["off_epa_diff", "def_epa_diff", "off_pass_diff", "off_rush_diff",
                   "def_pass_diff", "def_rush_diff", "sr_off_diff", "sr_def_diff"]
    lr_epa_m = LinearRegression().fit(train[epa_m_feats], train["home_margin"])
    epa_t_feats = ["off_epa_sum", "def_epa_sum", "off_pass_sum", "off_rush_sum",
                   "def_pass_sum", "def_rush_sum"]
    lr_epa_t = LinearRegression().fit(train[epa_t_feats], train["total_pts"])
    print("EPA margin R^2 (train):", round(lr_epa_m.score(train[epa_m_feats], train["home_margin"]), 3))
    print("EPA total R^2 (train):", round(lr_epa_t.score(train[epa_t_feats], train["total_pts"]), 3))

    d["pred_elo"] = lr_elo.predict(d[["elo_diff"]])
    d["pred_epa_m"] = lr_epa_m.predict(d[epa_m_feats])
    d["pred_epa_t"] = lr_epa_t.predict(d[epa_t_feats])

    # (c) walk-forward GBM, 2021+
    d["pred_gbm_m"] = np.nan
    d["pred_gbm_t"] = np.nan
    bt = d[d["season"] >= 2021].copy()
    weeks = bt[["season", "week"]].drop_duplicates().sort_values(["season", "week"])
    print("walk-forward weeks:", len(weeks), flush=True)
    for i, (s, w) in enumerate(weeks.itertuples(index=False)):
        hist = d[(d["season"] < s) | ((d["season"] == s) & (d["week"] < w))]
        cur = (d["season"] == s) & (d["week"] == w)
        if len(hist) < 200:
            continue
        gm = make_gbm().fit(hist[MARGIN_FEATS], hist["home_margin"])
        gt = make_gbm().fit(hist[TOTAL_FEATS], hist["total_pts"])
        d.loc[cur, "pred_gbm_m"] = gm.predict(d.loc[cur, MARGIN_FEATS])
        d.loc[cur, "pred_gbm_t"] = gt.predict(d.loc[cur, TOTAL_FEATS])
        if i % 20 == 0:
            print(f"  done {s} w{w} ({i+1}/{len(weeks)})", flush=True)

    d.to_parquet(f"{DATA}/games_with_preds.parquet", index=False)
    print("saved games_with_preds.parquet")
    # save fitted linear models + gbm factory info
    import pickle
    with open(f"{DATA}/linear_models.pkl", "wb") as f:
        pickle.dump({"lr_elo": lr_elo, "lr_epa_m": lr_epa_m, "lr_epa_t": lr_epa_t,
                     "epa_m_feats": epa_m_feats, "epa_t_feats": epa_t_feats,
                     "gbm_backend": GBM}, f)

if __name__ == "__main__":
    main()
