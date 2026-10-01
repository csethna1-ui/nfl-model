# RESULTS — Props Experiment 003C: Pass Attempts + Hierarchical Completions

**Status: COMPLETE — single locked-test evaluation run 2026-10-01.
Protocol frozen and approved by Cale 2026-10-01 12:25 CDT before any
2023–2024 computation for this experiment. Fit once; no retries; no
deviations.**

## Verdict

| Leg | Comparison | Verdict |
|---|---|---|
| Pass attempts M1 (volume model) | vs M0 | **MATERIAL WIN** — bar cleared |
| Pass attempts M2 (M1 + NGS passing) | vs M0 | **MATERIAL WIN** — bar cleared (strongest rung) |
| Pass attempts M3 (M1 + context families) | vs M0 | **MATERIAL WIN** — bar cleared |
| Completions C1 (modeled completion%) | vs C0 (naive downstream) | **NULL** — bar NOT cleared |

- Attempts: M1/M2/M3 each independently clear the preregistered win bar.
  The completions leg is reported narrowly as NULL; it is not a standalone
  model and gets no independent verdict beyond the C1-vs-C0 comparison.
- Per the shared protocol §8, **no production changes are made.** A
  production recommendation package is provided below (002 §14 precedent);
  work STOPS here pending Cale's explicit authorization.

## Sample sizes (preregistered minimums)

- Population: QB with `eligible_hist=1` AND `played_role=1` (002
  expected-starter reconstruction), market `pass_yards` rows of the frozen
  002 extended table.
- Train 2018–2020: n=1,270. Dev 2021–2022: n=986. **Locked test
  2023–2024: n=1,010** (2023: 503, 2024: 507).
- Minimum-sample rule (≥700 pooled for pass attempts): **clears**
  (1,010). Per-season slices (503 / 507) are well above the <150
  underpowered line.
- Locked test touched exactly once, for this experiment's preregistered
  evaluation only.

## Method (as implemented, frozen ladder)

- M0: `trail_pass_att_ewma` (trailing attempts EWMA, hl=3, max 16,
  strictly prior weeks), NaN→0.
- Rung point projection = equal-weight mean of (a) Ridge with alpha
  dev-selected from {0.1, 1, 10, 100} and (b) HistGradientBoostingRegressor
  with params dev-selected from the 8-combo grid {lr ∈ {0.05, 0.1},
  max_depth ∈ {3, 5}, max_iter ∈ {200, 500}} (shared protocol 002 §7
  hyperparameter procedure; seeds: bootstrap 1337, GBM random_state=11).
- Dev-selected hyperparams (frozen for test refit): all rungs
  alpha=100.0, GBM {learning_rate: 0.05, max_depth: 3, max_iter: 200}.
- Rung features exactly per prereg §4 (see `feature_audit.csv`):
  M1 = pace_team_plays, pace_combined, pace_neutral_pass_rate, ctx_elo_adv,
  trail_pass_att_ewma, qb_changed, exp_rookie, exp_second_year,
  exp_career_games, trail_games.
  M2 = M1 + 6 NGS passing trailing features (time to throw,
  aggressiveness, intended air yards, air yards to sticks, expected
  completion %, CPOE — strictly prior weeks only).
  M3 = M1 + families B, C, D1, D2, L + QB efficiency trails
  (qb_epa_trail, qb_cpoe_trail, qb_adot_trail, qb_pressure_trail).
  No spread/total/implied features anywhere (leakage rule honored).
- Completions leg: feeder = **M1's attempts projection** (predetermined
  before the test eval; identical feeder for C0 and C1 so the comparison
  isolates completion% modeling). C0 = feeder × trailing completion%
  (clipped [0,1]). C1 = feeder × modeled completion probability
  (features: ngs_xcomp_trail, ngs_cpoe_trail, ngs_aggro_trail,
  qb_adot_trail, qb_pressure_trail; target actual_comp/actual_att,
  sample_weight=actual_att; output clipped [0.05, 0.98]).
- As-of discipline: Friday 18:00 CT; all features from the frozen 002
  table (already as-of) plus new NGS trailing computed strictly from prior
  weeks. NGS merge rate on population rows: 93.78%; rows with no NGS
  history (10.38%) trail to 0.0. Actual completions from local pbp
  (001 definition: sum of complete_pass for passer_player_name), merge
  100%, comp ≤ att holds on all 2,256 train+dev rows.

## Locked-test metrics (2023–2024, n=1,010)

### Pass attempts — MAE vs actual attempts

| Rung | Pooled MAE | M0 MAE | Rel. improvement | 2023 | 2024 | 95% paired bootstrap CI (M0−rung) | Bar |
|---|---|---|---|---|---|---|---|
| M0 | 7.90 | — | — | 7.71 | 8.09 | — | — |
| M1 | 7.22 | 7.90 | **+8.65%** | 7.22 (+6.43%) | 7.22 (+10.76%) | [0.325, 1.032] | PASS |
| M2 | 7.15 | 7.90 | **+9.61%** | 7.10 (+8.01%) | 7.19 (+11.12%) | [0.410, 1.084] | PASS |
| M3 | 7.31 | 7.90 | **+7.46%** | 7.23 (+6.26%) | 7.40 (+8.59%) | [0.242, 0.945] | PASS |

Win bar (all required): ≥5% pooled ✓ (all three), ≥2% in 2023 ✓ and 2024 ✓
individually, bootstrap CI excludes zero ✓ (all three).

Reading: the volume model (expected plays × pass rate × ELO-diff script ×
QB role context) beats trailing history by ~8.7%. Adding the NGS passing
family (M2) adds a further ~1pp (9.6% total) — NGS time-to-throw /
aggressiveness / air-yard / expected-completion trails carry incremental
volume information. The full context stack (M3, +7.5%) clears the bar but
does not beat the leaner M2 — consistent with the 002 lesson that bigger
is not better.

