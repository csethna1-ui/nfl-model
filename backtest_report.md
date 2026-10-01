# NFL Prediction Model — Backtest Report

**Built:** 2026-09-11 | **Data:** nflverse 2018–2025 (2,229 games) | **Method:** walk-forward, no lookahead

## Bottom line up front

**No verified betting edge.** The ensemble does not beat the market spread:

- At the validation-chosen operating threshold (|model − market| ≥ 3.0):
  - **Validation (2021–2022):** 53.9% ATS (103–88, n=191), ROI **+2.9%** at -110
  - **Test (2023–2025):** 52.8% ATS (140–125, n=265), ROI **+0.9%** at -110
- 52.8% on n=265 has a standard error of ±3.1% — the 52.4% breakeven line is inside the noise. The validation→test decay (+2.9% → +0.9%) is the classic signature of threshold overfitting.
- **The market's own spread predicts final margins better than the model does** (test MAE: market 9.79 vs model 10.22). If your model can't out-predict the line, it can't beat the line.
- **Totals: do not bet.** Negative ROI at every threshold on validation (−11.6% to −14.1%) and test (−6.7% to −8.5%). The totals component is reliably −EV, so `week1_predictions.csv` marks every total as "no play."

This is the expected outcome, and it's why we backtested: academic work is unanimous that NFL spreads are extremely efficient. A sophisticated model losing to the market is the norm, not a bug.

## Which approach won

Ensemble of three margin components, weights tuned by MAE on the 2021–2022 validation window:

| Component | Weight | Val MAE |
|---|---|---|
| ELO → margin (linear, fit 2018–2020) | 0.4 | 10.20 |
| EPA ratings → margin (linear, fit 2018–2020) | 0.5 | 10.15 |
| Gradient boosting on efficiency differentials | 0.1 | 10.46 |
| **Ensemble** | — | **10.04** |

The honest surprise: **the gradient booster added almost nothing.** On ~270 games/season, simple linear models on ELO + EPA differentials beat it. The GBM got 0.1 weight because that's all it earned. (Implementation note: xgboost would not compile in this environment, so sklearn's `HistGradientBoostingRegressor` was used — methodologically equivalent gradient-boosted trees, same modest hyperparameters. Given its 0.1 weight, this substitution does not move any conclusion.)

Totals ensemble (also by validation MAE): EPA-linear 0.8 + GBM 0.2 → val MAE 11.28. Still −EV against the market, so it's benched.

## Full backtest tables

**Spreads vs market** (pushes excluded, -110 both sides):

| Edge threshold | Validation (2021–22) n | W–L | Win% | ROI | Test (2023–25) n | W–L | Win% | ROI |
|---|---|---|---|---|---|---|---|---|
| ≥1.5 | 373 | 195–178 | 52.3% | −0.2% | 533 | 265–268 | 49.7% | −5.1% |
| ≥2.0 | 306 | 160–146 | 52.3% | −0.2% | 438 | 221–217 | 50.5% | −3.7% |
| ≥2.5 | 246 | 132–114 | 53.7% | +2.4% | 348 | 174–174 | 50.0% | −4.5% |
| ≥3.0 | 191 | 103–88 | 53.9% | +2.9% | 265 | 140–125 | 52.8% | +0.9% |

**Totals vs market:**

| Edge threshold | Validation n | Win% | ROI | Test n | Win% | ROI |
|---|---|---|---|---|---|---|
| ≥1.5 | 405 | 46.2% | −11.8% | 598 | 48.8% | −6.8% |
| ≥2.0 | 353 | 45.6% | −12.9% | 506 | 48.6% | −7.2% |
| ≥2.5 | 291 | 45.0% | −14.1% | 444 | 48.9% | −6.7% |
| ≥3.0 | 244 | 46.3% | −11.6% | 386 | 47.9% | −8.5% |

Model edge vs actual cover correlation: 0.052 (validation), **0.007** (test) — effectively zero signal beyond the market.

## Methodology (reproducible)

