#!/usr/bin/env python3
"""Step 7: Weekly model update (final-fit, no walk-forward refit).

Refreshes the 2026 schedule/scores + play-by-play from nflverse, rolls the
ELO and EPA ratings forward through all played weeks (no lookahead), refits
the gradient boosters on the expanding window, and predicts the upcoming week.

Usage:
    ./venv/bin/python scripts/07_update_weekly.py --season 2026 --week 2 \
        --market-json data/market_2026_w2.json

Market JSON format: {"AWAY_HOME": [spread, total], ...} with the home-spread
convention (+ means home favored) and nflverse abbreviations (LA = Rams).
If --market-json is omitted, model lines are still computed but no picks.

Optional extra sections in the market JSON:
  "qb":   {"AWAY_HOME": ["Away QB full name", "Home QB full name"], ...}
           Expected starters, in schedule name format ("Jayden Daniels").
           When absent for a game, defaults to each team's most recent
           starter (prior weeks of the season, else last season).
  "wind": {"AWAY_HOME": mph, ...}
           Forecast wind for outdoor games. Dome/closed-roof games are always
           0; outdoor games without a forecast assume 8 mph (typical).

Writes: data/predictions_2026_w<W>.csv
Also refreshes the cached schedules/pbp parquets in place (incremental).

Model versions: --model v1 (ELO+EPA+GBM, the validated baseline) or
--model v2 (+ walk-forward QB EPA/play ratings + wind). v2 artifacts:
linear_models_v2.pkl, ensemble_params_v2.json.
"""
import argparse
import json
import pickle
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from model_lib import (add_features, add_wind, make_gbm, GBM_BACKEND,
                       MARGIN_FEATS, TOTAL_FEATS, EPA_M_FEATS, EPA_T_FEATS,
                       MARGIN_FEATS_V2, TOTAL_FEATS_V2,
                       EPA_M_FEATS_V2, EPA_T_FEATS_V2)
from importlib import import_module
from qb_ratings import build_name_map, run_qb_ratings, qb_effective

ratings_mod = import_module("03_ratings")
run_elo = ratings_mod.run_elo

DATA = os.path.join(REPO_ROOT, "data")

DIVISIONS = {
    "BUF": "AFCE", "MIA": "AFCE", "NE": "AFCE", "NYJ": "AFCE",
    "BAL": "AFCN", "CIN": "AFCN", "CLE": "AFCN", "PIT": "AFCN",
    "HOU": "AFCS", "IND": "AFCS", "JAX": "AFCS", "TEN": "AFCS",
    "DEN": "AFCW", "KC": "AFCW", "LAC": "AFCW", "LV": "AFCW",
    "DAL": "NFCE", "NYG": "NFCE", "PHI": "NFCE", "WAS": "NFCE",
    "CHI": "NFCN", "DET": "NFCN", "GB": "NFCN", "MIN": "NFCN",
    "ATL": "NFCS", "CAR": "NFCS", "NO": "NFCS", "TB": "NFCS",
    "ARI": "NFCW", "LA": "NFCW", "SF": "NFCW", "SEA": "NFCW",
}

PBP_COLS = ["game_id", "posteam", "defteam", "play_type", "epa", "success",
            "season", "week"]


def run_epa_current(pbp, games):
    """Copy of 03_ratings.run_epa, but captures the rating state after the
    last week present in `games` instead of hardcoding 2025."""
    use = pbp[(pbp["play_type"].isin(["pass", "run"])) & pbp["epa"].notna()].copy()
    use["is_pass"] = (use["play_type"] == "pass").astype(int)

    off = use.groupby(["season", "week", "posteam"]).agg(
        off_plays=("epa", "size"), off_epa=("epa", "mean"),
        off_pass_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 1].mean()),
        off_rush_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 0].mean()),
        off_sr=("success", "mean")).reset_index()
    dff = use.groupby(["season", "week", "defteam"]).agg(
        def_plays=("epa", "size"), def_epa=("epa", "mean"),
        def_pass_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 1].mean()),
        def_rush_epa=("epa", lambda s: s[use.loc[s.index, "is_pass"] == 0].mean()),
        def_sr=("success", "mean")).reset_index()

    metrics = ["off_epa", "off_pass_epa", "off_rush_epa", "off_sr",
               "def_epa", "def_pass_epa", "def_rush_epa", "def_sr"]
    ratings = {m: {} for m in metrics}
    out_rows = []
    final_state = {}
    last = games[["season", "week"]].drop_duplicates().sort_values(
        ["season", "week"]).iloc[-1]
    last_season, last_week = int(last["season"]), int(last["week"])

    for (season, week), grp in games.groupby(["season", "week"], sort=True):
        if week == 1:
            for m in metrics:
                for t in list(ratings[m].keys()):
                    ratings[m][t] *= (1 - ratings_mod.PRIOR_WT)
        for _, g in grp.iterrows():
            row = {"game_id": g["game_id"]}
            for m in metrics:
                row[f"home_{m}"] = ratings[m].get(g["home_team"], 0.0)
                row[f"away_{m}"] = ratings[m].get(g["away_team"], 0.0)
            out_rows.append(row)
        wk_off = off[(off["season"] == season) & (off["week"] == week)].set_index("posteam")
        wk_def = dff[(dff["season"] == season) & (dff["week"] == week)].set_index("defteam")
        teams = set(wk_off.index) | set(wk_def.index)
        for t in teams:
            for m in metrics:
                src = wk_off if m.startswith("off") else wk_def
                val = src.loc[t, m] if t in src.index else np.nan
                if pd.isna(val):
                    continue
                old = ratings[m].get(t, 0.0)
                ratings[m][t] = ratings_mod.ALPHA * val + (1 - ratings_mod.ALPHA) * old
        if season == last_season and week == last_week:
            for m in metrics:
                final_state[m] = dict(ratings[m])

    return pd.DataFrame(out_rows), final_state


