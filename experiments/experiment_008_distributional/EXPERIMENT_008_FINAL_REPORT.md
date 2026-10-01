# EXPERIMENT 008 — Final Report

**Status: DISTRIBUTIONAL_CANDIDATES_FAILED**
**Date:** 2026-09-29
**Protocol:** `protocol.md` (frozen before validation; one amendment for implementation bug fixes, documented below — no tuning)

## What was tested
Whether the scalar expected-margin target itself is the binding constraint on
NFL margin prediction. Three preregistered distributional/scoring-process
architectures, each run exactly once under walk-forward discipline on
2021–2022 REG (n=543, same sample as V2-A–D):

- **008-A** — separate home/away score regressions (OLS on exp-weighted
  home/away-split team scoring ratings, 8-game half-life); margin = E[home] − E[away]
- **008-B** — linear quantile regression (τ = 0.10/0.25/0.50/0.75/0.90);
  conditional median as the MAE-optimal point forecast
- **008-C** — heteroskedastic margin model (mean = frozen V1; log σ² linear in
  pregame features); Question B only

## What failed
| Candidate | MAE | Δ vs V1 (10.059) | paired p | Gates |
|---|---|---:|---:|---|
| 008-A | 10.366 | −0.307 | 0.980 (sig. worse) | FAIL G4, G8 |
| 008-B | 10.084 | −0.024 | 0.659 (tied) | FAIL G4, G8 |
| 008-C | 10.059 | 0.000 | — (same mean) | Q-B only; log score worse than constant σ |

- 008-A is **significantly worse** than V1 in both seasons (pred–actual corr
  0.299 vs V1 0.383). Modeling the two scoring processes separately produced a
  worse location estimate, not a better one.
- 008-B is statistically tied with V1 (Δ −0.024, CI [−0.139, +0.092]) with a
  **0.995 error correlation** — the conditional median carries essentially the
  same information as V1's conditional mean. Its intervals are well calibrated
  ([q10,q90] coverage 0.805 vs 0.80 nominal), but that reflects the empirical
  residual distribution, not predictable heteroskedasticity.
- 008-C: predicted-σ log score −4.63 vs constant-σ −3.97; 80% PI coverage
  0.578. Modeling conditional variance from pregame info **hurts**.

## Whether variance was predictable
No. Phase-2 walk-forward diagnostic: corr(predicted |resid|, actual |resid|)
= 0.055; in-sample R² = 0.021; quintiles non-monotone. Game-level error scale
is essentially unpredictable from pregame information.

## Whether distributional modeling helped
- **Question A (better expected margin): no.** The best distributional
  candidate ties V1; the two-process candidate loses significantly.
- **Question B (better uncertainty): no.** Variance models underperform a
  constant-variance baseline; quantile intervals match nominal coverage only
  because the residual distribution is stable, not because uncertainty is
  conditionally predictable.

## What evidence remains
The combined record is now: 6 failed feature experiments (001–003, 005, 007),
a failed component-decomposition ladder (V2-A–D, all significantly worse than
V1), and a failed target-architecture experiment (008-A–C). V1's residual is
orthogonal to its features, its errors correlate 0.967 with the market's, and
no tested information space — team-strength, strategy, availability,
matchups, possession structure, explosiveness, pressure, QB value, separate
scoring processes, conditional quantiles, conditional variance — moves it.
The remaining ~10.06 MAE (vs market ~9.73) is consistent with largely
irreducible game variance plus information the market prices that is not
available in free pregame data.

## Implementation notes (transparency)
Two implementation bugs were found and fixed before the valid run; both are
documented in `protocol.md` amendments. No model, hyperparameter, or gate was
changed for performance reasons:
1. 008-A first ran with all ratings stuck at league average (state-update
   ordering bug) → flat predictions. Rewrote as a single chronological pass.
2. 008-B's `ens_total` feature is entirely NaN for 2018–2020 (no backfill) →
   all-NaN design matrix → diverged QuantReg fits (|q50| in the thousands).
   Dropped the feature; five remain.
`statsmodels` 0.15.0 was installed into the repo venv (needed for QuantReg).

## Vault / production
- Vault (2023–2025) **never touched**. No V2_DISTRIBUTIONAL_PREVAULT_REVIEW
  (no candidate passed gates).
- **V1 remains production, unmodified.** Experiment 006 continues independently.

## The next legitimate hypothesis
The pregame public-information margin-prediction problem appears saturated at
~V1's level with free data: neither more features, nor component structure,
nor distributional targets improve on direct scalar margin regression. The
remaining legitimate research directions are *different problems*, not
extensions of this one:
1. **Information timing** — Experiment 006 (prospective): does a Tuesday vs
   Friday information set change prediction quality? Already collecting.
2. **In-game modeling** — a different target (win probability / live margin)
   with different data; not a V2 for the pregame sheet.
3. **New data, not new math** — the binding constraint may be information
   (e.g., real-time injury/lineup news the market prices in minutes), which
   no architecture can manufacture from box scores.
4. Accept the null: V1 is the ceiling for this problem with these data, and
   further effort has negative expected value.

## Files
- `experiments/experiment_008_distributional/`: `literature_review.md`,
  `architecture_comparison.md`, `methodology.md`, `protocol.md`,
  `variance_diagnostic.md/.json`, `validation_report_008.md`,
  `validation_results_008.json`, `manifest_008{a,b,c}.json`,
  `EXPERIMENT_008_FINAL_REPORT.md` (this file)
- `scripts/`: `45_008_variance_diagnostic.py`, `46_008a_scores.py`,
  `47_008b_quantile.py`, `48_008c_hetero.py`, `49_008_evaluate.py`
- `data/v2/`: `pred_008{a,b,c}.parquet`
