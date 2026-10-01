# Experiment 004 — Phase 1: Information Timeline Audit

Diagnostic only. No model fitted. Vault untouched.

## Model side: what V1 knew and when

V1's prediction inputs and their information timestamps (verified in code, `scripts/03_ratings.py`):

| Input | Update cadence | Information state for a week-N game | Exact timestamp stored? |
|---|---|---|---|
| ELO ratings | Weekly batch: all week-N games use pre-week ELO; updates applied after the week's games | Through week N−1 final whistle (~Mon/Tue before week N) | No — implied by batching |
| EPA / success-rate ratings | Weekly EWMA (α=0.25); pre-week ratings attached, updated after | Through week N−1 | No — implied by batching |
| GBM features | Same pre-week rating snapshot, expanding-history refit | Through week N−1 | No |
| Rest differential | Schedule-derived (`home_rest`, `away_rest` in games.csv) | Known preseason (schedule release) except flexed games | No |
| Division flag | Schedule-derived | Known preseason | No |
| QB injury news | **Not in V1 historically.** 2026 production only: `scripts/11_injury_adjust.py` voids picks on unexpected Out/Doubtful QB changes (conservative, void-only) | n/a historically | n/a |
| Non-QB injuries | **Not in V1 at all** | n/a | n/a |
| Weather | **Not in V1.** (v2 tested wind historically: measurable on totals, no spread signal; totals never bet) | n/a | n/a |
| Line movement | **Not in V1** | n/a | n/a |

Two structural notes:
1. **No within-week updating.** Thursday-night results do not refresh ratings for the same week's Sunday games (weekly batching). Minor staleness, uniform across history.
2. **The model's effective information timestamp is ~Tuesday morning of game week** — everything it knows was knowable after the previous week's games. It knows nothing that happened Wed–Sun of game week.

Classification for every historical game: model information state is **well-defined but not timestamped** (implied by weekly batching, not recorded).

## Market side: what the spread_line snapshot is

`spread_line` in `data/games.csv` (nflverse schedules):

| Property | Finding |
|---|---|
| Observations per game | Exactly one. No line history, no timestamps, no source book identified |
| nflverse documentation of timing | **None found.** The field is undocumented as to snapshot (open vs close vs consensus) |
| This repo's own description | **Internally inconsistent:** `backtest_report.md:65` says "likely consensus/opening"; `scripts/08_grade_week.py:68` and `scripts/15_export_ui_json.py:78` call it a "close proxy"; `scripts/16_build_experiment_dataset.py` stamps `line_provenance='nflverse_proxy_open'` |
| Independent external measurements | One third-party analysis measured nflverse `spread_line` against captured lines: 68.1% exact match to the captured **close** (mean abs gap 0.196) vs 24.7% match to the captured **opener** (gap 0.998). A second third-party design doc describes nflverse schedules as including "closing spread, total, moneyline" |
| Verdict | **Unverified.** Evidence leans close/consensus, contradicting this repo's "opening proxy" working assumption — but neither is documented by nflverse |

Companion columns exist (`away_moneyline`, `home_moneyline`, `away_spread_odds`, `home_spread_odds`, `total_line`) — same single-snapshot, no-timestamp limitation.

## Comparison classification

| Game set | Model info state | Market snapshot | Classification |
|---|---|---|---|
| All historical games (2018–2025) | Post-week-N−1 (~Tue AM), implied | Unknown timestamp, unverified provenance | **Timestamp unknown** |
| 2026 live weeks | Friday-morning research (model run + `market_2026_wN.json` lines + `qb_news` all researched Friday AM) | Friday AM researched line; CLV vs nflverse close proxy | **Timestamp aligned** (Friday AM state, documented in pipeline) |

Per the task rules, alignment is **not inferred** where timestamps are unavailable: every historical comparison is classified **timestamp unknown**.

## The central timing finding

If the historical market snapshot is close-ish (as the external evidence suggests), the comparison being run in every backtest is:

- **V1:** Tuesday-morning information (team performance through last week, no week-of-game news)
- **Market:** ~Sunday-morning information (includes Wed–Fri injury news, weather forecast updates, late sharp action, final roster clarity)

That is a **4–5 day information gap**, not a modeling gap. Three failed architecture experiments (residual, opponent-adjusted EPA, dynamic strength — the last with 0.985 error correlation to V1) are consistent with this: you cannot represent your way out of information you never had.
