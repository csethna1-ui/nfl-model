# Phase 1 — As-of reconstruction notes (2026-10-01)

How the W1–W3 Model D projection sets were regenerated with strict as-of
discipline. Monitoring only: no refit, no retraining, no threshold changes,
no tuning on W1–W3 outcomes.

## What was run

`code/16_prod_player_projection_asof.py` — a byte-patched copy of the frozen
`scripts/16_prod_player_projection.py`. The original is untouched
(`diff` of the two files shows only the changes below):

1. `--data-dir`: overrides the data directory so each weekly run reads
   truncated as-of caches and writes outputs there. All model/feature/predict
   code paths are identical.
2. `--prediction-timestamp`: overrides the script's Sunday-anchored
   `friday_timestamp()` with the task-specified Friday 18:00 CT timestamps.
   Reason: the script's rule computes W1 Friday as 2026-09-11 (Sunday 9/13
   minus 2 days), which falls *after* W1's Wednesday 9/9 (NE@SEA) and
   Thursday 9/10 (SF@LA) kickoffs — those two games would have been silently
   excluded, contradicting the task's "Friday 18:00 CT before that week's
   games". Pinned timestamps: W1 2026-09-04, W2 2026-09-11, W3 2026-09-18
   (all 18:00 America/Chicago). With these, all 16 games/32 teams are
   included every week (verified: no kickoff precedes any timestamp).
3. Eligibility gate adaptation: the frozen script's gate ("most recent cached
   game in the current season", added 2026-09-30) would empty the W1 universe
   entirely against an as-of cache (no 2026 games exist as of 9/4). As-of
   reading of the gate's intent (exclude long-retired players whose stale
   history passes the trailing guards): eligible iff the player has ≥1 game
   in the 2025 season OR ≥1 game in 2026 with week < W — both strictly as-of.
   The fitted models (A/B/C) are untouched.
4. Additive instrumentation: the week feature frame is dumped to
   `week_frame_2026_w{W}.parquet` for the audit's trailing-opportunity and
   rich-pbp coverage diagnostics. Predictions consume the identical frame.

## As-of inputs (`inputs/asof_w{W}/`)

Per week W, built from the production caches by strict truncation —
`(season < 2026) OR (season == 2026 AND week < W)`:

- `player_games.parquet`: W1 44,016 rows (0 from 2026); W2 44,329 (313 from
  2026 W1); W3 44,649 (633 from 2026 W1–W2). Verified zero rows with
  2026 week ≥ W.
- `prod_pbp_rich_2026.parquet`: same week filter (W1: empty frame, schema
  preserved). Verified zero rows with week ≥ W.
- Symlinks (read-only) to the shared, week-invariant inputs:
  `team_defense.parquet`, `schedules_2018_2025.parquet`,
  `prod_pbp_rich_2025.parquet`, the experiment rich cache
  `experiments/player_props_projection/data/pbp_rich_2018_2024.parquet`
  (referenced via the unchanged EXP_DATA path), and the frozen model
  artifacts `prod_player_models_v2.pkl` / `_meta.json` (fit 2026-09-30 on
  2018–2020 train / 2021–2022 dev; no 2026 data in fitting).

Trailing features therefore use only games strictly before (2026, W); the
opponent-trailing lookup masks the same way; `player_team`/`position` come
from the truncated cache (most recent as-of game).

## Known reconstruction limitations

- **Game lines (spread/total → implied totals, model features).** Taken from
  `schedules_2018_2025.parquet` as cached 2026-09-30 (nflverse pull). These
  are the best reconstructable pregame lines, but they are not guaranteed to
  equal the lines visible at each Friday 18:00 CT. Only the ENV features
  (spread/total/implied totals) are affected; trailing player/opponent
  features are not.
- **W1 team assignment staleness (pipeline property, not a reconstruction
  artifact).** For W1, `player_team` comes from each player's last 2025 game,
  so 2026 offseason moves are missed. A true 9/4 production run of the frozen
  pipeline would have had exactly the same staleness (no 2026 games existed;
  depth charts are not a model input). Quantified in the audit:
  57/262 scored W1 rows (21.7%) were projected for the wrong team; those rows
  err more (see PHASE1.md). This is a genuine finding about the pipeline's
  early-season behavior, not a flaw in the reconstruction.
- **Actuals source.** `nfl_data_py.import_weekly_data([2026])` 404s —
  nflverse has not published `player_stats_2026.parquet` at the version's
  expected release URL
  (`.../releases/download/player_stats/player_stats_2026.parquet`, checked
  2026-10-01). Actuals use the local `data/player_games.parquet`
  (built 2026-09-30 from nflverse pbp by the pipeline's own pull script;
  313/320/318 player-game rows for W1/W2/W3). Same yardage columns the model
  predicts.
- **Name collisions in the 2026 data.** 23 player-weeks have 2+ actual rows
  under one abbreviated name on different teams (e.g. `J.Love` on ARI and GB
  simultaneously; `M.Evans` on CAR and SF; `K.Allen` on IND and WAS). Audit
  rule: attribute the actual to the row matching the projection's team;
  unscorable when none matches (1 row). Flagged as `dup_actual_teams` in the
  error table. The same collisions also double-count those players' trailing
  histories (pre-existing pipeline behavior, noted not fixed).
- **Market lines.** Historical captures `data/market_props_2026_w{W}.json`
  used as-is (old schema: player/market/line, no source/captured_at —
  tolerated by the loader). 36/16/12 rows; attached to projections via the
  pipeline's own name matcher: W1 36/36, W2 14/16, W3 11/12 (lined players
  outside the projected universe get no attachment).
- **Scored sample conditioning.** Only ~50% of projections score (796/1600):
  the universe includes backups with trailing data who then record no stats
  (DNP/dressed-but-unused). 28 scored rows have zero in-game opportunity;
  93 have zero yards in the market column (mostly WRs with targets but no
  yards — legitimate outcomes). Sensitivity excluding zero-opportunity rows
  is reported in PHASE1.md. Rookies cannot score (MIN_GAMES=3 trailing guard;
  all scored rows are non-rookies). All scored rows had full rich-pbp
  coverage of their trailing games (no fallback cases in the scored sample).

## What was NOT done

No refit or modification of the frozen models; no threshold/bucket tuning
(the diagnostic tertiles are descriptive cutoffs on the scored sample,
reported in the aggregates JSON); no W1–W3 outcomes entered any feature;
production `data/` and `scripts/` files were read but never written
(mtimes verified unchanged). All outputs live under
`experiments/props_season_to_date_audit_2026/phase1/`.
