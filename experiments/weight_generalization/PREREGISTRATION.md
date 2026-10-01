# Preregistered Analysis — V1 Ensemble Weight Generalization (2023–2025)

**Date:** 2026-09-29
**Status:** PREREGISTERED — analysis not yet run.

## Question

Did the ensemble weights tuned on 2021–2022 (0.4 ELO / 0.5 EPA / 0.1 GBM)
generalize to 2023–2025?

## Why this is legitimate

The weights were frozen before 2023–2025 was ever examined for this purpose.
Evaluating a frozen, preregistered specification on held-out data is the
textbook use of a test set — it is reporting, not training.

2023–2025 was previously used exactly once: to report frozen V1's ATS record
(140–125, 52.8%, +0.9% ROI). This analysis adds a second reporting use (MAE
diagnostics). The vault remains unspent for model *selection*.

## Data and methodology (fixed in advance)

- Component predictions on 2023–2025 from frozen methodology identical to
  production: ELO-linear and EPA-linear fit on 2018–2020 only; GBM walk-forward
  trained solely on pre-week history (as `07_update_weekly.py` does).
- No refitting of any kind on 2023–2025. No weight optimization on 2023–2025.

## Evaluations (all fixed, no optimization)

1. ELO component alone — MAE on 2023–2025
2. EPA component alone — MAE
3. GBM component alone — MAE
4. **V1 frozen 40/50/10 — MAE (the preregistered test)**
5. Equal weights (1/3, 1/3, 1/3) — MAE, fixed reference point
6. Full 0.1-step weight grid (66 combinations) — MAE each, **diagnostic only**:
   report the distribution and V1's rank/percentile within it.

## Binding decision rule

**No weight changes result from this analysis regardless of outcome.**
If the weights look unstable across regimes, the follow-up is a separately
preregistered Experiment 009 (ensemble weight robustness), designed without
using 2023–2025 for selection. Seeing the grid distribution spends researcher
degrees of freedom; this rule contains that cost.

## Interpretation scenarios (preregistered)

- **Scenario 1** (components hold rank order, V1 ≈ best blend): weighting
  generalized; strengthens V1's ensemble construction.
- **Scenario 2** (component rank order flips vs 2021–2022): weights did not
  generalize; relationship between components is regime-dependent. Correct
  language: "the V1 architecture has not been improved, but its fixed
  ensemble weights may not be robust across regimes."
- **Scenario 3** (a different fixed blend clearly better, V1 held back):
  ensemble weighting becomes a legitimate next experiment (009).

## Language

Not "V1 is the ceiling." Instead: "V1 is the current best validated
specification under the frozen information set. Its ensemble weights were
optimized on 2021–2022 and have not been re-optimized; 2023–2025 provides the
out-of-sample test of their generalization."

## What this does NOT authorize

- No production weight change.
- No re-tuning on 2023–2025.
- No new model, no vault use beyond this diagnostic.
- Experiment 009 is not authorized by this document; it requires its own
  preregistration and Cale's explicit approval.
