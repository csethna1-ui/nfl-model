# REPRODUCIBILITY — Props Experiment 003B: Rush Attempts

Frozen 2026-10-01. Locked test (2023–2024) evaluated exactly once.

## Environment

- Repo: `~/workspace/nfl-model`; Python venv: `~/workspace/nfl-model/venv`
  (pandas 3.0.5, pyarrow 25.0.1, scikit-learn 1.9.1, nfl_data_py 0.3.3,
  numpy 2.5.3).
- Seeds: bootstrap RNG 1337; GBM `random_state=11`; quantile GBM
  `random_state=7`.

## Frozen inputs (untouched, read-only)

- `experiments/player_props_projection/data/modeling_table.parquet`
  (001 frozen base, 2018–2024).
- `experiments/props_experiment_002/data/extended_features_2018_2024.parquet`
  (002 frozen extended features, 2018–2024).

## Pipeline (in order)

1. `scripts/build_003b_features.py` — DATA PREP ONLY (no fitting).
   Merges trailing NGS rushing EWMAs (half-life 3, max 16 games,
   most-recent-first, strictly prior weeks; `week==0` season-aggregate
   rows excluded — see RESULTS.md) per player, derives
   `neut_rush_rate = 1 − pace_neutral_pass_rate`.
   → `data/ngs_rushing_2018_2024.parquet` (raw NGS pull, keyless),
   → `data/features_003b_2018_2024.parquet`.
2. `scripts/audit_003b_features.py` — availability/leakage audit;
   verification checks run on train+dev only.
   → `data/feature_audit.csv`.
3. `scripts/run_experiment_003b.py --phase dev` — fit on train
   (2018–2020), hyperparameter selection on dev (2021–2022); test slice
   untouched. → `data/experiment_003b_dev.json`.
4. `PROTOCOL_FROZEN` sentinel written (prereg approved by Cale 2026-10-01
   12:25 CDT; dev complete).
5. `scripts/run_experiment_003b.py --phase test` — SINGLE locked-test
   evaluation: refit on train with dev-frozen hyperparameters, predict
   2023–2024 once, paired bootstrap (2000, seed 1337), win-bar verdict.
   → `data/experiment_003b_test.json`,
   → `data/experiment_003b_test_predictions.parquet`,
   → `models/{M1,M2,M3}_fitted.pkl` (exact fitted ensembles).

## Model procedure (per rung M1/M2/M3)

A = single-stage Ridge on rung features (StandardScaler; the 002 two-stage
opportunity×efficiency degenerates for a pure-opportunity target — see
script docstring), α dev-selected from {0.1, 1, 10, 100}. B =
HistGradientBoostingRegressor direct, 8-combo grid dev-selected
(lr ∈ {0.05,0.1} × depth ∈ {3,5} × iter ∈ {200,500}). C = quantile-GBM
median, fixed a priori (lr 0.1, depth 3, iter 300, min_samples_leaf 20).
D = equal-weight mean of A/B/C point projections, clipped ≥ 0.
M0 = `trail_rush_att_ewma` (NaN→0). Population: RB, eligible_hist=1,
played_role=1, trail_rush_att_ewma ≥ 5. No spread/total/implied features
anywhere.

## Rung feature sets (frozen)

- M1: pace_team_plays, trail_rush_share_ewma, opp2_snap_pct, neut_rush_rate,
  ctx_elo_adv, trail_rz_carries_ewma, trail_games.
- M2: M1 + ngs_eff, ngs_xrush, ngs_ryoe, ngs_ryoe_pct, ngs_8box, ngs_ttl.
- M3: M1 + ctx_team_off_epa, ctx_team_off_pass_epa, ctx_team_off_rush_epa,
  ctx_team_off_sr, oppd_def_rush_epa, envs_dome, envs_team_pts_trail,
  envs_opp_pts_allowed_trail, envf_days_rest, envf_rest_diff, envf_short_week,
  envf_long_rest, envf_div_game, pace_combined, pace_neutral_pass_rate.

## Win bar (shared protocol §5)

≥5% pooled relative-MAE reduction vs M0; ≥2% in 2023 AND 2024; 95% paired
bootstrap CI of the MAE difference excludes zero. Result: M2 MATERIAL WIN
(+29.76% / +31.56% / +27.80%, CI [1.112, 1.414]); M1, M3 PARTIAL/SIGNAL.
