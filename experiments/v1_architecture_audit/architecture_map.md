# V1 Architecture Map

Read-only audit. All facts verified against code in `scripts/` on 2026-09-29.
No parameters were modified; this document describes what exists.

## 1. Prediction pipeline (production, `scripts/07_update_weekly.py`)

For a prediction week W of season S, using only games with `week < W`:

1. **Refresh inputs**: re-pull schedules + PBP for season S (`refresh_schedules`,
   `refresh_pbp`). Ratings rolled forward deterministically (see §3).
2. **Build game rows**: for each game in week W, attach pre-week team ratings
   → `home_off_epa`, `away_off_epa`, … (8 EPA/SR metrics × home/away),
   `elo_diff`, `home_rest`/`away_rest`, `div_game`, `week`.
3. **Feature engineering** (`model_lib.add_features`): home−away differentials
   (`off_epa_diff`, `def_epa_diff`, `off_pass_diff`, `off_rush_diff`,
   `def_pass_diff`, `def_rush_diff`, `sr_off_diff`, `sr_def_diff`) and sums
   (for totals).
4. **Component predictions**:
   - `pred_elo` = `lr_elo.predict(elo_diff)` — linear model, coefficients
     **frozen** (fit on 2018–2020 in `04_backtest.py`, loaded from
     `data/linear_models.pkl`).
   - `pred_epa_m` = `lr_epa_m.predict(8 EPA differentials)` — linear model,
     coefficients **frozen** (same source).
   - `pred_gbm_m` = GBM predict on `MARGIN_FEATS` (elo_diff + 8 EPA diffs +
     rest_diff + div_game + week) — GBM **refit from scratch** on all
     played+rated games through week W−1 (expanding window, includes 2026
     in-season data in production).
5. **Ensemble** (frozen weights from `data/ensemble_params.json`):
   - `model_spread = 0.4·pred_elo + 0.5·pred_epa_m + 0.1·pred_gbm_m`
   - `model_total  = 0.8·pred_epa_t + 0.2·pred_gbm_t`
6. **Picks**: `edge = model_spread − market_spread`; pick if `|edge| ≥ 3.0`
   (threshold frozen, selected on 2021–2022 validation ROI).
7. **Injury filter** (`11_injury_adjust.py`, separate post-step): may only
   *remove* picks on unexpected starting-QB Out/Doubtful; never creates/flips.

## 2. Component specifications

### (a) ELO → margin (linear)
- ELO update (`03_ratings.run_elo`): K=20, HFA_ELO=55 (~2.2 pts, used only in
  win-probability, **not** in `elo_diff`), offseason regression 1/3 toward 1500,
  margin-of-victory multiplier `log(|margin|+1)·2.2/(2.2+0.001·|elo_diff|)`.
  Weekly batching: all games in a week use pre-week ELO.
- Mapping: `margin = 0.634 + 0.04506 · elo_diff` (fit 2018–2020, frozen).
- Home field enters only via the intercept (~0.63 pts).

### (b) EPA → margin (linear)
- EPA ratings (`03_ratings.run_epa`): per-team EWMA with ALPHA=0.25 on weekly
  mean EPA / pass EPA / rush EPA / success rate, offense and defense
  separately (8 metrics); offseason regression 35% toward 0 (league avg).
  Plays: `play_type ∈ {pass, run}` with non-null EPA. Weekly batching.
- Mapping (fit 2018–2020, frozen):
  `margin = 0.650 + 18.96·off_epa_diff + 2.92·def_epa_diff − 2.14·off_pass_diff
   + 4.38·off_rush_diff − 7.91·def_pass_diff − 9.30·def_rush_diff
   + 52.85·sr_off_diff − 30.22·sr_def_diff`
- Note the pass/rush split coefficients partially offset the aggregate EPA
  coefficients (multicollinear by construction: off_epa ≈ blend of pass/rush).

### (c) GBM → margin (nonlinear)
- Backend that generated the backtest predictions: **sklearn
  HistGradientBoostingRegressor** (recorded in `linear_models.pkl`;
  XGBoost fallback was not installed at backtest time).
- Hyperparameters (manually specified, never tuned):
  `n_estimators/max_iter=200, max_depth=3, learning_rate=0.05,
   subsample=0.8, colsample_bytree=0.8, reg_lambda/l2=1.0, random_state=42`.
- Features: `MARGIN_FEATS` = elo_diff + 8 EPA differentials + rest_diff +
  div_game + week (12 features). The GBM's feature set is a **superset** of
  (a)+(b)'s inputs plus rest/division/week.
- Training: walk-forward; in backtest, one fit per predicted week on all
  prior games (expanding). In production, one final fit on all games through
  W−1.

## 3. What is the "team rating"?

There is no single team-strength number. V1 carries per-team, per-metric
ratings: ELO (one scalar) + 8 EPA/SR metrics (off/def × total/pass/rush/SR).
Game prediction uses only **home−away differentials** of these ratings
(plus rest differential, division flag, week number). The architecture is:

> per-team metric ratings → game-level differentials → three estimators of
> E[home margin | differentials] → fixed linear ensemble → point estimate.

## 4. Structural observations (descriptive, not prescriptive)

- The three components estimate the **same conditional expectation** from
  overlapping inputs; the GBM's inputs strictly contain the linears' inputs.
  The ensemble is variance-averaging over estimators, not information fusion.
- The target is a **single scalar point estimate** (home margin). There is no
  uncertainty / variance output, no decomposition of *why* a margin is
  expected, and no interaction between matchup structure and home field
  beyond additive intercepts.
- The residual-correction experiment pattern (001, 003, 005, 007) appends a
  regularized correction to this point estimate using features drawn from the
  same team-strength information space.
