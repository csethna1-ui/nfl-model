#!/usr/bin/env python3
"""Step 40: V2-A -- component architecture (protocol section 5).

Implements EXACTLY the protocol section 5 V2-A feature list:
  * Offense block (5): points_per_drive, epa_per_drive, scoring_drive_rate,
    rz_trip_rate, gtg_td_rate            -> (home_off - away_off)
  * Defense block (4): points_per_drive_allowed, epa_per_drive_allowed,
    scoring_drive_allowed, rz_trip_allowed -> (away_def - home_def)
  * alpha (intercept = home edge), beta_R * (home_rest - away_rest)
Home perspective, no doubling: 10 regressors + intercept.
(NOTE: protocol section 5 prints "20 regressors + intercept"; the section 3
model form and the section 5 feature list it enumerates yield 10 differential
regressors + intercept. Implemented as enumerated, home-perspective.)

Alpha selection (protocol section 4): walk-forward over 2018-2020
(V2-defined games only: non-fallback games with V2 predictions) for
alpha in {0.1, 1.0, 10.0, 100.0}, by MAE. This development-window metric is
explicitly authorized by the protocol. It is computed ONLY on 2018-2020,
never on 2021-2022. The winning alpha is frozen, then predictions are
generated for the 2021-2022 validation weeks.

Outputs:
  data/v2/pred_v2a.parquet : game_id, season, week, home_team, away_team,
                             pred_margin, fallback_flag (2021-2022 REG only;
                             fallback games carry V1 ens_margin)
  data/v2/manifest_v2a.json: frozen alpha, per-week n_train, missingness
                             summaries, feature-list hash, code versions,
                             timestamp-policy attestation, leakage checklist.

No 2021-2022 evaluation metrics are computed or written anywhere.
"""
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# 39_v2_harness.py is not importable by a plain `import` (leading digit), so
# load it explicitly from the same directory.
_hspec = importlib.util.spec_from_file_location(
    "v2_harness",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "39_v2_harness.py"))
v2_harness = importlib.util.module_from_spec(_hspec)
_hspec.loader.exec_module(v2_harness)
V2A_SPEC = v2_harness.V2A_SPEC
DESIGN_COLS = v2_harness.DESIGN_COLS
TEAM_FEATURES = v2_harness.TEAM_FEATURES
load_games = v2_harness.load_games
load_modeling_table = v2_harness.load_modeling_table
walkforward_predict = v2_harness.walkforward_predict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
ALPHAS = [0.1, 1.0, 10.0, 100.0]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def feature_list_hash():
    spec = {"name": V2A_SPEC["name"], "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"], "rest": V2A_SPEC["rest"],
            "form": "home_off-away_off; away_def-home_def; home_rest-away_rest",
            "design_cols": DESIGN_COLS}
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode()).hexdigest()


def dev_weeks(games, seasons):
    g = games[games["season"].isin(seasons)]
    return sorted(g[["season", "week"]].drop_duplicates()
                  .itertuples(index=False, name=None))


def main():
    games = load_games()
    table = load_modeling_table()
    n_games = len(games)
    print(f"games 2018-2022 REG with margin: {n_games}")

    # ---- Phase 1: alpha selection on 2018-2020 (development; authorized) ----
    sel_weeks = dev_weeks(games, [2018, 2019, 2020])
    alpha_mae, alpha_n = {}, {}
    for alpha in ALPHAS:
        preds, fits = walkforward_predict(V2A_SPEC, sel_weeks, alpha,
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
    preds, fits = walkforward_predict(V2A_SPEC, val_weeks, frozen_alpha,
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

    outp = f"{V2}/pred_v2a.parquet"
    preds[["game_id", "season", "week", "home_team", "away_team",
           "pred_margin", "fallback_flag"]].to_parquet(outp, index=False)
    print(f"wrote {outp}")

    # ---- manifest ----
    mm = preds[~preds["fallback_flag"]]["missing_frac"]
    manifest = {
        "model": "V2-A",
        "protocol": "v2_research/protocol.md (frozen 2026-09-29)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "feature_spec": {
            "offense": V2A_SPEC["offense"],
            "defense": V2A_SPEC["defense"],
            "rest": "home_rest - away_rest",
            "form": "home perspective, no doubling; "
                    "10 regressors + intercept "
                    "(protocol sec.5 prints '20 regressors + intercept'; "
                    "the enumerated feature list under the sec.3 model form "
                    "yields 10 -- implemented as enumerated)",
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
            "definition": "fraction of the 10 design columns NaN "
                          "pre-imputation, per predicted (non-fallback) game",
            "mean_over_predicted_games": float(mm.mean()),
            "max_over_predicted_games": float(mm.max()),
            "n_predicted_games": int(len(mm)),
            "imputation": "walk-forward median over training team-rows "
                          "(chronological (season, pred_week) < (S, W), "
                          "hist_games >= 4)",
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
            "sec.5 '20 regressors + intercept' vs enumerated 5+4+rest "
            "differentials under the sec.3 model form -> implemented 10 "
            "regressors + intercept (home-perspective, no doubling).",
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
            "38_v2_rebuild_table.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "38_v2_rebuild_table.py"))[:16],
            "39_v2_harness.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "39_v2_harness.py"))[:16],
            "40_v2a.py": sha256_file(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "40_v2a.py"))[:16],
            "modeling_table": "data/v2/team_features_pred_v2.parquet",
            "sklearn": __import__("sklearn").__version__,
            "ridge": "Ridge(alpha), default solver (deterministic)",
        },
    }
    outm = f"{V2}/manifest_v2a.json"
    with open(outm, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {outm}")


if __name__ == "__main__":
    main()
