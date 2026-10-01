# Props Market Expansion — Shared Protocol

**Status: FROZEN — APPROVED by Cale 2026-10-01 12:25 CDT. Frozen exactly as drafted: nothing added, nothing removed after freeze. Fit once; evaluate per preregistered target and win bar. No production changes regardless of outcome.
Nothing in this package selects, fits, or evaluates a model. Each experiment
(003A–003D) freezes its own preregistration before any 2023–2024 computation
for that experiment.**

Branch: NFL player-stat projection (the engine underneath player props).
Research only. Separate from the spread model (V1), Experiment 006, the PFT
corpus, and the power-ranking work. This package extends the 001/002 research
line to four new offensive markets authorized by Cale 2026-10-01.

## 0. What this package is and is not

- These four markets are **worth building and evaluating given our actual
  data/market constraints**. Selection is NOT a claim that any of them is
  likely to have an edge. That is exactly what the experiments test.
- Defensive props are OUT OF SCOPE: the 2026-10-01 Bovada coupon audit found
  zero defensive prop lines — a modeling exercise without a market is not a
  market-edge experiment.
- Each experiment (003A–003D) **passes or fails independently**. There is no
  pooled "Props 003" verdict. A receptions win with an anytime-TD null is
  reported exactly that way.

## 1. Research philosophy (from 001/002, binding)

- Frozen protocols before any locked-test computation, per experiment.
- Train 2018–2020 (all fitting) / Dev 2021–2022 (the ONLY selection ground;
  these preregs use fixed ladders — see §6 — so dev serves for
  hyperparameter procedure checks and diagnostics, not family selection) /
  Locked test 2023–2024 (evaluated ONCE per experiment, after freezing).
- 2025: reference/robustness only, same frozen models, non-binding.
  2026: production monitoring only. Never tuned or selected on.
- The 2023–2024 window was 001/002's locked test **for their candidates**.
  It remains valid for THESE NEW targets because each protocol — target,
  features, ladder, bar, decision rules — is frozen BEFORE any 2023–2024
  computation for that experiment (002 §0 precedent).
- Honest nulls are successful experiments. Do not manufacture an edge.
  Integrity above all.

## 2. As-of discipline (binding, all experiments)

- Prediction timestamp: **Friday 18:00 America/Chicago** of game week
  (same as 001/002 and production).
- Every feature computed from information available **at or before** that
  timestamp. Trailing features use games strictly before (season, week).
- Games kicking off at/before the timestamp are excluded.
- **NGS trailing-use only.** NGS weekly releases are post-game; only
  strictly-prior-week trailing values are timestamp-safe (002 precedent for
  `rq_ngs_separation`). The latest NGS value is NEVER a proxy for
  cutoff-time knowledge.
- **Injury reports:** as-of state = latest row per player with
  `date_modified <= Friday 18:00 CT` (002 Family L precedent). Measures
  *feed-available* injury information, not perfect market knowledge.
- **Market lines (spread/total/implied) are EXCLUDED from all new
  features.** Closing lines are unavailable at the Friday 18:00 CT cutoff,
  and no timestamped historical Friday lines exist (Experiment 006 backfill
  found zero A-class Friday lines). Pre-week ELO/EPA ratings are the
  keyless, timestamp-safe proxy for expected game script. This extends
  002 §5-D1's leakage rule to the new markets.
- **As-of reconstruction rule:** where a source updates intraday, the
  feature must reflect what was knowable at the cutoff — explicit timestamp
  filters or trailing completed-game values only.

## 3. Baselines (M0) — frozen per experiment

