#!/usr/bin/env python3
"""Step 39: shared walk-forward modeling harness for V2 candidates.

Reusable, randomness-free pipeline implementing the frozen research protocol
(v2_research/protocol.md sections 2-5):

  load_games()            game list 2018-2022 REG with labels and V1 fallback
  load_modeling_table()   rebuilt team modeling table (script 38 output)
  tuesday_batch_cutoff()  Tuesday 08:00 ET batch cutoff per (season, week)
  build_design()          per-game team features, rest diff, fallback flags
  walkforward_impute()    walk-forward medians over training team-rows
  walkforward_standardize() walk-forward mu/sigma (population std) over
                          training team-rows
  walkforward_predict()   per-week Ridge fits on kickoff-filtered training
                          games; predictions + per-fit manifests

Information-set discipline (timestamp_policy.md):
  * Team features: week grain, modeling-table rows with chronological
    (season, pred_week) strictly before (S, W), hist_games >= 4.
  * Ridge training set (protocol section 4): REG games with
    kickoff < Tuesday 08:00 ET batch cutoff of week W. For normal weeks this
    is exactly the games of chronological weeks < W; four COVID-rescheduled
    games break the equivalence (documented in tuesday_batch_cutoff).
  * Fallback (cold start, protocol section 3, Option C): either team's
    hist_games < 4 -> no V2 prediction; V1 ens_margin logged as fallback.
    Fallback games are excluded from Ridge training (their V2 features are
    structurally all-NaN under the >=4-games component gate; the median
    imputation policy covers sporadic missingness, not structural absence)
    and from the primary comparison.

No evaluation metrics are computed here (no MAE/RMSE/calibration/error
correlations). Callers may compute development-window metrics only where the
protocol authorizes them (alpha selection on 2018-2020).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from zoneinfo import ZoneInfo

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
ET = ZoneInfo("America/New_York")

MIN_TEAM_GAMES = 4      # component gate: >=4 prior games (protocol section 3)
MIN_SCALING_ROWS = 30   # scaling-set gate |S(W)| >= 30 (standardization_spec)
SIGMA_FLOOR = 1e-12     # constant features -> z = 0

# V2-A feature spec (protocol section 5). Offense features are "higher=better";
# defense features are "allowed" measures (higher=worse defense).
V2A_SPEC = {
    "name": "V2-A",
    "offense": ["points_per_drive", "epa_per_drive", "scoring_drive_rate",
                "rz_trip_rate", "gtg_td_rate"],
    "defense": ["points_per_drive_allowed", "epa_per_drive_allowed",
                "scoring_drive_allowed", "rz_trip_allowed"],
    "rest": True,
}
TEAM_FEATURES = V2A_SPEC["offense"] + V2A_SPEC["defense"]  # 9 team-level cols
DESIGN_COLS = ([f"d_off_{c}" for c in V2A_SPEC["offense"]]
               + [f"d_def_{c}" for c in V2A_SPEC["defense"]]
               + ["rest_diff"])  # 10 design columns


def load_games():
    """2018-2022 REG games with label (home_margin), V1 fallback (ens_margin),
    rest (from games_v2_features), and kickoff timestamps (from games.csv)."""
    g = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    g = g[(g["season"].between(2018, 2022)) & (g["game_type"] == "REG")
          & g["home_margin"].notna()].copy()
    gv = pd.read_parquet(f"{V2}/games_v2_features.parquet")
    gv = gv[["game_id", "home_rest", "away_rest"]]
    assert gv["home_rest"].notna().all() and gv["away_rest"].notna().all()
    # rest comes from games_v2_features per spec; drop any pre-existing rest
    # cols so the merge cannot silently keep the other source.
    g = g.drop(columns=["home_rest", "away_rest"], errors="ignore")
    g = g.merge(gv, on="game_id", how="left")
    assert g["home_rest"].notna().all(), "rest missing for some games"
    gc = pd.read_csv(f"{DATA}/games.csv",
                     usecols=["game_id", "gameday", "gametime"])
    gc["kickoff_et"] = pd.to_datetime(gc["gameday"] + " " + gc["gametime"]) \
        .dt.tz_localize(ET)
    g = g.merge(gc[["game_id", "kickoff_et"]], on="game_id", how="left")
    assert g["kickoff_et"].notna().all()
    g = g.sort_values(["season", "week", "kickoff_et"]).reset_index(drop=True)
    return g[["game_id", "season", "week", "home_team", "away_team",
              "home_margin", "ens_margin", "home_rest", "away_rest",
              "kickoff_et"]]


def load_modeling_table():
    """Rebuilt team modeling table (script 38): PFR lagged through W-2,
    injury features under the Tuesday row-level cutoff, QB historical merge."""
    t = pd.read_parquet(f"{V2}/team_features_pred_v2.parquet")
    assert not t.duplicated(["team", "season", "pred_week"]).any()
    return t.set_index(["team", "season", "pred_week"])


def tuesday_batch_cutoff(season, week, games):
    """Tuesday 08:00 ET batch cutoff for predicting (season, week).

    Defined as 08:00 ET on the Tuesday immediately preceding week W's Sunday
    slate (Sunday date - 5 days). This is the Tuesday-batch time at which a
    production system would emit the week's predictions.

    Equivalence note (protocol section 4 gloss): for normally scheduled weeks
    this admits exactly the games of chronological weeks < W (all week-(W-1)
    games, incl. MNF, kick off before it; all week-W games kick off after).
    Four COVID-rescheduled games break the equivalence, verified empirically
    in data/games.csv 2018-2022 REG:
      * 2020 W5 BUF-TEN (Tue 2020-10-13 19:00 ET): excluded from W6 training
        (kicked off after the Tue 08:00 batch).
      * 2020 W12 BAL-PIT (Wed 2020-12-02 15:40 ET): excluded from W13 training
        under the conservative Sunday-anchored batch (Tue 2020-12-01 08:00 ET);
        a week-grain rule would include it. Single affected training row.
      * 2020 W13 DAL-BAL (Tue 2020-12-08 20:05 ET): excluded from W14 training.
      * 2021 W15 SEA-LA, WAS-PHI (Tue 2021-12-21 19:00 ET): excluded from W16
        training.
    The protocol-literal kickoff rule is implemented (not the week<W proxy).
    """
    wk = games[(games["season"] == season) & (games["week"] == week)]
    assert len(wk) > 0, f"no games for {season} W{week}"
    # Sunday slate: most games kick off Sunday; take the modal Sunday date.
    sundays = wk["kickoff_et"][wk["kickoff_et"].dt.weekday == 6]
    assert len(sundays) > 0, f"no Sunday games for {season} W{week}"
    sun_date = sundays.dt.normalize().mode().iloc[0]
    tues = (sun_date - pd.Timedelta(days=5)).replace(hour=8, minute=0,
                                                    second=0, microsecond=0)
    return tues


def build_design(game_ids, feature_spec, games, table):
    """Per-game inputs for a feature spec.

    For each game (season S, week W): home/away team rows from the modeling
    table at pred_week=W. Cold start (either team's hist_games < 4, or a team
    row is absent) -> fallback_flag=True and no V2 features are needed.

    Returns (home_feat, away_feat, rest_diff, meta):
      home_feat/away_feat: DataFrame indexed by game_id, TEAM_FEATURES cols
        (raw scale, NaN allowed; NaN rows for fallback games)
      rest_diff: Series indexed by game_id (home_rest - away_rest)
      meta: DataFrame indexed by game_id with season, week, home_team,
        away_team, y, v1, fallback_flag, missing_frac (fraction of the 10
        design columns NaN pre-imputation).
    """
    off = feature_spec["offense"]
    deff = feature_spec["defense"]
    feats = off + deff
    g = games.set_index("game_id")
    home_feat, away_feat, rest_diff, rows = {}, {}, {}, []
    for gid in game_ids:
        r = g.loc[gid]
        S, W = int(r["season"]), int(r["week"])
        hf = awf = None
        try:
            hrow = table.loc[(r["home_team"], S, W)]
            arow = table.loc[(r["away_team"], S, W)]
            if (hrow["hist_games"] >= MIN_TEAM_GAMES
                    and arow["hist_games"] >= MIN_TEAM_GAMES):
                hf = hrow[feats].astype(float)
                awf = arow[feats].astype(float)
        except KeyError:
            pass
        fallback = hf is None
        home_feat[gid] = hf if hf is not None else pd.Series(
            np.nan, index=feats)
        away_feat[gid] = awf if awf is not None else pd.Series(
            np.nan, index=feats)
        rest_diff[gid] = float(r["home_rest"] - r["away_rest"])
        # design-level missingness pre-imputation: a differential col is NaN
        # if either side is NaN; rest_diff is never NaN.
        if fallback:
            miss = np.nan
        else:
            dnan = int(((hf[feats].isna()) | (awf[feats].isna())).sum())
            miss = dnan / (len(feats) + 1)
        rows.append({"game_id": gid, "season": S, "week": W,
                     "home_team": r["home_team"], "away_team": r["away_team"],
                     "y": float(r["home_margin"]),
                     "v1": (None if pd.isna(r["ens_margin"])
                            else float(r["ens_margin"])),
                     "fallback_flag": fallback, "missing_frac": miss})
    home_feat = pd.DataFrame(home_feat).T
    away_feat = pd.DataFrame(away_feat).T
    rest_diff = pd.Series(rest_diff)
    meta = pd.DataFrame(rows).set_index("game_id")
    return home_feat, away_feat, rest_diff, meta


def walkforward_impute(train_team_rows, feature_cols):
    """Walk-forward medians over the training team-rows (raw scale)."""
    return train_team_rows[feature_cols].median()


def walkforward_standardize(train_team_rows, feature_cols):
    """Walk-forward mu/sigma (population std, ddof=0) over training team-rows.

    Constant features (sigma < floor) standardize to 0.
    """
    mu = train_team_rows[feature_cols].mean()
    sigma = train_team_rows[feature_cols].std(ddof=0)
    sigma = sigma.where(sigma >= SIGMA_FLOOR, np.nan)  # -> z=0 below
    return mu, sigma


def _standardize_frame(df, medians, mu, sigma):
    z = (df.fillna(medians) - mu) / sigma
    return z.fillna(0.0)  # sigma-floored (constant) features -> 0


def walkforward_predict(feature_spec, seasons_weeks, alpha, games=None,
                        table=None):
    """Walk-forward Ridge predictions for the given (season, week) list.

    For each week W in chronological order:
      * scaling/imputation sets: modeling-table rows with chronological
        (season, pred_week) strictly before (S, W) and hist_games >= 4;
        |S(W)| >= 30 required, else the week's games all fall back.
      * training games: REG games with kickoff < Tuesday 08:00 ET batch
        cutoff of W, excluding fallback games (documented choice; their V2
        features are structurally all-NaN).
      * fit Ridge(alpha) (deterministic), predict W's non-fallback games;
        fallback games get V1 ens_margin (may be NaN where V1 has no value,
        e.g. 2018-2020).

    Returns (preds, fits):
      preds: DataFrame[game_id, season, week, home_team, away_team,
        pred_margin, fallback_flag, missing_frac]
      fits: list of per-week dicts {season, week, alpha, n_train,
        n_scaling_rows, gate_pass, n_predicted, n_fallback,
        missing_mean, missing_max}
    """
    if games is None:
        games = load_games()
    if table is None:
        table = load_modeling_table()
    off = feature_spec["offense"]
    deff = feature_spec["defense"]
    feats = off + deff

    # static per-game design inputs (fallback flags do not vary by week)
    all_ids = games["game_id"].tolist()
    home_feat, away_feat, rest_diff, meta = build_design(
        all_ids, feature_spec, games, table)
    gidx = games.set_index("game_id")

    # Tuesday batch cutoff per (season, week)
    cutoffs = {(S, W): tuesday_batch_cutoff(S, W, games)
               for (S, W) in seasons_weeks}

    tbl = table.reset_index()
    preds, fits = [], []
    for (S, W) in sorted(seasons_weeks):
        T = cutoffs[(S, W)]
        wk_ids = games[(games["season"] == S) & (games["week"] == W)] \
            ["game_id"].tolist()

        # --- scaling / imputation set: team-rows strictly before (S, W) ---
        srows = tbl[((tbl["season"] < S)
                     | ((tbl["season"] == S) & (tbl["pred_week"] < W)))
                    & (tbl["hist_games"] >= MIN_TEAM_GAMES)]
        gate_pass = len(srows) >= MIN_SCALING_ROWS
        fit = {"season": int(S), "week": int(W), "alpha": alpha,
               "n_scaling_rows": int(len(srows)), "gate_pass": bool(gate_pass)}

        if not gate_pass:
            for gid in wk_ids:
                m = meta.loc[gid]
                preds.append({"game_id": gid, "season": S, "week": W,
                              "home_team": m["home_team"],
                              "away_team": m["away_team"],
                              "pred_margin": m["v1"],
                              "fallback_flag": True,
                              "missing_frac": m["missing_frac"]})
            fit.update(n_train=0, n_predicted=0,
                       n_fallback=len(wk_ids), missing_mean=None,
                       missing_max=None)
            fits.append(fit)
            continue

        medians = walkforward_impute(srows, feats)
        mu, sigma = walkforward_standardize(srows, feats)

        # --- training games: kickoff < Tuesday batch, non-fallback ---
        tr = games[(games["kickoff_et"] < T)
                   & (~games["game_id"].isin(
                       meta[meta["fallback_flag"]].index))]
        # rest_diff scaling: walk-forward mu/sigma over training games
        rd_tr = rest_diff.loc[tr["game_id"]]
        mu_r, sd_r = rd_tr.mean(), rd_tr.std(ddof=0)

        def design(ids):
            zh = _standardize_frame(home_feat.loc[ids], medians, mu, sigma)
            za = _standardize_frame(away_feat.loc[ids], medians, mu, sigma)
            X = pd.DataFrame(index=ids)
            for c in off:
                X[f"d_off_{c}"] = zh[c] - za[c]
            for c in deff:
                # defense features are "allowed" (higher = worse defense)
                X[f"d_def_{c}"] = za[c] - zh[c]
            rd = rest_diff.loc[ids]
            X["rest_diff"] = ((rd - mu_r) / sd_r) if sd_r >= SIGMA_FLOOR \
                else 0.0
            return X[DESIGN_COLS]

        n_predicted = n_fallback = 0
        miss_vals = []
        tr_ids = tr["game_id"].tolist()
        if tr_ids:
            Xtr = design(tr_ids)
            ytr = meta.loc[tr_ids, "y"].astype(float).to_numpy()
            model = Ridge(alpha=alpha)
            model.fit(Xtr.to_numpy(), ytr)
        for gid in wk_ids:
            m = meta.loc[gid]
            if m["fallback_flag"] or not tr_ids:
                preds.append({"game_id": gid, "season": S, "week": W,
                              "home_team": m["home_team"],
                              "away_team": m["away_team"],
                              "pred_margin": m["v1"],
                              "fallback_flag": True,
                              "missing_frac": m["missing_frac"]})
                n_fallback += 1
            else:
                Xw = design([gid])
                p = float(model.predict(Xw.to_numpy())[0])
                preds.append({"game_id": gid, "season": S, "week": W,
                              "home_team": m["home_team"],
                              "away_team": m["away_team"],
                              "pred_margin": p,
                              "fallback_flag": False,
                              "missing_frac": float(m["missing_frac"])})
                n_predicted += 1
                miss_vals.append(float(m["missing_frac"]))
        fit.update(n_train=len(tr_ids), n_predicted=n_predicted,
                   n_fallback=n_fallback,
                   missing_mean=(float(np.mean(miss_vals))
                                 if miss_vals else None),
                   missing_max=(float(np.max(miss_vals))
                                if miss_vals else None))
        fits.append(fit)

    preds = pd.DataFrame(preds)
    return preds, fits
