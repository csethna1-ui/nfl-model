# V2 Research -- Leakage & Timestamp Audit

Walk-forward rule (enforced in scripts/35): every team feature for prediction
week W uses only games with week < W (all prior seasons + current season).
MIN_GAMES = 4 prior games else NaN. No offseason mean reset (expanding
all-history); recency weighting is a modeling-stage decision.

## Per-family assessment

### possession / explosiveness / pressure_pbp / special_teams -- SAFE
PBP aggregates over completed games only. Drive points use in-game score
deltas (no future scores). Explosive thresholds (>=16 pass / >=10 rush,
20+/40+) are fixed constants, not tuned.

### pressure_pfr -- SAFE WITH LAG CAVEAT
PFR weekly files can lag the weekend box scores by ~1 day (known nflverse
issue). Consume in the Tuesday batch, not Monday. Primary-passer proxy:
`times_pressured_pct` taken from the max-`times_pressured` player because
attempts are not published in this file -- documented approximation.
Defense sums are exact team sums.

### player_qb -- MIXED
- `qb_sched` (scheduled starter): pregame-safe.
- `qb_backup_flag` at played-week grain: uses played-week PBP -- safe in the
  source table. The CURRENT-week flag for prediction week W must come from the
  pregame injury report, not PBP -- enforced at modeling stage.
- `qb_value_poll`: 2026-anchored, anachronistic for 2018-2025. Labeled
  limitation; do not interpret historically.

### player_continuity -- SAFE
Prior-season roster from prior-season snap counts; current shares from
completed games only.

### player_availability -- HIGHEST RISK, NEEDS DISCIPLINE
`date_modified` must be strictly before the week's first kickoff. The
week-grain fallback (any Out/Doubtful row that week) can include post-game
updates. Modeling stage must enforce the timestamp filter; the source table
retains `date_modified` for this. Name matching (snap `player` vs injury
`full_name`, lowercased/strip) is fuzzy -- unmatched injuries contribute 0
(conservative).

### matchup -- SAFE
Pure functions of walk-forward-safe components. No new raw data.

### environment -- SAFE EXCEPT WEATHER
Rest/roof/surface/division/gametime are schedule facts. `temp_game`/`wind_game`
are forecasts at pull time -- freeze at prediction time (Tuesday pull
discipline, same as Experiment 006). Travel uses hardcoded stadium coords.

## Timestamp summary for the 2026 timing study
All PBP/PFR/snap features are week-grain and timestampable to the Tuesday
batch. Injury features require row-level `date_modified` discipline. Nothing
in this build consumes Experiment 006 observations.
