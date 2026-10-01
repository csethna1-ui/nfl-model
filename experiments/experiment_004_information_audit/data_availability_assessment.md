# Experiment 004 — Data Availability Assessment

All sources below are free and keyless (no API keys, no card-gated services).

## Verified working (probed 2026-09-29)

| Source | Access | Coverage | Grain | Timestamps? |
|---|---|---|---|---|
| nflverse `load_injuries()` | nflreadpy (pip-installable; installed into project venv for probing) | 2009–present claimed; 2021–2022 verified (11,269 rows) | Weekly, per player | Yes — `date_modified` UTC, zero nulls |
| nflverse schedules (`spread_line`, moneylines, totals) | local `data/games.csv` | 2018–2025, 100%, zero nulls | One snapshot per game | **No** |
| nflverse pbp | local `data/pbp_*.parquet` | 2018–2025 | Per play | Game date only |
| games.csv weather (`temp`, `wind`, `roof`, `surface`) | local | temp/wind 55.9% (outdoor games), roof 98.3% | Game-time observed | Game date only |

## Documented available (not probed; standard nflverse releases)

| Source | Coverage | Notes |
|---|---|---|
| `load_rosters_weekly()` | 1999– | Active/inactive by week |
| `load_depth_charts()` | 2001– | Weekly positional depth |
| `load_snap_counts()` | 2012– | Per-game snaps (PFR-sourced) |
| `load_player_stats()` | 1999– | Weekly box + advanced |
| Open-Meteo | 1940– (ERA5) + 16-day forecast | Keyless, 10k calls/day — forecast-vintage weather if needed |

## To verify before any predictive experiment

1. `load_injuries()` coverage for 2018–2020 and 2023–2025 (only 2021–2022 probed; one third-party note claims post-2024 gaps — re-verify, do not assume).
2. Whether `date_modified` semantics are stable across seasons (report-modification time vs file-generation time).
3. Join keys: `gsis_id` → weekly rosters for team assignment of injured players.

## Unavailable under the constraint

- Timestamped historical betting lines (openers, intraday moves): no free/keyless source. Single undated nflverse snapshot is all that exists.
- Real-time injury news wire: ESPN/Sleeper endpoints exist but are current-only, fragile, unofficial — fine for the live Friday pipeline, not for historical reconstruction.