def refresh_schedules(season):
    """Re-pull `season` schedule from nflverse, merge into cache, compute
    rest days + div_game for the fresh rows. Returns updated DataFrame."""
    import nfl_data_py as nfl
    cache = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    fresh = nfl.import_schedules([season]).copy()
    fresh["gameday"] = pd.to_datetime(fresh["gameday"])
    cache = cache[cache["season"] != season].copy()
    sched = pd.concat([cache, fresh], ignore_index=True)
    sched["gameday"] = pd.to_datetime(sched["gameday"])

    s26 = sched[sched["season"] == season].copy().sort_values("gameday")
    s26["div_game"] = (s26["away_team"].map(DIVISIONS)
                       == s26["home_team"].map(DIVISIONS)).astype(int)
    last_game = {}
    rests_h, rests_a = [], []
    for _, g in s26.sort_values("gameday").iterrows():
        for team, out in ((g["home_team"], rests_h), (g["away_team"], rests_a)):
            if team in last_game:
                out.append((g["gameday"] - last_game[team]).days)
            else:
                out.append(7)
        last_game[g["home_team"]] = g["gameday"]
        last_game[g["away_team"]] = g["gameday"]
    order = s26.sort_values("gameday").index
    s26.loc[order, "home_rest"] = rests_h
    s26.loc[order, "away_rest"] = rests_a
    sched.update(s26[["div_game", "home_rest", "away_rest"]])
    sched["div_game"] = sched["div_game"].astype(int)
    sched.to_parquet(f"{DATA}/schedules_2018_2025.parquet", index=False)
    print(f"schedules refreshed: {len(sched)} rows, "
          f"{int(sched[(sched['season']==season) & sched['home_score'].notna()].shape[0])} played in {season}")
    return sched


def refresh_pbp(season):
    """Re-pull `season` pbp from nflverse, merge into cache. Returns DataFrame."""
    import nfl_data_py as nfl
    cache = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
    fresh = nfl.import_pbp_data([season], downcast=False)[PBP_COLS].copy()
    cache = cache[cache["season"] != season].copy()
    pbp = pd.concat([cache, fresh], ignore_index=True)
    pbp.to_parquet(f"{DATA}/pbp_2018_2025.parquet", index=False)
    print(f"pbp refreshed: {len(pbp)} rows")
    return pbp


PBP_QB_COLS = ["game_id", "season", "week", "posteam", "passer_player_name",
               "play_type", "epa"]


def refresh_pbp_qb(season):
    """Minimal pbp cache for QB ratings (passer + epa only)."""
    import nfl_data_py as nfl
    import os
    path = f"{DATA}/pbp_qb_2018_2026.parquet"
    cache = pd.read_parquet(path) if os.path.exists(path) else pd.DataFrame(columns=PBP_QB_COLS)
    fresh = nfl.import_pbp_data([season], downcast=False)[PBP_QB_COLS].copy()
    cache = cache[cache["season"] != season].copy()
    pbp = pd.concat([cache, fresh], ignore_index=True)
    pbp.to_parquet(path, index=False)
    print(f"qb pbp refreshed: {len(pbp)} rows")
    return pbp


def norm_name(n):
    return re.sub(r"[^a-z ]", "", str(n).lower()).strip()


