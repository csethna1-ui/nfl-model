# PREREGISTRATION — Props Experiment 002: Matchup, Team Context & Opportunity

**Status: PROTOCOL FROZEN 2026-09-30. No model fit. No locked-test computation performed.
Locked-test (2023–2024) feature values have not been inspected.**

Branch: NFL player-stat projection (the engine underneath player props).
Research only. Separate from the spread model (V1), Experiment 006, the PFT corpus,
and the power-ranking work.

---

## 0. Locked-test authorization (recorded explicitly)

- The 2023–2024 window was Experiment 001's locked test **for its candidates**.
  It remains a valid locked test for THESE NEW candidate families because this
  protocol — candidate specifications, model ladder, win bar, decision rules —
  is frozen BEFORE any 2023–2024 computation for Experiment 002 is performed.
- The 2023–2025 window was separately used for a **game-margin** power-ranking
  confirmation (different target, different features, no prop features tuned
  there). That work does not contaminate this experiment's locked test.
- Experiment 001's results, code, and artifacts are untouched and remain the
  frozen baseline reference.

## 1. Question

**Primary:** Does adding pregame team, matchup, opportunity, player-quality, and
game-environment information materially improve out-of-sample player-yardage
prediction beyond the frozen Player Projection v2 Model D?

**Secondary:** Can uncertainty estimation be improved enough to make the
High/Medium/Low labels statistically meaningful (i.e., do they correspond to
realized error)?

Targets evaluated separately: **passing yards, rushing yards, receiving yards.**
No receptions market.

## 2. Baseline (Model 0) — frozen

Model D exactly as implemented in
`experiments/player_props_projection/scripts/run_experiment_001.py`,
imported verbatim (the same functions production uses in
`scripts/16_prod_player_projection.py`):

- A: two-stage opportunity × efficiency (Ridge; alpha dev-selected from
  {0.1, 1, 10, 100} — re-selected per ladder rung on dev, same grid)
- B: HistGradientBoostingRegressor direct yards (8-combo grid dev-selected —
  re-selected per ladder rung on dev, same grid)
- C: quantile GBM P25/median/P75 (fixed a priori: lr=0.1, max_depth=3,
  max_iter=300, min_samples_leaf=20, random_state=7)
- D = equal-weight mean of A/B/C point projections.

001's dev-selected choices (A alpha=10.0; B lr=0.05/max_depth=3/max_iter=200)
are NOT carried over — each ladder rung re-runs the identical selection
procedure on dev, because feature sets change. The selection *procedure* is
frozen; its *outcomes* may differ per rung.

## 3. Periods

- **Train:** 2018–2020 — all fitting.
- **Dev:** 2021–2022 — hyperparameter selection, family selection for M11,
  uncertainty-threshold calibration. The ONLY selection ground.
- **Locked test:** 2023–2024 — evaluated **once**, after this protocol is
  frozen. No iteration on test results.
- **2025:** reference/robustness only — same frozen models evaluated once,
  reported as a non-binding extra column. No selection on 2025.
- **2026:** production monitoring only. Never used to tune or select.

## 4. Prediction timestamp and as-of discipline

- Prediction timestamp: **Friday 18:00 America/Chicago** of game week
  (same as Experiment 001 and production).
- Every feature is computed from information available **at or before** that
  timestamp. Trailing features use games strictly before (season, week).
- Games kicking off at/before the timestamp are excluded (same rule as 001).
- **As-of reconstruction rule:** where a source updates intraday (nflverse
  snap counts/advanced stats, injury reports), the feature must reflect what
  was knowable at the cutoff — implemented via explicit timestamp filters
  (`date_modified <= Friday 18:00 CT`) or via trailing completed-game values
  only. The latest historical DB value is NEVER used as a proxy for
  cutoff-time knowledge.
- Eligibility/grading guards identical to 001: evaluated only if
  `eligible_hist=1` AND `played_role=1`. Same role thresholds.

## 5. Feature families (exact specifications)

Trailing convention (all `trail_*`): EWMA half-life 3, max 16 games,
most-recent-first, strictly prior (season, week). NaN→0 for undefined
rates/shares; `trail_games` preserved.

Name matching (snap counts, PFR advstats, injuries → nflverse player rows):
lowercased full-name key `first-initial.last|team` with suffix stripping
(Jr/Sr/II/III/IV), following repo precedent (`scripts/50_injury_exp_build.py`).
Match rates measured and reported per source in the audit. Collisions
(same key, same team, multiple players) resolved by position-group match;
unresolved collisions dropped from the feature (counted in missingness).

