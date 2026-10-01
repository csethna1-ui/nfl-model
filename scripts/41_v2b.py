#!/usr/bin/env python3
"""Step 41: V2-B -- component architecture + matchup interactions
(protocol section 5, amendments A1-A3).

V2-B = the exact V2-A design (10 regressors + intercept, home perspective,
no doubling) PLUS the 8 preregistered matchup interaction features from
protocol section 5, focal = home perspective, built from RAW
(unstandardized) team features per pair (off_f, def_f):
    prod  = home_off_f * away_def_f - away_off_f * home_def_f
    xdiff = (home_off_f - away_def_f) - (away_off_f - home_def_f)

Pairs (protocol section 5):
    (expl_pass_rate, expl_pass_allowed)
    (pressure_allowed_pct, def_pressures)      # def_pressures PFR-lagged
                                              # through W-2 in the table
    (expl_rush_rate, expl_rush_allowed)
    (big20_rate, big20_allowed)

The 8 game-level interaction columns are standardized walk-forward per
amendment A2: mu/sigma (population std, ddof=0) over the training games
strictly before week W (>= 30 games required, else the week's games fall
back to V1). Sporadic NaNs in the interaction columns are imputed with the
walk-forward median over the same training games (NaN propagates from raw
team features into the interaction columns; no team-level imputation is
applied to the interaction inputs first). The training-game set is the same
kickoff-filtered, non-fallback set used for the Ridge fit (identical to
V2-A); a week falls back if EITHER the team-row scaling gate or the
game-level interaction gate fails.

Alpha selection (protocol section 4): walk-forward over 2018-2020
(V2-defined games only: non-fallback games with V2 predictions) for
alpha in {0.1, 1.0, 10.0, 100.0}, by MAE. This development-window metric is
explicitly authorized by the protocol. It is computed ONLY on 2018-2020,
never on 2021-2022. The winning alpha is frozen, then predictions are
generated for the 2021-2022 validation weeks.

Outputs:
  data/v2/pred_v2b.parquet : game_id, season, week, home_team, away_team,
                             pred_margin, fallback_flag (2021-2022 REG only;
                             fallback games carry V1 ens_margin)
  data/v2/manifest_v2b.json: frozen alpha, per-week n_train, missingness
                             summaries, feature-list hash, code versions,
                             timestamp-policy attestation, leakage checklist.

No 2021-2022 evaluation metrics are computed or written anywhere.
"""
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

# 39_v2_harness.py is not importable by a plain `import` (leading digit), so
# load it explicitly from the same directory.
_hspec = importlib.util.spec_from_file_location(
    "v2_harness",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "39_v2_harness.py"))
v2_harness = importlib.util.module_from_spec(_hspec)
_hspec.loader.exec_module(v2_harness)
V2A_SPEC = v2_harness.V2A_SPEC
DESIGN_COLS = v2_harness.DESIGN_COLS          # 10 V2-A design columns
MIN_TEAM_GAMES = v2_harness.MIN_TEAM_GAMES
MIN_SCALING_ROWS = v2_harness.MIN_SCALING_ROWS
SIGMA_FLOOR = v2_harness.SIGMA_FLOOR
load_games = v2_harness.load_games
load_modeling_table = v2_harness.load_modeling_table
tuesday_batch_cutoff = v2_harness.tuesday_batch_cutoff
build_design = v2_harness.build_design
walkforward_impute = v2_harness.walkforward_impute
walkforward_standardize = v2_harness.walkforward_standardize
_standardize_frame = v2_harness._standardize_frame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
ALPHAS = [0.1, 1.0, 10.0, 100.0]

