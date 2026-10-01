# V1 Training-Window Audit

Read-only. Verified against `scripts/03_ratings.py`, `04_backtest.py`,
`05_metrics.py`, `07_update_weekly.py`, `data/linear_models.pkl`,
`data/ensemble_params.json` on 2026-09-29.

## Parameter inventory

| Parameter / artifact | Value / source | Status |
|---|---|---|
| ELO: K, HFA_ELO, REGRESS, MOV multiplier | K=20, HFA=55, regress=1/3, `log(m+1)·2.2/(2.2+0.001·d)` | Manually specified, never fit |
| EPA: ALPHA, PRIOR_WT | 0.25 weekly EWMA, 0.35 offseason regression to 0 | Manually specified, never fit |
| ELO per-team ratings | Rolled forward weekly, weekly batching | Updated weekly (deterministic, not fit) |
| EPA per-team ratings (8 metrics) | EWMA rolled forward weekly | Updated weekly (deterministic, not fit) |
| `lr_elo` (intercept 0.634, coef 0.04506) | Fit on 2018–2020 train in `04_backtest.py` | **Frozen** (`linear_models.pkl`) |
| `lr_epa_m` / `lr_epa_t` (8/6 coefs) | Fit on 2018–2020 train in `04_backtest.py` | **Frozen** (`linear_models.pkl`) |
| GBM hyperparameters | 200 trees, depth 3, lr 0.05, subsample/colsample 0.8, λ=1.0, seed 42 | Manually specified, never tuned |
| GBM backend | sklearn HistGradientBoostingRegressor (per saved pickle) | Fixed at backtest time |
| GBM coefficients/trees | Refit per predicted week (backtest) / final fit through W−1 (production) | **Refit walk-forward, expanding window** |
| Ensemble weights (margin 0.4/0.5/0.1; total 0.8/0.2) | Grid search (0.1 steps) on 2021–2022 validation MAE in `05_metrics.py` | Frozen (`ensemble_params.json`) |
| Operating threshold |edge| ≥ 3.0 | Selected on 2021–2022 validation ROI | Frozen |

## The one genuine ambiguity

**"Frozen V1" is not uniformly frozen.** The linear components and the
ensemble weights are frozen to their stated windows, but the **GBM component
is perpetually refit on an expanding window that includes the validation
years**: when the backtest predicts a 2022 game, that week's GBM was trained
on 2018–2021 — i.e., 2021 validation games are inside the GBM's training set.
(The linear coefficients never saw 2021–2022; the ensemble weights were
selected on 2021–2022.)

Consequences:

1. The label "V1 trained on 2018–2020" is true only for the linear
   components. The full V1 prediction for validation games contains a
   component fit on data through the prior week, including prior validation
   games. This is legitimate walk-forward methodology (no future leakage —
   each prediction uses only past games), but it is not the same as a frozen
   2018–2020 model.
2. Experiments 001–007 used the frozen *predictions* in
   `games_with_preds.parquet`, so they are mutually consistent — the
   ambiguity does not invalidate any experiment result.
3. Anyone reproducing "V1" from scratch must replicate the walk-forward GBM
   refit, not just load the linear coefficients. The production `07` GBM
   additionally trains on 2018–2026 (in-season), so production V1 is a
   slowly moving target by design, while the research V1 is the fixed
   artifact in `games_with_preds.parquet`.
4. The ensemble-weight tuning (05) and the GBM walk-forward (04) both
   consume 2021–2022 in different roles (selection vs. training). This is
   disclosed, not hidden, but it means the validation window is doing double
   duty and should not be treated as a pristine holdout for the *full*
   pipeline — only the vault (2023–2025) is.

## Verdict

No leakage: every prediction uses only data through the prior week
(weekly batching in both ratings loops; expanding-window GBM fits).
One real documentation-level ambiguity (above) about what "frozen" covers.
No silent refitting of the linear components or ensemble weights occurs in
production — `07` loads both from disk and only refits the GBM.
