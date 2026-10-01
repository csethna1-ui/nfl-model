#!/usr/bin/env python3
"""Step 12: v2 backtest — adds walk-forward QB EPA/play ratings + wind.

Same discipline as v1 (04/05): linear components fit on 2018-2020,
walk-forward GBM from 2021+, ensemble weights + spread threshold tuned on
2021-2022 validation, honest report on 2023-2025 test.

The QB feature (qb_epa_diff) is folded into the linear models as a raw
feature rather than pre-scaled to points: OLS then estimates its partial
effect controlling for team pass EPA (which is correlated, since team pass
EPA includes the QB). A separate pre-scaling OLS would double-count the QB
signal and need another ensemble weight to tune. Wind enters both margin
and total models.

Usage: ./venv/bin/python scripts/12_backtest_v2.py
Saves: linear_models_v2.pkl, ensemble_params_v2.json, games_with_preds_v2.parquet
"""
import itertools
import json
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from importlib import import_module

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from model_lib import (add_features, add_wind, make_gbm, GBM_BACKEND,
                       EPA_M_FEATS, EPA_T_FEATS,
                       MARGIN_FEATS_V2, TOTAL_FEATS_V2,
                       EPA_M_FEATS_V2, EPA_T_FEATS_V2)
from qb_ratings import build_name_map, run_qb_ratings

ratings_mod = import_module("03_ratings")
run_elo = ratings_mod.run_elo
run_epa_current = import_module("07_update_weekly").run_epa_current
m05 = import_module("05_metrics")

DATA = os.path.join(REPO_ROOT, "data")
THRESHOLDS = [1.5, 2.0, 2.5, 3.0]


def ols_tstats(X, y):
    """Coef + t-stats via normal equations (for the report, not used for fit)."""
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, res, rank, sv = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    s2 = resid @ resid / (len(y) - X1.shape[1])
    cov = s2 * np.linalg.inv(X1.T @ X1)
    se = np.sqrt(np.diag(cov))[1:]
    return beta[1:], beta[1:] / se


def build_frame(use_qb=True):
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    g = sched[(sched["home_score"].notna()) & (sched["season"] <= 2025)].copy()
    g = g.sort_values(["season", "week"]).reset_index(drop=True)
    g["home_margin"] = g["home_score"] - g["away_score"]
    g["total_pts"] = g["home_score"] + g["away_score"]
    print("played games 2018-2025:", len(g), flush=True)

    elo_df, _ = run_elo(g)
    pbp = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
    epa_df, _ = run_epa_current(pbp, g)

    out = g[["game_id", "season", "week", "home_team", "away_team",
             "home_score", "away_score", "home_margin", "total_pts",
             "spread_line", "total_line", "home_rest", "away_rest", "div_game",
             "home_qb_name", "away_qb_name", "wind", "roof"]].merge(
        elo_df, on="game_id").merge(epa_df, on="game_id")

    if use_qb:
        pbp_qb = pd.read_parquet(f"{DATA}/pbp_qb_2018_2026.parquet")
        name_map = build_name_map(g, pbp_qb)
        print("QB name mappings learned:", len(name_map), flush=True)
        qb_df, _, lg_mean = run_qb_ratings(pbp_qb, g, name_map)
        out = out.merge(qb_df, on="game_id")
        print(f"league-mean pass EPA/play: {lg_mean:.3f}", flush=True)
    else:
        out["qb_epa_home"] = 0.0
        out["qb_epa_away"] = 0.0

    out = add_wind(out)
    out["qb_epa_diff"] = out["qb_epa_home"] - out["qb_epa_away"]
    out = add_features(out)
    return out


def run_pipeline(use_qb=True):
    d = build_frame(use_qb)
    train = d[d["season"] <= 2020]
    print("train games 2018-2020:", len(train), flush=True)

    lr_elo = LinearRegression().fit(train[["elo_diff"]], train["home_margin"])
    lr_epa_m = LinearRegression().fit(train[EPA_M_FEATS_V2], train["home_margin"])
    lr_epa_t = LinearRegression().fit(train[EPA_T_FEATS_V2], train["total_pts"])

    if use_qb:
        for feats, y in ((EPA_M_FEATS_V2, train["home_margin"]),
                         (EPA_T_FEATS_V2, train["total_pts"])):
            coefs, ts = ols_tstats(train[feats].values, y.values)
            for f, c, t in zip(feats, coefs, ts):
                if f in ("qb_epa_diff", "wind_eff"):
                    print(f"  OLS {f}: coef={c:+.3f} t={t:+.2f}", flush=True)

    d["pred_elo"] = lr_elo.predict(d[["elo_diff"]])
    d["pred_epa_m"] = lr_epa_m.predict(d[EPA_M_FEATS_V2])
    d["pred_epa_t"] = lr_epa_t.predict(d[EPA_T_FEATS_V2])

    d["pred_gbm_m"] = np.nan
    d["pred_gbm_t"] = np.nan
    bt = d[d["season"] >= 2021].copy()
    weeks = bt[["season", "week"]].drop_duplicates().sort_values(["season", "week"])
    for i, (s, w) in enumerate(weeks.itertuples(index=False)):
        hist = d[(d["season"] < s) | ((d["season"] == s) & (d["week"] < w))]
        cur = (d["season"] == s) & (d["week"] == w)
        if len(hist) < 200:
            continue
        gm = make_gbm().fit(hist[MARGIN_FEATS_V2], hist["home_margin"])
        gt = make_gbm().fit(hist[TOTAL_FEATS_V2], hist["total_pts"])
        d.loc[cur, "pred_gbm_m"] = gm.predict(d.loc[cur, MARGIN_FEATS_V2])
        d.loc[cur, "pred_gbm_t"] = gt.predict(d.loc[cur, TOTAL_FEATS_V2])
        if i % 25 == 0:
            print(f"  walk-forward {i+1}/{len(weeks)}", flush=True)
    return d, (lr_elo, lr_epa_m, lr_epa_t)