- **ELO:** FiveThirtyEight-style NFL (K=20, HFA≈55 ELO, margin-of-victory multiplier, 1/3 offseason regression to 1500). Updated in weekly batches — no within-week leakage.
- **EPA ratings:** per-team offensive/defensive EPA per play with pass/rush splits + success rate, EWMA (α=0.25) over weekly aggregates, 35% offseason regression toward league average. Pre-game ratings use only prior weeks.
- **GBM features (home perspective):** ELO diff, EPA/success-rate differentials and pass/rush splits, rest-day differential, division-game flag, week number. Modest hyperparameters (depth 3, lr 0.05) for the small-data regime. Retrained weekly on an expanding window — each prediction used only games already played.
- **Ensemble weights** chosen by validation MAE; **edge threshold** chosen by validation ROI (n≥40 guard); test window never touched during selection.
- **Betting math:** home covers iff `home_margin > spread_line` (nflverse convention: spread_line > 0 = home favored); pushes excluded; ROI assumes -110 both sides.

## Data limitations

1. **Market lines are nflverse's**, not verified closing lines (coverage is 100% for 2018–2025, but provenance is likely consensus/opening). Week 1 2026 market in the CSV uses fresher bet365 lines (Sept 10) instead.
2. **No injury, weather, or QB-change adjustments.** The model is team-strength only.
3. **2026 Week 1 uses regressed 2025 priors** (ELO 1/3 to 1500, EPA 35% to 0) with no 2026 data and no hand-tuning for offseason moves (e.g., Mahomes's ACL recovery, Garrett→Rams, Kyler→Vikings, Harbaugh→Cowboys, A.J. Brown→Patriots). Big camp/preseason information is invisible to it.
4. **Small samples:** ~270 games/season caps what any model can learn; confidence intervals are wide everywhere.

## Week 1 2026 output

`week1_predictions.csv` — 14 games, model spread/total vs bet365 market, picks only where |edge| ≥ 3.0, totals all "no play" per above. Five spread plays triggered; treat as **unvalidated model outputs, not recommendations** — the backtest does not support betting them.

## Files

- `scripts/01_pull_schedules.py`, `02_pull_pbp.py`, `03_ratings.py`, `04_backtest.py`, `05_metrics.py`, `06_week1.py`, `scripts/model_lib.py`
- `data/` — cached parquets, `ensemble_params.json`, `linear_models.pkl`, `gbm_final.pkl`, `final_2025_state.pkl`
- `venv/` — Python environment (nfl_data_py, pandas, scikit-learn)
- Re-run weekly: refresh nflverse data → `03_ratings.py` → `04_backtest.py` (or skip to final-fit) → `06_week1.py`. (A `07_update_weekly.py` that skips the full walk-forward refit would be the natural next step.)

## Weekly operations (added 2026-09-11)

The picks spreadsheet is now driven by this model (the original qualitative
picks tab was removed at Cale's request). Two scripts support the weekly cycle:

- `scripts/07_update_weekly.py` — final-fit weekly update. Re-pulls the 2026
  schedule/scores and play-by-play from nflverse, rolls ELO/EPA forward through
  all played weeks (no lookahead), refits the gradient boosters on the expanding
  window, and predicts the upcoming week. Market lines are supplied via a
  `--market-json` file (`{"AWAY_HOME": [spread, total], ...}`, home-spread
  convention, nflverse abbreviations). Linear components stay frozen (fit on
  2018-2020); ensemble weights/thresholds stay as selected on validation.
- `scripts/08_grade_week.py` — grades a week's spread picks against final
  scores (pushes excluded from W-L) and appends the result to `data/record.csv`
  (re-runnable; replaces the week's row).

### Correction: 06_week1.py double-regressed ELO (fixed in 07)

`final_2025_state.pkl`'s ELO dict had already passed through the 2026-week-1
offseason regression, because the two already-played 2026 games were in the
schedule cache when `03_ratings.py` ran. `06_week1.py` then applied the 2/3
regression a second time, pulling all ELOs too close to 1500 (e.g. LV 1397.0
instead of 1345.5). EPA was unaffected (its final state is captured at end of
2025 by construction). `07_update_weekly.py` applies the offseason regression
exactly once. The Week 1 2026 model tab was regenerated with the corrected
numbers; the 5 threshold picks were unchanged.

### Standing rules for weekly runs

- Spreads only at |edge| >= 3.0. Totals are always "no play".
- Never describe outputs as a proven edge; the Record tab is the honest scoreboard.

## v2: QB EPA/play ratings + wind (added 2026-09-11)

### What was added
- `scripts/qb_ratings.py` — walk-forward QB EPA/play ratings. Per-game mean EPA
  on pass plays, EWMA (alpha=0.2) with weekly batching, 35% offseason regression
  toward league mean, effective rating shrunk toward league mean with 60 career
  attempts of weight. Schedule starter names ("Matt Ryan") are mapped to pbp
  passer names ("M.Ryan") empirically: majority vote of each team's top passer
  per game (154 QBs mapped). No lookahead: a week-W rating uses only plays
  before week W; the starter identity is known pre-game.
- `wind_eff` in `model_lib.py` — dome/closed roof = 0 mph; outdoor/open with
  missing wind = 8 mph (outdoor median). Added to margin and total feature
  sets (v2 lists; v1 lists untouched).
- `scripts/12_backtest_v2.py` — full re-backtest under v1 discipline
  (linears on 2018-2020, walk-forward GBM 2021+, weights/threshold tuned on
  2021-2022 validation, reported on 2023-2025 test), plus a no-QB ablation.
- `scripts/07_update_weekly.py --model v2` — wired in. New artifacts:
  `linear_models_v2.pkl`, `ensemble_params_v2.json`, `games_with_preds_v2.parquet`.
  v1 remains the default.

Design choice: `qb_epa_diff` entered the linear models as a raw feature rather
than pre-scaled to points, so OLS estimates its partial effect controlling for
team pass EPA (which is correlated — team pass EPA already includes the QB).
Pre-scaling would have double-counted the QB signal and needed another
ensemble weight to tune.

### Signal check (OLS on 2018-2020)
- `qb_epa_diff` on margin: coef +7.1, **t = +1.17 (not significant)**.
- `wind_eff` on margin: coef +0.04, t = +0.47 (nothing).
- `wind_eff` on total: coef -0.38, **t = -4.25 (real)** — each mph of wind
  cuts ~0.4 points off the total. Totals are not bet, so this doesn't help ROI.

### Backtest results
Validation 2021-2022 @ |edge| >= 3.0 (weights re-tuned to 0.4/0.5/0.1 — unchanged):
- v2-full (+QB+wind): 102-83 (55.1%), ROI +5.3%
- v2-noQB (wind only): 104-91 (53.3%), ROI +1.8%
- v1: 103-88 (53.9%), ROI +2.9%

Test 2023-2025 @ 3.0:
- v2-full: 135-130 (50.9%), **ROI -2.7%**, MAE 10.23
- v2-noQB: 135-127 (51.5%), ROI -1.6%, MAE 10.23
- v1: 140-125 (52.8%), ROI +0.9%, MAE 10.22
- market: MAE 9.79

### Honest verdict: v2 does NOT beat v1
The QB feature looked promising on validation (+5.3% vs +2.9%) and decayed on
test (-2.7% vs +0.9%) — the same validation-to-test decay seen throughout this
project. The t-stat (+1.17) already warned there was no real signal. Likely
reasons: (1) the market prices QB news into the spread within minutes, so any
QB edge is arbitraged away before our lines; (2) team-level pass EPA already
contains most of the QB signal, leaving little residual. Wind is genuinely
predictive for totals but irrelevant for spreads, and totals stay unbettable.
Per the no-tuning rule, v2 ships as-is behind `--model v2`; v1 stays default.

### Weekly market JSON: new optional sections (v2 only)
```json
{
  "DAL_NYG": [-2.5, 48.5],
  "qb":   {"DAL_NYG": ["Jalen Hurts", "Jaxson Dart"]},
  "wind": {"DAL_NYG": 14}
}
```
- `"qb"`: per-game `[away_QB, home_QB]` expected starters, full names as in the
  schedule data ("Jayden Daniels"), matched case-insensitively. Absent a game
  entry, defaults to each team's most recent starter (earlier this season,
  else last season) — no lookahead. Unknown QBs (e.g. debuting rookies) get
  the league-mean rating.
- `"wind"`: forecast wind mph for outdoor games. Domes/closed roofs are always
  0; outdoor games without a forecast assume 8 mph (typical).

## Player prop projector v1 (added 2026-09-11)

`scripts/10_prop_projector.py` — a data-backed yardage projector for three
markets: QB `pass_yards`, RB `rush_yards`, WR/TE `receiving_yards`. It exists to
flag large projection-vs-line gaps for paper-tracking. **There are no
historical prop lines, so this system cannot be backtested and no edge is
claimed.** What is reported instead: projection accuracy (correlation, MAE)
on a 2025 holdout.

### Method
- Per-player trailing per-game yards with exponential recency weighting
  (half-life 3 games, same season first then prior season, max 16 games).
- Fewer than 3 trailing games → shrink toward the positional season mean
  (QB/RB/WRTE groups from touch mix).
- Matchup adjustment: opponent's trailing defensive yards allowed per game
  (vs pass for pass/receiving, vs rush for rushing) minus league average,
  with the coefficient FIT by OLS of (actual − base projection) on the
  differential over 2018–2024 — not hand-picked. R² was 0.1–0.8%, i.e. the
  adjustment is negligible; it is kept for principled completeness.
- Data: `data/pbp_players_2018_2026.parquet` (nflverse pbp, player columns only;
  existing `pbp_2018_2025.parquet` untouched) → `data/player_games.parquet`
  (44,058 player-games) + `data/team_defense.parquet` (4,458 team-games).
  Betas cached in `data/prop_matchup_betas.json`.

### 2025 holdout diagnostics (role-eligible players who actually played)
| market | n | corr | MAE | naive last-3 MAE |
|---|---|---|---|---|
| pass_yards | 566 | 0.303 | 63.1 | 69.3 |
| rush_yards | 1031 | 0.371 | 25.4 | 27.3 |
| receiving_yards | 2535 | 0.438 | 22.5 | 24.3 |

Context: week-to-week yardage is mostly noise — lag-1 autocorrelation is only
0.17–0.25, so the projector (corr 0.30–0.44) extracts roughly as much signal as
exists. It beats the naive trailing average on all three markets, but the gaps
are small. A large share of big misses are playing-time events (benchings,
injuries, blowout benchings), which no yards model captures; diagnostics grade
only games where the player actually played the role (books void those props
anyway).

### Weekly use
Friday worker: re-pull 2026 pbp (`pull_pbp_players.py --refresh-season 2026`),
`--rebuild` aggregates, then `--season 2026 --week N --market-json
data/market_props_2026_wN.json` (list of `{"player","market","line"}`).
Output: `data/prop_gaps_2026_wN.csv` sorted by |projection − line| with
over/under leans; unmatched names reported explicitly. Runs in <1s on cached
aggregates. Name matching is best-effort (last name + first initial;
e.g. "Josh Allen" → "J.Allen"); ambiguous matches are flagged and resolved to
the higher-volume player.

### Standing rules
- Gaps are paper-tracked only. No ROI or edge claims — there is no
  historical line data to validate against.
- Treat gaps smaller than ~0.5× the market's MAE as noise.
- Never present a "best prop" as a proven +EV bet.

### Framework review (2026-09-29, SportsCommand.ai "7 frameworks" articles)

Mapped the article's 7 frameworks against this model; implemented only what
survived honest scrutiny. No pick logic, weights, or thresholds changed.

- CLV analysis (#1): already tracked avg CLV; extended 08_grade_week.py with
  weekly `clv_hit_rate` and a per-pick log `data/clv_picks.csv` (Friday number
  vs nflverse close proxy).
- Situational handicapping (#2): rest/div already GBM features. New script
  `scripts/14_framework_diagnostics.py` tests pre-specified buckets on the
  2023-2025 test @ |edge|>=3.0: baseline 140-125 (52.8%), divisional 46-48
  (48.9%), late-season divisional 22-19 (53.7%, n=41), pick-side rest
  disadvantage 14-16 (46.7%, n=30), rest advantage 7-11 (38.9%, n=18).
  No bucket validates a filter; small-n deviations are noise.
- Sharp line movement (#3): no intraday data historically. The article's
  independence test (ATS split by |Fri->close move| <=1 vs >1) runs in script
  14 once 2026 graded picks reach n>=20.
- Player availability (#4): QB stale-news void filter (11) already covers the
  article's "doubtful ~= out". O-line weighting skipped: article gives no
  quantitative evidence.
- Weather (#5): wind is real for totals (v2, t=-4.25) but totals are never
  bet; no spread signal. No wind-direction data for crosswind splits.
- ATS trends w/ context filters (#6): skipped deliberately — secondary
  confirmation at best, high data-mining risk.
- AI composite (#7): the ensemble already is this; weekly refits are the
  continuous recalibration; judged via CLV per the article.

Verdict: production v1 unchanged. Articles mostly validated existing design;
the durable additions are CLV hit-rate tracking and the forward-looking
independence test.
