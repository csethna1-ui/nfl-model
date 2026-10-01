# Modeling Table — Data Dictionary

`data/modeling_table.parquet` — Player Projection Experiment 001.
Built by `scripts/build_modeling_table.py`. **Data prep only; no model was fit.**

Grain: one row per (player, season, week, market) for the player's primary
role-market pair: QB → `pass_yards`, RB → `rush_yards`, WR/TE → `receiving_yards`.
Regular season only, 2018–2024. Games kicking off at or before the prediction
timestamp are excluded (Thursday games, the 2024 Brazil Friday game is kept —
it kicked off after the timestamp; rescheduled odd-weekday games).

## Identity / metadata

| Column | Meaning |
|---|---|
| `player_name` | nflverse player name (e.g. `J.Allen`) |
| `team` | player's team that game |
| `opponent` | opposing team |
| `season`, `week` | NFL season / week |
| `game_id` | nflverse game id |
| `position` | `QB` / `RB` / `WRTE` (season touch-mix, same rule as the current projector) |
| `market` | `pass_yards` / `rush_yards` / `receiving_yards` |
| `kickoff_et` | kickoff, America/New_York ISO |
| `prediction_timestamp` | Friday 18:00 America/Chicago of game week, ISO with offset |
| `period` | `train` (2018–2020) / `dev` (2021–2022) / `test` (2023–2024) |
| `eligible_hist` | trailing history meets the role guard (≥3 games AND trailing pass_att≥10 / rush_att≥5 / targets≥5 — mirrors the current projector's `ELIGIBLE`) |
| `played_role` | the actual game meets the grading guard (pass_att≥10 / rush_att≥5 / targets≥3 — mirrors `ACTUAL_MIN`; books void the rest) |
| `actual_yards` | target: actual yards in the market |
| `actual_att` | actual attempts/targets in the market (for the `played_role` guard) |
| `trail_games` | number of trailing games used (0–16) |

## Opportunity features — stage 1 (all trailing EWMA, half-life 3, max 16 games, strictly prior season/week)

| Column | Meaning |
|---|---|
| `trail_targets_ewma` | expected targets/game |
| `trail_rush_att_ewma` | expected carries/game |
| `trail_pass_att_ewma` | expected pass attempts/game (QB) |
| `trail_target_share_ewma` | player targets ÷ team targets |
| `trail_rush_share_ewma` | player carries ÷ team carries |
| `trail_air_share_ewma` | player air yards ÷ team air yards |
| `trail_team_targets_ewma` | team targets/game (passing volume environment) |
| `trail_team_pass_att_ewma` | team pass attempts/game |
| `trail_team_rush_att_ewma` | team rush attempts/game |
| `trail_rz_targets_ewma` | red-zone targets/game (line of scrimmage ≤ 20 yds to goal) |
| `trail_rz_carries_ewma` | red-zone carries/game |
| `trail_air_yards_ewma` | air yards/game |

## Efficiency features — stage 2 (same trailing convention)

| Column | Meaning |
|---|---|
| `trail_ypt_ewma` | yards per target |
| `trail_ypc_ewma` | yards per carry |
| `trail_ypa_ewma` | yards per pass attempt |
| `trail_comp_rate_ewma` | completions ÷ attempts |
| `trail_yac_pt_ewma` | yards after catch per target |
| `trail_pass_yards_ewma` / `trail_rush_yards_ewma` / `trail_receiving_yards_ewma` | trailing yards/game in the market (the current projector's signal) |

## Opponent (trailing EWMA, strictly prior weeks)

| Column | Meaning |
|---|---|
| `opp_trail_pass_allowed_ewma` | opponent's trailing passing yards allowed/game |
| `opp_trail_rush_allowed_ewma` | opponent's trailing rushing yards allowed/game |

## Game environment (all known pre-kickoff)

| Column | Meaning |
|---|---|
| `spread_line` | nflverse closing spread; **positive = home team favored** (verified) |
| `total_line` | nflverse closing total |
| `is_home` | 1 if player's team is home |
| `team_spread` | spread from the player's-team perspective (negative = team favored) |
| `team_implied_total` | `total_line/2 − team_spread/2` |
| `opp_implied_total` | `total_line/2 + team_spread/2` |

## Leakage and missing-data notes

- **Weather excluded entirely.** `temp`/`wind` in nflverse schedules are
  game-time observations, not forecasts — using them would leak.
- **Closing lines are legitimate features**: known before kickoff, usable as
  game-script proxies.
- **Trailing windows use strictly prior (season, week)** — no within-week
  information. Thursday games of the current week are excluded from both rows
  and trailing inputs (conservative; documented simplification).
- **NaN → 0** for rate/share trailing features (undefined = no opportunity);
  `trail_games` records how much history existed. Models must handle
  thin-history rows via `trail_games`, not by assuming the zeros are real.
- **Test-slice blindness**: validation checks (nulls, ranges, merge rates,
  share bounds) were run on train+dev only. The 2023–2024 slice was built by
  identical code without inspection.
- **2025 excluded**: the current system's 2025 diagnostics are published, so
  2025 cannot serve as a clean test. Reference numbers live in INVENTORY.md.
- **Not available**: routes run, snap counts/shares (nflverse has a separate
  snap-counts dataset, not pulled); weather *forecasts* as of Friday 18:00 CT;
  historical prop lines at any timestamp. Receptions are derivable from the
  rich pbp cache (`complete_pass` on receiver plays) but no receptions market
  is defined in this protocol version.