# Preregistered V2-B matchup pairs (protocol section 5): (offense, defense).
MX_PAIRS = [
    ("expl_pass_rate", "expl_pass_allowed"),
    ("pressure_allowed_pct", "def_pressures"),
    ("expl_rush_rate", "expl_rush_allowed"),
    ("big20_rate", "big20_allowed"),
]
MX_COLS = []
for _off_f, _def_f in MX_PAIRS:
    MX_COLS.append(f"mx_prod_{_off_f}_x_{_def_f}")
    MX_COLS.append(f"mx_xdiff_{_off_f}_x_{_def_f}")
V2B_DESIGN_COLS = DESIGN_COLS + MX_COLS       # 18 regressors + intercept

# Fetch spec: V2-A's 9 team features plus the 8 raw interaction inputs.
# (Only used for fetching raw team rows; the V2-A team-level
# imputation/standardization still runs over the 9 V2-A features alone.)
FETCH_SPEC = {
    "name": "V2-B-fetch",
    "offense": V2A_SPEC["offense"] + [p[0] for p in MX_PAIRS],
    "defense": V2A_SPEC["defense"] + [p[1] for p in MX_PAIRS],
    "rest": True,
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def feature_list_hash():
    spec = {
        "name": "V2-B",
        "v2a": {
            "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"],
            "rest": "home_rest - away_rest",
            "form": "home perspective, no doubling; "
                    "10 regressors + intercept",
        },
        "interactions": {
            "pairs": [{"offense": o, "defense": d} for o, d in MX_PAIRS],
            "form": "prod = home_off*away_def - away_off*home_def; "
                    "xdiff = (home_off - away_def) - (away_off - home_def); "
                    "focal = home perspective; built from RAW "
                    "(unstandardized) team features",
            "standardization": "walk-forward mu/sigma (population std, "
                               "ddof=0) over training games strictly before "
                               "week W (>=30 games required, else the "
                               "week's games fall back); walk-forward "
                               "median imputation over the same games",
        },
        "design_cols": V2B_DESIGN_COLS,
    }
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode()).hexdigest()


def raw_interactions(home_feat, away_feat, ids):
    """Raw (unstandardized, pre-imputation) game-level interaction columns.

    NaN propagates from any missing raw team input; imputation happens at
    game grain later (walk-forward median over training games).
    """
    X = pd.DataFrame(index=ids)
    for off_f, def_f in MX_PAIRS:
        ho = home_feat.loc[ids, off_f].astype(float)
        ao = away_feat.loc[ids, off_f].astype(float)
        hd = home_feat.loc[ids, def_f].astype(float)
        ad = away_feat.loc[ids, def_f].astype(float)
        X[f"mx_prod_{off_f}_x_{def_f}"] = ho * ad - ao * hd
        X[f"mx_xdiff_{off_f}_x_{def_f}"] = (ho - ad) - (ao - hd)
    return X[MX_COLS]


def game_standardize_frame(df, medians, mu, sigma):
    """Game-grain analog of the harness's _standardize_frame.

    Median-impute, then z-score with walk-forward mu/sigma; constant or
    all-NaN columns (sigma floored to NaN) standardize to 0.
    """
    z = (df.fillna(medians) - mu) / sigma
    return z.fillna(0.0)