Each experiment defines M0 as the **trailing-history baseline**: trailing
EWMA (half-life 3, max 16 games, most-recent-first, strictly prior weeks)
of the target itself, computed on role-eligible player-games. NaN→0 for
players with no history; `trail_games` preserved as a weight input.
For 003D (binary), M0 is the trailing EWMA of the binary outcome
(equivalently, a shrinkage-toward-position-base-rate estimator — the exact
shrinkage form is frozen in 003D's prereg).

M0 is deliberately naive: it is "what history alone says." Every challenger
rung must beat it to claim that its information has incremental value.

## 4. Model ladder convention (fixed — no family selection)

The 002 overfitting lesson is binding: **no candidate-selection across
model families inside a prereg.** Each experiment uses a FIXED ladder:

| Rung | Definition |
|---|---|
| M0 | Trailing-history baseline (§3), frozen |
| M1 | Structural/process model for the target (the experiment's hypothesis) |
| M2 | M1 + NGS tracking family (named candidate family, tested not assumed) |
| M3 | M1 + team/matchup/game-context families |

Each rung is evaluated independently against the win bar. No M11-style
union, no dev-gated mega-model. If M2 fails and M1 passes, the verdict is
"M1 passes; NGS adds nothing here" — reported narrowly.

Hyperparameter procedure follows 002 §7 (Ridge alpha grid {0.1,1,10,100}
re-selected on dev per rung; GBM 8-combo grid re-selected on dev per rung;
quantile hyperparams fixed a priori). Seeds fixed (1337). The procedure is
frozen; its outcomes may differ per rung.

## 5. Metrics and win bars

**003A–003C (count targets):** primary = walk-forward MAE of point
projections vs actuals on evaluated rows (eligible_hist=1 & played_role=1,
per-experiment role thresholds). Also RMSE, bias, MAE by season. Paired
bootstrap (2000 resamples, seed 1337) CIs for M0-vs-challenger differences,
pooled test.

Win bar (all must hold — the single-market analogue of 002 §9):
1. Pooled 2023–2024: **≥5% relative MAE reduction** vs M0;
2. **≥2% relative reduction in 2023 AND in 2024 individually**;
3. **95% paired bootstrap CI** of the MAE difference excludes zero.

**003D (binary):** primary = **Brier score**; secondary = log loss,
calibration (reliability by predicted-probability bucket), ROC-AUC / PR-AUC
as diagnostics, actual event rate. Win bar (all must hold):
1. Pooled 2023–2024: **≥5% relative Brier-score reduction** vs M0;
2. **≥2% relative Brier reduction in 2023 AND in 2024 individually**;
3. **Calibration:** no predicted-probability bucket (n≥100) deviates more
   than 0.06 absolute from the diagonal; calibration slope within
   [0.85, 1.15];
4. 95% paired bootstrap CI of the Brier difference excludes zero.

**"Likely to score" is NOT a betting recommendation.** 003D produces
probabilities, not picks. No wagering implication may be drawn without
validated calibration AND a prospective market comparison (§7).

**Verdict taxonomy (per experiment):** `MATERIAL WIN` (bar cleared →
production recommendation package per 002 §14, then STOP for authorization) /
`NULL` (no production change; directional hypotheses reported narrowly) /
`PARTIAL/SIGNAL` (significant but sub-bar → reported narrowly, no
production change).

## 6. Sample requirements (per the audit's minimum-sample rule)

- Count targets: pooled n ≥ receptions 2,500 / rush attempts 1,000 /
  pass attempts 700 (002 precedent). All clear on 2023–2024 alone.
- Binary (anytime TD): pooled ≥3,000 player-games AND ≥500 TD events
  (have 6,235 / 1,830 — clears comfortably).
- Per-season slices < 150 player-games are reported as underpowered, not
  as wins or nulls.

## 7. Paper-tracking stream (prospective market dataset)

The audit's binding constraint: **no historical prop lines exist keyless.**
We do not pretend to backtest betting edge. Instead:

1. Build the four experimental projection engines (research-only).
2. **Freeze predictions before lines/outcomes** — same Friday 18:00 CT
   discipline; predictions timestamped at generation.
3. Continue capturing timestamped Bovada lines via
   `scripts/30_pull_prop_lines.py`, **extended to the new markets**
   (currently parses only the three yardage markets). Each capture records
   `{player, market, line, source, captured_at}`.
4. Track projection-vs-line-vs-outcome prospectively through 2026,
   accumulating an out-of-sample market dataset.
5. Coverage note: rush-attempt lines are currently thin (2/slate) and
   anytime-TD coverage varies — the stream records what exists; sparse
   markets accumulate slowly. That is a fact about the market, not a
   modeling failure.

Once enough live observations accumulate, model-vs-market can be evaluated
directly. Until then: **no betting-edge claims from projection accuracy
alone.**

## 8. Production gate

**No production changes until an individual experiment clears its
preregistered bar.** Even on a win: produce (a) research verdict,
(b) proposed production architecture, (c) exact changed features,
(d) data dependencies, (e) freshness requirements, (f) failure behavior,
(g) rollback plan — then STOP and wait for Cale's explicit authorization
(002 §14 precedent).

## 9. Required outputs (per experiment)

1. `PREREGISTRATION.md` (frozen before any locked-test computation)
2. Feature availability/leakage audit (`feature_audit.csv` + notes)
3. Dev diagnostics table
4. Locked-test results (single evaluation)
5. Paired bootstrap results (003A–C) / calibration analysis (003D)
6. Final research verdict (`RESULTS.md`)
7. Reproducibility manifest
