# Experiment 005 — Non-QB Player Availability: REPORT

## Preregistered design (summary)

- **Hypothesis.** Frozen V1's effective information state is ~Tuesday morning of game week.
  Later-arriving non-QB player-availability information (through Friday 12:00 ET) is a
  fundamentally different information category ("who is playing" vs "how the team
  performed"). Test whether adding it improves margin prediction.
- **Candidate.** `candidate_margin = v1_margin + ridge_pred`, where a Ridge(α=1.0)
  predicts `(actual_margin − v1_margin)` from 30 signed non-QB injury-count features
  (5 position groups × 3 designations, away−home signed, `date_modified < min(kickoff,
  Friday 12:00 ET)`). V1 frozen and untouched.
- **Timing distinction (intentional).** V1 ≈ Tuesday AM information; the injury layer uses
  information through Friday 12:00 ET. This is the hypothesis under test, not a flaw —
  but the candidate must not be described as "V1 plus injuries" without this distinction.
- **Preregistration amendment (before any validation evaluation).** Config locked
  position grouping, designation encoding, aggregation, and Ridge(α=1.0) trained on
  2018–2020 — but frozen-V1 margins do not exist pre-2021 (all 803 null;
  V1 predictions begin 2021). Amended to two-fold season cross-fit within 2021–2022
  (fit on one season's V1 residuals, predict the other). No validation numbers had been
  seen when amended; the build script had crashed on the NaN target before fitting.
- **Baselines.** Market-only, frozen V1, candidate. No ATS tuning, no threshold tuning.

## Validation results (2021–2022, n=569)

| Model | MAE | RMSE | Calib | 2021 MAE | 2022 MAE |
|---|---|---|---|---|---|
| Market-only | 9.727 | 12.562 | 0.939 | 10.667 | 8.783 |
| Frozen V1 | 10.042 | 12.937 | 0.941 | 11.082 | 8.999 |
| Candidate | 10.077 | 12.975 | 0.835 | 11.079 | 9.071 |

The candidate is **worse** than frozen V1 (−0.035 MAE) and far from the market (+0.350).

## Error correlation

- market–V1: 0.967
- market–candidate: 0.954
- **V1–candidate: 0.985** — the candidate reproduces V1's mistakes almost exactly.

## Coefficient stability (folds)

Largest-magnitude ridge coefficients flip sign across folds
(e.g. SKILL_Out −1.37 trained-on-2021 vs +5.47 trained-on-2022; DB_Out +1.17 vs −1.30;
OL_Doubtful +10.44 driven by a handful of rare events). The layer fit noise on
~285 games per fold and added it to V1 out-of-sample.

## Gate decision

| Criterion | Result |
|---|---|
| A. Materially beat frozen V1 (≥0.10 MAE) | **FAIL** (10.077 vs 10.042 — worse) |
| B. Beat market-only by ≥0.15 MAE | **FAIL** (loses by 0.350) |
| C. Holds in 2021 AND 2022 | **FAIL** (worse in both) |
| D. Calibration slope in [0.8, 1.2] | pass (0.835) |
| E. V1–candidate error correlation < 0.95 | **FAIL** (0.985) |

Diagnostics were descriptive only (candidate marginally better than V1 solely in the
division bucket, 10.425 vs 10.663 — noise-scale, not acted on).

## Three-concept separation

1. **Prediction accuracy.** Candidate MAE 10.077 vs V1 10.042 vs market 9.727 — no improvement.
2. **Market-residual accuracy.** Not the target of this experiment; the injury layer was
   trained on V1 residuals, not market residuals.
3. **Tradable-signal evidence.** None. Nothing here is an edge, +EV, lock, or betting
   signal. Historical lines remain the unverified single-snapshot benchmark (Exp 004);
   2026 live CLV is kept fully separate.

## Verdict

A materially different, verified-pregame, timestamped information category — who is
actually playing — does not change V1's predictions in any useful way. The injury layer
learned noise (unstable cross-fold coefficients, several sign flips) and the candidate
is a 0.985-correlation twin of V1 that scores slightly worse. Four experiments
(residual modeling, opponent-adjusted EPA, dynamic team strength, player availability)
have now failed to dent the market–V1 gap without the vault ever being touched.

## Final gate decision

GATE FAILED — vault remains untouched
