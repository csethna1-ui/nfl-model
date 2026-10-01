# V2 Research Architecture -- Build Report

Date: 2026-09-29. READ-ONLY research build. No models trained, no validation evaluated,
no 2026 Experiment-006 data used, 2023-2025 vault untouched, V1 untouched.
**No V2-A..E comparison was built or run; none is authorized by this build.**

## What was built
- **144 features** inventoried across 10 families (0 unclassified)
- Build scripts: `scripts/30_v2_pull_sources.py` (acquisition),
  `scripts/31_v2_features_pbp.py` (possession/explosiveness/PBP-pressure/ST),
  `scripts/32_v2_features_pfr.py` (PFR pressure),
  `scripts/33_v2_features_player.py` (QB/continuity/availability),
  `scripts/34_v2_features_env.py` (environment),
  `scripts/35_v2_assemble.py` (walk-forward assembler),
  `scripts/36_v2_inventory.py` (this inventory).
- Data tables: `data/v2/team_week_*.parquet` (played-week source),
  `data/v2/team_features_pred.parquet` (pred-week grain, 2743 x 80),
  `data/v2/games_v2_features.parquet` (game grain, 1372 x 223, 2018-2022 only).

| table | shape | seasons |
|---|---|---|
| team_week_pbp.parquet | 2744 x 53 | 2018–2022 |
| team_week_pfr.parquet | 2744 x 21 | 2018–2022 |
| team_week_player.parquet | 2744 x 15 | 2018–2022 |
| game_env.parquet | 1372 x 19 | 2018–2022 |
| team_features_pred.parquet | 2743 x 80 | 2018–2022 |
| games_v2_features.parquet | 1372 x 223 | 2018–2022 |
| raw/ | 45 PFR + snap + injury files | 2018–2026 cached (source availability only) |

Walk-forward rule: every pred-week feature uses games strictly before that week
(min 4 prior games, else NaN). 1372 game rows = all 2018–2022 games with scores.
- Docs: `v2_research/{architecture.md, feature_inventory.json,
  data_availability.json, leakage_audit.md, REPORT.md}`.
- All 7 scripts `py_compile` clean (verified 2026-09-29).

## Features per family
- environment: 14
- explosiveness: 15
- matchup: 32
- player_availability: 2
- player_continuity: 3
- player_qb: 26
- possession: 17
- pressure_pbp: 9
- pressure_pfr: 17
- special_teams: 9

## Feasibility summary
- FULLY FEASIBLE: possession, explosiveness, PBP pressure proxies, special teams (PBP local);
  PFR pressure (pulled 2018-2026); snap-count continuity; schedules env; QB identity.
- PARTIAL / NEEDS DISCIPLINE: value-weighted availability (fuzzy name match, date_modified
  discipline required -- highest leakage risk); weather (freeze-at-prediction-time).
- LIMITED: `qb_value_poll` is 2026-anchored (anachronistic pre-2026); per-season QB values
  unsourced. Special teams: few plays/week (noisy) + kickoff rule breaks 2023/2024/2025.
- HISTORY BOUND: PFR pressure starts 2018 (matches train window); FTN/participation excluded
  (2022+/post-season-only -- incompatible with walk-forward).

## Genuinely new vs V1 (audit's uncorrelated-with-ELO/EPA filter)
Per the V1 architecture audit (components = three views of one latent team-strength axis,
error corr ~0.95; V1 errors corr 0.967 with market errors), only information uncorrelated with
ELO/EPA can move the residual. Ranked by likely independence:
1. **Matchup interactions** — unit-vs-unit structure (protection x rush, explosiveness x coverage)
   destroyed by V1's scalar collapse; structurally new though inputs are derived.
2. **Possession structure** — V1 knows EPA/play outcomes, not how drives are built.
3. **Explosiveness distribution shape** — volatility orthogonal to mean EPA by construction;
   also feeds the future variance target.
- MAYBE (needs the filter at modeling stage): PBP sack rates, continuity (confounded with
  strength), value-weighted availability (market prices news fast).
- WEAK PRIORS: travel/time-zone, special teams (noisy).

## Bugs found and fixed during the build
1. `three_and_out_rate` — play-count proxy missed penalty-extended drives (was 0.0%, then 7.4%);
   redefined via `drive_first_downs == 0 & result == 'Punt'` → 19.6%, matching the known NFL rate.
2. `start_y100` sign convention documented (stores `yardline_100`; larger = worse field position).
3. ST EPA `posteam` attribution verified as the kicking team (2024 KC: 33 games, st_epa +10.95).
4. PBP name format (`S.Bradford` vs `Sam Bradford`) broke backup detection (88% false flags);
   last-name normalization → 3.1% with sensible cases (Murray→Streveler, Jackson→Huntley).
5. Game-assembly merge collisions (duplicate `qb_backup_flag`, `div_game_x/y`, keep-list duplication
   producing duplicate columns) — fixed with pre-merge renames and dedup.