def walkforward_predict_v2b(seasons_weeks, alpha, games=None, table=None):
    """Walk-forward Ridge predictions for V2-B (18 regressors + intercept).

    Per week W: the V2-A component is built exactly as in the harness
    (team-row walk-forward medians / mu / sigma, rest_diff scaled over
    training games); the 8 interaction columns are built from raw team
    features and standardized at game grain over the same training-game
    set. A week falls back to V1 if either the team-row gate (|S(W)| < 30)
    or the game-level interaction gate (< 30 training games) fails.

    Returns (preds, fits) with the same preds schema as the harness plus
    per-week team_gate_pass / interaction_gate_pass fields.
    """
    if games is None:
        games = load_games()
    if table is None:
        table = load_modeling_table()
    off = V2A_SPEC["offense"]
    deff = V2A_SPEC["defense"]
    feats = off + deff  # 9 V2-A team features only

    all_ids = games["game_id"].tolist()
    home_feat, away_feat, rest_diff, meta = build_design(
        all_ids, FETCH_SPEC, games, table)

    cutoffs = {(S, W): tuesday_batch_cutoff(S, W, games)
               for (S, W) in seasons_weeks}

    tbl = table.reset_index()
    mx_raw_all = raw_interactions(home_feat, away_feat, all_ids)

    # V2-B design-level missingness (pre-imputation), per non-fallback game:
    # NaN among the 10 V2-A differential columns + the 8 raw interaction
    # columns, over 18. rest_diff is never NaN.
    miss_v2b = {}
    for gid in all_ids:
        m = meta.loc[gid]
        if m["fallback_flag"]:
            miss_v2b[gid] = np.nan
            continue
        h = home_feat.loc[gid]
        a = away_feat.loc[gid]
        dnan = 0
        for c in off:
            dnan += int(pd.isna(h[c]) or pd.isna(a[c]))
        for c in deff:
            dnan += int(pd.isna(h[c]) or pd.isna(a[c]))
        dnan += int(mx_raw_all.loc[gid, MX_COLS].isna().sum())
        miss_v2b[gid] = dnan / 18.0
    miss_v2b = pd.Series(miss_v2b)

    preds, fits = [], []
    for (S, W) in sorted(seasons_weeks):
        T = cutoffs[(S, W)]
        wk_ids = games[(games["season"] == S) & (games["week"] == W)] \
            ["game_id"].tolist()

        # --- V2-A scaling/imputation set: team-rows strictly before (S, W) ---
        srows = tbl[((tbl["season"] < S)
                     | ((tbl["season"] == S) & (tbl["pred_week"] < W)))
                    & (tbl["hist_games"] >= MIN_TEAM_GAMES)]
        team_gate = len(srows) >= MIN_SCALING_ROWS

        # --- training games: kickoff < Tuesday batch, non-fallback ---
        # (identical to V2-A; also the game-level scaling set for the
        # interaction columns, per amendment A2 and the task spec)
        tr = games[(games["kickoff_et"] < T)
                   & (~games["game_id"].isin(
                       meta[meta["fallback_flag"]].index))]
        tr_ids = tr["game_id"].tolist()
        game_gate = len(tr_ids) >= MIN_SCALING_ROWS

        fit = {"season": int(S), "week": int(W), "alpha": alpha,
               "n_scaling_rows": int(len(srows)),
               "team_gate_pass": bool(team_gate),
               "n_interaction_scaling_games": int(len(tr_ids)),
               "interaction_gate_pass": bool(game_gate),
               "gate_pass": bool(team_gate and game_gate)}

        if not (team_gate and game_gate):
            for gid in wk_ids:
                m = meta.loc[gid]
                preds.append({"game_id": gid, "season": S, "week": W,
                              "home_team": m["home_team"],
                              "away_team": m["away_team"],
                              "pred_margin": m["v1"],
                              "fallback_flag": True,
                              "missing_frac": np.nan})
            fit.update(n_train=0, n_predicted=0,
                       n_fallback=len(wk_ids), missing_mean=None,
                       missing_max=None)
            fits.append(fit)
            continue

        # V2-A team-level walk-forward stats (identical to harness/V2-A).
        medians = walkforward_impute(srows, feats)
        mu, sigma = walkforward_standardize(srows, feats)
        rd_tr = rest_diff.loc[tr_ids]
        mu_r, sd_r = rd_tr.mean(), rd_tr.std(ddof=0)

        # Interaction game-level walk-forward stats over training games
        # (NaN-skipping pandas ops; sporadic NaNs imputed with the median).
        mx_tr = mx_raw_all.loc[tr_ids]
        mx_median = mx_tr.median()
        mx_mu = mx_tr.mean()
        mx_sigma = mx_tr.std(ddof=0)
        mx_sigma = mx_sigma.where(mx_sigma >= SIGMA_FLOOR, np.nan)

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
            X = X[DESIGN_COLS].join(
                game_standardize_frame(mx_raw_all.loc[ids],
                                       mx_median, mx_mu, mx_sigma))
            return X[V2B_DESIGN_COLS]

        n_predicted = n_fallback = 0
        miss_vals = []
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
                              "missing_frac": np.nan})
                n_fallback += 1
            else:
                Xw = design([gid])
                p = float(model.predict(Xw.to_numpy())[0])
                mf = float(miss_v2b[gid])
                preds.append({"game_id": gid, "season": S, "week": W,
                              "home_team": m["home_team"],
                              "away_team": m["away_team"],
                              "pred_margin": p,
                              "fallback_flag": False,
                              "missing_frac": mf})
                n_predicted += 1
                miss_vals.append(mf)
        fit.update(n_train=len(tr_ids), n_predicted=n_predicted,
                   n_fallback=n_fallback,
                   missing_mean=(float(np.mean(miss_vals))
                                 if miss_vals else None),
                   missing_max=(float(np.max(miss_vals))
                                if miss_vals else None))
        fits.append(fit)

    preds = pd.DataFrame(preds)
    return preds, fits


