# ELO Offseason-Regression Diagnostic — Research Report

**Date:** 2026-09-30 · **Status:** diagnostic only — nothing in V1 changed
**Dir:** `experiments/elo_regression_diagnostic/`
**Question:** Does the 1/3 offseason ELO regression toward 1500 carry too much 2025 information into 2026?

## Verification (read first)

- Current ELOs were **recomputed from scratch** using the exact production code path
  (`scripts/03_ratings.run_elo`, K=20, HFA=55, MOV multiplier, weekly batching) on
  2018–2026 Week 3 schedules. Max abs diff vs the production snapshot
  (`data/ratings_current_2026_w4.parquet`, the exact snapshot V1 used): **0.000000**.
- Preseason decomposition uses the exact additive identity of the production
  methodology: `current − 1500 = (preseason − 1500) + Σ(2026 weekly deltas)`.
  Identity verified to 3e-13. No approximation.
- Historical audit used **2018–2022 only**. The 2023–2025 locked-test vault was never touched.
- `data/final_2025_state.pkl` is **stale** (Sep-11 artifact, differs up to ~94 pts from
  recomputed production 2025 finals, corr 0.993). It is not used by current production
  (only `06_week1.py` reads it). Recomputed values are authoritative throughout this report.
  Flagged as data hygiene, not a V1 calculation bug.

## A. Current 2026 diagnostic (all 32 teams)

Full table: `table_32team_sorted_by_disagreement.csv` (sorted by |ELO rank − performance rank|).
Performance rank = rank-average of exported current-season efficiency metrics only
(off EPA, def EPA, off success rate, def success rate). No new formula, no market.

Largest absolute ELO-vs-current-performance disagreements:

| team | ELO rk | perf rk | d_perf | W-L | offEPA rk | defEPA rk |
|------|--------|---------|--------|-----|-----------|-----------|
| CAR | 28 | 11 | +17 | 1-2 | 13 | 15 |
| NO  | 27 | 11 | +16 | 1-2 | 12 | 17 |
| PIT | 15 | 29 | −14 | 2-1 | 28 | 18 |
| GB  | 17 | 31 | −14 | 1-2 | 18 | 28 |
| MIN |  4 | 16 | −12 | 3-0 | 30 |  1 |
| PHI | 12 | 24 | −12 | 2-1 | 22 | 20 |
| CIN | 16 |  6 | +10 | 2-1 |  8 | 14 |
| ATL | 18 |  9 |  +9 | 1-2 | 21 | 13 |
| TEN | 32 | 23 |  +9 | 0-3 | 24 | 22 |
| NE  |  9 | 18 |  −9 | 1-2 | 29 |  7 |

Distribution of d_perf: mean +0.2, sd 8.0, IQR −6…+5. Disagreement is the norm, not the exception, at n=3 games.

## B. Patriots case study (descriptive only)

| metric | value |
|---|---|
| 2025 final ELO | 1626.2 (**rank 6 of 32** — genuinely strong 2025) |
| Preseason 2026 ELO (post 1/3 regression) | 1584.2 |
| Current ELO | 1563.2 (rank 9) |
| Change from preseason | **−20.9** (ELO has *declined* in 2026) |
| 2026 record / point diff | 1-2 / −15 |
| Off EPA / rank | −0.107 / **29** |
| Def EPA / rank | −0.051 / **7** |
| Net success rate / rank | −0.011 / 17 |
| ELO rank − off EPA rank | **−20** |

Numerical description: NE's ELO rank (9) sits 9 ranks above its composite current-performance
rank (18), driven almost entirely by the offense (ELO 9 vs off-EPA 29). The 2025 finish
(rank 6) explains the starting point; the 1-2 record has already cost −20.9 ELO points.
NE is the **10th-largest** disagreement of 32 — CAR, NO, PIT, GB, MIN, PHI, CIN, ATL, and
TEN all disagree more. **NE is not an unusual outlier.** The same pattern (strong-2025 team,
slow-2026 start, ELO above efficiency ranks) appears for PHI (−12), GB (−14), and DEN (−6).

## C. League-wide outliers

