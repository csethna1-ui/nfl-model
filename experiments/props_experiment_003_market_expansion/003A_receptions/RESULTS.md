# RESULTS — Props Experiment 003A: Receptions

**Verdict: MATERIAL WIN** — all three challenger rungs (M1, M2, M3) clear the
preregistered win bar on the single locked-test evaluation (2023–2024).
M2 (process model + NGS tracking family) is the best rung at **+19.5%**
pooled relative MAE reduction vs the frozen M0 baseline.

Per the shared protocol §5 verdict taxonomy, a cleared bar means a
production recommendation package (below), then STOP for Cale's explicit
authorization. **No production changes were made.**

## 1. Locked-test results (single evaluation, 2023–2024)

Population: receiving market, `eligible_hist=1` & `played_role=1`,
`trail_targets_ewma > 0` (100% of the eligible population), pbp actual
merged. n = **3,625** player-games (2023: 1,846; 2024: 1,779) — clears the
≥2,500 pooled minimum; per-season slices (≥150) are powered.

| Rung | Pooled MAE | rel Δ vs M0 | 2023 MAE (rel Δ) | 2024 MAE (rel Δ) | 95% paired bootstrap CI of (M0−rung) | RMSE | Bias |
|---|---|---|---|---|---|---|---|
| M0 (trailing receptions EWMA) | 1.6767 | — | 1.6447 | 1.7099 | — | 2.1962 | −0.498 |
| M1 (process model) | 1.5894 | **+5.20%** ✓ | 1.5741 (+4.29%) ✓ | 1.6053 (+6.12%) ✓ | [+0.058, +0.117] ✓ | 2.0848 | −0.035 |
| M2 (M1 + NGS family) | 1.3496 | **+19.51%** ✓ | 1.3346 (+18.86%) ✓ | 1.3653 (+20.15%) ✓ | [+0.291, +0.364] ✓ | 1.8109 | +0.021 |
| M3 (M1 + context families) | 1.5902 | **+5.16%** ✓ | 1.5688 (+4.62%) ✓ | 1.6124 (+5.70%) ✓ | [+0.059, +0.113] ✓ | 2.0893 | −0.084 |

Win bar (all required): ≥5% pooled ✓ (M1 5.20%, M2 19.51%, M3 5.16%);
≥2% in 2023 AND 2024 individually ✓ for all three rungs;
bootstrap CI excludes zero ✓ (2000 paired resamples, seed 1337).

Per-component (test) point MAE:

| Rung | A (2-stage Ridge) | B (GBM direct) | C (quantile median) | D = mean(A,B,C) |
|---|---|---|---|---|
| M1 | 1.6013 | 1.6082 | 1.6019 | 1.5894 |
| M2 | 1.3698 | 1.3659 | 1.3540 | 1.3496 |
| M3 | 1.6044 | 1.6107 | 1.6007 | 1.5902 |

Quantile coverage (p25–p75) on test: M1 0.459, M2 0.526, M3 0.468
(diagnostic only; nominal 0.50).

Narrow reading (per the fixed-ladder rule):
- **M1 passes**: the process decomposition (expected targets × catch
  probability) beats naive trailing history for receptions.
- **M2 passes by a wide margin; NGS adds large incremental value here**:
  M2 − M1 = −0.2398 MAE (≈15% further reduction). The NGS tracking family
  (trailing separation, cushion, intended air yards, intended-air-yard
  share, expected YAC, YAC over expected) carries information about the
  routes→targets→receptions mechanism that trailing box-score history
  does not.
- **M3 passes, but team/matchup/game-context adds ~nothing beyond M1**:
  M3 − M1 = −0.0008 MAE. Reported narrowly: context families B/C/D1/D2/E/L
  do not add incremental value for the receptions target once the process
  model is in place.

## 2. Dev diagnostics (train 2018–2020, n=4,975; dev 2021–2022, n=3,689)

Dev was hyperparameter-selection and diagnostics ground only (fixed ladder,
no family selection). Test slice was never loaded during dev.

| Rung | Dev D MAE | Dev M0 MAE | Ridge α (selected) | GBM params (selected) |
|---|---|---|---|---|
| M1 | 1.5606 | 1.6801 | 100.0 | lr=0.05, depth=3, iter=200 |
| M2 | 1.3525 | 1.6801 | 100.0 | lr=0.05, depth=3, iter=200 |
| M3 | 1.5574 | 1.6801 | 100.0 | lr=0.05, depth=3, iter=200 |

Dev selected the same hyperparameters for all rungs; test used them frozen.
Test MAEs landed within 0.04 of dev for every rung (no dev-overfitting
signature).

## 3. As-of / leakage audit

- All features verified timestamp-safe at the Friday 18:00 CT cutoff:
  trailing EWMAs use strictly prior (season, week); NGS uses strictly prior
  NGS release weeks (trailing only, never the current week); injury
  features use `date_modified <= cutoff`; ratings are strictly pre-week;
  market spread/total/implied scoring excluded everywhere (ELO diff is
  the proxy).