### Family B — team offensive context (`ctx_*`), source: pre-week ratings
`data/games_with_ratings.parquet` attaches PRE-WEEK ELO/EPA ratings
(verified in `scripts/03_ratings.py`: ratings attached before the week's
games are folded in; week-1 offseason regression applied).

| Feature | Definition |
|---|---|
| `ctx_team_off_epa` | team's pre-week offensive EPA/play |
| `ctx_team_off_pass_epa` | team's pre-week offensive pass EPA/play |
| `ctx_team_off_rush_epa` | team's pre-week offensive rush EPA/play |
| `ctx_team_off_sr` | team's pre-week offensive success rate |
| `ctx_elo_adv` | pre-week (team ELO − opponent ELO) |

As-of: pre-week ratings are strictly prior-week information. Thursday games
of the current week are not yet folded in (conservative, matches 001).

### Family C — opponent defensive context (`oppd_*`), source: pre-week ratings
| Feature | Definition |
|---|---|
| `oppd_def_epa` | opponent's pre-week defensive EPA/play |
| `oppd_def_pass_epa` | opponent's pre-week defensive pass EPA/play |
| `oppd_def_rush_epa` | opponent's pre-week defensive rush EPA/play |
| `oppd_def_sr` | opponent's pre-week defensive success rate |

Note: 001 already includes opponent trailing yards allowed
(`opp_trail_pass_allowed_ewma`, `opp_trail_rush_allowed_ewma`). These EPA
versions are the incremental test. Same pre-week as-of discipline as B.

### Family D1 — game scoring environment (`envs_*`, pre-cutoff known)
| Feature | Definition | Source |
|---|---|---|
| `envs_dome` | 1 if dome/retractable-roof venue | schedules stadium (static, pre-known) |
| `envs_team_pts_trail` | trailing points scored/game (EWMA) | schedules scores, strictly prior weeks |
| `envs_opp_pts_allowed_trail` | trailing points allowed/game by opponent (EWMA) | schedules scores, strictly prior weeks |

**Market lines (spread/total/implied totals) are EXCLUDED from all new
features.** 001's table carries closing lines, but closing lines are not
available at the Friday 18:00 CT cutoff, and this protocol's leakage rule
("never closing lines when the cutoff was earlier") forbids them. The frozen
Model 0 baseline retains its 001 feature set unchanged (documented as a
frozen-baseline property, not re-litigated); every challenger must beat a
baseline that already sees closing lines. This asymmetry is conservative.

### Family D2 — schedule/fatigue (`envf_*`, all pre-known from schedules)
| Feature | Definition |
|---|---|
| `envf_days_rest` | team's days since its last game |
| `envf_rest_diff` | team days rest − opponent days rest |
| `envf_short_week` | 1 if days_rest ≤ 5 |
| `envf_long_rest` | 1 if days_rest ≥ 10 |
| `envf_div_game` | 1 if divisional game |

Travel/time-zone: excluded (marginal, not worth the venue-coordinate build;
documented).

### Family E — pace/play volume (`pace_*`), source: pbp team-game aggregates
| Feature | Definition |
|---|---|
| `pace_team_plays` | trailing offensive plays/game (EWMA) |
| `pace_combined` | (team trailing plays/game + opponent trailing plays allowed/game)/2 |
| `pace_neutral_pass_rate` | trailing pass rate in neutral situations (quarters 1–3, score diff within 10) |

Tests whether volume predicts beyond efficiency.

### Family F — player opportunity, incremental (`opp2_*`), source: snap counts
nflverse snap counts (local: `data/v2/raw/snap_counts_2018–2025.csv`,
official nflverse-data release). Weekly `offense_pct`.
| Feature | Definition |
|---|---|
| `opp2_snap_pct` | trailing EWMA of offensive snap share |
| `opp2_snap_trend` | mean snap share last 3 games − trailing-16 EWMA |

Route participation: NOT available in any local source → documented exclusion.
Target/carry/air-yard shares already in Model 0.

