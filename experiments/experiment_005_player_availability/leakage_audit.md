# Experiment 005 — Leakage Audit

## Construction (all verified in `scripts/21_experiment_005_availability.py`)

1. **One row per player-week.** nflverse `import_injuries()` returns a single row per
   (season, week, team, player) with one final `report_status` (verified 2026-09-29:
   zero player-weeks with multiple distinct statuses). No within-week status
   transitions to resolve; no practice-status oscillations used.
2. **Strictly pregame cutoff.** For each game, `T = min(kickoff, Friday 12:00 America/New_York
   of game week)`. Kickoff from `schedules_2018_2025.parquet` (gameday + gametime, ET).
   Only rows with `date_modified < T` (UTC) are kept. Post-kickoff designations
   (the ~0.14% noted in Exp 004) are dropped by construction. Thursday games are
   bounded by kickoff, not Friday noon.
3. **Non-QB only.** All `position == 'QB'` rows excluded — no overlap with the 2026
   production stale-QB void filter and no double-counting of v2's failed QB feature.
4. **No market features.** The injury layer never sees `market_spread`, closing lines,
   or any line movement.
5. **V1 frozen.** `v1_margin` is read from the experiment dataset, never recomputed or tuned.
6. **Cross-fit discipline.** Each validation game's injury adjustment comes from a ridge
   fit on the *other* season's V1 residuals only (2021→2022, 2022→2021). No game is
   predicted by a model trained on its own season.
7. **Vault isolation.** The script asserts `season <= 2022` on load; 2023–2025 data was
   never read. Zero vault evaluations.

## Residual risks — all mitigated

| Risk | Status |
|---|---|
| Final designation known after Friday-noon prediction time | Eliminated by `date_modified < T` hard filter |
| Retroactive corrections to injury files | `date_modified` reflects report modification; post-cutoff rows dropped |
| Game-day inactives (90 min pre-kickoff) | Excluded — postdates the Friday prediction time by design |
| QB double-count | QB positions excluded entirely |
| Questionable noise | Included as preregistered; coefficients estimated, not assumed |
| Same-season training leakage | Eliminated by season cross-fit |