def default_starters(sched, season, week):
    """Most recent starter per team before `week` (this season, else last
    season). Returns dict team -> schedule-format QB name. No lookahead."""
    out = {}
    for team in pd.concat([sched["home_team"], sched["away_team"]]).unique():
        hg = sched[(sched["home_team"] == team) & (sched["home_qb_name"].notna())]
        ag = sched[(sched["away_team"] == team) & (sched["away_qb_name"].notna())]
        cand = []
        for _, g in hg.iterrows():
            if (g["season"] < season) or (g["season"] == season and g["week"] < week):
                cand.append((g["season"], g["week"], g["home_qb_name"]))
        for _, g in ag.iterrows():
            if (g["season"] < season) or (g["season"] == season and g["week"] < week):
                cand.append((g["season"], g["week"], g["away_qb_name"]))
        if cand:
            out[team] = max(cand)[2]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True,
                    help="upcoming week to predict")
    ap.add_argument("--market-json", default=None)
    ap.add_argument("--model", default="v1", choices=["v1", "v2"],
                    help="v1: ELO+EPA+GBM baseline; v2: + QB EPA/play ratings + wind")
    args = ap.parse_args()
    S, W = args.season, args.week
    V2 = args.model == "v2"
    print("GBM backend:", GBM_BACKEND, "| model:", args.model, flush=True)

    sched = refresh_schedules(S)
    pbp = refresh_pbp(S)

    played = sched[sched["home_score"].notna()].copy()
    played = played[(played["season"] < S) |
                    ((played["season"] == S) & (played["week"] < W))]
    played = played.sort_values(["season", "week"]).reset_index(drop=True)
    played["home_margin"] = played["home_score"] - played["away_score"]
    played["total_pts"] = played["home_score"] + played["away_score"]
    print(f"played games through {S} w{W-1}: {len(played)}")

    elo_df, elos = run_elo(played)
    epa_df, epa_state = run_epa_current(pbp, played)

    if W == 1 and not (played["season"] == S).any():
        # no current-season data: regressed priors, like 06_week1.py
        elos = {t: 1500.0 + (e - 1500.0) * (2.0 / 3.0) for t, e in elos.items()}
        epa_state = {m: {t: v * 0.65 for t, v in d.items()}
                     for m, d in epa_state.items()}
        print("week 1: using regressed 2025 priors")

    lin_file = f"{DATA}/linear_models_v2.pkl" if V2 else f"{DATA}/linear_models.pkl"
    ens_file = f"{DATA}/ensemble_params_v2.json" if V2 else f"{DATA}/ensemble_params.json"
    with open(lin_file, "rb") as f:
        lin = pickle.load(f)
    with open(ens_file) as f:
        ens = json.load(f)
    M_FEATS = MARGIN_FEATS_V2 if V2 else MARGIN_FEATS
    T_FEATS = TOTAL_FEATS_V2 if V2 else TOTAL_FEATS
    EM_FEATS = EPA_M_FEATS_V2 if V2 else EPA_M_FEATS
    ET_FEATS = EPA_T_FEATS_V2 if V2 else EPA_T_FEATS

    # ---- v2: QB ratings + starters + wind ----
    qb_state, qb_lg, name_map, starters, wind_ovr = {}, 0.0, {}, {}, {}
    qb_game_df = None
    if V2:
        pbp_qb = refresh_pbp_qb(S)
        name_map = build_name_map(played, pbp_qb)
        qb_game_df, qb_state, qb_lg = run_qb_ratings(pbp_qb, played, name_map)
        if W == 1 and not (played["season"] == S).any():
            # no current-season plays: apply the offseason regression once
            for qb in qb_state:
                qb_state[qb]["rating"] = (qb_lg + (qb_state[qb]["rating"] - qb_lg) * 0.65)
            print("week 1: QB ratings regressed toward league mean")
        starters = default_starters(sched, S, W)
        print(f"QB ratings: {len(qb_state)} QBs, league mean {qb_lg:.3f}")

    market = {}
    if args.market_json:
        with open(args.market_json) as f:
            market = json.load(f)
    qb_ovr = {norm_name(k): v for k, v in market.get("qb", {}).items()}
    wind_ovr = {k: float(v) for k, v in market.get("wind", {}).items()}

    # upcoming games
    up = sched[(sched["season"] == S) & (sched["week"] == W)
               & sched["home_score"].isna()].copy()
    print(f"unplayed games in {S} w{W}: {len(up)}")
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
        if V2:
            key = f"{a}_{h}"
            if key in qb_ovr or norm_name(key) in qb_ovr:
                a_qb, h_qb = qb_ovr.get(key, qb_ovr.get(norm_name(key)))
            else:
                a_qb, h_qb = starters.get(a), starters.get(h)
            nmap = {norm_name(k): v for k, v in name_map.items()}
            row["qb_epa_home"] = qb_effective(nmap.get(norm_name(h_qb)), qb_state, qb_lg)
            row["qb_epa_away"] = qb_effective(nmap.get(norm_name(a_qb)), qb_state, qb_lg)
            row["qb_epa_diff"] = row["qb_epa_home"] - row["qb_epa_away"]
            roof = str(g.get("roof", "outdoors"))
            if roof in ("dome", "closed"):
                row["wind_eff"] = 0.0
            else:
                row["wind_eff"] = wind_ovr.get(key, 8.0)
        rows.append(row)
    pred = add_features(pd.DataFrame(rows))

    pred["pred_elo"] = lin["lr_elo"].predict(pred[["elo_diff"]])
    pred["pred_epa_m"] = lin["lr_epa_m"].predict(pred[EM_FEATS])
    pred["pred_epa_t"] = lin["lr_epa_t"].predict(pred[ET_FEATS])

    # refit GBM on expanding window (all played + rated games)
    rated = played[["game_id", "season", "week", "home_team", "away_team",
                    "home_margin", "total_pts", "home_rest", "away_rest",
                    "div_game", "wind", "roof"]].merge(
        elo_df, on="game_id").merge(epa_df, on="game_id")
    if V2:
        rated = rated.merge(qb_game_df, on="game_id")
        rated["qb_epa_diff"] = rated["qb_epa_home"] - rated["qb_epa_away"]
    rated = add_wind(rated)
    rated = add_features(rated)
    gm = make_gbm().fit(rated[M_FEATS], rated["home_margin"])
    gt = make_gbm().fit(rated[T_FEATS], rated["total_pts"])
    pred["pred_gbm_m"] = gm.predict(pred[M_FEATS])
    pred["pred_gbm_t"] = gt.predict(pred[T_FEATS])

    pred["model_spread"] = (ens["w_elo"] * pred["pred_elo"]
                            + ens["w_epa"] * pred["pred_epa_m"]
                            + ens["w_gbm"] * pred["pred_gbm_m"])
    pred["model_total"] = (ens["w_epa_t"] * pred["pred_epa_t"]
                           + ens["w_gbm_t"] * pred["pred_gbm_t"])

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
            "model_total": round(float(r["model_total"]), 1),
            "market_total": mkt_t,
            "total_pick": "no play",  # totals are -EV per backtest; never played
        })
    out = pd.DataFrame(out_rows).sort_values("game")
    csv_path = f"{DATA}/predictions_{S}_w{W}.csv"
    out.to_csv(csv_path, index=False)
    print(out.to_string(index=False))
    print(f"\nsaved {csv_path}")

    # ---- provenance sidecar (audit fix, 2026-09-30) ----
    # Machine-readable record of exactly what data the ratings/predictions
    # were built from. Additive: the predictions CSV is untouched.
    # `played` is the single source of truth -- every game with a final score
    # as of this run, which is what run_elo / run_epa_current consumed.
    cur = played[played["season"] == S]
    prov = {
        "model_version": "v1",
        "season": S,
        "week": W,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": (str(cur["gameday"].max())
                       if len(cur) else str(played["gameday"].max())),
        "ratings_as_of": (str(cur["gameday"].max())
                          if len(cur) else str(played["gameday"].max())),
        "ratings_as_of_note": ("ELO and EPA ratings are recomputed from scratch "
                             "by 07 on every run from the scored games above; "
                             "there is no cached ratings file, so ratings_as_of "
                             "== data_as_of by construction."),
        "latest_game_included": played.sort_values(
            ["season", "week", "game_id"]).iloc[-1]["game_id"],
        "season_games_included": {
            str(S): {"weeks": sorted(int(x) for x in cur["week"].unique()),
                     "n_games": int(len(cur))},
        },
        "ratings_window": f"2018 through {S} week {W - 1} "
                          f"({len(played)} scored games)",
        "elo_source": "03_ratings.run_elo recomputed from scratch on all "
                      "scored games with week < W (no cached/stale ratings)",
        "epa_source": "run_epa_current recomputed from scratch on pbp for "
                      "all scored games with week < W (no cached ratings)",
        "gbm_train_through": str(played.sort_values(
            ["season", "week", "game_id"]).iloc[-1]["game_id"]),
        "gbm_n_train": int(len(rated)),
        "gbm_backend": GBM_BACKEND,
        "weights": {"elo": ens["w_elo"], "epa": ens["w_epa"],
                    "gbm": ens["w_gbm"]},
    }
    prov_path = f"{DATA}/predictions_{S}_w{W}.provenance.json"
    with open(prov_path, "w") as f:
        json.dump(prov, f, indent=2)
    print(f"saved {prov_path}")


if __name__ == "__main__":
    main()
