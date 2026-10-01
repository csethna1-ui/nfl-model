#!/usr/bin/env python3
"""Step 6: Week 1 2026 predictions.
Priors = 2025 final ratings regressed toward the mean (ELO: 1/3 to 1500; EPA: 35% to 0).
GBM fit once on all games through 2025. Market = bet365 lines (Sept 10, via parent research).
No hand-tuning for offseason roster changes.
Usage: run from ~/workspace/nfl-model as ./venv/bin/python scripts/06_week1.py
"""
import json
import pickle
import sys
import numpy as np
import pandas as pd

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from model_lib import (add_features, make_gbm, GBM_BACKEND,
                       MARGIN_FEATS, TOTAL_FEATS, EPA_M_FEATS, EPA_T_FEATS)

DATA = os.path.join(REPO_ROOT, "data")

# Market: bet365, Sept 10 2026 (home-spread convention: + = home favored)
MARKET = {
    ("ATL", "PIT"): (3.5, 41.5),
    ("BAL", "IND"): (-3.5, 48.5),
    ("BUF", "HOU"): (-1.5, 44.5),
    ("CHI", "CAR"): (-2.5, 46.5),
    ("CLE", "JAX"): (8.5, 40.5),
    ("NO", "DET"): (6.5, 49.5),
    ("NYJ", "TEN"): (1.5, 39.5),
    ("TB", "CIN"): (3.5, 50.5),
    ("ARI", "LAC"): (9.5, 47.5),
    ("GB", "MIN"): (1.5, 46.5),
    ("MIA", "LV"): (3.5, 40.5),
    ("WAS", "PHI"): (5.5, 44.5),
    ("DAL", "NYG"): (-2.5, 48.5),
    ("DEN", "KC"): (2.5, 43.5),
}

def main():
    print("GBM backend:", GBM_BACKEND, flush=True)
    with open(f"{DATA}/final_2025_state.pkl", "rb") as f:
        state = pickle.load(f)
    with open(f"{DATA}/linear_models.pkl", "rb") as f:
        lin = pickle.load(f)
    with open(f"{DATA}/ensemble_params.json") as f:
        ens = json.load(f)

    # regressed priors
    elos = {t: 1500.0 + (e - 1500.0) * (2.0 / 3.0) for t, e in state["elos"].items()}
    epa = {m: {t: v * 0.65 for t, v in d.items()} for m, d in state["epa"].items()}

    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    w1 = sched[(sched["season"] == 2026) & (sched["week"] == 1) & sched["home_score"].isna()].copy()
    print("unplayed week-1 games:", len(w1))

    rows = []
    for _, g in w1.iterrows():
        h, a = g["home_team"], g["away_team"]
        row = {"game_id": g["game_id"], "away_team": a, "home_team": h,
               "week": 1, "div_game": g["div_game"],
               "home_rest": g["home_rest"], "away_rest": g["away_rest"],
               "elo_diff": elos.get(h, 1500.0) - elos.get(a, 1500.0)}
        for m in ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
                  "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]:
            row[f"home_{m}"] = epa[m].get(h, 0.0)
            row[f"away_{m}"] = epa[m].get(a, 0.0)
        rows.append(row)
    pred = add_features(pd.DataFrame(rows))

    # linear components (fit on 2018-2020, frozen)
    pred["pred_elo"] = lin["lr_elo"].predict(pred[["elo_diff"]])
    pred["pred_epa_m"] = lin["lr_epa_m"].predict(pred[EPA_M_FEATS])
    pred["pred_epa_t"] = lin["lr_epa_t"].predict(pred[EPA_T_FEATS])

    # GBM trained on all games through 2025
    hist = add_features(pd.read_parquet(f"{DATA}/games_with_ratings.parquet"))
    gm = make_gbm().fit(hist[MARGIN_FEATS], hist["home_margin"])
    gt = make_gbm().fit(hist[TOTAL_FEATS], hist["total_pts"])
    pred["pred_gbm_m"] = gm.predict(pred[MARGIN_FEATS])
    pred["pred_gbm_t"] = gt.predict(pred[TOTAL_FEATS])
    import pickle as pk
    with open(f"{DATA}/gbm_final.pkl", "wb") as f:
        pk.dump({"gbm_margin": gm, "gbm_total": gt}, f)

    pred["model_spread"] = (ens["w_elo"] * pred["pred_elo"] +
                            ens["w_epa"] * pred["pred_epa_m"] +
                            ens["w_gbm"] * pred["pred_gbm_m"])
    pred["model_total"] = (ens["w_epa_t"] * pred["pred_epa_t"] +
                           ens["w_gbm_t"] * pred["pred_gbm_t"])

    op_s, op_t = ens["op_spread_thresh"], ens["op_total_thresh"]
    out_rows = []
    def fmt_pick(home, away, mkt_s, edge):
        # standard notation: "-3.5" = favored by 3.5, "+3.5" = getting 3.5
        if edge > 0:  # bet home
            return f"{home} -{mkt_s:.1f}" if mkt_s > 0 else (
                f"{home} +{-mkt_s:.1f}" if mkt_s < 0 else f"{home} PK")
        else:  # bet away; away spread = -mkt_s
            a = -mkt_s
            return f"{away} -{a:.1f}" if a > 0 else (
                f"{away} +{-a:.1f}" if a < 0 else f"{away} PK")

    for _, r in pred.iterrows():
        key = (r["away_team"], r["home_team"])
        mkt_s, mkt_t = MARKET[key]
        edge = r["model_spread"] - mkt_s
        if op_s is not None and abs(edge) >= op_s:
            pick = fmt_pick(r["home_team"], r["away_team"], mkt_s, edge)
        else:
            pick = "no play"
        t_edge = r["model_total"] - mkt_t
        if op_t is not None and abs(t_edge) >= op_t:
            tpick = f"Over {mkt_t}" if t_edge > 0 else f"Under {mkt_t}"
        else:
            tpick = "no play"
        out_rows.append({
            "game": f"{r['away_team']} @ {r['home_team']}",
            "model_spread": round(r["model_spread"], 1),
            "market_spread": mkt_s,
            "edge": round(edge, 1),
            "spread_pick": pick,
            "model_total": round(r["model_total"], 1),
            "market_total": mkt_t,
            "total_edge": round(t_edge, 1),
            "total_pick": tpick,
        })
    out = pd.DataFrame(out_rows).sort_values("game")
    out.to_csv(f"{DATA}/../week1_predictions.csv", index=False)
    print(out.to_string(index=False))
    print("\nsaved week1_predictions.csv")

if __name__ == "__main__":
    main()