### Family G — receiver quality, incremental (`rq_*`)
| Feature | Source | Definition |
|---|---|---|
| `rq_adot` | pbp | trailing air_yards/targets |
| `rq_yac_per_rec` | pbp | trailing yards_after_catch/receptions |
| `rq_drop_pct` | PFR advstats (nflverse release) | trailing receiving_drop_pct |
| `rq_broken_tackles` | PFR advstats | trailing receiving_broken_tackles per game |
| `rq_ngs_separation` | NGS (nfl_data_py pull) | trailing avg_separation |
| `rq_ngs_xYAC` | NGS | trailing avg_expected_yac |

NGS weekly releases are post-game; trailing (strictly prior weeks) use is
timestamp-safe. (trail_ypt, trail_yac_pt, trail_air_share already in Model 0.)

### Family H — rusher quality, incremental (`ruq_*`)
| Feature | Source | Definition |
|---|---|---|
| `ruq_ybc_per_att` | PFR advstats | trailing rushing_yards_before_contact_avg |
| `ruq_yac_per_att` | PFR advstats | trailing rushing_yards_after_contact_avg |
| `ruq_broken_tackles` | PFR advstats | trailing rushing_broken_tackles per game |
| `ruq_explosive_rate` | pbp | trailing share of carries ≥ 10 yards |
| `ruq_stuff_rate` | pbp | trailing share of carries ≤ 1 yard |
| `ruq_goal_line_carries` | pbp | trailing carries with yardline_100 ≤ 5 per game |

### Family I — QB context (`qb_*`)
**Expected-starter reconstruction** (documented algorithm, no post-game info):
for each team-week, expected starter = QB with most pass attempts over the
team's trailing 4 games; if that QB has injury `report_status` in
{Out, Doubtful} as of Friday 18:00 CT (`date_modified <= cutoff`), use the
next-highest-attempt QB. The ACTUAL game starter is never used.

| Feature | Definition |
|---|---|
| `qb_epa_trail` | trailing EPA/play of expected starter (min 50 att; else 50/50 blend with league mean) |
| `qb_cpoe_trail` | trailing CPOE of expected starter (pbp `cpoe`) |
| `qb_adot_trail` | trailing air_yards/attempt of expected starter |
| `qb_pressure_trail` | trailing PFR times_pressured_pct of expected starter |
| `qb_changed` | 1 if expected starter ≠ trailing-4-game primary QB |

No fixed "backup = −X yards" adjustments. The existing 2026 QB-expectation
plumbing is production-only (append-only from 2026 W4, no backfill) and is
NOT used here; this reconstruction is the research counterpart, and its
incremental value is separately identifiable.

### Family J — OL/pressure (`ol_*`)
| Feature | Source | Definition |
|---|---|---|
| `ol_team_pressure_allowed` | PFR advstats, team-aggregated | trailing times_pressured_pct of team's QBs |
| `ol_opp_sack_rate` | pbp | trailing opponent sacks per opponent pass attempt faced |

