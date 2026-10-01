# Prop Market Lines — Runbook

Real sportsbook prop lines (pass/rush/receiving yards) joined onto the
Player Projection v2 export so the dashboard can show projection vs market
and line gaps. Paper tracking only; no edge is claimed.

## Source

Bovada's public, unauthenticated JSON coupon API — no signup, no API key, no card:

    https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl?preMatchOnly=true&lang=en

Only the main Over/Under total per player is used (market key `2W-OU`,
"Total {Passing|Rushing|Receiving} Yards - {Name} ({TEAM})"); alternate lines
are excluded. The line recorded is the Over handicap.

Known quirks:
- DraftKings/FanDuel block datacenter IPs (bot protection); Bovada does not.
- Bovada throttles bursts with empty `{}` responses — the script retries with
  backoff. urllib gets fingerprinted; the script shells out to curl.
- Bovada typically posts props for only a subset of games (8 of 16 for Week 4).
  Games without posted props get no lines — never imputed.

## Scripts

- `scripts/30_pull_prop_lines.py --season 2026 --week N`
  Pulls the coupon, parses main lines, matches players to our prop-export ids
  on (team, last_name, market) with first-initial disambiguation; ambiguous
  matches are left null, never guessed. Writes
  `data/market_props/market_props_{season}_w{week}.json` and REFUSES to
  overwrite an existing file. Each line records
  `{player, market, line, source, captured_at}` with the real pull timestamp.
- `scripts/15_export_ui_json.py` joins `market_line` from that file into
  `props.json` at export time (null where no line exists). Also stamps
  `market_lines_source` / `market_lines_captured_at` on props.json.

## Friday cron order

1. `16_prod_player_projection.py` (projections)
2. `30_pull_prop_lines.py --week N` (market lines)
3. `15_export_ui_json.py` (export joins them)

## What the dashboard shows

- `market_line` populated → projection vs line and gap.
- `market_line` null → "projection-only" card. This is honest: it means no
  line was captured for that player-market (game not posted, player not listed,
  or ambiguous match), not that the line doesn't exist somewhere.