## Protection statement (verified 2026-09-29)
- All analytical tables asserted 2018–2022 only; no 2023–2025 or 2026 rows anywhere.
- No reads of `data/market_*` or `experiments/experiment_006_information_timing/observations`.
- V1 files, dashboard exports, and Experiment 006 observations unmodified
  (no files newer than the build start under 006).
- `data/v2/raw/` holds 2018–2026 source files as availability cache only; never evaluated.

## What must be resolved before V2-A..E comparisons
1. Per-season QB value sourcing (or drop `qb_value_poll` from historical modeling).
2. Injury timestamp discipline enforced in the modeling pipeline (date_modified < kickoff).
3. PFR lag discipline: consume in Tuesday batch, not Monday.
4. Cold-start policy for pred_weeks 1-4 (MIN_GAMES=4 -> NaN; modeling must define fallback).
5. Matchup standardization choice (raw products now; z-score at modeling stage).
6. Human authorization of the V2-A..E comparison protocol (gates, metrics, baselines).

V2-A through V2-E are NOT authorized by this build.

---

# PHASE 1 — Blocker resolution (2026-09-29, completed)

Governing directive adopted 2026-09-29: autonomous V2 research → production
execution. Phase 1 gate documents (all under v2_research/):
- blocker_resolution.md — per-blocker resolved-vs-remaining record
- timestamp_policy.md — frozen Tuesday-AM information-set rules
- cold_start_policy.md — four options documented; Option C (V1 fallback) frozen in protocol
- leakage_audit_v2_final.md — consolidated audit, supersedes the build audit where they differ
- family_overlap_matrix.json — diagnostic family correlations, 2021–2022, n=569
- overlap_matrix.json / overlap_matrix.md — same matrix + interpretation
- qb_value_design.md, injury_cutoff_policy.md, pfr_lag_audit.md, standardization_spec.md

Key resolutions: (1) historical QB value built — scripts/37_v2_qb_value.py →
data/v2/qb_value_pred.parquet (2,744×17); qb_value_historical =
recency-weighted (8-game half-life) qb_epa/dropback, QB-keyed with
team-agnostic carryover, ≥4 games + ≥40 dropbacks else NaN (88.7% coverage);
qb_value_poll QUARANTINED. (2) Injury cutoff: date_modified <
min(prediction_cutoff, kickoff); Tuesday set is identically zero (report cycle
starts Wednesday); 2025/26 rows unusable (no date_modified); scripts/33's
unapplied filter flagged as a code gap for the modeling rebuild. (3) PFR:
all 17 pressure_pfr features lag one week (PFR publishes advanced stats
Wednesday AM); stored team_week_pfr must be shifted (W ← ≤W−2) before use.
(4) Cold start: Option C frozen — <4 prior games → V1 fallback, logged and
reported separately. (5) Standardization: league-wide expanding z-score,
|S(W)|≥30, cross-season option A, NaN propagation + walk-forward median
imputation — frozen, none tuned.

Overlap matrix key finding: pressure (−0.10) and QB (0.06) essentially
orthogonal to the V1/ELO/EPA axis; matchup/possession/explosiveness form a
correlated cluster (0.63–0.80, expected — matchups are built from those
inputs); continuity 0.38, ST 0.03, environment −0.06, availability −0.12.

Inventory: 144 → 153 features (9 QB features added; poll quarantined).
Refined filter applied throughout: low correlation with latent strength is a
PRIORITY criterion, NOT an exclusion rule.

# PHASE 2 — Research protocol frozen (2026-09-29)

v2_research/protocol.md — FROZEN. 2018–2020 development (ridge alpha from
{0.1,1,10,100} by walk-forward MAE); 2021–2022 validation (one evaluation
per candidate, no re-tuning); 2023–2025 vault (single locked run only if a
candidate passes all gates and V2_FINAL_* is complete); 2026
production/prospective only.

Candidates: V2-A (component ridge, 20 regressors + intercept, §5 feature
list), V2-B (V2-A + 8 preregistered matchup interactions), V2-C (V2-A + 7
QB/player differentials), V2-D (V2-A + 37 pressure/explosiveness/possession
structure differentials), V2-E (V2-A + families of gate-passing candidates
only). Gates G1–G6: paired-bootstrap MAE improvement (p<0.05), better in
both seasons, |bias|<1.0 with slope in [0.8,1.2], leakage audit, error-corr
with V1 < 0.98, timestamp defensibility. No ATS/ROI in selection. Stopping
rules: one evaluation per candidate; failed gates stay failed.

# PHASE 3 — Modeling (in progress)

- scripts/39_v2_harness.py — shared walk-forward harness (modeling-table
  rebuild with PFR shift + injury cutoff + QB merge; walk-forward
  standardization/imputation; cold-start fallback; per-fit manifests).
- scripts/40_v2a.py — V2-A implementation (delegated 2026-09-29).
- V2-B/C/D to follow on the frozen harness once V2-A lands.
