# Experiment 008 — Frozen Research Protocol

**Frozen:** 2026-09-29, before any candidate validation results were examined.
**Status:** locked. No changes after validation results.

## Research question
Does a distributional/scoring-process architecture improve expected-margin
prediction (Question A) or uncertainty representation (Question B) over V1's
direct scalar margin regression?

## Timeline
- 2018–2020: development / parameter estimation
- 2021–2022: validation (REG only, n=543 — same sample as V2 validation, for comparability)
- 2023–2025: LOCKED VAULT (untouched until Phase 7)
- 2026: excluded entirely

## Candidates (exactly three; one run each; no retuning)

### 008-A — Separate home/away score model
- Team scoring ratings per team-week, strictly prior games: points scored
  (offense) and points allowed (defense), exponentially weighted, 8-game
  half-life, split home/away (home_off, home_def, away_off, away_def).
  Fewer than 1 prior game → league average. No opponent adjustment
  (kept deliberately simple; preregistered).
- Model: OLS. home_score ~ home_off_home + away_def_away;
  away_score ~ away_off_away + home_def_home. Intercept included.
- Fit: expanding window from 2018 REG, refit weekly through 2021–2022.
- Prediction: margin = E[home_score] − E[away_score].
- Structural claim: two scoring processes instead of one scalar margin.

### 008-B — Distributional margin via quantile regression
- Linear quantile regression (statsmodels QuantReg),
  τ ∈ {0.10, 0.25, 0.50, 0.75, 0.90}.
- Features (preregistered, all available 2018–2022, all pregame):
  pred_epa_m, elo_diff, off_epa_diff, def_epa_diff, ens_total, rest_diff.
  (`ens_margin` excluded: unavailable before 2021.)
- Fit: expanding window from 2018 REG, refit weekly through 2021–2022.
- Point forecast: conditional median (τ=0.50) — the MAE-optimal forecast.
- Structural claim: direct estimation of the margin distribution; median may
  beat V1's mean-based forecast under asymmetry.

### 008-C — Heteroskedastic margin model (Question B ONLY)
- Mean: frozen V1 `ens_margin` (not refit).
- log(σ²) = linear in [ens_total, |ens_margin|, pace_sum, explosiveness_sum],
  fit by OLS on log(resid²), walk-forward within 2021–2022 (min 40 games).
- Cannot advance as a margin predictor. Tests only whether uncertainty
  calibration improves (log score, interval coverage).

## Preprocessing / walk-forward rules
- Every prediction uses only games completed before the prediction week.
- All transforms deterministic; no fitted parameters from future data.
- Cold start: league-average fallback (documented; affects only early 2018,
  not the validation window).

## Metrics (per candidate, 2021–2022 validation)
1. MAE, 2. RMSE, 3. signed bias, 4. calibration intercept, 5. calibration
slope, 6. residual SD, 7. prediction–actual correlation, 8. V1 error
correlation, 9. absolute-error comparison vs V1, 10. season splits,
11. prediction-magnitude splits, 12. variance calibration,
13. distributional calibration (008-B/008-C), 14. Gaussian log score
(008-C), 15. interval coverage (008-B: [q10,q90],[q25,q75]; 008-C: 80% PI).

## Gates (Question A candidates: 008-A, 008-B)
- G1: no leakage (manifest audit).
- G2: timestamp discipline (all features pregame-defensible).
- G3: walk-forward procedure passes (expanding, weekly refit).
- G4: candidate MAE < V1 MAE in **both** 2021 and 2022 separately.
- G5: improvement not subgroup-dependent: candidate MAE < V1 MAE in ≥2 of 3
  prediction-magnitude buckets (|pred| < 3, 3–7, > 7).
- G6: calibration defensible: |candidate bias − V1 bias| < 1.0
  (relative gate — the sample carries ~+1.3 home drift that V1 itself shows);
  calibration slope in [0.6, 1.4].
- G7: complexity justified (preregistered small models; satisfied by design).
- G8: paired bootstrap (10,000) p < 0.05 for (V1 MAE − candidate MAE) > 0.
- G9: no post-hoc tuning (one run each; grids frozen below).
- G10: genuine structural difference from scalar margin regression
  (satisfied by design; verified via V1 error correlation < 0.99).
- **Advance to vault only if ALL gates pass.**

## Frozen hyperparameter policy
- 008-A: none (OLS closed form).
- 008-B: no tuning; QuantReg default solver; τ fixed.
- 008-C: no tuning; OLS on log(resid²).
- No grid searches. No refits with different settings.

## Question A vs Question B (preregistered)
- Question A (better expected margin): decided by gates above.
- Question B (better uncertainty): 008-B interval coverage vs nominal;
  008-C log score vs constant-σ baseline. A Question-B-only improvement is
  documented as a distributional improvement, NEVER as a superior margin
  predictor, and never advances to vault.

## Vault policy
- Vault accessed only if a Question-A candidate passes all gates.
- Then: freeze V2_DISTRIBUTIONAL_PREVAULT_REVIEW.md, run vault exactly once,
  no changes afterward.

## Phase-2 finding incorporated (diagnostic, pre-protocol)
Variance-predictability diagnostic (walk-forward within 2021–2022):
corr(predicted |resid|, actual |resid|) = 0.055; in-sample R² = 0.021;
predicted-σ log score worse than constant σ. **Verdict: WEAK.**
Per the directive, complex variance models are de-emphasized; 008-C is a
Question-B test only. The distributional hypothesis therefore rests on
location structure (008-A, 008-B), not heteroskedasticity.

## Amendments
- 2026-09-29 (before corrected validation re-run; implementation bug fixes,
  not tuning): (1) 008-A rewrote to a single chronological pass — the first
  version computed all ratings before any state updates, leaving every rating
  at the league average (flat predictions). (2) 008-B dropped `ens_total`
  from features — it is entirely NaN for 2018–2020 (no backfill), which made
  the standardized design matrix all-NaN and diverged the first QuantReg fits
  (|q50| in the thousands for 2021-W1). Five features remain. No model,
  hyperparameter, or gate was changed for performance reasons.
