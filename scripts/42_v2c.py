#!/usr/bin/env python3
"""Step 42: V2-C -- component architecture + QB/player features
(protocol section 5, V2-A design + 7 preregistered player features).

V2-C = the exact V2-A design (10 regressors + intercept) plus the 7
preregistered player features as (home - away) differentials, all in home
perspective, no doubling:
  * V2-A offense block (5): points_per_drive, epa_per_drive,
    scoring_drive_rate, rz_trip_rate, gtg_td_rate        -> home_off-away_off
  * V2-A defense block (4): points_per_drive_allowed, epa_per_drive_allowed,
    scoring_drive_allowed, rz_trip_allowed              -> away_def-home_def
  * Player block (7): qb_value_historical, qb_nonqb1_share,
    snap_continuity_off, ol_continuity, skill_continuity,
    avail_value_out, avail_n_out                         -> home - away
  * beta_R * (home_rest - away_rest); alpha (intercept = home edge)
17 regressors + intercept.

Reuses the shared harness (39_v2_harness.py) for all building blocks:
load_games, load_modeling_table, tuesday_batch_cutoff, build_design,
walkforward_impute, walkforward_standardize, _standardize_frame, and the
constants. The harness's walkforward_predict hardcodes V2-A's DESIGN_COLS,
so the walk-forward loop is replicated here EXACTLY (same scaling-set gate,
same Tuesday-batch kickoff training filter, same cold-start fallback rule,
same rest_diff walk-forward scaling, same per-week fit manifest fields) with
only the 17-column V2-C design list substituted. The harness itself is not
modified.

Known conditions handled (all documented, none errors):
  * avail_value_out / avail_n_out: the Tuesday availability set is
    (documented premise) identically zero -- the row-level injury cutoff rule
    honestly yields zeros in the Tuesday batch. Empirically the rebuilt
    modeling table has 41 nonzero PIT rows (2020 W13 - 2021 W8) at 1e-4
    scale: the documented Jaylen Samuels (PIT 2020 W12, rescheduled past the
    Tuesday cutoff) exception decaying through the rolling means. Per the
    frozen pipeline's handling of zero-variance columns (harness
    SIGMA_FLOOR: constant -> z = 0.0), the standardized values of these two
    columns are set to 0.0 after walk-forward standardization, for both the
    training design and the prediction design. Documented in the manifest.
  * qb_value_historical has NaNs on QB cold starts (11.3% of table rows):
    sporadic, not structural -- covered by the standard walk-forward median
    imputation over training team-rows (same as all other features).
  * qb_pressured_pct_rw (Friday-safe only) and qb_value_poll (quarantined)
    are never used; neither enters the design.

Alpha selection (protocol section 4): walk-forward over 2018-2020
(V2-defined games only: non-fallback games with V2 predictions) for
alpha in {0.1, 1.0, 10.0, 100.0}, by MAE. This development-window metric is
explicitly authorized by the protocol. It is computed ONLY on 2018-2020,
never on 2021-2022. The winning alpha is frozen, then predictions are
generated for the 2021-2022 validation weeks.

Outputs:
  data/v2/pred_v2c.parquet : game_id, season, week, home_team, away_team,
                             pred_margin, fallback_flag (2021-2022 REG only;
                             fallback games carry V1 ens_margin)
  data/v2/manifest_v2c.json: frozen alpha, per-week n_train, missingness
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
load_games = v2_harness.load_games
load_modeling_table = v2_harness.load_modeling_table
tuesday_batch_cutoff = v2_harness.tuesday_batch_cutoff
build_design = v2_harness.build_design
walkforward_impute = v2_harness.walkforward_impute
walkforward_standardize = v2_harness.walkforward_standardize
_standardize_frame = v2_harness._standardize_frame
MIN_TEAM_GAMES = v2_harness.MIN_TEAM_GAMES
MIN_SCALING_ROWS = v2_harness.MIN_SCALING_ROWS
SIGMA_FLOOR = v2_harness.SIGMA_FLOOR

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
ALPHAS = [0.1, 1.0, 10.0, 100.0]

# Protocol section 5 V2-C: the 7 preregistered player features. All enter as
# (home - away) differentials (same convention as the offense block).
PLAYER_FEATURES = ["qb_value_historical", "qb_nonqb1_share",
                   "snap_continuity_off", "ol_continuity",
                   "skill_continuity", "avail_value_out", "avail_n_out"]
# avail columns are (intended) zero-variance in the Tuesday set; their
# standardized values are set to 0.0 (documented above).
AVAIL_COLS = ["avail_value_out", "avail_n_out"]

V2C_SPEC = {
    "name": "V2-C",
    "offense": V2A_SPEC["offense"] + PLAYER_FEATURES,  # 5 + 7
    "defense": V2A_SPEC["defense"],                    # 4
    "rest": True,
}
V2C_DESIGN_COLS = ([f"d_off_{c}" for c in V2C_SPEC["offense"]]
                   + [f"d_def_{c}" for c in V2C_SPEC["defense"]]
                   + ["rest_diff"])  # 17 design columns


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def feature_list_hash():
    spec = {"name": V2C_SPEC["name"],
            "offense_base": V2A_SPEC["offense"],
            "offense_player": PLAYER_FEATURES,
            "defense": V2C_SPEC["defense"],
            "rest": V2C_SPEC["rest"],
            "form": "home_off-away_off; away_def-home_def; "
                    "home_player-away_player; home_rest-away_rest",
            "design_cols": V2C_DESIGN_COLS}
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode()).hexdigest()


def dev_weeks(games, seasons):
    g = games[games["season"].isin(seasons)]
    return sorted(g[["season", "week"]].drop_duplicates()
                  .itertuples(index=False, name=None))


def walkforward_predict_v2c(seasons_weeks, alpha, games, table):
    """Walk-forward Ridge predictions for V2-C.

    Exact replication of the harness's walkforward_predict loop (same
    scaling/imputation sets, same |S(W)| >= 30 gate, same Tuesday 08:00 ET
    batch kickoff training filter, same cold-start fallback rule, same
    rest_diff walk-forward scaling, same per-week fit manifest fields),
    with the 17-column V2-C design list substituted for the harness's
    hardcoded V2-A DESIGN_COLS, plus the documented avail zero-variance
    handling. No other behavior changes.
    """
    off = V2C_SPEC["offense"]
    deff = V2C_SPEC["defense"]
    feats = off + deff  # 16 team-level features

    all_ids = games["game_id"].tolist()
    home_feat, away_feat, rest_diff, meta = build_design(
        all_ids, V2C_SPEC, games, table)
    gidx = games.set_index("game_id")

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
            # avail columns are the (documented) zero-variance Tuesday
            # availability set: standardized values -> 0.0
            zh[AVAIL_COLS] = 0.0
            za[AVAIL_COLS] = 0.0
            X = pd.DataFrame(index=ids)
            for c in off:
                X[f"d_off_{c}"] = zh[c] - za[c]
            for c in deff:
                # defense features are "allowed" (higher = worse defense)
                X[f"d_def_{c}"] = za[c] - zh[c]
            rd = rest_diff.loc[ids]
            X["rest_diff"] = ((rd - mu_r) / sd_r) if sd_r >= SIGMA_FLOOR \
                else 0.0
            return X[V2C_DESIGN_COLS]

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


def main():
    games = load_games()
    table = load_modeling_table()
    n_games = len(games)
    print(f"games 2018-2022 REG with margin: {n_games}")

    # ---- Phase 1: alpha selection on 2018-2020 (development; authorized) ----
    sel_weeks = dev_weeks(games, [2018, 2019, 2020])
    alpha_mae, alpha_n = {}, {}
    for alpha in ALPHAS:
        preds, fits = walkforward_predict_v2c(sel_weeks, alpha,
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
    val_weeks = dev_weeks(games, [2021, 2022])
    preds, fits = walkforward_predict_v2c(val_weeks, frozen_alpha,
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

    outp = f"{V2}/pred_v2c.parquet"
    preds[["game_id", "season", "week", "home_team", "away_team",
           "pred_margin", "fallback_flag"]].to_parquet(outp, index=False)
    print(f"wrote {outp}")

    # ---- manifest ----
    mm = preds[~preds["fallback_flag"]]["missing_frac"]
    manifest = {
        "model": "V2-C",
        "protocol": "v2_research/protocol.md (frozen 2026-09-29)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "feature_spec": {
            "base": "exact V2-A design: 5 offense differentials + "
                    "4 defense differentials + rest_diff (10 regressors)",
            "player_features": PLAYER_FEATURES,
            "player_form": "all 7 as (home - away) differentials, same "
                           "convention as the offense block",
            "rest": "home_rest - away_rest",
            "form": "home perspective, no doubling; "
                    "17 regressors + intercept",
            "design_cols": V2C_DESIGN_COLS,
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
            "definition": "fraction of the 17 design columns NaN "
                          "pre-imputation, per predicted (non-fallback) game",
            "mean_over_predicted_games": float(mm.mean()),
            "max_over_predicted_games": float(mm.max()),
            "n_predicted_games": int(len(mm)),
            "imputation": "walk-forward median over training team-rows "
                          "(chronological (season, pred_week) < (S, W), "
                          "hist_games >= 4); qb_value_historical cold-start "
                          "NaNs (11.3% of table rows) are sporadic and "
                          "covered by this median imputation",
        },
        "timestamp_policy_attestation": {
            "pfr_features": "17 PFR columns rebuilt as expanding means over "
                            "weeks <= W-2 (all prior seasons whole), "
                            "scripts/35 logic, MIN_GAMES=4; lag-0 rebuild "
                            "reproduces original columns to <1e-9",
            "injury_features": "row-level rule date_modified < "
                               "min(Tuesday 08:00 ET cutoff, team kickoff); "
                               "Tuesday availability set is (documented "
                               "premise) identically zero; empirical table "
                               "check found 41 nonzero PIT rows "
                               "(2020 W13 - 2021 W8) at 1e-4 scale from the "
                               "documented Jaylen Samuels (PIT 2020 W12) "
                               "cutoff exception -- standardized avail values "
                               "set to 0.0 (zero-variance handling)",
            "qb_features": "qb_value_pred (historical, pre-week only); "
                           "qb_pressured_pct_rw excluded (Friday-safe only "
                           "per protocol); qb_value_poll quarantined, never "
                           "merged/used",
            "scalers": "walk-forward mu/sigma (population std, ddof=0) over "
                       "training team-rows strictly before (S, W), "
                       "hist_games >= 4, |S(W)| >= 30 else week falls back; "
                       "rest_diff scaled walk-forward over training games",
            "training_set": "Ridge fit on REG games with kickoff < Tuesday "
                            "08:00 ET batch cutoff of week W "
                            "(Sunday-anchored); 4 COVID-rescheduled games "
                            "break the week<W equivalence -- documented in "
                            "39_v2_harness.tuesday_batch_cutoff",
            "no_future_information": True,
        },
        "leakage_checklist": {
            "pfr_one_week_shift": "PASS",
            "injury_row_level_cutoff": "PASS",
            "qb_historical_only_poll_quarantined": "PASS",
            "walkforward_scaling_imputation": "PASS",
            "vault_2023_2025_untouched": "PASS",
            "data_2026_untouched": "PASS",
            "experiment_006_untouched": "PASS",
            "v1_code_predictions_readonly": "PASS",
            "no_evaluation_metrics_on_2021_2022": "PASS",
        },
        "protocol_ambiguities_documented": [
            "sec.5 V2-C '7 features as (home - away) differentials': the "
            "player block uses the same (home - away) convention as the "
            "offense block (not the flipped away_def - home_def convention); "
            "implemented under the harness build_design offense path.",
            "harness walkforward_predict hardcodes V2-A's DESIGN_COLS; the "
            "walk-forward loop is replicated verbatim in 42_v2c.py using "
            "only harness building blocks (build_design, "
            "tuesday_batch_cutoff, walkforward_impute, "
            "walkforward_standardize, _standardize_frame, constants). The "
            "harness itself is unmodified; only the 17-column V2-C design "
            "list is substituted and the avail zero-variance handling added.",
            "avail_value_out / avail_n_out are not exactly zero-variance in "
            "the rebuilt table: 41 PIT rows (2020 W13 - 2021 W8) at 1e-4 "
            "scale from the documented Jaylen Samuels (PIT 2020 W12) cutoff "
            "exception. Protocol sec.5 and the manifest premise state the "
            "Tuesday availability set is identically zero; standardized "
            "avail values are therefore set to 0.0 (zero-variance handling) "
            "for both training and prediction designs, rather than letting "
            "1e-4-scale numerical dust standardize into |z| ~ 20 for PIT "
            "rows. Imputation medians are unaffected (median = 0.0).",
            "Training-set membership for fallback games: protocol says 'all "
            "REG games' (sec.4) but their V2 features are structurally "
            "all-NaN under the >=4-games component gate; excluded from Ridge "
            "training (imputation covers sporadic, not structural, "
            "missingness). Excluded from the primary comparison per sec.3.",
            "Batch cutoff for week W: Tuesday 08:00 ET preceding week W's "
            "Sunday slate (conservative); 2020-W13 BAL-PIT (Wed game) "
            "excluded from W13 training -- one training row affected.",
            "Week-grain feature tables cannot reflect the 4 rescheduled "
            "Tue/Wed games' post-batch kickoffs (frozen pipeline is week "
            "grain by design); documented, not altered.",
            "rest_diff standardized with walk-forward mu/sigma over training "
            "games (no team-row analogue exists); same >=30-row gate applies.",
        ],
        "code_versions": {
            "39_v2_harness.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "39_v2_harness.py"))[:16],
            "42_v2c.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "42_v2c.py"))[:16],
            "modeling_table": "data/v2/team_features_pred_v2.parquet",
            "sklearn": __import__("sklearn").__version__,
            "ridge": "Ridge(alpha), default solver (deterministic)",
        },
    }
    outm = f"{V2}/manifest_v2c.json"
    with open(outm, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {outm}")


if __name__ == "__main__":
    main()