- Efficiency-over-ELO (ELO "behind" current stats): CAR (+17), NO (+16), CIN (+10).
- ELO-over-efficiency (ELO "ahead" of current stats): PIT (−14), GB (−14), MIN (−12), PHI (−12), NE (−9).
- MIN is instructive: 3-0 with the #1 defense by EPA but #30 offense — ELO rank 4 vs perf rank 16.
  ELO (results vs prior-strength) and EPA (per-play efficiency) measure different things;
  they are *supposed* to disagree early.

## D. Historical regression audit (2019–2022 test seasons, walk-forward, n=369 early games)

ELO-implied home margin = OLS(home_margin ~ pre-game elo_diff) fit per setting on
strictly-prior seasons (no lookahead). Checkpoints: weeks 1, 2, 3, 4, 6, 8.

**Pooled early-season MAE:**

| setting | MAE |
|---|---|
| 1/2 regression | 9.558 |
| **1/3 (current)** | **9.566** |
| 2/3 regression | 9.629 |
| full regression | 10.046 |

- 1/2 vs 1/3: +0.008 MAE, paired t = 0.16, **p = 0.876** — statistical noise.
- By season (early): 1/3 wins 2019, 2020, 2021; 2/3 wins 2022 (1/2 second, 1/3 third).
  The entire 1/2 pooled edge comes from **one season (2022)** — exactly the kind of
  single-season win that must not drive a parameter choice.
- Full regression is worse in 3 of 4 seasons and pooled (−0.48 vs 1/3): **strong evidence
  against full regression**, i.e. against the "too sticky" hypothesis in its strong form.
- Weeks 9–18: all four settings within 0.06 MAE — the regression choice washes out
  by midseason, as expected.
- Full per-season/per-checkpoint table: `table_historical_regression_audit.csv`;
  pooled: `table_historical_regression_pooled.csv`.

## E. Interpretation

**Observed facts:**
1. Mechanically, the preseason starting point dominates current ELO: median 74% of each
   team's |deviation from 1500| is preseason carryover; 23/32 teams are preseason-dominated
   (`table_preseason_decomposition.csv`). This is arithmetic, not a modeling finding —
   with 3 games played, each game moves ELO only ~5–15 points while preseason deviations
   run to ±173.
2. NE's ELO rank exceeds its efficiency ranks, but 9 teams disagree more. Not unusual.
3. Historically, no alternative regression setting consistently beats 1/3 early-season
   across seasons. The only pooled challenger (1/2) differs by a non-significant 0.008
   driven by a single season.

**Interpretation:** ELO is behaving as designed. It intentionally blends prior-season
results with current-season results; at n=3 games the prior *should* dominate.
ELO-vs-EPA disagreement is expected: ELO scores results against opponent strength,
EPA scores per-play efficiency, and W/L vs efficiency routinely diverge in September.

**Evidence that would justify a change** (not observed): an alternative regression
setting beating 1/3 on early-season MAE consistently across multiple historical
seasons with statistical significance.

This maps to interpretation **(1)/(2)**: no meaningful issue warranting a parameter
change; ELO may look slow to adapt early, but that is the designed behavior and the
historical record does not support "fixing" it.

## F. Recommendation

**KEEP V1 UNCHANGED — no sufficient evidence.**

- Do not change the 1/3 offseason regression, K, HFA, MOV, or the 40/50/10 blend.
- The stale `final_2025_state.pkl` should be regenerated or retired at the next
  convenient maintenance window (data hygiene; not a production calculation bug).
- If Cale wants this revisited: the preregistered bar is a multi-season,
  statistically significant early-season MAE improvement on vault-clean historical
  data. This diagnostic does not clear it.

## Artifacts (all in this directory)

- `01_snapshot_diagnostic.py` — snapshot, disagreement, decomposition (re-runnable)
- `02_historical_audit.py` — historical walk-forward audit (re-runnable)
- `table_32team_diagnostic.csv` — all 32 teams, full diagnostic row
- `table_32team_sorted_by_disagreement.csv` — sorted by |ELO rank − perf rank|
- `table_preseason_decomposition.csv` — per-team preseason vs 2026-games ELO components
  (+ alternative preseason starting points under 1/2, 2/3, full regression)
- `table_historical_regression_audit.csv` — MAE by setting × season × checkpoint
- `table_historical_regression_pooled.csv` — n-weighted pooled MAE
- `REPORT.md` — this file