### Completions (hierarchical, downstream of M1 attempts) — MAE vs actual completions

| Leg | Pooled MAE | Rel. improvement vs C0 | 2023 | 2024 | 95% paired bootstrap CI (C0−C1) | Bar |
|---|---|---|---|---|---|---|
| C0 (M1 att × trailing comp%) | 5.07 | — | 5.11 | 5.03 | — | — |
| C1 (M1 att × modeled comp prob) | 5.00 | +1.44% | 5.08 (+0.68%) | 4.92 (+2.20%) | [−0.024, 0.177] | **FAIL** |

The completion-probability model (NGS expected completion %, CPOE trail,
aggressiveness, ADOT, pressure) does not add validated value given the
attempts projection: +1.4% pooled is below the 5% bar, the 2023 slice is
below the 2% per-season bar, and the bootstrap CI includes zero. **NULL —
reported narrowly.** Trailing completion% remains the binding downstream
choice.

### Dev diagnostics (procedure check only — not a selection ground)

Dev MAE: M0 8.30, M1 7.27, M2 7.21, M3 7.19, C0 5.08, C1 5.04. The dev
ordering (M1/M2/M3 all well ahead of M0; C1 ≈ C0) is consistent with the
test outcome. No family selection was performed or permitted.

## Production recommendation package (002 §14 — for authorization, NOT deployed)

(a) **Research verdict:** attempts M1/M2/M3 MATERIAL WIN; completions C1 NULL.
(b) **Proposed production architecture:** pass-attempt projection engine
    = M2 rung (M1 volume features + NGS passing trailing family);
    per-rung procedure = mean(dev-selected Ridge, dev-selected GBM),
    refit on the production training window per the 002 refit cadence;
    completions downstream stays C0 (M2 attempts × trailing completion%).
    Research-only; no betting use.
(c) **Exact changed features (new vs production):** the six NGS passing
    trailing features (`ngs_ttt_trail`, `ngs_aggro_trail`, `ngs_iay_trail`,
    `ngs_ayts_trail`, `ngs_xcomp_trail`, `ngs_cpoe_trail`) plus the M1
    volume feature set listed above. Nothing else in production changes.
(d) **Data dependencies:** keyless nflverse NGS `passing` weekly feed;
    must be pulled weekly post-games and converted to strictly-prior-week
    trailing EWMAs (hl=3, max 16) before each Friday 18:00 CT prediction
    run. Local pbp cache for completions.
(e) **Freshness requirements:** NGS pull must complete before the Friday
    cutoff; a missing weekly NGS pull degrades the six features to 0.0
    (their no-history value) — predictions still run, flagged as
    degraded.
(f) **Failure behavior:** NGS feed schema change or pull failure →
    fall back to M1-only projection (volume model without NGS), log the
    degradation, never silently substitute same-week NGS values.
(g) **Rollback plan:** revert to current production player-projection
    code path (16_prod_player_projection.py) unchanged; the 003C engine is
    additive and isolated.

**STOP. No production changes made. Awaiting Cale's explicit
authorization.**

## What this establishes — and what it does not

- ESTABLISHED: a volume model of QB pass attempts (expected plays, pass
  rate, ELO-diff script proxy, QB role context) plus trailing NGS passing
  data predicts attempts ~9.6% better (MAE) than trailing history alone on
  locked 2023–2024 data, with per-season and bootstrap confirmation.
- ESTABLISHED: modeling completion probability from NGS/accuracy features
  adds no validated value downstream of the attempts projection (NULL).
- NOT ESTABLISHED: any betting edge. This is projection quality only.
  **No timestamped historical prop markets exist keyless** (shared protocol
  §7), so projection accuracy cannot be converted to an edge claim. The
  paper-tracking stream (timestamped Bovada line captures via
  scripts/30_pull_prop_lines.py, extended to pass-attempt/completion
  markets) is the only route to a market comparison, prospectively.
- NOT CLAIMED: that attempts improvements transfer to yards (002's target
  is separate); that M3's extra features are worth their complexity
  (M2 ≥ M3); anything about 2025+ (reference only) or production
  performance.

## Artifacts (frozen, in this directory)

- `scripts/01_build_003c_table.py` — data prep (NGS pull, trailing, completions)
- `scripts/02_run_003c.py` — dev + single locked-test evaluation
- `data/ngs_passing_2016_2024.parquet` — raw NGS pull (provenance)
- `data/table_003c.parquet` — population + 003C columns (3,266 rows)
- `data/experiment_003C_dev.json` — dev diagnostics + frozen hyperparams
- `data/experiment_003C_test.json` — locked-test metrics (single eval)
- `data/experiment_003C_test_predictions.parquet` — per-row test predictions
- `feature_audit.csv` — per-feature source / as-of / missingness audit
- `REPRODUCIBILITY.md` — manifest

## Protocol compliance statement

- Splits honored: train 2018–2020 / dev 2021–2022 / locked test
  2023–2024; test computed exactly once (single `--phase test` run).
- Fit once; fixed M0/M1/M2/M3 ladder; no feature-family selection after
  seeing results; no ladder changes; no retries.
- Preregistration frozen (Cale 2026-10-01 12:25 CDT) before any 2023–2024
  computation for this experiment.
- Spread/total/implied scoring excluded everywhere; pre-week ELO diff +
  trailing scoring are the stated proxies (no historical spread/total
  substitution).
- Completions evaluated only downstream of attempts (C1 vs C0); never as
  a standalone model.
- Fit-once discipline: dev used solely for hyperparameter selection
  (fixed grids) and procedure diagnostics.
