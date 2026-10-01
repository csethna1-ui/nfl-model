# Player-Stat Projection — Data Inventory (audit only, 2026-09-30)

Scope: inventory for a possible separate research branch on NFL player-stat
projection (underlying player props). NO modeling authorized. V1, Experiment 006,
the spread vault, and the PFT corpus were not touched.

---

## 1. What the current prop section produces

`scripts/10_prop_projector.py` produces **both** point projections and picks:

- **Point projection** (`projection` column, e.g. 199.5 pass yards): trailing
  exponentially-weighted per-game yards (half-life 3 games, same season then
  prior season, max 16 games; shrink toward positional mean if <3 games) plus a
  matchup adjustment (opponent's trailing defensive yards allowed vs league
  average, coefficient FIT by OLS on 2018–2024 residuals, cached in
  `data/prop_matchup_betas.json`; R² 0.1–0.8% — negligible, kept for
  completeness).
- **Pick** (`lean` column, "over"/"under"): sign of `projection − line`.
  Output CSV is sorted by |gap|, i.e. it ranks picks by gap size.

Inputs: `data/market_props_<season>_w<week>.json` — hand-built list of
`{"player","market","line"}`. Three markets only: `pass_yards`, `rush_yards`,
`receiving_yards`. **There is no receptions market and no receptions projection.**

Outputs: `data/prop_gaps_<season>_w<week>.csv` (columns: player, matched_as,
team, opp, market, line, projection, gap, lean, trailing_games, match_note);
latest week exported to `data/ui_json/v1/props.json` for the dashboard.

Method documented in `backtest_report.md` §"Player prop projector v1".
Standing rules there: gaps are paper-tracked only; no ROI/edge claims; gaps
< ~0.5× market MAE treated as noise.

## 2. Historical prop outputs (timestamp / leakage audit)

| File | Rows | File mtime (proxy for run time) | Timestamps inside? |
|---|---|---|---|
| `data/prop_gaps_2026_w1.csv` | 36 | 2026-09-11 19:57 | No |
| `data/prop_gaps_2026_w2.csv` | 16 | 2026-09-18 23:32 | No |
| `data/prop_gaps_2026_w3.csv` | 12 | 2026-09-25 02:57 | No |
| `data/market_props_2026_w4.json` | 0 (`[]`) | 2026-09-25 23:42 | No — week 4 run produced nothing |
| `data/ui_json/v1/props.json` | 12 | — | No; re-export of week 3 |

- **No prediction timestamps** in any prop file. Run time is recoverable only
  from file mtimes (Friday runs).
- **No market-line capture timestamps.** The market JSONs carry only
  player/market/line — no source, no capture time, no open vs close.
- **Leakage status of the projections themselves: clean.** `trailing()` uses
  rows strictly before (season, week); Friday lines are for weekend games.
  But there is no auditable record proving *when* a given line was captured.
- **Prop leans have never been graded.** `scripts/08_grade_week.py` contains no
  prop code; `data/record.csv` is spread-picks only. Nothing compares a past
  `lean` to the player's actual yards.

## 3. Market-line availability for props (historical)

- **Only 2026 weeks 1–3** have prop lines, hand-researched each Friday by the
  weekly worker (single snapshot; source unrecorded). Week 4's file is empty.
- **No open/close, no line movement, no timestamps.**
- **Zero historical prop lines before 2026.** Consequence, stated in
  `backtest_report.md`: the pick side (over/under vs line) **cannot be
  backtested** — only projection accuracy (MAE/corr vs actual yards) is
  measurable historically. Any future study must evaluate projections, not picks.

## 4. Candidate data inventory (nflverse, keyless)

Already cached locally:

- `data/player_games.parquet` — 44,670 player-games, 1,600 players, 2018–2026.
  Columns: player_name, team, opponent, season, week, game_id, pass_yards,
  pass_att, rush_yards, rush_att, receiving_yards, **targets** (no receptions),
  touches, position (QB/RB/WRTE from touch mix).
- `data/team_defense.parquet` — 4,458 team-games of pass/rush allowed.
- `data/pbp_players_*.parquet` — slim 13-column cache (no routes, snaps,
  air yards, YAC, red-zone flags). Full nflverse pbp is re-pullable keyless via
  `scripts/pull_pbp_players.py` (extend the `WANT` column list).
- `data/schedules_2018_2025.parquet` (covers 2018–2026): `spread_line`,
  `total_line` (closing lines — known pre-kickoff, usable as game-script
  features), **`temp`, `wind` are game-time observations, not forecasts** —
  using them as features is mild leakage; true pre-game work needs forecast
  vintages (not cached).

Not available (would need new pulls or sources):

- Receptions (derivable from full pbp `complete_pass`; not in slim cache).
- Routes run, snap shares/counts (nflverse snap-counts dataset; not cached).
- Red-zone usage (derivable from full pbp; not cached).
- Weather *forecasts* as of prediction time (not cached).
- Historical prop lines at any timestamp (do not exist in repo; no keyless
  source identified).

## 5. Recommended experiment design (for future authorization — not started)

Splits: **2018–2020 train / 2021–2022 dev / 2023–2024 locked test.**
Caution on the obvious alternative (2023–2025): the current projector's
diagnostics were already reported on **2025** (table below), and its matchup
betas were fit on 2018–2024. Re-using 2025 as a "locked" test would be
re-reading spent data. If the user insists on 2023–2025, the current system's
row must be labeled already-seen.

Evaluation: walk-forward MAE of point projections vs actual yards, graded only
on games where the player actually played the role (books void the rest —
same `ELIGIBLE`/`ACTUAL_MIN` guards as the current script). Report per market.

MAE table skeleton (current-system row filled from the documented 2025 holdout):

| Model | Pass Yds MAE | Rush Yds MAE | Rec Yds MAE | Receptions MAE |
|---|---|---|---|---|
| Current system (10_prop_projector.py) | 63.1 (n=566) | 25.4 (n=1031) | 22.5 (n=2535) | n/a — no market/projection |
| Simple baseline (trailing avg / naive last-3) | — (ref: 69.3) | — (ref: 27.3) | — (ref: 24.3) | — |
| GBM | — | — | — | — |
| Simulation / distribution | — | — | — | — |
| Ensemble | — | — | — | — |

(Reference naive last-3 MAEs from the same 2025 holdout: 69.3 / 27.3 / 24.3.)

Context from `backtest_report.md`: week-to-week yardage lag-1 autocorrelation is
0.17–0.25; the current projector achieves corr 0.30–0.44 — roughly the
available signal. Expect small gains; most big misses are playing-time events
(benchings/injuries), which no yards model captures.

## 6. Honest gaps for a fair comparison

1. **Picks can't be validated historically** — no prop lines before 2026. The
   study can only compare projection MAE, never over/under hit rates or ROI.
2. **Receptions has no current-system baseline** — the existing projector
   doesn't cover it; a receptions column would compare only new models.
3. **Opportunity-model inputs are partial**: targets and attempts exist;
   target *share*, routes, snap share, red-zone usage do not (re-pullable from
   nflverse except routes, which nflverse pbp lacks entirely).
4. **Weather must be forecast vintages**, not the observed temp/wind in
   schedules — otherwise the "weather" feature leaks game-time information.
5. **Sample sizes are modest** for QB markets (n=566 pass-yard games in the
   2025 holdout); year-to-year MAE comparisons will be noisy — pre-register
   minimum-n and a noise threshold before any verdict.
6. **2025 is spent** for the current system (diagnostics published); keep it
   out of any locked test or label it accordingly.
