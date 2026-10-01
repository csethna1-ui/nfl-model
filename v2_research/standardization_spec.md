# BLOCKER 5 — Matchup Interaction Feature Standardization Spec

**Status:** spec only. Authorizes nothing beyond documenting the transform.
**Date:** 2026-09-29.
**Scope:** the 32 `matchup` interaction features in `feature_inventory.json`
(derived in `scripts/35_v2_assemble.py`, raw scale in
`data/v2/games_v2_features.parquet`).
**Hard rule carried forward:** scaling parameters must be estimated ONLY from
information available at the prediction date. Any choice below marked
`(MODELING DECISION)` is enumerated here but NOT chosen — choosing belongs to
a future modeling authorization (V2-A..E), which is not granted.

## Raw construction (reference; read-only, from `scripts/35_v2_assemble.py`)

For prediction week W, each component (e.g. `expl_pass_rate`,
`epa_per_drive_allowed`) is the walk-forward expanding mean over that team's
games strictly before W (min 4 prior games, else NaN; no offseason reset).
The 32 matchup features are pure functions of those components:

- product: `mx_{off}_x_{deff}_homeoff = home_off × away_def`
  (awayoff side: `away_off × home_def`)
- cross-differential (unit-comparable pairs only):
  `mx_{off}_v_{deff}_homeoff = home_off − away_def`
  (awayoff side: `away_off − home_def`)

Component pairs: `expl_pass_rate×expl_pass_allowed`, `expl_rush_rate×expl_rush_allowed`,
`epa_per_drive×epa_per_drive_allowed`, `points_per_drive×points_per_drive_allowed`,
`adot×def_adot_allowed`, `rz_trip_rate×rz_trip_allowed`, `start_y100×start_y100_allowed`
(product + differential), plus `pressure_allowed_pct×def_pressures` and
`sack_rate×def_sacks` (product only — units not comparable). Each × home/away offense
side = 32.

---

## 1. The leakage class: full-sample scaling

**Claim.** Estimating scaling statistics (mean, std, min/max, empirical
quantiles — any of them) over the full dataset leaks future information into
every past observation's scaled value.

**Why.** A standardized value `z = (x − μ)/σ` is a function of the scaling
statistics. If μ and σ are computed over games that include future games
(relative to the prediction date of game g), then any future game's outcome
shifts μ and σ, which shifts z_g — a value that is supposed to represent only
information available when game g was predicted.

**Concrete numeric example.** Take `mx_expl_pass_rate_x_expl_pass_allowed`
(raw = product of two walk-forward rate means, bounded in [0,1]).

Walk-forward statistics (only games completed before the week-5 prediction):
10 prior league games, μ_H = 0.050, σ_H = 0.010. The week-5 game has raw
x_g = 0.040.

> z_walkforward = (0.040 − 0.050) / 0.010 = **−1.00**

Now suppose the analyst z-scores across the FULL 2018–2022 dataset, and a
future week-17 game has raw x_F = 0.30 (an explosive-shootout outlier). With
n = 11:

- new μ = (10·0.050 + 0.30) / 11 = 0.80/11 = **0.07273**
- old Σx² = 10·(0.010² + 0.050²) = 0.026; new Σx² = 0.026 + 0.30² = 0.116
- new σ = √(0.116/11 − 0.07273²) = √0.00526 = **0.07253**

> z_fullsample = (0.040 − 0.07273) / 0.07253 = **−0.45**

The *same* week-5 game — same raw value, same teams, same history — moves from
z = −1.00 to z = −0.45, purely because a game that had not happened yet entered
the scaling statistics. The future game shifted the mean up *and* inflated the
std; every past z-value is doubly moved. This is leakage, and it flows
downstream: any coefficient, threshold, or split learned on z_fullsample has
seen the future through the scaling.

**The class is broader than z-scoring.** The following are all full-sample
leakage when statistics are estimated over games at or after the prediction
date:

1. Full-sample z-score / min-max / robust (median/IQR) scaling.
2. Full-sample percentile / rank transforms.
3. Full-sample winsorization (clip bounds from full-sample quantiles).
4. Scaling the *components* full-sample and *then* forming the product — the
   leakage enters through the components, not the interaction operator.
5. Imputing NaN with a league mean estimated over the full sample.
6. Any "normalize to [0,1] using observed min/max" — min/max are full-sample
   statistics and future extremes reset them.