def tune(d):
    tmp = d.dropna(subset=["pred_gbm_m"])
    best, best_mae = None, 1e9
    for w1, w2 in itertools.product(np.arange(0, 1.01, 0.1), repeat=2):
        w3 = round(1 - w1 - w2, 10)
        if w3 < -1e-9:
            continue
        mae = np.abs(w1 * tmp[tmp["season"].isin([2021, 2022])]["pred_elo"]
                     + w2 * tmp[tmp["season"].isin([2021, 2022])]["pred_epa_m"]
                     + w3 * tmp[tmp["season"].isin([2021, 2022])]["pred_gbm_m"]
                     - tmp[tmp["season"].isin([2021, 2022])]["home_margin"]).mean()
        if mae < best_mae:
            best_mae, best = mae, (round(w1, 2), round(w2, 2), round(w3, 2))
    w_elo, w_epa, w_gbm = best
    best, best_mae = None, 1e9
    for w1 in np.arange(0, 1.01, 0.1):
        w2 = round(1 - w1, 10)
        vv = tmp[tmp["season"].isin([2021, 2022])]
        mae = np.abs(w1 * vv["pred_epa_t"] + w2 * vv["pred_gbm_t"]
                     - vv["total_pts"]).mean()
        if mae < best_mae:
            best_mae, best = mae, (round(w1, 2), round(w2, 2))
    w_epa_t, w_gbm_t = best
    d["ens_margin"] = w_elo * d["pred_elo"] + w_epa * d["pred_epa_m"] + w_gbm * d["pred_gbm_m"]
    d["ens_total"] = w_epa_t * d["pred_epa_t"] + w_gbm_t * d["pred_gbm_t"]
    val = d[d["season"].isin([2021, 2022])].copy()
    return d, val, {"w_elo": w_elo, "w_epa": w_epa, "w_gbm": w_gbm,
                    "w_epa_t": w_epa_t, "w_gbm_t": w_gbm_t,
                    "val_mae": round(best_mae, 2)}


def main():
    print("GBM backend:", GBM_BACKEND, flush=True)
    results = {}
    for use_qb, tag in ((True, "v2-full"), (False, "v2-noQB")):
        print(f"\n===== {tag} =====", flush=True)
        d, lins = run_pipeline(use_qb)
        if use_qb:
            lr_elo, lr_epa_m, lr_epa_t = lins
            with open(f"{DATA}/linear_models_v2.pkl", "wb") as f:
                pickle.dump({"lr_elo": lr_elo, "lr_epa_m": lr_epa_m,
                             "lr_epa_t": lr_epa_t,
                             "epa_m_feats": EPA_M_FEATS_V2,
                             "epa_t_feats": EPA_T_FEATS_V2,
                             "gbm_backend": GBM_BACKEND}, f)
            print("saved linear_models_v2.pkl", flush=True)
        d, val, w = tune(d)
        vm = m05.ats_metrics(val, "ens_margin", side="spread")
        print("validation ATS:", flush=True)
        for t, m in vm.items():
            print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} "
                  f"wr={m['win_rate']:.3f} roi={m['roi']:.3f}", flush=True)
        cand = [(t, m) for t, m in vm.items() if m["n"] >= 40]
        op_t = max(cand, key=lambda kv: kv[1]["roi"])[0] if cand else None
        print("operating threshold:", op_t, "| weights:", w, flush=True)
        test = d[d["season"].isin([2023, 2024, 2025])].copy()
        tm = m05.ats_metrics(test, "ens_margin", side="spread")
        print("test ATS:", flush=True)
        for t, m in tm.items():
            print(f"  edge>={t}: n={m['n']} {m['w']}-{m['l']} "
                  f"wr={m['win_rate']:.3f} roi={m['roi']:.3f}", flush=True)
        mae_test = np.abs(test["ens_margin"] - test["home_margin"]).mean()
        mae_mkt = np.abs(test["spread_line"] - test["home_margin"]).mean()
        print(f"test MAE: model {mae_test:.2f} vs market {mae_mkt:.2f}", flush=True)
        results[tag] = {"op_thresh": op_t, "weights": w, "test_mae": round(mae_test, 2),
                        "test_at_op": tm.get(op_t)}
        if use_qb:
            d.to_parquet(f"{DATA}/games_with_preds_v2.parquet", index=False)

    print("\n===== v1 baseline (from report) =====")
    print("test MAE 10.22 vs market 9.79 | thresh 3.0: 140-125 (52.8%) ROI +0.9%")
    print("\n===== summary =====")
    for tag, r in results.items():
        m = r["test_at_op"]
        print(f"{tag}: test MAE {r['test_mae']}, op_thresh {r['op_thresh']}, "
              f"test@{r['op_thresh']}: n={m['n']} {m['w']}-{m['l']} roi={m['roi']:.3f}")

    with open(f"{DATA}/ensemble_params_v2.json", "w") as f:
        json.dump({**results["v2-full"]["weights"],
                   "op_spread_thresh": results["v2-full"]["op_thresh"],
                   "op_total_thresh": None,
                   "note": "v2: +QB EPA/play ratings + wind; totals still not played"}, f, indent=2)
    print("\nsaved ensemble_params_v2.json + games_with_preds_v2.parquet")


if __name__ == "__main__":
    main()
