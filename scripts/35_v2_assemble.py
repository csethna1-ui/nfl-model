#!/usr/bin/env python3
"""Step 35: Assemble V2 walk-forward feature tables (NO model fitting).

Reads played-week source tables (31/32/33) and converts to prediction-week
grain with strict walk-forward discipline:

  feature(team, season S, pred_week W) =
      expanding mean over games with (season < S) OR (season == S AND week < W)

Rules:
  - MIN_GAMES = 4 prior games else NaN (documented; early-season cold start)
  - No offseason reset of the mean (expanding all-history); recency weighting
    is a MODELING-stage decision, not made here.
  - Non-mean features (qb_backup_flag, qb_sched identity): carried as the
    CURRENT week's scheduled values -- they are pregame-known for week W and
    do not leak (documented in leakage_audit.md).
  - qb_value_poll: static 2026-anchored lookup (labeled limitation).

Outputs:
  data/v2/team_features_pred.parquet -- team x season x pred_week, all features
  data/v2/games_v2_features.parquet  -- game grain, 2018-2022 ONLY
      (train+validation window; 2023-2025 vault EXCLUDED, 2026 EXCLUDED),
      with home_/away_ component features and matchup interaction columns.

Matchup interactions: for defined (offense, defense) pairs, both a product
term and -- where units are comparable -- a cross-differential. Raw scale;
standardization is a modeling-stage decision.

NO model fitting. NO validation evaluation. Architecture only.
"""
import os

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
MIN_GAMES = 4
GAME_SEASONS = (2018, 2022)  # vault excluded, 2026 excluded

# (offense feature, defense feature, allow_cross_diff)
MATCHUP_PAIRS = [
    ("expl_pass_rate", "expl_pass_allowed", True),
    ("expl_rush_rate", "expl_rush_allowed", True),
    ("epa_per_drive", "epa_per_drive_allowed", True),
    ("points_per_drive", "points_per_drive_allowed", True),
    ("pressure_allowed_pct", "def_pressures", False),
    ("sack_rate", "def_sacks", False),
    ("adot", "def_adot_allowed", True),
    ("rz_trip_rate", "rz_trip_allowed", True),
    ("start_y100", "start_y100_allowed", True),
]

MEAN_FEATURES = None  # set in main: all numeric source cols except keys/identity


def expanding_pred_frame(src, id_cols=("team", "season", "week")):
    """Long played-week table -> pred-week rows with expanding means."""
    feat_cols = [c for c in src.columns
                 if c not in list(id_cols) + ["qb_sched", "qb_primary_pbp",
                                             "primary_passer",
                                             "qb_backup_flag"]]
    src = src.sort_values(["team", "season", "week"]).copy()
    # cumulative sums/counts over all history (all prior seasons + weeks < W)
    out_rows = []
    for team, g in src.groupby("team", observed=True):
        g = g.sort_values(["season", "week"]).reset_index(drop=True)
        vals = g[feat_cols].apply(pd.to_numeric, errors="coerce")
        csum = vals.cumsum()
        cnt = vals.notna().cumsum()
        for i, r in g.iterrows():
            # history strictly before this row's (season, week)
            if i == 0:
                continue
            hist_n = cnt.iloc[i - 1]
            row = {"team": team, "season": r["season"],
                   "pred_week": r["week"]}
            for c in feat_cols:
                n = hist_n[c]
                row[c] = (csum[c].iloc[i - 1] / n) if n >= MIN_GAMES else np.nan
            row["hist_games"] = int(hist_n.max())
            out_rows.append(row)
    return pd.DataFrame(out_rows)


def main():
    os.makedirs(V2, exist_ok=True)
    pbp = pd.read_parquet(f"{V2}/team_week_pbp.parquet")
    pfr = pd.read_parquet(f"{V2}/team_week_pfr.parquet")
    ply = pd.read_parquet(f"{V2}/team_week_player.parquet")

    src = pbp.merge(pfr, on=["team", "season", "week"], how="outer")
    src = src.merge(ply, on=["team", "season", "week"], how="outer")
    print("source shape:", src.shape)

    pred = expanding_pred_frame(src)
    pred.to_parquet(f"{V2}/team_features_pred.parquet", index=False)
    print(f"wrote team_features_pred: {pred.shape}")

    # ---------- game grain ----------
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    sched = sched[(sched["season"] >= GAME_SEASONS[0])
                  & (sched["season"] <= GAME_SEASONS[1])
                  & (sched["week"] <= 22)
                  & sched["home_score"].notna()].copy()
    feat_cols = [c for c in pred.columns
                 if c not in ("team", "season", "pred_week", "hist_games")]
    hp = pred.rename(columns={"team": "home_team", "pred_week": "week",
                              **{c: f"home_{c}" for c in feat_cols}})
    ap = pred.rename(columns={"team": "away_team", "pred_week": "week",
                              **{c: f"away_{c}" for c in feat_cols}})
    g = sched.merge(hp, on=["home_team", "season", "week"], how="left")
    g = g.merge(ap, on=["away_team", "season", "week"], how="left")
    # current-week QB identity (pregame-known, no leak)
    qcur = ply[["team", "season", "week", "qb_sched", "qb_primary_pbp",
                "qb_backup_flag"]].copy()
    qh = qcur.rename(columns={"team": "home_team"})
    qa = qcur.rename(columns={"team": "away_team"})
    g = g.merge(qh, on=["home_team", "season", "week"], how="left")
    g = g.merge(qa, on=["away_team", "season", "week"], how="left",
                suffixes=("", "_a"))
    g = g.rename(columns={"qb_sched": "home_qb_sched",
                          "qb_primary_pbp": "home_qb_primary",
                          "qb_backup_flag": "home_qb_backup_flag",
                          "qb_sched_a": "away_qb_sched",
                          "qb_primary_pbp_a": "away_qb_primary",
                          "qb_backup_flag_a": "away_qb_backup_flag"})

    # matchup interactions
    for off, deff, allow_diff in MATCHUP_PAIRS:
        ho, ad = f"home_{off}", f"away_{deff}"
        ao, hd = f"away_{off}", f"home_{deff}"
        if ho in g.columns and ad in g.columns:
            g[f"mx_{off}_x_{deff}_homeoff"] = g[ho] * g[ad]
            if allow_diff:
                g[f"mx_{off}_v_{deff}_homeoff"] = g[ho] - g[ad]
        if ao in g.columns and hd in g.columns:
            g[f"mx_{off}_x_{deff}_awayoff"] = g[ao] * g[hd]
            if allow_diff:
                g[f"mx_{off}_v_{deff}_awayoff"] = g[ao] - g[hd]

    # environment (game grain); sched already carries div_game
    env = pd.read_parquet(f"{V2}/game_env.parquet").drop(columns=["div_game"])
    g = g.merge(env, on=["game_id", "season", "week", "home_team",
                         "away_team"], how="left")

    keep = list(dict.fromkeys(
        ["game_id", "season", "week", "home_team", "away_team",
         "home_score", "away_score"] +
        [c for c in g.columns if c.startswith(("home_", "away_", "mx_",
                                              "rest_", "short_", "off_bye",
                                              "dome_", "grass_", "temp_",
                                              "wind_", "div_", "month",
                                              "travel_", "altitude_",
                                              "primetime"))]))
    g = g[[c for c in keep if c in g.columns]]
    g.to_parquet(f"{V2}/games_v2_features.parquet", index=False)
    print(f"wrote games_v2_features: {g.shape}")
    print("cols:", len(g.columns))


if __name__ == "__main__":
    main()
