# Phase 3 — As-of Reconstruction Notes

Prospective season-to-date audit of the two frozen experimental prop heads
(003B rush attempts, 003A receptions) on 2026 Weeks 1–3. MONITORING ONLY.

## How the W1–W3 runs were produced

The production scripts were imported as modules **read-only** and executed
through their verbatim `weekly_run()` code path (feature build → frozen
model predict → market join → schema validation). The only redirection was
the modules' `DATA` / `NGS_CACHE` / `NGS_CACHE_PREV` globals, pointed at
`phase3/work/datamirror/` — a directory of symlinks to production `data/`
plus three as-of reconstructions (below). Nothing was written to `data/`;
production files and frozen experiment dirs are untouched. Outputs were
moved to `phase3/projections/`.

Per-week outputs: `projections/prop_v2_2026_w{W}_{rush_attempts,receptions}.json`
(6 files), each passing the scripts' own `validate_output()`.

## As-of reconstructions (all under `phase3/work/`)

1. **Prediction timestamps (IMPORTANT — differs from the task's assumed dates).**
   The task stated W1 Friday = 2026-09-04, W2 = 2026-09-11, W3 = 2026-09-18.
   The actual 2026 schedule (`data/schedules_2018_2025.parquet`, nflverse)
   has W1 games on **Wed 2026-09-09 / Thu 09-10 / Sun 09-13 / Mon 09-14**,
   W2 on Thu 09-17 / Sun 09-20 / Mon 09-21, W3 on Thu 09-24 / Sun 09-27 /
   Mon 09-28. The production `friday_timestamp()` rule (Friday 18:00 CT
   before the week's Sunday games) therefore yields:
   - W1: **2026-09-11 18:00 CT** (2 games — Wed/Thu openers — excluded as
     already kicked off, exactly as production does)
   - W2: **2026-09-18 18:00 CT** (1 Thu game excluded)
   - W3: **2026-09-25 18:00 CT** (1 Thu game excluded)
   Cross-check: `data/predictions_2026_w1.csv` (V1 pipeline) was written
   **Sep 11 17:50**, confirming Friday Sep 11 was the real W1 prediction
   day. The task's dates are each one week early vs the data; the audit
   follows the production schedule-derived rule. Flagged to the parent
   for confirmation — the trailing features are unaffected either way
   (strictly-prior-week filtering), only the projected game set and the
   timestamp label differ.

2. **Pre-week ratings** (`datamirror/ratings_current_2026_w{W}.parquet`).
   Only the W4 file existed in `data/`; the scripts refuse stale ratings.
   Rebuilt W1–W3 with the exact w4 code path (`03_ratings.run_elo` +
   `07_update_weekly.run_epa_current`, W1 regressed-prior rule from 07
   lines 240–245). Verification: the same procedure for W4 reproduces
   `data/ratings_current_2026_w4.parquet` **exactly** (ELO max diff 0.0,
   EPA max diff 0.0). 33rd team "OAK" (stale abbreviation lingering in
   the ELO dict) filtered to the 32 current teams to match the w4 file.
   Provenance JSONs in `phase3/work/ratings_2026_w{W}.provenance.json`.

3. **2026 play-by-play** (`datamirror/pbp_2026.parquet` → `work/pbp_2026_full.parquet`).
   `data/pbp_2026.parquet` does not exist (the 19 head's `build_player_history`
   would otherwise see no 2026 in-season games). Keyless nflverse pull of
   2026 REG pbp (8,311 rows, W1–W3) with the superset of columns needed by
   both heads + `qb_kneel`. Strictly-prior-week filtering inside the prod
   code enforces the as-of (W1 sees no 2026 rows, W2 sees W1, W3 sees W1–W2).

4. **NGS trailing.** Fresh keyless pulls at audit time (2026-10-01) for
   rushing (1,188 rows, 2024–2026 W1–W3) and receiving; week==0 aggregate
   rows excluded (141 rushing rows); trailing vectors use only rows with
   (season, week) strictly before the target week. Required-release check
   passed every week (W1 needs 2025; W2 needs 2026-W1; W3 needs 2026-W2).
   Assumption (documented): each prior week's NGS release was published
   before that week's Friday 18:00 CT cutoff — consistent with NGS's
   next-day release cadence, but the feed carries no release timestamps to
   verify. All runs stayed on the M2 rung; `stale_ngs_used=false` everywhere.

## Mid-task code changes to the 003A script (flagged — TWO edits)

`scripts/19_prod_receptions.py` was edited by the parent **twice** during
this audit (all times UTC; CDT = UTC−5):

- **Edit 1** (before ~18:28 UTC): added a **predictable-game filter** —
  the 003A player-trailing history keeps only (season, week, team) rows
  whose game kicked off *after* that week's Friday 18:00 CT timestamp
  (Thursday/Wednesday games excluded), replicating the experiment's frozen
  base-row convention. Base rows were built from pbp receivers. The audit's
  first 003A W1–W3 run used this version (driver log: "predictable
  team-games 2018..2026: 4450", "predictable filter: 34972 -> 32292
  player-games", "player trailing: 1011 eligible player-weeks").
- **Edit 2** (2026-10-01 **18:34:47 UTC** = 13:34:47 CDT, verified by file
  mtime): refactored the filter to a **game_id inner join** and — the
  material change — rebuilt the player-trailing **base rows from
  `data/player_games.parquet`** (nflverse player_stats) instead of pbp
  receivers, so 0-target games are included ("exactly the 001 base
  construction", per the new code comment). 003B
  (`17_prod_rush_attempts.py`, unmodified since 18:03 UTC) has no such
  filter — its player trailing uses all games.

The audit **re-ran 003A W1–W3 against the edit-2 version**
(sha256 `b804ef81b5fbdd53`; driver `phase3/work/rerun_003A_current.py`;
run log: "predictable REG games 2018..2026: 2225",
"player_games 2018..2026: 44967 -> 40088 predictable REG",
"player trailing: 1077 eligible player-weeks"). Diff edit-1 vs edit-2
projections: **identical player sets** (190/211/209 rows), max |Δ|
0.2/0.7/0.4 per week, mean |Δ| ≈ 0.01, only 11/15/10 rows differ by
>0.05. The refactor is behavior-preserving in practice; all audit
aggregates in PHASE3.md reflect the edit-2 runs. The edit-1 outputs are
preserved at `phase3/work/projections_003A_pbp_version/` for the record.

Consequences / notes:
- The grading script's opportunity-volume cut (player_games-based, no
  predictable filter) remains a slight approximation for 003A;
  documented as analysis-only.
- Parent should confirm the edit-2 version is the intended verified
  deployment. No further 19-script edits occurred after 18:34:47 UTC
  (mtime checked at audit close).

## Known as-of imperfections (documented, not hidden)

- **Player spine.** Both scripts define eligibility from the full-season
  2026 player list (last 2026 row = current team/position). For the W1
  retro-run this includes a few players whose first 2026 appearance was
  W2/W3, and assigns post-trade teams to traded players. Their *features*
  remain strictly prior-week (2025-only for W1), so no outcome leakage;
  it is an eligibility-list difference vs a true Friday run, and it is
  also exactly what production does (the W4 run's spine is season-to-date).
- **Injury report (003A QB features).** `injuries_2026.csv` was refreshed
  2026-09-29, so target-week report rows may reflect post-Friday updates.
  The script's documented production analog (target-week rows, no
  date_modified in the 2026 file) is used verbatim. QB features are inputs
  to the frozen model, not audit outputs; they are not separately graded.
- **Snap counts / advstats 2026.** `snap_counts_2026.csv`,
  `advstats_week_{rec,pass}_2026.parquet` were refreshed through W3
  (Sep 29). All are consumed through strictly-prior-week trailing only.
- **NGS revisions.** Historical NGS rows are taken as current; any
  post-cutoff revisions to 2024–2025 rows are accepted as immaterial noise.

## Data problems found
1. `data/market_props_2026_w{W}.json` contain **no receptions or
   rush_attempts lines at all** (only pass_yards / rush_yards /
   receiving_yards). The market join ran faithfully and matched 0 lines in
   all 6 runs → `market_line` is null for every audit row; model−market,
   over/under-vs-line, and lean grading are all null. The audit grades
   projection-vs-actual only.
2. nflverse has not published per-season 2026 weekly player stats
   (`player_stats_2026.parquet` 404s; the unversioned file ends at 2024),
   and `data/player_games.parquet` has no `receptions` column. Actuals
   were derived from the pulled 2026 pbp (receptions = complete_pass sums,
   the experiment's own recipe; rush attempts excluding `qb_kneel==1`).
   Validation: pbp-derived rush attempts match `player_games.rush_att`
   **100% exactly** (940/940 matched rows, RB subset 233/233).
3. `data/prod_ngs_receiving.parquet` did not exist (the 19 head was never
   run in production — no W4 receptions output exists); the audit is the
   first application of its code path, via fresh keyless pulls.
4. Pre-week ratings files for W1–W3 did not exist (rebuilt; see above).
5. Task's Friday dates were one week early vs the actual schedule (see §1).

## Grading conventions (grade_phase3.py)

- Actuals join: exact `(player, team, week)` first. The spine assigns a
  player's team from their last *predictable* game, so early-2026 team
  changers are projected under their 2025 team (e.g. "A.Brown"/PHI projected,
  actual row on NE). Fallback: a single actuals row for `(player, week)` on
  another team is used and flagged `team_changed:<actual_team>` (4 rows).
  True name collisions (same abbreviated name, multiple teams, same week —
  e.g. D.Moore on BUF and CAR) would be excluded as ambiguous; 0 occurred.
- Projections with no actuals row that week (verified genuinely absent from
  the 2026 pbp, e.g. B.Bowers with zero W1–W2 rows) are graded actual=0 and
  flagged `dnp_no_actual_row` (150 rows: 138 receptions, 12 rush). Aggregates
  are reported both pooled and excl.-DNP; the excl.-DNP cut is the
  apples-to-apples comparison to the locked tests (both required
  `played_role=1`).
- NGS status: `ngs_trail_weeks >= 8` → full; 1–7 → partial; 0 →
  fallback-or-zero (0-filled per the trained convention).
- Opportunity volume: trailing EWMA (hl=3, max 16 games, strictly prior
  weeks) of targets (003A) / rush attempts (003B) from player_games,
  terciled within market × week. For 003A this does not apply the
  predictable-game filter — a slight approximation, analysis only.
- Rookie = first season in player_games == 2026. The frame requires trailing
  history, so no rookies are projected (n=0, degenerate cut, kept for the
  record).
