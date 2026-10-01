#!/usr/bin/env python3
"""Step 53: Run a challenger model variant for an upcoming week.

Challenger-vs-champion framework: V1 (champion) is NEVER touched by this
script. Each challenger is ONE controlled change to the v1 pipeline, declared
in challengers/registry.json. The challenger replays the exact 07_update_weekly
v1 flow with its override and writes
    data/challengers/<name>/predictions_<season>_w<week>.csv
in the same format as the champion's file, so the ledger grades them
identically (raw model_spread vs the same market lines; no QB overlay —
the overlay is a separate approved layer, applied only to the champion's
sheet, and to a challenger only if it ever promotes).

C1 "fast_elo": ELO K 20 -> 32 so ratings adapt faster to 2026 results
(Cale's hypothesis: the 2025 prior dominates too long).
  - lr_elo is REFIT on the challenger's own ELO series (final-fit on all
    played games, exactly like the champion's own GBM refit — no leakage:
    the ELO series itself is walk-forward).
  - Everything else frozen: EPA, features, GBM config, ensemble weights,
    pick threshold. One change, clean read.

The challenger is NOT backtest-selected. Its record starts 0-0 and it must
prove itself prospectively under the charter's promotion bar.

Usage:
    ./venv/bin/python scripts/53_run_challenger.py --challenger c1_fast_elo \
        --season 2026 --week 4 --market-json data/market_2026_w4.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from importlib import import_module

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
w07 = import_module("07_update_weekly")
ratings_mod = import_module("03_ratings")
from model_lib import (add_features, add_wind, make_gbm, MARGIN_FEATS,
                       TOTAL_FEATS, EPA_M_FEATS, GBM_BACKEND)

DATA = "/home/hatch/workspace/nfl-model/data"
REGISTRY = "/home/hatch/workspace/nfl-model/challengers/registry.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--market-json", default=None)
    args = ap.parse_args()

    with open(REGISTRY) as f:
        registry = json.load(f)
    cfg = registry[args.challenger]
    assert cfg["status"] == "live", f"challenger {args.challenger} is not live"
    S, W = args.season, args.week
    print(f"Challenger {args.challenger}: {cfg['name']}")
    print(f"  hypothesis: {cfg['hypothesis']}")
    print(f"  changes: {cfg['changes']} | frozen: {cfg['frozen']}")

    # ---- the ONE controlled change ----
    if "elo_k" in cfg:
        ratings_mod.K = float(cfg["elo_k"])
        print(f"  ELO K: 20.0 -> {ratings_mod.K}")

    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    pbp = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
    played = sched[sched["home_score"].notna()].copy()
    played = played[(played["season"] < S) | ((played["season"] == S) & (played["week"] < W))]
    played = played.sort_values(["season", "week"]).reset_index(drop=True)
    played["home_margin"] = played["home_score"] - played["away_score"]
    played["total_pts"] = played["home_score"] + played["away_score"]
    print(f"  played games through {S} w{W-1}: {len(played)} (caches, no network)")

    elo_df, elos = ratings_mod.run_elo(played)
    epa_df, epa_state = w07.run_epa_current(pbp, played)

    with open(f"{DATA}/linear_models.pkl", "rb") as f:
        import pickle
        lin = pickle.load(f)
    with open(f"{DATA}/ensemble_params.json") as f:
        ens = json.load(f)

    market = {}
    if args.market_json:
        with open(args.market_json) as f:
            market = json.load(f)

    up = sched[(sched["season"] == S) & (sched["week"] == W)
               & sched["home_score"].isna()].copy()
    print(f"  unplayed games in {S} w{W}: {len(up)}")
    rows = []
    for _, g in up.iterrows():
        h, a = g["home_team"], g["away_team"]
        row = {"game_id": g["game_id"], "away_team": a, "home_team": h,
               "week": W, "div_game": int(g["div_game"]),
               "home_rest": g["home_rest"], "away_rest": g["away_rest"],
               "elo_diff": elos.get(h, 1500.0) - elos.get(a, 1500.0)}
        for m in ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
                  "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]:
            row[f"home_{m}"] = epa_state[m].get(h, 0.0)
            row[f"away_{m}"] = epa_state[m].get(a, 0.0)
        rows.append(row)
    pred = add_features(pd.DataFrame(rows))

    # refit GBM on expanding window (challenger's own ELO features) + refit
    # lr_elo on the challenger's ELO scale. Identical discipline to the
    # champion's Friday refit; the only difference is the ELO series.
    rated = played[["game_id", "season", "week", "home_team", "away_team",
                    "home_margin", "total_pts", "home_rest", "away_rest",
                    "div_game", "wind", "roof"]].merge(
        elo_df, on="game_id").merge(epa_df, on="game_id")
    rated = add_wind(rated)
    rated = add_features(rated)
    lr_elo_c = LinearRegression().fit(rated[["elo_diff"]], rated["home_margin"])
    print(f"  challenger lr_elo: margin = {lr_elo_c.intercept_:.2f} "
          f"+ {lr_elo_c.coef_[0]:.4f}*elo_diff (n={len(rated)})")
    gm = make_gbm().fit(rated[MARGIN_FEATS], rated["home_margin"])
    gt = make_gbm().fit(rated[TOTAL_FEATS], rated["total_pts"])

    pred["pred_elo"] = lr_elo_c.predict(pred[["elo_diff"]])
    pred["pred_epa_m"] = lin["lr_epa_m"].predict(pred[EPA_M_FEATS])
    pred["pred_gbm_m"] = gm.predict(pred[MARGIN_FEATS])
    pred["model_spread"] = (ens["w_elo"] * pred["pred_elo"]
                            + ens["w_epa"] * pred["pred_epa_m"]
                            + ens["w_gbm"] * pred["pred_gbm_m"])

    op_s = ens["op_spread_thresh"]

    def fmt_pick(home, away, mkt_s, edge):
        if edge > 0:
            return (f"{home} -{mkt_s:.1f}" if mkt_s > 0 else
                    f"{home} +{-mkt_s:.1f}" if mkt_s < 0 else f"{home} PK")
        a = -mkt_s
        return (f"{away} -{a:.1f}" if a > 0 else
                f"{away} +{-a:.1f}" if a < 0 else f"{away} PK")

    out_rows = []
    for _, r in pred.iterrows():
        key = f"{r['away_team']}_{r['home_team']}"
        mkt = market.get(key)
        if mkt and op_s is not None:
            mkt_s, mkt_t = mkt
            edge = r["model_spread"] - mkt_s
            pick = (fmt_pick(r["home_team"], r["away_team"], mkt_s, edge)
                    if abs(edge) >= op_s else "no play")
        else:
            mkt_s = mkt_t = edge = None
            pick = "no play"
        out_rows.append({
            "game": f"{r['away_team']} @ {r['home_team']}",
            "model_spread": round(float(r["model_spread"]), 1),
            "market_spread": mkt_s,
            "edge": round(float(edge), 1) if edge is not None else None,
            "spread_pick": pick,
            "model_total": None, "market_total": mkt_t, "total_pick": "no play",
        })
    out = pd.DataFrame(out_rows).sort_values("game")
    cdir = f"{DATA}/challengers/{args.challenger}"
    os.makedirs(cdir, exist_ok=True)
    csv_path = f"{cdir}/predictions_{S}_w{W}.csv"
    out.to_csv(csv_path, index=False)
    print(out[["game", "model_spread", "market_spread", "edge", "spread_pick"]]
          .to_string(index=False))
    print(f"\nsaved {csv_path}")

    prov = {
        "challenger": args.challenger, "challenger_name": cfg["name"],
        "changes": cfg["changes"], "frozen": cfg["frozen"],
        "season": S, "week": W,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ratings_window": f"2018 through {S} week {W-1} ({len(played)} scored games)",
        "gbm_backend": GBM_BACKEND, "gbm_n_train": int(len(rated)),
        "weights": {"elo": ens["w_elo"], "epa": ens["w_epa"], "gbm": ens["w_gbm"]},
        "lr_elo_refit": {"intercept": float(lr_elo_c.intercept_),
                         "slope": float(lr_elo_c.coef_[0])},
        "note": "Challenger prediction. Champion (V1) untouched. "
                "No backtest selection: record starts 0-0.",
    }
    with open(f"{cdir}/predictions_{S}_w{W}.provenance.json", "w") as f:
        json.dump(prov, f, indent=2)
    print("saved provenance sidecar")


if __name__ == "__main__":
    main()