- NGS as-of spot audit: 5/5 sampled player-weeks recomputed by hand match
  the stored trailing values to 1e-9, using only strictly prior NGS weeks.
- NGS trailing coverage on the train+dev eval population: 63%; missing →
  0 per the frozen NaN convention (same as 002).
- pbp actuals (targets = `receiver_player_name` count, receptions =
  `complete_pass` sum) merged at 100% on the eval population; 405
  non-merged rows are all outside the eval population (played_role=0),
  zero sample impact.

## 4. What was claimed and what was not

**Claimed:** the receptions process model (M1), and especially the
process model + trailing NGS tracking data (M2), projects player-game
receptions more accurately than trailing history alone, on a locked
2023–2024 test the experiment never touched during design. The effect is
large (M2: −19.5% MAE), consistent across seasons (2023 −18.9%, 2024
−20.2%), consistent across model components (A/B/C all show the M2 jump),
and the bootstrap CI is far from zero.

**NOT claimed:**
- This establishes **projection quality only**. It cannot establish a
  betting edge: no timestamped historical receptions prop lines exist
  keyless, so model-vs-market was not and cannot be backtested. The
  prospective paper-tracking stream (shared protocol §7) is the vehicle
  for any future market comparison.
- No claim that routes were tested directly — route participation is
  unavailable keyless; snap share + NGS intended-air-yard share remain
  the frozen documented proxies.
- A win here does not touch the spread model (V1), Experiment 006, the
  PFT corpus, or any production system. No production changes were made.
- M3's pass does not mean "context matters" — the ladder comparison
  shows context adds nothing beyond M1 for this target.

## 5. Production recommendation package (per 002 §14) — STOPS HERE

Recommended rung: **M2** (process model + NGS family), D = mean(A,B,C).

- (a) Research verdict: MATERIAL WIN as above.
- (b) Proposed production architecture: reuse the 16_prod_player_projection
  pipeline; add a receptions target head with the M2 two-stage Ridge +
  direct GBM + quantile GBM, features frozen per `feature_audit.csv`;
  Friday 18:00 CT prediction timestamp unchanged.
- (c) Exact changed features: 8 stage-1 + 9 stage-2 process features,
  plus 6 trailing NGS receiving fields (all in `data/feature_audit.csv`).
- (d) Data dependencies: nflverse weekly player_stats, pbp, snap_counts
  (all local, keyless), `import_ngs_data('receiving')` weekly (keyless).
- (e) Freshness requirements: NGS trailing must use only completed-week
  releases; the Friday job must not ingest the current week's NGS file.
- (f) Failure behavior: if NGS is unavailable for a player-week, features
  fall back to 0 (the trained convention); if the whole NGS feed fails,
  fall back to the M1 rung (still a bar-clearing model).
- (g) Rollback plan: keep the M0 trailing baseline wired as the fallback
  projection; one-flag revert.

**No authorization is assumed. Nothing was changed in production.**

## 6. Reproducibility manifest

- Preregistration: `PREREGISTRATION.md` (FROZEN, approved 2026-10-01 12:25 CDT)
- Shared protocol: `../MARKET_EXPANSION_PROTOCOL.md` (FROZEN)
- Test gate: `PROTOCOL_FROZEN_003A`
- Feature build (data prep only): `scripts/build_003A_features.py`
- Experiment runner: `scripts/run_003A.py` (`--phase dev`, then `--phase test`)
- Feature table: `data/features_003A_2018_2024.parquet` (21,838 receiving rows)
- Feature audit: `data/feature_audit.csv` (45 rows)
- Dev outputs: `data/experiment_003A_dev.json`
- Test outputs: `data/experiment_003A_test.json`,
  `data/experiment_003A_test_predictions.parquet` (3,625 × 4 rungs)
- Seeds: 1337 (bootstrap); GBM random_state=11; quantile random_state=7
- Fit discipline: fit once. Train 2018–2020 / dev 2021–2022 / locked test
  2023–2024, test evaluated exactly once. No retries.

## 7. Protocol deviations and judgment calls (all documented, none material)

1. **M1 stage-2 "separation-proxy"**: the prereg names "ADOT/separation-proxy/
   QB context" without enumerating the proxy. Implemented as the trailing
   pbp catch-point-quality features (`rq_yac_per_rec`, `rq_drop_pct`,
   `rq_broken_tackles`) + `rq_adot` + the 002 Family I QB context; NGS
   separation was kept M2-only per the prereg's family assignment.
2. **Name-collision trailing convention**: first-initial.last collisions
   (e.g. A.Brown = Antonio + A.J. Brown, 460 rows) mix in the
   player_name-grouped trailing EWMA exactly as they do in 001's
   `trail_targets_ewma` (002's `trail_frame_player` convention). Documented,
   not changed — fixing it would deviate from the frozen 001/002
   comparability the prereg assumes. Per-row pbp actuals merge on
   ukey|team and are unaffected.
3. **M2/M3 stage assignment**: NGS and context families added to all three
   model slots (stage 1, stage 2, B/C pool) with dedupe — the literal
   "M1 + family" reading of the prereg's fixed ladder.
4. No data problems forced any spec change. No retries were performed.