### Family L — injury/personnel (`inj_*`), as-of Friday 18:00 CT
nflverse injury reports (local CSVs 2018–2025) carry `date_modified`.
As-of state = latest row per player with `date_modified <= Friday 18:00 CT`.
| Feature | Definition |
|---|---|
| `inj_player_status` | 0=unlisted/full, 1=Questionable, 2=Doubtful, 3=Out (player's own report_status) |
| `inj_team_out_share` | share of team's trailing-4-week offensive snaps (snap counts) belonging to players with as-of status Out/Doubtful |
| `inj_ol_out` | count of OL (T/G/C) with as-of status Out/Doubtful |

Timing caveat (documented in audit): nflverse `date_modified` is when the
feed recorded the report, which may lag real-world knowledge. This family
measures the value of *feed-available* injury information at the cutoff, not
perfect market knowledge. Kept as a separate family so its incremental value
is identifiable.

### Family O — experience/role (`exp_*`)
| Feature | Definition | Source |
|---|---|---|
| `exp_career_games` | career regular-season games played to date | player_games history |
| `exp_rookie` | 1 if first NFL season | player_games history |
| `exp_second_year` | 1 if second NFL season | player_games history |

### Family P — recency, incremental (`rec2_*`)
Model 0 already has half-life-3 EWMAs. Incremental variants only:
| Feature | Definition |
|---|---|
| `rec2_yards_hl1` | trailing yards EWMA half-life 1 (market-specific yards col) |
| `rec2_yards_hl8` | trailing yards EWMA half-life 8 |
| `rec2_opp_hl1` | trailing opportunity EWMA half-life 1 (targets/carries/attempts per market) |

These enter the B/C feature pool only (not Model A's two stages), keeping
A's opportunity/efficiency decomposition clean.

### Family Q — expected opportunity (`xq_*`)
| Feature | Source | Definition |
|---|---|---|
| `xq_xYpt` | pbp (`air_yards`, `xyac_mean_yardage`) | trailing EWMA of (air_yards + xyac_mean_yardage)/target — expected yards per target, receiving market only (0 for other markets) |

Verifies the value is pre-target-game: xyac is a per-play model output
available in the historical pbp; trailing use only.

### Explicitly excluded from the primary experiment
| Family/feature | Reason |
|---|---|
| Market spread/total/implied (new) | Closing lines unavailable at Friday 18:00 CT cutoff |
| Route participation | No local source |
| Coverage/man-zone, WR-vs-CB matchup (K) | FTN charting 2022+ only — insufficient history for train/dev; fragile |
| Weather forecasts/temp/wind (M) | No forecast-at-cutoff historically; game-time obs leak |
| Historical depth-chart position | Local depth charts are 2026-only |
| Travel/time-zone | Marginal; venue-coordinate build not justified |
| PFT/news | Separate branch, per standing rule |
| Historical prop lines | None exist |

## 6. Model ladder (exact feature-set definitions)

Let `OPP0`, `EFF0`, `ALL0` be 001's OPPORTUNITY_FEATS, EFFICIENCY_FEATS,
ALL_FEATS. Context features (B, C, D1, D2, E, J, L, O) enter **both** A
stages and the B/C pool. Opportunity features (F) enter A-stage-1 and B/C.
Quality features (G, H, qb_eff) enter A-stage-2 and B/C. `qb_ctx`,
recency (P) enter B/C only.

| ID | Spec |
|---|---|
| M0 | Model D exactly (frozen) |
| M1 | D + B (`ctx_*`) |
| M2 | D + C (`oppd_*`) |
| M3 | D + D1 (`envs_*`) |
| M4 | D + E (`pace_*`) |
| M5 | D + F (`opp2_*`) |
| M6 | D + position quality: receiving→`rq_*`; rushing→`ruq_*`; passing→`qb_eff`={qb_epa_trail,qb_cpoe_trail,qb_adot_trail} |
| M7 | D + full QB family (`qb_*` = qb_eff + qb_ctx) for ALL markets |
| M8 | D + J (`ol_*`) |
| M9 | D + L (`inj_*`) |
| M10 | D + D2 (`envf_*`) |
| M11 | D + union of families selected ONLY on train/dev (rule §7) |
| M12 | Regularized all-family model: RidgeCV + HistGBM on ALL new features; evaluated on test ONLY if the dev gate (§7) passes |

A more complicated model does NOT win on lower dev MAE alone (§7, §9).

## 7. Fitting and selection (frozen procedure)

- Fit on train (2018–2020) only. All selection on dev (2021–2022) only.
- Per ladder rung and market: A-alpha re-selected from {0.1,1,10,100} on dev;
  B params re-selected from the 001 8-combo grid on dev; C hyperparams fixed
  a priori (same as 001).
- **M11 selection rule (preregistered):** family f enters M11 for market m
  iff dev relative MAE improvement vs M0 ≥ **1.0%** AND adding f regresses no
  market's dev MAE by more than **1.0%** vs M0. M11 refit on train with
  hyperparams re-selected on dev. This is a heuristic screen; the locked
  test is the arbiter.
- **M12 dev gate:** M12 is evaluated on the locked test only if its dev MAE
  beats M0 by ≥1% in ≥1 market with no market >1% worse on dev.
- Seeds fixed (1337 for bootstrap RNG; sklearn random_states as in 001).
  sklearn 1.9.1, scipy 1.18.1.

## 8. Evaluation

- Primary: walk-forward MAE of point projections vs actual_yards, per market,
  on evaluated rows (eligible_hist=1 & played_role=1).
- Also: RMSE, median AE, bias, MAE by season, MAE by experience bucket
  (rookie / 2nd-year / veteran), MAE by uncertainty bucket, MAE by
  opportunity bucket (trailing opportunity terciles), MAE by market
  availability n/a (no historical lines).
- Paired bootstrap (2000 resamples, seed 1337) CIs for M0-vs-challenger MAE
  differences, per market, pooled test.
- Report: n player-games, missing-feature rates per family, feature
  availability/coverage, timestamp-compliance checks.
- Min-n: pooled ≥ 700 (pass) / 1000 (rush) / 2500 (receiving); per-season
  slices ≥ 150 (else reported as underpowered, not as wins).

## 9. Win bar (all must hold; same structure as 001)

1. Pooled 2023–2024: **≥5% relative MAE reduction** vs M0 in **≥2 of 3 markets**;
2. **No market regresses by more than 2%** relative;
3. Each claimed market shows **≥2% relative reduction in 2023 AND in 2024
   individually**;
4. **95% paired bootstrap CI** of the MAE difference excludes zero (pooled,
   per claimed market).

If no candidate clears the bar: **VERDICT = NULL / NO PRODUCTION CHANGE.**
A null is a successful experiment.

## 10. Uncertainty calibration (frozen procedure)

For M0 and each ladder rung, on dev:
- (a) empirical coverage of the [P25, P75] interval (nominal 50%);
- (b) MAE by relative-width tercile (does narrower ⇒ lower error?);
- (c) production-rule mirror: relative width = (p75−p25)/max(median,1);
  dev p33/p67 cutoffs → High/Medium/Low labels applied to test; MAE per
  label; coverage per label.
- Verdict per model: labels are *meaningful* iff High-label MAE is
  materially (<10% relative) below Low-label MAE on test AND interval
  coverage is within [40%, 60%]. If not, recommend dashboard wording
  **HIGH / MEDIUM / LOW UNCERTAINTY** instead of confidence language.
- Never create betting probabilities from these labels.

## 11. Market lines

No historical prop lines exist; projection MAE only (same as 001).
Spread/total lines are excluded from new features (§5, leakage rule).
Market-line research stays separate from the core player-stat model.

## 12. Decision rules and verdict taxonomy

- `MATERIAL WIN`: a ladder model clears §9 → production recommendation
  package (§14), then STOP for authorization.
- `NULL`: no ladder model clears §9 → no production change. Report which
  families showed consistent directional gains as hypotheses for future
  work, without claiming wins.
- `PARTIAL/SIGNAL`: significant but sub-bar gains (e.g., one market only)
  → reported narrowly, no production change.
- Dev→test shrinkage is expected; only the locked test counts.

## 13. Final report must explicitly answer

A. Does team ELO help? B. Does team offensive EPA help?
C. Does opponent defensive EPA help? D. Does spread/total help?
E. Does pace help? F. Does player opportunity help beyond Model D?
G. Do air yards/ADOT/advanced receiving metrics help?
H. Do pressure/OL metrics help? I. Does QB context help?
J. Do injuries/personnel context help? K. Does coverage matchup info help?
L. Does weather help? M. Does NGS/expected-opportunity info help?
N. Does any combination materially outperform Model D?
O. Is uncertainty better calibrated? P. Is there enough evidence to
change production?

(For K and L-weather: the preregistered answer is "not tested in primary —
excluded for the documented reasons"; the report states this plainly.)

## 14. Production rule

Even if a candidate wins: DO NOT deploy. Produce (a) research verdict,
(b) proposed production architecture, (c) exact changed features,
(d) expected data dependencies, (e) freshness requirements,
(f) failure behavior, (g) rollback plan — then STOP and wait for explicit
authorization.

## 15. Required outputs

1. `experiment_002_protocol.md` (this file — frozen)
2. Feature availability/leakage audit (`feature_audit.csv` + notes)
3. Feature-family results (dev table)
4. Model comparison table (dev + test)
5. Paired bootstrap results
6. Uncertainty calibration results
7. Locked-test results
8. Final research verdict (`RESULTS.md`)
9. Exact production recommendation, if any
10. Reproducibility manifest (`REPRODUCIBILITY.md`)

## 16. Final principle

The goal is NOT the model with the most features. The goal is determining
which PRE-GAME information provides reproducible incremental predictive
value over the frozen Model D. If the answer is "nothing," that is a
successful experiment. Do not manufacture an edge. Integrity above all.

---

*Protocol frozen 2026-09-30 before any Experiment 002 model fitting and
before any 2023–2024 computation for Experiment 002. The 001 modeling
table (with its 2023–2024 rows) exists on disk from prior work; Experiment
002's extended feature build will process all seasons with identical code
and validate on train+dev only — test rows are never inspected before the
single locked-test evaluation.*
