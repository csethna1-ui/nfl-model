#!/usr/bin/env python3
"""Step 43: V2-D -- component + pressure / explosiveness-shape /
possession-structure (protocol section 5).

Implements EXACTLY the protocol section 5 V2-D feature list:
  * V2-A design verbatim (10 regressors + intercept): 5 offense differentials
    (home_off - away_off), 4 defense differentials (away_def - home_def),
    beta_R * (home_rest - away_rest). Built via the harness's build_design
    for the V2-A spec (code reuse, not reinvention).
  * 37 structure features, ALL as (home - away) differentials (protocol
    section 5: "37 features as (home - away) differentials", regardless of
    each feature's offensive/defensive character):
      possession structure (7): three_and_out_rate, start_y100,
        plays_per_drive, drive_to_rate, three_and_out_forced,
        start_y100_allowed, drive_to_forced
      explosiveness shape (15): epa_std, epa_median, epa_p10, epa_p90,
        expl_pass_rate, expl_rush_rate, big20_rate, big40_rate, air_per_att,
        adot, expl_pass_allowed, expl_rush_allowed, big20_allowed,
        big40_allowed, epa_std_allowed
      pressure (15): pressure_allowed_pct, sack_rate, qb_hit_rate,
        hits_taken, hurries_taken, pressures_taken, blitzed_taken, drops,
        bad_throw_pct, def_blitzes, def_hurries, def_qb_hits, def_sacks,
        def_pressures, def_missed_tackles
        (PFR-sourced members are already one-week-lagged in the rebuilt
        modeling table -- used as-is.)
    Built through the harness's build_design + standard
    walk-forward standardization/imputation path (imputation medians and
    mu/sigma over training team-rows strictly before (S, W),
    hist_games >= 4, |S(W)| >= 30).
  * 47 regressors + intercept: d_off_* (5), d_def_* (4), d_struct_* (37),
    rest_diff.
  * Overlap of the 37 with V2-A's base features is checked at build time;
    any overlap aborts with an error.

Cold-start rule (Option C), Tuesday cutoff, kickoff-rule training filter,
fallback exclusion from training, and all other harness behaviors are
identical to V2-A: the weekly loop here is a line-for-line mirror of
harness.walkforward_predict with the extended design function, and reuses
the harness's load_games / load_modeling_table / tuesday_batch_cutoff /
build_design / walkforward_impute / walkforward_standardize /
_standardize_frame.

Alpha selection (protocol section 4): walk-forward over 2018-2020
(V2-defined games only: non-fallback games with V2 predictions) for
alpha in {0.1, 1.0, 10.0, 100.0}, by MAE. This development-window metric is
explicitly authorized by the protocol. It is computed ONLY on 2018-2020,
never on 2021-2022. The winning alpha is frozen, then predictions are
generated for the 2021-2022 validation weeks.

Outputs:
  data/v2/pred_v2d.parquet : game_id, season, week, home_team, away_team,
                             pred_margin, fallback_flag (2021-2022 REG only;
                             fallback games carry V1 ens_margin)
  data/v2/manifest_v2d.json: frozen alpha, per-week n_train, missingness
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
DESIGN_COLS_A = v2_harness.DESIGN_COLS  # the 10 V2-A design columns
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

# ---- protocol section 5 preregistered V2-D structure feature lists ----
STRUCT_POSSESSION = ["three_and_out_rate", "start_y100", "plays_per_drive",
                     "drive_to_rate", "three_and_out_forced",
                     "start_y100_allowed", "drive_to_forced"]  # 7
STRUCT_EXPLOSIVENESS = ["epa_std", "epa_median", "epa_p10", "epa_p90",
                        "expl_pass_rate", "expl_rush_rate", "big20_rate",
                        "big40_rate", "air_per_att", "adot",
                        "expl_pass_allowed", "expl_rush_allowed",
                        "big20_allowed", "big40_allowed",
                        "epa_std_allowed"]  # 15
STRUCT_PRESSURE = ["pressure_allowed_pct", "sack_rate", "qb_hit_rate",
                   "hits_taken", "hurries_taken", "pressures_taken",
                   "blitzed_taken", "drops", "bad_throw_pct",
                   "def_blitzes", "def_hurries", "def_qb_hits", "def_sacks",
                   "def_pressures", "def_missed_tackles"]  # 15
STRUCT_FEATURES = STRUCT_POSSESSION + STRUCT_EXPLOSIVENESS + STRUCT_PRESSURE
assert len(STRUCT_FEATURES) == 37, f"expected 37, got {len(STRUCT_FEATURES)}"
assert len(set(STRUCT_FEATURES)) == 37, "duplicate structure feature names"

V2A_BASE = (list(V2A_SPEC["offense"]) + list(V2A_SPEC["defense"]))  # 9

# Build-time non-overlap guard (protocol section 5: "No overlap with V2-A's
# base features (verified at freeze time)"). Abort if any overlap is found.
_overlap = set(STRUCT_FEATURES) & set(V2A_BASE)
if _overlap:
    raise RuntimeError(
        "PROTOCOL VIOLATION: V2-D structure features overlap V2-A base "
        f"features: {sorted(_overlap)}")

# A harness feature spec for the structure block. Each member is treated as
# a home-away differential, which is exactly the harness's offense-channel
# form (zh - za); the offense label here is a harness plumbing detail, not a
# modeling claim. The resulting design columns are named d_struct_*.
STRUCT_SPEC = {
    "name": "V2-D-structure",
    "offense": STRUCT_FEATURES,
    "defense": [],
    "rest": False,
}
TEAM_FEATURES_D = V2A_BASE + STRUCT_FEATURES  # 46 team-level cols
DESIGN_COLS = ([f"d_off_{c}" for c in V2A_SPEC["offense"]]
               + [f"d_def_{c}" for c in V2A_SPEC["defense"]]
               + [f"d_struct_{c}" for c in STRUCT_FEATURES]
               + ["rest_diff"])  # 47 design columns
assert len(DESIGN_COLS) == 47


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def feature_list_hash():
    spec = {"name": "V2-D",
            "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"],
            "structure_possession": STRUCT_POSSESSION,
            "structure_explosiveness": STRUCT_EXPLOSIVENESS,
            "structure_pressure": STRUCT_PRESSURE,
            "rest": V2A_SPEC["rest"],
            "form": "home-perspective differentials: home_off-away_off; "
                    "away_def-home_def; structure all home-away; "
                    "home_rest-away_rest",
            "design_cols": DESIGN_COLS}
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode()).hexdigest()


def dev_weeks(games, seasons):
    g = games[games["season"].isin(seasons)]
    return sorted(g[["season", "week"]].drop_duplicates()
                  .itertuples(index=False, name=None))


def walkforward_predict_v2d(seasons_weeks, alpha, games, table):
    """V2-D walk-forward: a line-for-line mirror of
    harness.walkforward_predict with the extended 47-column design.

    The base (d_off_/d_def_/rest) path is the harness's build_design for the
    V2-A spec; the structure path is the harness's build_design for the
    37-feature structure spec (each as home-away); both go through the
    harness's walk-forward imputation and standardization. Cold start,
    Tuesday cutoff, kickoff training filter, scaling gate, and fallback
    handling are byte-identical in behavior to V2-A.
    """
    off = V2A_SPEC["offense"]
    deff = V2A_SPEC["defense"]

    # --- per-game raw inputs via the harness (identical to V2-A for base) ---
    all_ids = games["game_id"].tolist()
    home_a, away_a, rest_diff, meta_a = build_design(all_ids, V2A_SPEC,
                                                     games, table)
    home_s, away_s, rest_diff_s, meta_s = build_design(all_ids, STRUCT_SPEC,
                                                       games, table)
    # cold-start flags must be identical: they depend only on hist_games
    # >= 4 and row presence, never on which features are read.
    assert (meta_a["fallback_flag"] == meta_s["fallback_flag"]).all(), \
        "fallback flags diverge between base and structure build_design"
    assert (rest_diff == rest_diff_s).all(), \
        "rest_diff diverges between build_design calls"
    fallback_flag = meta_a["fallback_flag"]

    # combined pre-imputation missingness: fraction of the 47 design
    # columns NaN (a differential col is NaN if either side is NaN;
    # rest_diff is never NaN).
    missing_frac = {}
    for gid in all_ids:
        if fallback_flag.loc[gid]:
            missing_frac[gid] = np.nan
        else:
            hf = pd.concat([home_a.loc[gid, V2A_BASE],
                            home_s.loc[gid, STRUCT_FEATURES]])
            af = pd.concat([away_a.loc[gid, V2A_BASE],
                            away_s.loc[gid, STRUCT_FEATURES]])
            dnan = int(((hf.isna()) | (af.isna())).sum())
            missing_frac[gid] = dnan / len(DESIGN_COLS)
    meta = pd.DataFrame({
        "game_id": all_ids,
        "season": meta_a["season"].values,
        "week": meta_a["week"].values,
        "home_team": meta_a["home_team"].values,
        "away_team": meta_a["away_team"].values,
        "y": meta_a["y"].values,
        "v1": meta_a["v1"].values,
        "fallback_flag": fallback_flag.values,
        "missing_frac": [missing_frac[g] for g in all_ids],
    }).set_index("game_id")
    home_feat = pd.concat([home_a[V2A_BASE], home_s[STRUCT_FEATURES]],
                          axis=1)
    away_feat = pd.concat([away_a[V2A_BASE], away_s[STRUCT_FEATURES]],
                          axis=1)

    # --- Tuesday batch cutoff per (season, week) ---
    cutoffs = {(S, W): tuesday_batch_cutoff(S, W, games)
               for (S, W) in seasons_weeks}

    tbl = table.reset_index()
    preds, fits = [], []
    for (S, W) in sorted(seasons_weeks):
        T = cutoffs[(S, W)]
        wk_ids = games[(games["season"] == S) & (games["week"] == W)] \
            ["game_id"].tolist()

        # scaling / imputation set: team-rows strictly before (S, W)
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

        medians = walkforward_impute(srows, TEAM_FEATURES_D)
        mu, sigma = walkforward_standardize(srows, TEAM_FEATURES_D)

        # training games: kickoff < Tuesday batch, non-fallback
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
            for c in STRUCT_FEATURES:
                # protocol section 5: all 37 structure features as
                # (home - away) differentials
                X[f"d_struct_{c}"] = zh[c] - za[c]
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


def main():
    games = load_games()
    table = load_modeling_table()
    n_games = len(games)
    print(f"games 2018-2022 REG with margin: {n_games}")
    print(f"V2-D design: {len(DESIGN_COLS)} regressors + intercept "
          f"(10 V2-A base + 37 structure)")

    # ---- Phase 1: alpha selection on 2018-2020 (development; authorized) ----
    sel_weeks = dev_weeks(games, [2018, 2019, 2020])
    alpha_mae, alpha_n = {}, {}
    for alpha in ALPHAS:
        preds, fits = walkforward_predict_v2d(sel_weeks, alpha,
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
    preds, fits = walkforward_predict_v2d(val_weeks, frozen_alpha,
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

    outp = f"{V2}/pred_v2d.parquet"
    preds[["game_id", "season", "week", "home_team", "away_team",
           "pred_margin", "fallback_flag"]].to_parquet(outp, index=False)
    print(f"wrote {outp}")

    # ---- manifest (same schema as manifest_v2a.json) ----
    mm = preds[~preds["fallback_flag"]]["missing_frac"]
    manifest = {
        "model": "V2-D",
        "protocol": "v2_research/protocol.md (frozen 2026-09-29)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "feature_spec": {
            "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"],
            "structure_possession": STRUCT_POSSESSION,
            "structure_explosiveness": STRUCT_EXPLOSIVENESS,
            "structure_pressure": STRUCT_PRESSURE,
            "rest": "home_rest - away_rest",
            "form": "home perspective, no doubling; 47 regressors + "
                    "intercept: 10 V2-A base differentials + 37 structure "
                    "features, all as (home - away) per protocol sec.5",
            "overlap_check_v2a_base": "PASS (37 structure features disjoint "
                                      "from the 9 V2-A base features; "
                                      "build aborts on any overlap)",
            "design_cols": DESIGN_COLS,
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
            "definition": "fraction of the 47 design columns NaN "
                          "pre-imputation, per predicted (non-fallback) game",
            "mean_over_predicted_games": float(mm.mean()),
            "max_over_predicted_games": float(mm.max()),
            "n_predicted_games": int(len(mm)),
            "imputation": "walk-forward median over training team-rows "
                          "(chronological (season, pred_week) < (S, W), "
                          "hist_games >= 4)",
        },
        "timestamp_policy_attestation": {
            "pfr_features": "PFR-sourced pressure members used as-is from "
                            "the rebuilt table (already one-week-lagged "
                            "through W-2, script 38 output); no additional "
                            "shift applied",
            "injury_features": "none enter V2-D directly; row-level rule "
                               "date_modified < min(Tuesday 08:00 ET "
                               "cutoff, team kickoff) already applied in "
                               "the rebuilt table (as documented in "
                               "manifest_v2a.json)",
            "qb_features": "none enter V2-D",
            "scalers": "walk-forward mu/sigma (population std, ddof=0) over "
                       "training team-rows strictly before (S, W), "
                       "hist_games >= 4, |S(W)| >= 30 else week falls back; "
                       "rest_diff scaled walk-forward over training games; "
                       "all 46 team features (9 base + 37 structure) on the "
                       "same path as V2-A",
            "training_set": "Ridge fit on REG games with kickoff < Tuesday "
                            "08:00 ET batch cutoff of week W "
                            "(Sunday-anchored); 4 COVID-rescheduled games "
                            "break the week<W equivalence -- documented in "
                            "39_v2_harness.tuesday_batch_cutoff; fallback "
                            "games excluded from Ridge training",
            "no_future_information": True,
        },
        "leakage_checklist": {
            "structure_feature_lags": "PASS (table rebuilt by script 38; "
                                     "PFR lagged through W-2 as-is)",
            "non_overlap_with_v2a_base": "PASS",
            "walkforward_scaling_imputation": "PASS",
            "cold_start_option_c_identical_to_v2a": "PASS",
            "vault_2023_2025_untouched": "PASS",
            "data_2026_untouched": "PASS",
            "experiment_006_untouched": "PASS",
            "v1_code_predictions_readonly": "PASS",
            "no_evaluation_metrics_on_2021_2022": "PASS",
        },
        "protocol_ambiguities_documented": [
            "Sec.5 says the 37 structure features enter as (home - away) "
            "differentials regardless of each feature's offensive/defensive "
            "character (e.g. expl_pass_allowed, def_sacks): implemented "
            "literally as home-away, no sign flips. No ambiguity remains "
            "after the literal reading, but recorded here since a "
            "defense-channel (away-home) alternative exists in the "
            "harness -- the protocol's wording governs.",
            "The harness's build_design labels the structure block via its "
            "offense channel (d_struct_ prefix in the V2-D design matrix); "
            "this is a plumbing label only -- the differential form is "
            "exactly the protocol-specified home-away.",
            "Training-set membership for fallback games, batch cutoff "
            "conservatism, week-grain limitation for rescheduled games, and "
            "rest_diff standardization carry over unchanged from V2-A "
            "(see manifest_v2a.json protocol_ambiguities_documented).",
        ],
        "code_versions": {
            "38_v2_rebuild_table.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "38_v2_rebuild_table.py"))[:16],
            "39_v2_harness.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "39_v2_harness.py"))[:16],
            "43_v2d.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "43_v2d.py"))[:16],
            "modeling_table": "data/v2/team_features_pred_v2.parquet",
            "sklearn": __import__("sklearn").__version__,
            "ridge": "Ridge(alpha), default solver (deterministic)",
        },
    }
    outm = f"{V2}/manifest_v2d.json"
    with open(outm, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {outm}")


if __name__ == "__main__":
    main()