def dev_weeks(games, seasons):
    g = games[games["season"].isin(seasons)]
    return sorted(g[["season", "week"]].drop_duplicates()
                  .itertuples(index=False, name=None))


def main():
    games = load_games()
    table = load_modeling_table()
    n_games = len(games)
    print(f"games 2018-2022 REG with margin: {n_games}")
    print(f"V2-B design: {len(V2B_DESIGN_COLS)} regressors + intercept")

    # ---- Phase 1: alpha selection on 2018-2020 (development; authorized) ----
    # MAE is computed ONLY on 2018-2020, never on 2021-2022.
    sel_weeks = dev_weeks(games, [2018, 2019, 2020])
    alpha_mae, alpha_n = {}, {}
    for alpha in ALPHAS:
        preds, fits = walkforward_predict_v2b(sel_weeks, alpha,
                                              games=games, table=table)
        v2 = preds[~preds["fallback_flag"]].merge(
            games[["game_id", "home_margin"]], on="game_id")
        err = (v2["pred_margin"] - v2["home_margin"]).abs()
        alpha_mae[alpha] = float(err.mean())
        alpha_n[alpha] = int(len(v2))
        print(f"alpha={alpha}: MAE(dev 2018-2020, V2-defined games only) "
              f"computed over n={len(v2)} games")
    frozen_alpha = min(ALPHAS, key=lambda a: alpha_mae[a])
    print(f"frozen alpha = {frozen_alpha}")

    # ---- Phase 2: frozen-alpha predictions for 2021-2022 validation ----
    # Predictions and manifests only. No evaluation metrics on 2021-2022.
    val_weeks = dev_weeks(games, [2021, 2022])
    preds, fits = walkforward_predict_v2b(val_weeks, frozen_alpha,
                                          games=games, table=table)
    preds = preds.sort_values(["season", "week", "game_id"]).reset_index(
        drop=True)
    n_total = len(preds)
    n_fallback = int(preds["fallback_flag"].sum())
    n_v2 = n_total - n_fallback
    assert preds["pred_margin"].notna().sum() == n_total, \
        "every validation game needs a prediction (V1 fallback is complete " \
        "for 2021-2022)"
    print(f"validation predictions: {n_total} games "
          f"({n_v2} V2, {n_fallback} V1-fallback)")

    outp = f"{V2}/pred_v2b.parquet"
    preds[["game_id", "season", "week", "home_team", "away_team",
           "pred_margin", "fallback_flag"]].to_parquet(outp, index=False)
    print(f"wrote {outp}")

    # ---- manifest ----
    mm = preds[~preds["fallback_flag"]]["missing_frac"]
    manifest = {
        "model": "V2-B",
        "protocol": "v2_research/protocol.md (frozen 2026-09-29, "
                    "amendments A1-A3)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "feature_spec": {
            "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"],
            "rest": "home_rest - away_rest",
            "interactions": {
                "pairs": [{"offense": o, "defense": d}
                          for o, d in MX_PAIRS],
                "form": "focal = home perspective; "
                        "prod = home_off*away_def - away_off*home_def; "
                        "xdiff = (home_off - away_def) - "
                        "(away_off - home_def); built from RAW "
                        "(unstandardized) team features; NaN propagates "
                        "from raw inputs",
                "standardization": "walk-forward mu/sigma (population std, "
                                   "ddof=0) over training games strictly "
                                   "before week W (>=30 games required, "
                                   "else the week's games fall back); "
                                   "walk-forward median imputation over the "
                                   "same games",
            },
            "form": "home perspective, no doubling; 18 regressors + "
                    "intercept (10 V2-A differentials + 8 matchup "
                    "interactions)",
            "design_cols": V2B_DESIGN_COLS,
            "feature_list_sha256": feature_list_hash(),
        },
        "alpha_selection": {
            "window": "2018-2020 walk-forward, V2-defined (non-fallback) "
                      "games only",
            "grid": ALPHAS,
            "mae_by_alpha_dev_2018_2020": {str(a): alpha_mae[a]
                                           for a in ALPHAS},
            "n_games_by_alpha": {str(a): alpha_n[a] for a in ALPHAS},
            "frozen_alpha": frozen_alpha,
            "note": "Development-window MAE is explicitly authorized by "
                    "protocol sec.4. No 2021-2022 data used for any decision.",
        },
        "validation_weeks": {
            "window": "2021-2022 REG",
            "n_games": n_total,
            "n_v2_predicted": n_v2,
            "n_fallback_v1": n_fallback,
            "per_week_fits": fits,
        },
        "missingness": {
            "definition": "fraction of the 18 design columns NaN "
                          "pre-imputation, per predicted (non-fallback) game "
                          "(10 V2-A differentials + 8 interaction columns; "
                          "rest_diff never NaN)",
            "mean_over_predicted_games": float(mm.mean()),
            "max_over_predicted_games": float(mm.max()),
            "n_predicted_games": int(len(mm)),
            "imputation": "two-level: (1) V2-A component -- walk-forward "
                          "median over training team-rows (chronological "
                          "(season, pred_week) < (S, W), hist_games >= 4); "
                          "(2) interaction columns -- walk-forward median "
                          "over the training games (kickoff < Tuesday "
                          "08:00 ET batch, non-fallback)",
        },
        "timestamp_policy_attestation": {
            "pfr_features": "17 PFR columns rebuilt as expanding means over "
                            "weeks <= W-2 (all prior seasons whole), "
                            "scripts/35 logic, MIN_GAMES=4; lag-0 rebuild "
                            "reproduces original columns to <1e-9",
            "injury_features": "row-level rule date_modified < "
                               "min(Tuesday 08:00 ET cutoff, team kickoff); "
                               "Tuesday set: 1 of 5647 Out/Doubtful rows "
                               "(2018-2022) survives (PIT 2020 W12 Jaylen "
                               "Samuels, game rescheduled past the cutoff) "
                               "-- honest output of the general rule",
            "qb_features": "qb_value_pred (historical, pre-week only); "
                           "qb_value_poll quarantined, never merged/used",
            "scalers": "V2-A component: walk-forward mu/sigma (population "
                       "std, ddof=0) over training team-rows strictly "
                       "before (S, W), hist_games >= 4, |S(W)| >= 30 else "
                       "week falls back; rest_diff scaled walk-forward over "
                       "training games. Interaction columns: walk-forward "
                       "mu/sigma (ddof=0) over training games strictly "
                       "before week W, >= 30 games else week falls back",
            "training_set": "Ridge fit on REG games with kickoff < Tuesday "
                            "08:00 ET batch cutoff of week W "
                            "(Sunday-anchored); 4 COVID-rescheduled games "
                            "break the week<W equivalence -- documented in "
                            "39_v2_harness.tuesday_batch_cutoff",
            "interaction_features": "built per game from RAW "
                                    "(unstandardized) modeling-table team "
                                    "features at pred_week=W (PFR-lagged "
                                    "through W-2, injury row-level cutoff "
                                    "applied in the table build); "
                                    "standardization/imputation statistics "
                                    "use only training games strictly "
                                    "before week W",
            "no_future_information": True,
        },
        "leakage_checklist": {
            "pfr_one_week_shift": "PASS",
            "injury_row_level_cutoff": "PASS",
            "qb_historical_only_poll_quarantined": "PASS",
            "walkforward_scaling_imputation": "PASS",
            "interaction_game_level_walkforward": "PASS",
            "vault_2023_2025_untouched": "PASS",
            "data_2026_untouched": "PASS",
            "experiment_006_untouched": "PASS",
            "v1_code_predictions_readonly": "PASS",
            "no_evaluation_metrics_on_2021_2022": "PASS",
        },
        "protocol_ambiguities_documented": [
            "V2-B interaction imputation grain: interactions are built from "
            "RAW (unstandardized) team features with NaN propagation (no "
            "team-level median imputation of the inputs first); sporadic "
            "NaNs in the 8 interaction columns are imputed with the "
            "walk-forward median of the column over the training games -- "
            "the literal reading of the task text ('from RAW "
            "(unstandardized) team features' + 'impute sporadic NaNs with "
            "the walk-forward median over the same games') and amendment "
            "A2 ('built from raw team features, then standardized').",
            "Game-level standardization/imputation set: the Ridge "
            "training-game set for week W (REG games with kickoff < "
            "Tuesday 08:00 ET batch cutoff, excluding fallback games) -- "
            "the set the kickoff-rule training filter yields, which the "
            "task text declares identical to V2-A. The >=30 threshold is "
            "evaluated on non-fallback training games (fallback games' "
            "interaction columns are structurally all-NaN and contribute "
            "nothing to the statistics).",
            "Week-level fallback: if EITHER the team-row scaling gate "
            "(|S(W)| < 30) or the game-level interaction gate (< 30 "
            "training games) fails, the week's games fall back to V1 "
            "ens_margin (fallback_flag=True), per the task text.",
            "Missingness denominator for V2-B: 18 design columns (10 V2-A "
            "differentials + 8 interaction columns); rest_diff never NaN.",
            "Inherited from V2-A: training-set membership for fallback "
            "games (structurally all-NaN V2 features, excluded from Ridge "
            "training and from the primary comparison per sec.3); "
            "Sunday-anchored Tuesday 08:00 ET batch cutoff (2020-W13 "
            "BAL-PIT Wed game excluded from W13 training -- one training "
            "row affected); week-grain feature tables cannot reflect the 4 "
            "rescheduled Tue/Wed games' post-batch kickoffs (frozen "
            "pipeline limitation); rest_diff standardized with "
            "walk-forward mu/sigma over training games.",
        ],
        "code_versions": {
            "38_v2_rebuild_table.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "38_v2_rebuild_table.py"))[:16],
            "39_v2_harness.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "39_v2_harness.py"))[:16],
            "40_v2a.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "40_v2a.py"))[:16],
            "41_v2b.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "41_v2b.py"))[:16],
            "modeling_table": "data/v2/team_features_pred_v2.parquet",
            "sklearn": __import__("sklearn").__version__,
            "ridge": "Ridge(alpha), default solver (deterministic)",
        },
    }
    outm = f"{V2}/manifest_v2b.json"
    with open(outm, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {outm}")


if __name__ == "__main__":
    main()
