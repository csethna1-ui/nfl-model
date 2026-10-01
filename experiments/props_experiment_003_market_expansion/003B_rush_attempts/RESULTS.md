# RESULTS — Props Experiment 003B: Rush Attempts

**Status: COMPLETE 2026-10-01. Fit once. Locked test (2023–2024) evaluated
exactly once, after PREREGISTRATION.md froze (approved by Cale 2026-10-01
12:25 CDT). No production changes made.**

## Verdict (per preregistered win bar, shared protocol §5)

| Rung | Pooled rel. MAE vs M0 | 2023 | 2024 | 95% bootstrap CI excl. 0 | Bar verdict |
|---|---|---|---|---|---|
| M1 opportunity | +2.50% | +3.59% | +1.32% | yes [0.008, 0.200] | **PARTIAL/SIGNAL** (significant, sub-bar) |
| M2 + NGS rushing | **+29.76%** | **+31.56%** | **+27.80%** | yes [1.112, 1.414] | **MATERIAL WIN — bar cleared** |
| M3 + team/matchup/context | +2.72% | +3.99% | +1.34% | yes [0.017, 0.218] | **PARTIAL/SIGNAL** (significant, sub-bar) |

Win bar (all required): ≥5% pooled relative-MAE reduction vs M0; ≥2% in 2023
AND 2024 individually; 95% paired bootstrap CI of the MAE difference
excludes zero. **M2 clears all three by a wide margin. M1 and M3 are
significant but sub-bar: reported narrowly, no production implication.**
Per the shared protocol there is no pooled "Props 003" verdict — this
verdict is independent of 003A/003C/003D.

## Headline numbers (locked test 2023–2024, single evaluation)

