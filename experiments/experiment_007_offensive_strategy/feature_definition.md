# Experiment 007 — Feature Definition (preregistered)

All definitions locked in `config.json` before any validation computation.
No tuning after results.

## Candidate family: offensive strategy (ONLY)

Three team-level pregame ratings, each expressed as **home − away differential**.

### 1. PROE — offensive pass rate over expected
- Source: nflfastR `pass_oe` column in PBP.
- Play filter: `posteam == team`, `down ∈ {1,2,3}`, `pass_oe` not null.
- (4th down excluded: `pass_oe` is ~80% null on 4th down in this data.)
- Aggregation: pooled mean over qualifying plays.

### 2. Early-down behavior — early-down pass rate
- Definition: `P(play_type == 'pass')` on 1st and 2nd down.
- Play filter: `posteam == team`, `down ∈ {1,2}`, `play_type ∈ {'pass','run'}`.
- `qb_kneel` / `qb_spike` are separate `play_type` values and are excluded by the filter.
- No score / win-probability filter (locked simple definition).

### 3. Pace — seconds per play
- Definition: mean seconds elapsed between a team's consecutive offensive plays.
- Procedure: within each game, sort the team's plays by `play_id`; elapsed =
  `game_seconds_remaining[i] − game_seconds_remaining[i+1]`; keep diffs in (0, 40].
- The (0,40] window removes timeouts, quarter breaks, possession changes, halftime.
- Play filter: `posteam == team`, `play_type ∉ {'kickoff','punt','field_goal','extra_point','no_play'}`.
- Higher value = slower pace. No sign assumption preregistered; the ridge learns it.

## Pregame construction (all three)

- For a prediction game in week W of season S: pooled mean over the team's
  qualifying plays from games with `week < W` in season S (weekly batching).
- Minimum 2 completed games; otherwise the team value is treated as league
  average → the differential is set to 0.
- Offseason hard reset: no cross-season carryover.
- Equal weight per qualifying play.
- Week-1 games therefore have all-zero differentials (5.8% of validation rows).

## Explicitly excluded from 007

Explosiveness, pressure, QB EPA/CPOE/form, injuries, weather, special teams,
travel, matchup-interaction features, market variables, ATS-derived variables,
`actual_margin`, `market_spread`, any postgame information, and all 2026
Experiment 006 observations.
