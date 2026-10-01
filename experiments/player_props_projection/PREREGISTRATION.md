# PREREGISTRATION — Player Projection Experiment 001

**Status: PROTOCOL APPROVED AND RE-FROZEN 2026-09-30. Modeling authorized
per this protocol. No model has been fit yet.**

Amendment (user, 2026-09-30): Model D ensemble-weighting rule clarified —
primary D is the equal-weight average of A/B/C; any learned-weighting variant
is dev-selected, frozen before the locked test, and reported as a separate
D-variant that cannot replace the preregistered equal-weight D.

Branch: NFL player-stat projection (the engine underneath player props).
Separate from the spread model (V1), Experiment 006, and the PFT corpus.
Data: `data/modeling_table.parquet` (+ `data/DATA_DICTIONARY.md`).
Table built 2026-09-30 by `scripts/build_modeling_table.py`; validation checks
were run on train+dev only — the 2023–2024 test slice was built blind.

---

## 1. Question

Can a dedicated player-stat projection model **materially** reduce projection
MAE versus the current EWMA projector on the three prop markets
(pass / rush / receiving yards), without leakage?

## 2. Model roster (architecture sketches — nothing fit)

| ID | Sketch |
|---|---|
| **Baseline** | Current EWMA projector **without** the matchup adjustment: trailing exponentially-weighted yards (half-life 3, max 16 games, ≥3 games else shrink to positional mean). The matchup betas are dropped because they were fit by OLS on 2018–2024, which overlaps the locked test, and their R² was 0.1–0.8% (negligible). |
| **Model A** | Two-stage opportunity × efficiency. Stage 1 predicts opportunity (expected targets / carries / attempts) from the opportunity features; Stage 2 predicts efficiency (expected yards per opportunity) from the efficiency features; projection = stage1 × stage2. Directly tests the opportunity-decomposition hypothesis. |
| **Model B** | GBM (or equivalent tree ensemble) on the full allowable feature set, direct yards regression. |
| **Model C** | Distributional: quantile regression (P25 / median / P75) or game-script simulation producing a player-stat distribution. Graded on the median for MAE; the distribution itself is the deliverable for prop use. |
| **Model D** | Primary Model D = equal-weight average of A/B/C point projections. If a learned-weighting variant is evaluated, its weights must be selected exclusively on 2021–2022 and frozen before 2023–2024; it is reported as a separate D-variant and cannot replace the preregistered equal-weight D. (The test set never decides the ensemble.) |

No hyperparameter search on test. All selection decisions on dev (2021–2022).

## 3. Periods

- **Train:** 2018–2020 — all fitting.
- **Dev:** 2021–2022 — model selection, early stopping, ensemble decisions.
- **Locked test:** 2023–2024 — evaluated **once**, after the user approves the
  frozen candidates. No iteration on test results.
- **2025:** excluded from the table. The current system's 2025 diagnostics are
  published (pass 63.1 / rush 25.4 / receiving 22.5 MAE vs naive 69.3 / 27.3 /
  24.3) — 2025 is a spent, reference-only point, never a clean test.

## 4. Eligibility and grading rules

- A row is **evaluated** only if `eligible_hist = 1` (≥3 trailing games and the
  trailing role guard: pass_att ≥ 10 / rush_att ≥ 5 / targets ≥ 5) **and**
  `played_role = 1` (actual game meets pass_att ≥ 10 / rush_att ≥ 5 /
  targets ≥ 3 — books void the rest; a benched player's 0 says nothing about
  the projection). Both guards mirror the current projector.
- Prediction timestamp: **Friday 18:00 America/Chicago** of game week.
  Every feature is computed from games strictly before (season, week).
  Games kicking off at/before the timestamp (Thursday games, rescheduled
  odd-weekday games) are excluded from the table.
- **Allowable features:** exactly the 44 columns in `data/DATA_DICTIONARY.md`.
  Explicitly forbidden: `temp`/`wind` (game-time observations, not forecasts),
  any post-kickoff information, PFT/news data (separate branch), prop lines
  (none exist historically — this study grades projections, never picks).

## 5. Primary metric and the bar for a material win

- **Metric:** walk-forward MAE of point projections vs `actual_yards`,
  per market (pass / rush / receiving separately), on evaluated rows.
- **Baseline MAEs to beat** (2025 holdout, current system): pass **63.1**,
  rush **25.4**, receiving **22.5**. (Naive last-3: 69.3 / 27.3 / 24.3.)
- **Win bar** (all must hold):
  1. On the pooled 2023–2024 locked test: **≥5% relative MAE reduction** vs
     baseline in **at least two of three markets**,
  2. **and** no market regresses by more than **2%** relative,
  3. **and** each claimed market shows **≥2% relative reduction in 2023 and
     in 2024 individually** (guards against a one-season blip),
  4. **and** the 95% paired bootstrap CI of the MAE difference excludes zero
     on the pooled test for each claimed market.
- **Minimum-n:** pooled locked-test evaluated rows per market ≥
  700 (pass) / 1000 (rush) / 2500 (receiving). Observed test counts
  (eligible + played): pass 1010, rush 1528, receiving 3625 — all clear
  with margin. If a market fell short it would be reported as underpowered,
  not as a win. Per-season consistency slices require n ≥ 150.
- If no model clears the bar: report the null cleanly. A null here is
  evidence about the information content of opportunity features, not a
  failure of effort.

## 6. Hypothesis under test (recorded as hypothesis, NOT expectation)

> "Opportunity modeling reduces the big playing-time-driven misses that
> dominate the current projector's error."

Test: preregistered secondary analysis — MAE on the **top decile of baseline
absolute errors** (the big-miss subset, selected by the fixed baseline so no
challenger selection leaks in). If Model A specifically shrinks errors there
while matching baseline elsewhere, the hypothesis gains support. If the big
misses don't shrink, the hypothesis is rejected and recorded as such.

## 7. What stays locked / out of scope

- The 2023–2024 slice stays locked until the experiment runs. Dev is the only
  selection ground.
- No receptions market in this version (no current-system baseline; data is
  derivable from the rich pbp cache for a future extension).
- No pick/over-under evaluation — no historical prop lines exist. Projection
  MAE only.
- No changes to V1, Experiment 006, the spread vault, or the PFT corpus.
- 2025 remains reference-only.

## 8. Evaluation table (to be filled at experiment time)

| Model | Pass Yds MAE (test) | Rush Yds MAE (test) | Rec Yds MAE (test) | Meets bar? |
|---|---|---|---|---|
| Baseline (EWMA, no matchup adj) | — | — | — | — |
| A: opportunity × efficiency | — | — | — | — |
| B: GBM | — | — | — | — |
| C: distributional (median) | — | — | — | — |
| D: ensemble | — | — | — | — |

Reference (already published, not a clean test): 2025 current system
63.1 / 25.4 / 22.5.

---

*Re-frozen 2026-09-30 with the Model D clarification. User approved; modeling
authorized per this protocol.*