Population: RB, `market=='rush_yards'`, `eligible_hist==1`,
`played_role==1`, `trail_rush_att_ewma >= 5`. Target: `actual_att`
(carries; verified = pbp rusher counts). **n = 1,323** (2023: 678;
2024: 645) — clears the ≥1,000 minimum-sample rule (prereg estimated
~1,528; the ≥5 trailing-carries cut trims the audit's estimate).

| | MAE | RMSE | Bias (pred−actual) |
|---|---|---|---|
| M0 trailing carries EWMA | 4.245 | 5.511 | −0.941 |
| M1 (D = mean A/B/C) | 4.138 | 5.231 | −0.207 |
| M2 (D = mean A/B/C) | **2.981** | 4.023 | −0.258 |
| M3 (D = mean A/B/C) | 4.129 | 5.194 | −0.053 |

Component MAEs on test — M2: A(Ridge)=2.987, B(GBM)=3.069,
C(quantile median)=2.998. M1: 4.122/4.228/4.213. M3: 4.134/4.180/4.198.

Per-season MAE — M2: 2023 = 2.958 (M0 4.322), 2024 = 3.006 (M0 4.163).
M1: 2023 = 4.167, 2024 = 4.108. M3: 2023 = 4.149, 2024 = 4.107.

Paired bootstrap (2000 resamples, seed 1337) of mean(M0 |err| − rung |err|),
pooled test: M2 mean diff **1.263**, 95% CI **[1.112, 1.414]**; M1
[0.008, 0.200]; M3 [0.017, 0.218].

## Dev diagnostics (train 2018–2020 → dev 2021–2022; test untouched)

n_train=1,679, n_dev=1,323. Dev M0 MAE = 4.355.

| Rung | dev A | dev B | dev C | dev D | dev D rel vs M0 | α (Ridge) | GBM params |
|---|---|---|---|---|---|---|---|
| M1 | 4.201 | 4.291 | 4.347 | 4.242 | +2.6% | 0.1 | lr 0.05 / d3 / 200 |
| M2 | 2.990 | 2.987 | 2.977 | 2.942 | +32.4% | 0.1 | lr 0.05 / d3 / 200 |
| M3 | 4.211 | 4.288 | 4.345 | 4.235 | +2.8% | 100.0 | lr 0.05 / d3 / 200 |

Hyperparameter *procedure* frozen per shared protocol §4 (Ridge α grid
{0.1,1,10,100}, GBM 8-combo grid, quantile hyperparams fixed a priori,
seeds fixed); selections above are the dev outcomes, frozen for the test
refit. Test-phase models refit on train only with these frozen selections.

## What drove the M2 win (dev-only diagnostic, not a ladder change)

Single-feature Ridge dev MAEs (M0 = 4.355): `ngs_xrush` 3.049,
`ngs_ttl` 3.198, `ngs_ryoe_pct` 3.302, `ngs_eff` 3.434, `ngs_8box` 3.628,
`ngs_ryoe` 4.651. Pure-tracking subset
(eff/ryoe_pct/8box/ttl, no volume composites): 3.212. The win is
broad-based across the NGS family, not carried by one column: the tracking
measurements are strong *role proxies* — 8-man-box rate and time-to-LOS
identify every-down workhorses vs committee/scat backs far better than
past carries alone (which are noisy from game script). Stated narrowly per
the ladder convention: **M2 passes; the NGS rushing family adds material
predictive value for carries. The structural opportunity model (M1) and the
team/matchup/context families (M3) do not clear the bar.**

## Data-hygiene correction (pre-test, not a spec change)

The keyless NGS feed carries `week==0` **season-total aggregate rows**
(354 rows; e.g. D. Henry 2022: 349 att / 1538 yds = full-season totals).
These are not weekly observations and contain the target week's own game
plus future games, so they are invalid inputs under the prereg's
"strictly-prior-week trailing" rule. They were excluded before trailing;
the first dev run (which included them) was discarded and re-run. The
corrected trailing was verified by hand-computed EWMA match
(Henry 2022-wk5: stored 2.78907249 vs hand 2.78907249). No spec change —
this implements the frozen as-of rule correctly. The locked test was never
touched by the contaminated run.

## Feature audit

`data/feature_audit.csv` (36 rows): 31 included features, 0 NaN on the
train+dev population, 0 market-line features. spread/total/implied lines
excluded everywhere (002 leakage rule); historical depth-chart levels
unavailable (injury feed only, as preregistered); NGS trailing-use only.

## What was claimed / what was NOT claimed

- **Claimed:** On the locked 2023–2024 test, evaluated once, the M2 rung
  (opportunity model + trailing NGS rushing family) reduces carry-projection
  MAE by 29.8% pooled (31.6% in 2023, 27.8% in 2024) vs the frozen trailing
  EWMA baseline, with the 95% paired bootstrap CI [1.112, 1.414] excluding
  zero. M1 and M3 show small significant improvements (+2.5%/+2.7%) that do
  not clear the bar.
- **NOT claimed:** any betting edge. This establishes **projection quality
  only**. No historical rush-attempt prop lines exist keyless, so
  model-vs-market cannot be evaluated retrospectively. Bovada currently
  posts ~2 rush-attempt lines per slate (vs 55 for receptions) — recorded
  as a paper-tracking limitation: the prospective stream
  (`scripts/30_pull_prop_lines.py`, to be extended to the new markets) will
  accumulate observations slowly for this market. That is a market fact,
  not a modeling caveat.
- **NOT claimed:** rushing efficiency — attempts only. The yards
  decomposition (attempts × efficiency) is future work, contingent on this
  result and on a separate preregistration.
- Depth-chart *levels* were not features (unavailable historically);
  depth-chart *changes* entered only via the as-of injury feed, as stated.

## Production gate (§8) — package, then STOP

M2 cleared the bar, so per the shared protocol the production
recommendation package is produced here and **work stops for Cale's
explicit authorization. No production changes were made.**

- (a) Research verdict: M2 MATERIAL WIN as above; M1/M3 PARTIAL/SIGNAL.
- (b) Proposed production architecture: Friday 18:00 CT carry-projection
  engine = frozen fitted M2 D-ensemble (Ridge α=0.1 + GBM lr0.05/d3/200 +
  quantile-GBM median, equal-weight mean, clip ≥0) on the 13 M2 features;
  feeds the rushing-yard distribution's volume half later.
- (c) Exact changed features vs current production (Player Projection v2):
  adds the 6 trailing NGS rushing features (ngs_eff, ngs_xrush, ngs_ryoe,
  ngs_ryoe_pct, ngs_8box, ngs_ttl) plus the 7 M1 opportunity features to the
  carry-projection path. No V1 spread-model impact (separate system).
- (d) Data dependencies: keyless NGS rushing feed
  (`nfl_data_py.import_ngs_data('rushing')`) pulled weekly; 002 extended
  feature table (frozen); week==0 aggregate-row exclusion (data-hygiene
  rule above, must be re-applied on every rebuild).
- (e) Freshness requirements: NGS trailing requires the prior week's NGS
  release before the Friday 18:00 CT cutoff; if the release is late, fall
  back to the previous trailing vector (stale-by-one-week) and flag it.
- (f) Failure behavior: any missing NGS feature → 0 (matches research
  convention); if the NGS pull fails entirely, engine degrades to M1
  (PARTIAL/SIGNAL rung, +2.5%) — never silently to M0.
- (g) Rollback plan: revert the carry-projection path to Player Projection
  v2's current behavior; the research artifacts (models/*.pkl) are
  versioned and the production table is untouched, so rollback is a config
  flip.

**Awaiting Cale's authorization before any production change.**

## Reproducibility

See `REPRODUCIBILITY.md`. Scripts:
`scripts/build_003b_features.py` (data prep, no fitting),
`scripts/audit_003b_features.py` (feature audit),
`scripts/run_experiment_003b.py --phase dev | --phase test`.
Frozen artifacts: `models/M1_fitted.pkl`, `models/M2_fitted.pkl`,
`models/M3_fitted.pkl` (exact fitted ensembles evaluated on the locked
test); `data/experiment_003b_dev.json`, `data/experiment_003b_test.json`,
`data/experiment_003b_test_predictions.parquet`,
`data/features_003b_2018_2024.parquet`,
`data/ngs_rushing_2018_2024.parquet`, `data/feature_audit.csv`.
Base tables reused frozen and untouched: 001 `modeling_table.parquet`,
002 `extended_features_2018_2024.parquet`.
