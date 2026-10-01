# props.json schema — Player Projection v2

The weekly engine (`scripts/16_prod_player_projection.py
--season S --week N`) writes `data/prop_v2_S_wN.json`; the exporter
(`scripts/15_export_ui_json.py`) copies its substance to
`data/ui_json/v1/props.json` with the model label intact. This file is
the field-by-field reference. Every row is validated against this schema
by the engine before it writes.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `model` | string | Always `"Player Projection v2 — Experimental Production"` |
| `season` | int | e.g. 2026 |
| `week` | int | e.g. 4 |
| `prediction_timestamp` | string | ISO timestamp of the Friday 18:00 America/Chicago cutoff. All trailing features use games strictly before this; games kicking off at/before it are excluded. |
| `generated_at` | string | ISO timestamp of when the file was produced |
| `disclaimer` | string | Experimental / no-verified-edge / paper-tracking-only language. Always present. |
| `experiment_provenance` | object | Frozen provenance: experiment name, preregistration + results doc pointers, the model recipe (D = equal-weight A/B/C; fit train 2018–2020, select dev 2021–2022; test never touched; PFT/news OFF) |
| `markets` | list[string] | `["pass_yards", "rush_yards", "receiving_yards"]` |
| `n_projections` | int | Equals `len(projections)` |
| `projections` | list[object] | One object per eligible player-market, sorted by (market, player) |

## Projection row

| Field | Type | Meaning |
|---|---|---|
| `player` | string | Player name as in nflverse (e.g. `"Josh Allen"`) |
| `team` | string | Player's most recent team abbreviation |
| `opp` | string | Opponent team abbreviation for the week's game |
| `market` | string | One of `pass_yards`, `rush_yards`, `receiving_yards`. Determined by position (QB / RB / WR-TE) from the most recent season with ≥3 games. |
| `projection` | number | **The** projection: Model D = (A + B + C-median)/3, rounded to 0.1 |
| `median` | number | Model C median (p50), rounded to 0.1 |
| `p25` | number | Model C 25th percentile, rounded to 0.1 |
| `p75` | number | Model C 75th percentile, rounded to 0.1. Monotonicity enforced: p25 ≤ median ≤ p75 |
| `confidence` | string | `High` / `Medium` / `Low` — from the Model C relative range width vs dev-calibrated 33rd/67th percentile cutoffs, per market |
| `why` | object | Explanation block (below) |
| `baseline_ewma` | number | EWMA (half-life 3) trailing-yards benchmark — the experiment's baseline, kept as comparison |
| `uncertainty_flag` | bool | true when relative width `(p75−p25)/max(median,1)` exceeds the market's dev 90th percentile |
| `uncertainty_note` | string \| null | When flagged: plain-language note naming the primary uncertainty driver by a fixed heuristic (player opportunity vs production efficiency); otherwise null |
| `market_line` | object \| null | Market-line block (below), or null when no line was captured for this player-market. **No line → no lean; the projection is still published.** |
| `prediction_timestamp` | string | Same Friday 18:00 CT cutoff as the top level |
| `trailing_games` | int | Number of trailing games behind the projection (3–16) |

## why block

Rule-based, from trailing/pre-kickoff data only. Fixed cutoffs — nothing
here is fit or tuned.

| Field | Type | Meaning |
|---|---|---|
| `expected_opportunities` | number | Model A stage-1: expected opportunity volume |
| `opportunity_unit` | string | `pass attempts` / `carries` / `targets` (by market) |
| `expected_efficiency` | number | Model A stage-2: expected yards per opportunity |
| `efficiency_unit` | string | `yards/attempt` / `yards/carry` / `yards/target` (by market) |
| `recent_usage_note` | string | Last-3 opportunity mean vs trailing EWMA: `elevated` (>1.15×), `reduced` (<0.85×), `stable` |
| `team_environment` | string | Team implied total vs the week's league average: `favorable` (≥+2), `unfavorable` (≤−2), `neutral` |
| `opponent_adjustment` | string | Opponent's trailing allowed (market-relevant stat: pass_allowed for pass/receiving markets, rush_allowed for rush) vs league average: `favorable` (>1.10×), `tough` (<0.90×), `neutral` |

## market_line block (null when no line)

Projection → line → lean is kept separate: projections are computed
without ever seeing the line.

| Field | Type | Meaning |
|---|---|---|
| `line` | number | The captured market line |
| `source` | string | Where the line was captured (e.g. `"DraftKings"`); `"unknown"` only for legacy files |
| `captured_at` | string \| null | ISO timestamp of the capture. **Recorded on every new capture** — this is what fixes the historical timestamp gap going forward. |
| `difference` | number | `projection − line`, rounded to 0.1 |
| `lean` | string | `over` if difference > 0 else `under`. **A lean is not an edge and not a bet recommendation** — paper-track only, no +EV claims. |

## Market-line input schema

`data/market_props_2026_wN.json` (populated by the Friday researcher) is a
JSON list of `{player, market, line, source, captured_at}`. Same three
market values. `source` and `captured_at` are required on new captures;
the engine tolerates their absence (fills `"unknown"` / null) but that is
a gap to close, not a norm.

## Eligibility (what gets a row)

A row exists for every eligible player-market of the week's remaining
games (kickoff after the timestamp), whether or not a market line was
captured. Eligible = trailing history ≥ 3 games AND trailing role volume
≥ 10 pass attempts / 5 rush attempts / 5 targets (the experiment's guards).