**Correlated-but-distinct non-issue:** estimating μ/σ over the expanding
pre-prediction distribution is NOT leakage — it is the prescribed procedure
(§2). The dividing line is the game-date cutoff, not the transform family.

---

## 2. Allowed transform family

### 2a. General form

For feature f, game g in prediction week W, let

```
x_{g,W,f}      = raw interaction value (from §1 reference construction)
S(W)           = scaling set: league games with kickoff strictly before
                 prediction_date(W)          [default; see §2b]
μ_{S(W),f}     = location statistic over { x_{h,f} : h ∈ S(W) }
σ_{S(W),f}     = scale statistic  over { x_{h,f} : h ∈ S(W) }
z_{g,W,f}      = (x_{g,W,f} − μ_{S(W),f}) / σ_{S(W),f}
```

`prediction_date(W)` is the prediction snapshot timestamp (the Tuesday batch
discipline from Experiment 006 / `scripts/22`): games completed before that
timestamp are in, everything else is out. "Week < W" is a valid coarse proxy
because all week-(<W) games have kicked off before the Tuesday batch of week W.

**Scaling set default: league-wide expanding.** Parameters are estimated over
*all* past league games in S(W), not per-team. Per-team scaling sets are
rejected as default: each team plays ~16 games/season, so per-team σ estimates
are unstable and themselves noisy functions of a few outcomes. (A team-specific
scaling set with shrinkage toward the league estimate is listed in §2d as an
un-chosen alternative.)

### 2b. Scaling window: expanding vs trailing

**Default: expanding.** S(W) = all league games with kickoff < prediction_date(W).
Justification:

1. The components being scaled are themselves expanding means
   (`scripts/35`, min 4 games, no offseason reset); the scaling window inherits
   that philosophy — one stable, growing reference distribution.
2. Interaction features are composites of two already-thin team histories;
   a trailing window compounds small-sample noise (trailing-K of a product of
   two expanding means discards most of the information the components kept).
3. The NFL information environment changes gradually; the recency question is
   a modeling-stage hyperparameter, not a scaling-stage necessity. Estimating
   the *reference distribution* expanding does not prevent the *model* from
   down-weighting old games later.

**Allowed alternative (MODELING DECISION, not chosen): trailing-K.**
S_K(W) = the K most recent league games with kickoff < prediction_date(W),
i.e. an expanding window truncated to the last K games. If authorized, K must
be preregistered from {8, 16, 32} with justification:

- K=8: ~half a season; captures within-season regime (injuries, coordinator
  changes) but σ estimates rest on 8 points — unstable for heavy-tailed
  features (Group B below).
- K=16: ~one full season; balances regime relevance and stability; the
  recommended candidate *if* a trailing window is ever authorized.
- K=32: ~two seasons; nearly expanding in the 2018–2022 window, included only
  to test sensitivity to the window choice.

The trailing window must be defined by *count of games*, not calendar span
(offseason gaps would otherwise admit stale games), and the cutoff timestamp
rule is unchanged.

### 2c. Minimum history requirement (else NaN)

Two independent gates; both must pass or the scaled value is NaN:

1. **Component gate (inherited):** both components must be defined (each
   team's expanding mean over ≥ 4 prior games). If either component is NaN,
   the raw interaction is NaN and there is nothing to scale.
2. **Scaling-set gate:** |S(W)| ≥ 30 games. Rationale: σ (and IQR) estimates
   below ~30 points are dominated by sampling noise; 30 is also comfortably
   above the degenerate cases (|S|=1 → σ=0; |S|=0 → undefined). In the
   2018–2022 research window this binds only for early-2018 games
   (S(W) empty at 2018 Week 1 by construction — there is no history, and the
   spec does not invent any).

The gate value 30 is a spec parameter: a future implementation may raise it
(with justification, recorded in the audit log §5) but may not lower it
without a new authorization, and it must be fixed before any model sees
outcomes.

### 2d. Fallback when history is insufficient — OPTIONS, NOT CHOSEN

When §2c gate 2 fails (scaled value NaN), the future modeling stage may pick
**exactly one** of the following, preregistered and applied uniformly.
This spec does not choose:

- **(F1) Propagate NaN.** The model handles missing values with its own
  missing-data policy. Pro: no invented information; the missingness pattern
  itself is honest (it marks "early history"). Con: requires a model that
  tolerates NaN.
- **(F2) Zero-impute in standardized space (z = 0).** Equivalent to imputing
  the expanding league mean *as estimated on the available S(W)* — which, when
  |S(W)| < 30, is exactly the unstable estimate the gate rejected. Pro:
  simple, keeps rows. Con: silently treats "unknown" as "average" using a
  statistic the spec deemed unreliable; the imputed value is a function of a
  tiny, noisy sample.
- **(F3) Shrinkage toward zero.** z_shrunk = z_raw · n/(n+k) with the
  available n = |S(W)| and shrinkage constant k preregistered (candidate k=30,
  matching the gate). Pro: degrades gracefully — with n=0 the value is 0
  (pure prior), with n≥30 it is ~the full estimate; no hard discontinuity at
  the gate. Con: k is a hyperparameter; the "prior" (league mean of the
  feature) is itself a modeling choice.
- **(F4) Cold-start composite from component league means.** Build the raw
  interaction from league-average components (league means of each component
  over S(W), however small), then scale with whatever S(W) exists — or emit
  0 if S(W) is empty. Pro: mirrors how a production system would cold-start.
  Con: most machinery; the league-mean components on tiny samples are the
  same unstable quantities as F2.

Explicitly FORBIDDEN as fallbacks: full-sample means, any statistic computed
over games at/after the prediction date, and borrowing the *future* value of
the same fixture (e.g. filling 2018 Week 1 with that matchup's later meetings).

---

## 3. Per-feature treatment

Interaction features differ in support and tail behavior; the transform is
specified per group. In every case the walk-forward rule is identical:
location/scale (or the empirical distribution for percentiles) is estimated
over S(W) only.

### Group A — rate×rate products (bounded in [0,1])
Features (6): `mx_expl_pass_rate_x_expl_pass_allowed_{homeoff,awayoff}`,
`mx_expl_rush_rate_x_expl_rush_allowed_{homeoff,awayoff}`,
`mx_rz_trip_rate_x_rz_trip_allowed_{homeoff,awayoff}`.
Raw construction: product of two [0,1] expanding rate means → support [0,1],
right-skewed (products of small rates pile near 0).

**Transform: location-scale z-score (default).** z = (x − μ)/σ over S(W).
**Allowed alternative (MODELING DECISION): walk-forward percentile.**
p = ( #{ h ∈ S(W) : x_h ≤ x_g } ) / |S(W)|, ties counted as ≤ (upper-tail
convention, fixed). Rationale for allowing it: for bounded, skewed products,
order often carries more signal than standardized magnitude, and percentiles
are robust to the skew by construction. If used, the "parameter" stored per
(W, f) is the empirical CDF of S(W) (or equivalently the sorted array);
the audit rule §5 applies to it as a parameter object.

### Group B — EPA/points products (unbounded, signed)
Features (4): `mx_epa_per_drive_x_epa_per_drive_allowed_{homeoff,awayoff}`,
`mx_points_per_drive_x_points_per_drive_allowed_{homeoff,awayoff}`.
Raw construction: product of two expanding means. EPA/drive means are signed
(negative×negative = positive — a bad offense vs a bad defense yields a
*positive* product, same sign as good×good; the spec records this semantic
quirk and does not "fix" it — sign disambiguation is modeling-stage work).
Heavy-tailed; outliers are real games, not errors — do not winsorize at
scaling stage.

**Transform: location-scale z-score (default), with robust variant allowed.**
Default: z = (x − μ)/σ over S(W).
Allowed alternative (MODELING DECISION): robust scaling,
z_r = (x − median(S(W))) / IQR(S(W)), with IQR floored at a small epsilon to
avoid division by zero (epsilon preregistered; candidate 1e-6 in raw units).
Rationale: heavy tails make σ itself outlier-driven, so a few shootouts
rescale every other game; median/IQR is the walk-forward-safe answer to that.
Percentile transform is NOT recommended here (it discards the magnitude of
genuinely extreme matchups, which is the information), but is not forbidden —
it would be a modeling-stage choice with justification.

### Group C — mixed-scale products
Features (6):
- rate×count: `mx_pressure_allowed_pct_x_def_pressures_{homeoff,awayoff}`,
  `mx_sack_rate_x_def_sacks_{homeoff,awayoff}` — support [0, ∞), count
  component unbounded.
- yards×yards: `mx_adot_x_def_adot_allowed_{homeoff,awayoff}` — support (0, ∞).
- field-position×field-position:
  `mx_start_y100_x_start_y100_allowed_{homeoff,awayoff}` — support (0, 10000],
  effectively bounded.

**Transform: location-scale z-score (default)** for all six, over S(W).
For `start_y100` products the bounded support makes the percentile alternative
(§3 Group A convention) available as a MODELING DECISION; for the rate×count
and yards products the robust median/IQR variant (§3 Group B convention) is
available as a MODELING DECISION. No log transform at scaling stage
(a log would change the feature's meaning; allowed only as a modeling-stage
feature-engineering choice, applied before scaling, with the same S(W) rule).

### Group D — cross-differentials (native units)
Features (12): `mx_{expl_pass_rate,expl_rush_rate,epa_per_drive,
points_per_drive,adot,rz_trip_rate,start_y100}_v_{allowed}_{homeoff,awayoff}`.
Raw construction: offense expanding mean MINUS opponent defense expanding mean,
in the component's native units (rates, EPA/drive, yards, points/drive).

**Transform: location-scale z-score (default)** over S(W). Because the units
are already comparable across the pair (that is the precondition for the `_v_`
operator existing), the z-score here is a pure unit conversion.
**Allowed passthrough (MODELING DECISION): leave raw.** A model may consume
the differential in native units (e.g. "home EPA/drive exceeds away
EPA/drive-allowed by 0.35"); if so, no scaling parameters exist for that
feature and §5 records "raw passthrough" instead. Raw passthrough is NOT
allowed for Groups A–C (products have no interpretable native unit).

### Summary table

| Group | Features | Support | Default transform | Allowed alternative (modeling decision) |
|---|---|---|---|---|
| A rate×rate | 6 products | [0,1], skewed | z = (x−μ)/σ on S(W) | walk-forward percentile |
| B EPA/pts products | 4 products | (−∞,∞), heavy tails | z = (x−μ)/σ on S(W) | robust (median/IQR) |
| C mixed products | 6 products | various, [0,∞) | z = (x−μ)/σ on S(W) | percentile (start_y100) or robust (others) |
| D differentials | 12 diffs | native units | z = (x−μ)/σ on S(W) | raw passthrough |

---

## 4. Cross-season boundaries

The expanding window S(W) must decide how prior-season games enter. Three
options (MODELING DECISION — this spec does not choose; `scripts/35` uses
Option A for the components, and consistency with the components is the
tiebreaker argument for it):

- **Option A — continuous expanding, no reset.** All prior seasons' games stay
  in S(W) with equal weight. Leakage constraint satisfied trivially (every
  included game has kickoff < prediction_date(W)). Pro: matches the component
  construction; maximal stability for σ. Con: a 2018 blowout still influences
  2022 scaling statistics — stale regimes linger in the reference distribution.
- **Option B — expanding with offseason decay.** Prior-season games enter with
  weight w = λ^{seasons_ago} (or λ^{days_ago/365}); μ, σ, median, IQR, and
  percentiles become weighted statistics over S(W). Leakage constraint: the
  weights must be deterministic functions of schedule timestamps only — never
  of game outcomes, scores, or any future information. λ is a hyperparameter
  (candidate grid {0.5, 0.7, 0.9} per season) and belongs to modeling-stage
  authorization. Pro: graceful regime adaptation. Con: weighted-quantile
  machinery; another tuning surface.
- **Option C — hard season reset.** S(W) contains only current-season games
  before W. Leakage-safe. Pro: simplest regime story ("this season's
  distribution"). Con: early-season weeks have tiny S(W) — the §2c gate
  (|S(W)| ≥ 30) fails for roughly the first two weeks every season,
  forcing heavy fallback use; discards the most stable part of the
  distribution.

**Leakage constraint (non-negotiable, all options):** for every game g in
week W, every observation contributing to g's scaling parameters must satisfy
kickoff < prediction_date(W), and every weight or inclusion rule must be a
function of timestamps/schedule alone. An option that conditions inclusion on
a game's outcome, margin, or any post-kickoff quantity is forbidden.

**Consistency note:** whichever option is chosen for matchup scaling should
match the option used for any scaling of the *components* in the same model
run, or the mismatch must be documented and justified — otherwise the
interaction and its inputs are standardized against different reference
worlds.

---

## 5. "Params available at prediction date" — audit rule

A future implementation must produce, per (feature f, prediction week W), an
audit record satisfying this checklist. An independent reviewer recomputing any
row must be able to verify each item from the schedule + completed-game data
alone.

- [ ] **A1. Raw construction.** Formula recorded (product or differential,
      which side, which components) with the `scripts/35` line reference.
      Reviewer check: recompute x_{g,W,f} from the component tables.
- [ ] **A2. Scaling-set definition.** Expanding (default) or trailing-K with
      preregistered K; cross-season option (A/B/C §4) with λ if applicable.
      Reviewer check: the definition is fixed in the run config, identical for
      all W.
- [ ] **A3. Scaling-set membership.** The exact game list (or its count and
      min/max kickoff timestamps) in S(W). Reviewer check:
      max kickoff in S(W) < prediction_date(W); |S(W)| reported; no game from
      week ≥ W present.
- [ ] **A4. Parameter values.** μ and σ (or median/IQR, or the empirical CDF
      object for percentiles) stored per (f, W), with the estimator named
      (population vs sample std — population, ddof=0, is the spec default;
      the choice must be recorded and constant).
- [ ] **A5. Timestamp discipline.** prediction_date(W) recorded per W
      (the Tuesday batch timestamp); components' info cutoff identical.
      Reviewer check: recompute S(W) from the schedule using that timestamp
      and confirm A3.
- [ ] **A6. Gate outcomes.** §2c gates 1–2 pass/fail per (g, f); every NaN
      emitted with the reason (component-NaN vs scaling-set-too-small).
- [ ] **A7. Fallback record.** Which of F1–F4 (§2d) was authorized and applied
      uniformly; per-(g,f) log of fallback applications.
- [ ] **A8. No target contact.** Attestation that no margin, spread, total,
      or outcome entered any computation in A1–A7 (transform is a function of
      features and timestamps only). Reviewer check: the scaling code path
      has no access to label columns.
- [ ] **A9. Reproducibility.** Random seed fixed if any stochastic element
      exists (none in the default spec); tie-breaking convention for
      percentiles recorded; epsilon floors recorded.

**Reviewer spot-check procedure:** pick 3 games (one early-season, one
mid-season, one late-season). For each, pull the schedule, rebuild S(W) from
kickoff timestamps, recompute the parameters, and compare to the stored A4
values to machine precision. Any mismatch = failed audit.

---

## 6. Explicitly out of scope

This spec does NOT cover, and must not be read as authorizing:

1. **Fitted scaling** — parameters learned from training labels (e.g. scaling
   by class-conditional statistics). All parameters here are unsupervised
   functions of the feature distribution.
2. **Target-aware transforms** — anything using margin/spread/outcome to
   shape the transform (supervised discretization, target encoding of any
   kind).
3. **Any application to a model** — no V2-A/B/C/D/E, no Experiment 008, no
   training, no validation, no performance numbers. This document produces
   parameters' *rules*, not parameters.
4. **Choosing among the enumerated options** — trailing-K vs expanding,
   cross-season option A/B/C, fallback F1–F4, default vs alternative
   transforms per group. Listing is not choosing; each choice needs its own
   modeling authorization.
5. **Component-level scaling** — how the 112 non-matchup features are
   standardized is a separate spec (same walk-forward principles apply).
6. **The variance target** — scaling rules for a future Var(margin) target
   are not defined here.

---

## Appendix: feature → group map

| # | Feature pattern (×2 sides) | Group | Default |
|---|---|---|---|
| 1 | `expl_pass_rate × expl_pass_allowed` (x + v) | A / D | z-score |
| 2 | `expl_rush_rate × expl_rush_allowed` (x + v) | A / D | z-score |
| 3 | `epa_per_drive × epa_per_drive_allowed` (x + v) | B / D | z-score |
| 4 | `points_per_drive × points_per_drive_allowed` (x + v) | B / D | z-score |
| 5 | `adot × def_adot_allowed` (x + v) | C / D | z-score |
| 6 | `rz_trip_rate × rz_trip_allowed` (x + v) | A / D | z-score |
| 7 | `start_y100 × start_y100_allowed` (x + v) | C / D | z-score |
| 8 | `pressure_allowed_pct × def_pressures` (x only) | C | z-score |
| 9 | `sack_rate × def_sacks` (x only) | C | z-score |

All 32 features: league-wide expanding scaling set S(W) = {games with kickoff
< prediction_date(W)}, |S(W)| ≥ 30 else NaN, population std (ddof=0) default,
no full-sample statistics anywhere in the pipeline.
