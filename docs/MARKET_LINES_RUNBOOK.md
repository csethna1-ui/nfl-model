# Market Lines — Hourly Capture Runbook

Paper tracking only. This pipeline captures market lines on a schedule; it
never places bets, never claims an edge, and never modifies models,
predictions, experiments, or research artifacts.

## Source

Keyless public endpoints only — no API key, no signup, no card details.

**Game lines (spread + total), two books per snapshot:**
- ESPN public scoreboard API (`http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`)
  — DraftKings odds, no fingerprinting, 16/16 games with odds (verified
  2026-10-01). Recorded under book name `draftkings`.
- Bovada public unauthenticated JSON coupon API
  (`https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl?preMatchOnly=true&lang=en`)
  — via curl (urllib gets fingerprinted). Throttles bursts with empty `{}`
  responses. Recorded under book name `bovada`.

**Player props:** Bovada only (PrizePicks/Underdog/DraftKings block automated
access — verified 2026-10-01). Captures Passing/Rushing/Receiving Yards plus
Receptions, Rush Attempts, Pass Attempts, Completions, and Anytime TD whenever
Bovada offers them. Markets not offered are listed in `markets_not_offered` —
recorded absent, never fabricated.

Known quirks:
- Bovada throttles bursts: the script uses 3 tries / 20s backoff (no retry
  storms). A throttled run writes a snapshot recording the throttle.
- Bovada posts props for only a subset of games. Games/players without posted
  props get no lines — never imputed.
- Prop player matching is conservative: (team, last name, market) with
  first-initial disambiguation; ambiguous → null, never a guess.

## Cadence

- Cron `nfl-market-lines-hourly`: every hour, year-round.
- The script no-ops cleanly (exit 0, nothing written) when neither source
  returns a pregame event (offseason / between slates).
- The legacy Friday pipeline is unchanged: `30_pull_prop_lines.py` still
  writes `data/market_props/market_props_{season}_w{week}.json` and the Friday
  cron order (16 → 30 → 15) is untouched.

## File layout (append-only, never overwritten)

```
data/market_hourly/
  game_lines/game_lines_{season}_w{week}_{utcstamp}.json   # utcstamp=YYYYMMDDTHHMMSSZ
  prop_lines/prop_lines_{season}_w{week}_{utcstamp}.json
```

Game snapshot: `{season, week, captured_at, status, sources: {espn_draftkings:
{status, n_games, error}, bovada: {...}}, convention, n_games, games:
[{away, home, game_key: "AWAY_HOME", books: {draftkings: {spread_home, total},
bovada: {...}}}]}`. `spread_home` follows the existing convention (+ means
home favored), matching `data/market_2026_wN.json`.

Prop snapshot: `{season, week, captured_at, status, source, markets_offered,
markets_not_offered, n_lines, n_matched, lines: [{player|None, bovada_player,
team, market, line, line_type: "handicap"|"odds", source, captured_at}]}`.
Anytime TD lines are the American price on Yes (`line_type: "odds"`), not a
handicap.

## Failure behavior

| Situation | Outcome |
|---|---|
| Bovada throttled | Snapshot written with `status: "throttled"` (props) or per-book status (games); run continues on ESPN. Auditable, not silent. |
| ESPN down | Game snapshot records `espn_draftkings: failed`; Bovada games still captured if reachable. |
| No pregame events anywhere | Exit 0, nothing written ("NO-OP"). |
| Unexpected internal error | Non-zero exit; cron reports it. |

"Latest" selectors (`scripts/market_lines_latest.py`) skip non-successful
snapshots, so a throttled hour never blanks live display lines.

## Friday 18:00 CT cutoff interaction

The hourly stream does **not** change the evaluation cutoff
(docs/PROSPECTIVE_PROTOCOL.md). For evaluation, select the newest
*successful* snapshot at or before the cutoff:

```python
from market_lines_latest import snapshot_at_or_before
snap = snapshot_at_or_before("game_lines", 2026, 4, "2026-10-02T18:00:00-05:00")
```

The dashboard exporters (`15_export_ui_json.py`, `18_export_experimental_markets.py`)
read the **latest successful** snapshot for *display* lines only:
- Props: `market_line` joins from the latest hourly prop snapshot, falling
  back to the legacy Friday file when no hourly snapshot succeeded yet.
- Games: additive `market_spread_live` / `market_total_live` /
  `market_live_books` per game plus top-level `market_lines_captured_at`.
  Friday `market_spread` / `edge` / picks are untouched.

## How to verify a capture ran

1. `ls -t data/market_hourly/game_lines/ | head -3` — newest file should be
   within the last hour during the season.
2. Check its `sources` block: both books' statuses, `n_games`, and any
   `error`/`notes`.
3. `venv/bin/python scripts/market_lines_latest.py 2026 4` — prints latest
   snapshot summary.
4. After an export, `data/ui_json/v1/predictions.json` carries
   `market_lines_captured_at`; `props.json` / `experimental_markets.json`
   carry `market_lines_source` / `market_lines_captured_at`.

## Scripts

- `scripts/31_pull_market_lines_hourly.py` — the hourly capture (game lines +
  prop lines, both books, week auto-detected from `data/games.csv`).
- `scripts/market_lines_latest.py` — read helpers: `latest_snapshot`,
  `snapshot_at_or_before` (Friday-cutoff selector),
  `latest_game_lines_by_book`, `latest_prop_lines`.
- `scripts/30_pull_prop_lines.py` — legacy Friday prop pull (unchanged).
