# V1 Architecture Audit — Report

**Scope:** read-only analysis of existing V1 outputs and code. Validation
2021–2022 only (n=569). No model fitting, no tuning, no vault, no 2026 data,
no ATS analysis, no new candidate. This is an audit, not a predictive
experiment. Experiment 008 is not recommended herein.

Companion files: `architecture_map.md` (pipeline documentation),
`component_correlations.json` (Q1/Q5 numbers),
`error_diagnostics.json` (Q2/Q6 numbers), `training_window_audit.md` (Q4).

---

## Q1/Q5 — Component redundancy and information content

**The three components are three views of one latent team-strength axis.**

| Pair | Prediction corr | Signed-error corr |
|---|---|---|
| ELO – EPA-linear | 0.763 | 0.949 |
| ELO – GBM | 0.832 | 0.955 |
| EPA-linear – GBM | 0.821 | 0.952 |

Component validation MAE: ELO 10.203, EPA-linear 10.146, GBM 10.463,
ensemble 10.043. The ensemble beats the best single component by only
**0.104 MAE** — a variance-averaging gain, not an information-combination
gain.

Feature-level: `elo_diff` correlates 0.67 with `off_epa_diff`; `off_epa_diff`
correlates 0.90 with `off_pass_diff` and 0.84 with `sr_off_diff`;
`def_epa_diff` correlates 0.89 with `def_pass_diff`. The GBM's feature set is
a strict superset of the two linear models' inputs.

**Ensemble-weight verdict:** the saved (0.4, 0.5, 0.1) weights are exactly
the argmax of the 0.1-grid search on validation MAE — defensible as "the grid
winner," but the surface is flat: 24 of 66 grid points sit within 0.05 MAE of
the best, and ELO+EPA *without* the GBM (0.5/0.5/0.0) scores 10.045 vs the
saved 10.043. The 0.1 GBM weight is nearly irrelevant. The weights are not
wrong; they are **nearly arbitrary within a flat neighborhood** — no strong
claim about the "right" blend can be supported.

**Most important structural fact:** the GBM — the only nonlinear component,
with access to every feature the linears see plus rest/division/week —
performs **worst alone** (10.463 vs 10.146 for the EPA linear). The mapping
from team-strength differentials to expected margin is already saturated by
linear structure. There is no unmodeled nonlinearity in the current feature
space for a more flexible estimator to extract.

## Q2 — Error structure

- Signed error: mean −1.25, std 12.88, skew −0.12. Median |error| 7.83,
  90th percentile 21.90.
- Calibration: `actual ≈ 1.29 + 0.94 × predicted`. Mild margin overstatement
  at the extremes, plus a **+1.3 point home-team drift** at neutral
  predictions (actual exceeds predicted for home teams on average).
- Bias by predicted decile: the most extreme predicted margins (|pred| ≈ 9–10)
  carry the largest MAE (12.3–12.7); mid-range predictions are best calibrated.
- Bias by actual decile: entirely the expected regression-to-the-mean fan —
  extreme actual margins are unpredictable by any pregame model.
- **Residual vs. every V1 feature: |r| < 0.08** (max: `week` −0.078,
  `div_game` −0.055, `def_rush_diff` −0.054; rest_diff 0.002). The residual is
  empirically orthogonal to the entire V1 information space.
- Residual lag-1 autocorrelation within team-season: −0.04 (n=1074 pairs) —
  no persistence. Errors do not carry over week to week.

## Q3 — Target/architecture assessment

V1 maps team ratings → predicted margin as a fixed linear blend of three
estimators of **E[home margin | pregame team-strength differentials]**, a
single scalar point estimate. Structural properties relevant to the
error-invariance pattern:

1. **One residual, not three.** Because the components' errors correlate at
   ~0.95, the ensemble has essentially one shared residual. Experiments that
   "correct V1's residual" are all correcting the same object.
2. **No variance model.** Every game gets a point estimate; the ~12.9-point
   residual std is treated as homogeneous noise. The architecture cannot
   distinguish high-variance from low-variance matchups and gives a
   residual-correction experiment no uncertainty to work with.
3. **Scalar target conflates mechanism.** Offense, defense, pace, and
   variance are collapsed into one number before any correction is applied.
   A correction feature must move the *shared scalar residual*, which —
   per Q2 — is orthogonal to the whole team-strength feature space.
4. **Home field is intercept-only** (~0.63–0.65 pts per linear component),
   with no interaction between venue and team characteristics.

No alternative architecture is proposed or fit in this audit (per scope).

## Q6 — Model-vs-market relationship (historical data only)

- V1 prediction vs market spread: r = 0.859.
- **V1 signed error vs market signed error: r = 0.967.** V1 and the market
  make the same mistakes, in the same direction, on the same games.
  Absolute-error correlation: 0.925.
- Market MAE 9.727 vs V1 10.043. Mean |V1 − market| disagreement: 2.70 pts
  (p90: 5.54).
