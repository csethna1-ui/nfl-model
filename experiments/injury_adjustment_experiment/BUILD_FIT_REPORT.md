# Phase 2 — Build + Fit + Dev-Selection Report

**Date:** 2026-09-30. **Protocol:** PREREGISTRATION.md (frozen by Cale 2026-09-30, win bar 0.15).
**Scope completed:** build (script 50) + fit/dev-selection (script 51). **Locked test NOT run.**

## 1. Timing-sanity audit (§4) — date_modified reliability

- 2,935 deduped player-weeks (2018–2022). **Null date_modified share: 0.000 in every season.** No vintage excluded.
- Post-kickoff date_modified: 0.04% (n=1) — excluded by the filter regardless.
- Friday-18:00-CT → kickoff window: 5.85% (n=155) — deliberately excluded information, measured not assumed.
- Weekday distribution: Friday 2,150 / Thursday 314 / Wednesday 260 / Saturday 174 / Tue–Mon–Sun 37 — consistent with the NFL injury-report cadence (final reports Friday).
- 50-row spot check (seed 42): all rows have non-null date_modified; statuses and dates plausible (final-report Fridays, midweek updates). Practice-only rows (null report_status) appear in the feed and are excluded from features per protocol.
- 285/2,935 rows could not be matched to a regular-season team-game (postseason weeks) — irrelevant to the experiment.

**Conclusion:** the historical date_modified field is reliable for 2018–2022. The Phase 1 audit's missing-field finding was specific to the 2026-season feed.

## 2. V1 reproduction

- Linear-model coefficients identical to data/linear_models.pkl (exact).
- Walk-forward GBM extended to 2019+ (frozen code; 2018 burn-in, hist ≥ 200).
- 2021–2022 pred_gbm_m and ens_margin reproduced to 0.00e+00 (exact).
- 1,225 regular-season games with kickoff > Friday 18:00 CT; 86 Thursday/pre-Friday games excluded.
- Train: 480 games (2019–2020). Dev: 506 games (2021–2022). Dev V1 MAE = 10.2431 (sane).

## 3. Dev results (2021–2022, n=506) — V1 baseline vs candidates

| Cand | V1 MAE | Cand MAE | Δ MAE | 95% paired CI | Injury subset Δ (n=167) | Non-injury Δ (n=339) | Bar |
|------|--------|----------|-------|---------------|------------------------|---------------------|-----|
| A | 10.2431 | 10.5053 | +0.2622 | [−0.5123, −0.0341] | +0.5905 | +0.1005 | ✗ |
| B | 10.2431 | 10.3562 | +0.1131 | [−0.3044, +0.0753] | +0.0548 | +0.1418 | ✗ |
| C | 10.2431 | 10.2323 | −0.0108 | [−0.1089, +0.1347] | −0.1442 | +0.0549 | ✗ |
| D | 10.2431 | 10.2889 | +0.0458 | [−0.2141, +0.1148] | +0.0354 | +0.0509 | ✗ |
| E | 10.2431 | 10.2716 | +0.0285 | [−0.1694, +0.1103] | −0.0421 | +0.0633 | ✗ |
| E-var | 10.2431 | 10.2324 | −0.0107 | [−0.0163, +0.0378] | — | — | sep |

(Δ negative = candidate better. CI is on V1_err − cand_err, so positive = better.)

**Dev selection: NO candidate clears the preregistered bar.** A is significantly worse
than V1 (CI excludes zero on the wrong side). C is the only candidate with a negative
point estimate (−0.0108, essentially noise) and the only one improving the injury subset
(−0.1442), but its CI includes zero and its non-injury regression (+0.0549) marginally
exceeds the 0.05 limit.

- E-variant (dev-learned, in-sample, reported separately): weights [A=0, B=0.0317, C=0.1798, D=0]
  — the constrained fit puts nearly everything on C.
- Coefficient stability: A 9/18 sign flips across 2019-vs-2020 fits (the Experiment 005
  failure mode, reproduced); B 3/6 flips.
- Secondary: no candidate improves RMSE vs V1 (13.22–13.62); calibration slopes 0.72–0.93;
  ATS at |edge|≥3 diagnostic-only, n=29–40, win rates 0.526–0.594 (underpowered, no bar).

## 4. Frozen bundle

`experiments/injury_adjustment_experiment/data/`:
- injury_candidates_frozen.pkl — `8eb5daabe6b98c6d524726bcf2a9620b9403176698bdb8d40835a698ca1150a8`
- fit_manifest.json — `3dfe2e68f03629b655b858d026ceeb6271628ce4dc6438a39c1338e4ad39b16d2`
- features_2018_2022.parquet — `bee77082807ac7442e1638684d5e3ee8012de63115af59cf35f3025d2985db44`
- build_audit.json — `b27841b1fc9a9cf979edb7d026ceeb6271628ce4dc6438a39c1338e4ad39b16d2`
- SHA256SUMS.txt (all four)

## 5. Leakage audit (§9) — all PASS

1. Timing filter (dm < T) enforced at build; game-day inactives excluded — PASS.
2. Sunday/final statuses excluded by construction — PASS.
3. Timing-sanity audit ran before fitting — PASS.
4. Snap/starter roles from pre-week data only — PASS.
5. V1 walk-forward; 2021–2022 margins reproduced to 1e-9 — PASS (linear components
   fit on 2018–2020 per protocol; train residuals partially in-sample for linear
   components — disclosed; dev/test fully out-of-sample).
6. No market columns in injury-layer inputs — PASS.
7. PFT never read by primary pipeline — PASS.
8. Test isolation: max season 2022 in every artifact; 2023+ never read — PASS.
9. qb_point_values.json never loaded (actual-load detection) — PASS.
10. practice_status excluded as a feature — PASS.
11. All writes confined to experiments/injury_adjustment_experiment/ — PASS.

## 6. Protocol deviations forced by the data (all justified)

1. **Regression check covers 2021–2022, not 2021–2025.** Reading 2023–2025 is forbidden
   (test isolation). The walk-forward loop is season-independent, so 2021–2022 equality
   at 1e-9 validates the reproduction.
2. **Injury rows deduped to one per player-week** (latest date_modified kept). The protocol
   specifies counts of injured *players*; 005 counted rows, which double-counts status
   updates. Dedup is the faithful implementation.
3. **ST (K/P/LS) excluded from candidate D's off/def burden.** D is defined as
   offense-vs-defense counts; kickers are neither. Documented, not tuned.
4. **Trailing snap window uses in-season prior weeks only** (1–4 available); week-1 games
   get weight 0. Cross-season trailing was unspecified; in-season-only is the
   conservative reading.
5. **C's missing-starter fraction is snap-share-weighted** (injured starters' shares ÷ all
   11 starters' shares), per the "fraction of expected-starter snaps" wording.
6. **Train is effectively 2019–2020** (480 games). 2018 is burn-in with no V1 margins by
   construction (GBM needs ≥200 prior games).
7. **ATS diagnostic uses spread_line as diagnostic-only input** (protocol §7 lists it;
   never a model feature; check 6 covers model inputs only).

## 7. Status

Build + fit + dev selection complete per the frozen protocol. **Ready for Cale's
re-confirmation before the one-shot locked test.** Honest read: dev selection yields no
candidate clearing the bar — a dev-stage null. Cale decides whether to (a) run the
locked test as a pure null-confirmation, or (b) stop here. Script 52 was not written or run.