- Where V1 and the market disagree most (top disagreement quartile,
  mean 5.6 pts), the **market** is better: V1 MAE 9.74 vs market 8.85.
  Disagreement does not favor V1.
- V1 errors concentrate at large predicted margins (top magnitude quartile:
  MAE 11.73 vs 8.97–10.11 elsewhere).

The 0.967 signed-error correlation is the single most explanatory number in
this audit (see §(A) below). Caveat: the historical `spread_line` is an
unverified single nflverse snapshot per game (per Experiment 004), so the
market side of these comparisons carries timestamp uncertainty.

## Q4 — Training stability (summary)

Documented fully in `training_window_audit.md`. One genuine ambiguity:
"frozen V1" is not uniformly frozen — the linear coefficients (2018–2020)
and ensemble weights (2021–2022 grid) are frozen, but the **GBM is refit
walk-forward on an expanding window that includes prior validation games**
(e.g., 2022 predictions use a GBM trained on 2018–2021). No future leakage
(each prediction uses only past weeks), and all experiments used the same
fixed prediction artifact, so no experiment result is affected. Reproducers
must replicate the walk-forward GBM, not just the linear coefficients.

---

## (A) What appears structurally sound

1. **No leakage.** Weekly batching in both ratings loops, expanding-window
   GBM fits, frozen linear/ensemble parameters loaded from disk in
   production. The walk-forward discipline is real.
2. **The ensemble weights are the honest grid winner**, and the flat surface
   around them means the exact blend barely matters — the model is not
   perched on a tuned knife-edge.
3. **The linear core is the right complexity for the feature space.** The
   GBM's failure to beat the EPA linear (10.463 vs 10.146) with a superset
   of features is evidence that E[margin | differentials] has no exploitable
   nonlinearity the current features can express. The model is not
   underfit in any way a more flexible estimator could fix.
4. **The residual is clean:** orthogonal to all V1 features, no weekly
   autocorrelation, symmetric. There is no leftover linear structure being
   ignored.

## (B) What is uncertain

1. **The +1.3 point home drift** (calibration intercept 1.29; mean signed
   error −1.25). Home teams outperformed the ensemble by ~1.3 points on
   2021–2022. Structural undercount of home field, or two-season sample
   noise? Cannot be distinguished without the vault, which stays locked.
2. **Whether the flat weight surface hides a better blend off-grid.**
   A finer search might find (0.35, 0.55, 0.10)-style optima, but the
   neighborhood analysis (±0.05 MAE across 24 grid points) says any such
   gain would be small and likely noise.
3. **The historical market benchmark's timestamp** (Experiment 004's finding)
   limits how strongly the 0.967 error-correlation can be interpreted as
   "V1 ≈ market information set" vs. "both ≈ the predictable component."
4. **Production vs research V1 drift:** production refits the GBM on
   2018–2026 while research V1 is the fixed backtest artifact. The
   difference is small by construction but unmeasured.

## (C) Hypotheses worth researching next

Ranked by how directly they follow from this audit's evidence. None is
authorized as an experiment; all would need preregistration.

1. **The residual is mostly irreducible game variance, not missing
   information.** V1's signed errors correlate 0.967 with the market's;
   the residual is orthogonal to the entire team-strength feature space and
   has no weekly persistence. The leading hypothesis for the 0.985–0.995
   error-invariance pattern is that six experiments have been trying to
   predict *noise that the market also cannot predict* — the common
   ~12.9-point std around any reasonable expectation. Experiment 006's
   Tuesday→Friday stream is the right arbiter: if Friday information moves
   predictions but not accuracy, the boundary is variance, not information.
2. **Genuinely orthogonal information is the only kind that can move the
   residual.** Any feature that is a function of the current team-strength
   space will project ~zero onto a residual that is already orthogonal to
   that space. This is a mathematical restatement of why representations of
   efficiency keep failing — and it sharpens the Feature Discovery Audit's
   conclusion: only information *uncorrelated with ELO/EPA* (not merely
   "different") is worth testing.
3. **The scalar point-estimate target may be the binding constraint.**
   V1 collapses offense, defense, pace, and variance into one number with
   no uncertainty representation. If the predictable component of margin
   lives in the *structure* of scoring (e.g., separate offensive/defensive
   scoring processes, possession counts, variance regimes), no correction
   applied to the collapsed scalar can recover it. This is the deferred
   component-based-target hypothesis, still unauthenticated and not
   authorized here.
4. **Disagreement-with-market is not a V1 edge signal.** Where V1 disagrees
   most with the market, the market wins (8.85 vs 9.74 MAE). Any future
   "V1 knows something the market doesn't" framing must contend with this.
5. **Home-field accounting deserves a look** once the vault may be touched:
   the +1.3 drift is the largest systematic bias found, and it is a
   property of the architecture (intercept-only HFA), not of any feature.

**Final note for the research program:** this audit strengthens the
interpretation that Experiments 001–007 were well-designed tests of a
hypothesis that is probably false — that V1's residual contains
recoverable team-strength information. The vault remains the decisive
asset; nothing in this audit warrants touching it.
