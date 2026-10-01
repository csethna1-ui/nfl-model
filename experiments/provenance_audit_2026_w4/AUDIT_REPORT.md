# Provenance Audit — 2026 Week 4 Production Outputs

**Date:** 2026-09-30 · **Auditor:** Scout (subagent) · **Scope:** read-only except two authorized fixes (D, E)
**Standing rules honored:** no V1 retune, no weight changes, no new experiments, no use of Week 4 outcomes.

## 1. Questions asked

1. Do Week 4 props contain retired/inactive players?
2. Why does the dashboard show the Patriots as the best offensive team?
3. Do the V1 Week 4 predictions incorporate 2026 Weeks 1–3?

## 2. Verdicts (result first)

1. **Props: YES — confirmed.** 779 of 1,115 Week 4 props players (70%) have no 2026 game in `player_games.parquet`. Includes T. Brady, D. Brees, A. Luck, E. Manning, P. Rivers, M. Ryan, C. Newton. → **EXPORT_PIPELINE_BUG (B)** — missing eligibility filter in `build_week_frame`. **Fix implemented and verified** (takes effect on next Friday run).
2. **Patriots: dashboard artifact is stale, model is not.** The Teams page renders `teams.json`, built from 2025 Week-18 pre-game ratings, where NE's off-EPA (0.247) ranks #1. The ratings V1 actually used for Week 4 predictions have NE's off-EPA at −0.059 (below average; BUF #1 at +0.205). No staleness or inversion in the prediction path. → **EXPORT_PIPELINE_BUG (B)** — stale ratings object on the display path, now explicitly labeled via provenance fields.
3. **Freshness: YES — with a precise, correct boundary.** The Week 4 predictions were reproduced **exactly, 16/16 games, max diff 0.00**, from the data state: 2026 Weeks 1–2 (32 games) + the Thursday Week-3 game ATL@GB (played 2026-09-24). The Week-3 Sunday/Monday games (Sep 27–28) were correctly excluded — they had not been played when predictions ran Friday Sep 25. **No bug.** The pipeline includes 2026 data by construction (recompute-from-scratch design).

## 3. A — End-to-end trace: NE @ BUF (2026_04_NE_BUF)

Reproduction method: re-ran the exact `07_update_weekly.py` logic (imports of `03_ratings.run_elo`, `run_epa_current`, frozen `linear_models.pkl`, frozen `ensemble_params.json`, deterministic GBM `random_state=42`, sklearn-hgbr backend) against the Sep-25 data state **without refreshing caches**. All 16 games reproduced to 0.00 (see §9 for the data-state proof).

| Quantity | Value |
|---|---|
| `model_spread` (CSV) | 4.3 |
| Recomputed | 4.3278 |
| ELO component (`pred_elo`) | 2.9314 |
| EPA-linear component (`pred_epa_m`) | 5.0194 |
| GBM component (`pred_gbm_m`) | 6.4562 |
| Blend check 0.4/0.5/0.1 | 4.3278 ✓ |

**ELO differential used:** +50.991 (BUF 1646.574 − NE 1595.584), via `lr_elo`: coef 0.04505717, intercept 0.63386845.

**EPA differential vector** (home − away = BUF − NE): off_epa +0.26357, def_epa +0.20451, off_pass +0.37884, off_rush +0.10613, def_pass +0.26221, def_rush +0.04630, sr_off +0.06605, sr_def +0.06179.

**GBM feature vector:** the 8 EPA diffs above + elo_diff +50.99056, rest_diff 0.0, div_game 1.0, week 4.0.

**lr_epa_m coefs:** off_epa 18.9606, def_epa 2.9249, off_pass −2.1382, off_rush 4.3793, def_pass −7.9068, def_rush −9.2963, sr_off 52.85, sr_def −30.2193, intercept 0.6495.

**GBM training set:** 2,260 games, seasons 2018–2026 (33 from 2026), `HistGradientBoostingRegressor(random_state=42)` — deterministic.

**Ratings inputs for this game:** NE's ratings include 2026 W1 (L 10–13 @ SEA) and W2 (W 20–3 vs PIT). BUF's include 2026 W1 (W 36–31 @ HOU) and W2 (W 41–31 vs DET). Neither played the Thursday W3 game. Latest game in the full ratings: `2026_03_ATL_GB` (2026-09-24).

**Data-state proof (why "W1–2 + Thu W3"):** four candidate data states were tested against `predictions_2026_w4.csv`: full current cache (W1–3) → max diff 2.90, 1/16 exact; no-2026 → max diff 7.20; W1–2 only → 14/16 within 0.1 with exactly two outliers (GB_TB, ATL_NO); W1–2 + `2026_03_ATL_GB` → **16/16 exact, max diff 0.00**. The two outliers under W1–2 are precisely the two teams that played Thursday Sep 24 (ATL 35 @ GB 14) — the only Week-3 game played before the Friday run. The Sep-29 cache refresh (which pulled the remaining W3 games) is what made the naive current-cache reproduction fail; it is not evidence of a production defect.

## 4. B — ELO/EPA update path (items 1–7)

1. **Schedule/pbp ingestion:** `07_update_weekly.main` → `refresh_schedules()` / `refresh_pbp()` re-pull the 2026 season from nflverse into `schedules_2018_2025.parquet` / `pbp_2018_2025.parquet` (2026 rows dropped and re-added; ≤2025 untouched).
2. **`played` filter:** `sched[home_score.notna()]` then `(season < S) | ((season == S) & (week < W))` — every scored game before the prediction week. For the W4 run: everything through the Thursday W3 game.
3. **ELO:** `03_ratings.run_elo(played)` — recomputed from scratch every run; no cached/stale ratings file is read. Offseason regression (33% toward 1500) and QB-adjustment replay apply at each season's week 1.
4. **EPA:** `run_epa_current(pbp, played)` — recomputed from scratch every run from pbp rows joined to `played` weeks; per-team EWMA (α=0.35) over pre-game states.
5. **Prediction features:** `add_features` builds home−away differentials; sign convention verified in code (no inversion).
6. **No production code reads a 2025/preseason artifact:** `07` reads only the two live caches, `linear_models.pkl`, `ensemble_params.json`, and the market JSON. `final_2025_state.pkl` is read only by `06_week1.py` (week-1 path, not the weekly loop). `games_with_ratings.parquet` is read by backtests/research scripts and by `15_export_ui_json.py` (display only — see §5).
7. **teams.json divergence:** `15_export_ui_json.py` builds `teams` from `games_with_ratings.parquet` filtered to `season==2025 & week==18` — a **static backtest artifact from the Sep-11 research run**, explicitly a different object from the ratings `07` recomputes. This is the stale object behind finding #2.

## 5. C — Patriots investigation

- `teams.json` (dashboard Teams page source): NE off_epa **0.247, ranked #1 of 32**; BUF 1662.0 ELO tops ELO. Source: 2025 Week-18 pre-game ratings = data through 2025 Week 17.
- Ratings actually used for Week 4 predictions: NE off_epa **−0.0588** (below average), off_pass −0.112, off_sr 0.336; league off-EPA leader **BUF +0.2048**, then BAL +0.133, SF +0.128. NE is not close to the best offense in the live ratings.
- Checks: not inverted (sign convention verified in `add_features`; NE's negative value is genuinely below-average offense through W2); not misjoined (team keys match; NE's two 2026 games present in `played`).
- Dashboard spec (§Teams) requires only "visual power board using ONLY available ELO, Off EPA, Def EPA, Success Rate" with no as-of label — so the stale 2025 object was presented without a visible date. **Classification: B (export pipeline).** The underlying prediction path is clean.

## 6. D — Props eligibility audit + AUTHORIZED FIX (implemented)

- `build_week_frame` (`scripts/16_prod_player_projection.py`, lines 397–590): player universe = every `player_name` ever seen in `player_games.parquet`; guards are only `MIN_GAMES` trailing and `ROLE_NEED`. **No active-roster/retirement/IR eligibility filter existed anywhere** (grep confirmed; `validate_output` is schema-only).
- Week 4 `props.json`: 1,115 projections (713 receiving / 278 rush / 124 pass). **779 players (70%) have no 2026 game** — full list in `prop_removals_w4.csv` (player, last season/week/team, reason). Retired QBs present included A. Luck (2018), D. Brees (2020), T. Brady (2022), E. Manning (2019), P. Rivers (2025), M. Ryan (2022), C. Newton (2021), B. Bortles (2019), N. Foles (2022), R. Fitzpatrick (2021), M. Schaub (2019), C. Daniel (2022). Also present: name-duplicate artifacts (`J.Daniels|TB`, `G.Minshew|KC` vs `G.Minshew II|JAX`, `Jos.Allen` vs `J.Allen`) — noted, out of fix scope.
- **Fix:** current-season eligibility gate in `build_week_frame` — a player is eligible only if their most recent cached game is in the current season (data/production fix; projection models untouched; predict-mode only, frozen fit unaffected).
- **Verified:** `build_week_frame(2026, 4)` → 402 players with a 2026 game, 1,203 retired/inactive excluded, 336 eligible player-weeks (218 receiving / 79 rush / 39 pass), **0 ineligible players remaining**; 1115 − 779 = 336 ✓.
- **Takes effect on the next Friday production run** (the current `prop_v2_2026_w4.json` / `props.json` were generated pre-fix and were intentionally not regenerated).

## 7. E — Provenance metadata + AUTHORIZED FIX (implemented)

- **Was missing:** no record existed of what data any weekly prediction was built from.
- **Fix 1:** `07_update_weekly.py` now writes `data/predictions_{S}_w{W}.provenance.json` on every run: `model_version, season, week, generated_at, data_as_of, latest_game_included, season_games_included, ratings_window, elo_source, epa_source, gbm_train_through, gbm_n_train, gbm_backend, weights`. Additive — the predictions CSV is untouched.
- **Fix 2 (backfill):** `data/predictions_2026_w4.provenance.json` written from the exact-repro data state (no re-run of 07, which would have refreshed caches and altered predictions): data_as_of 2026-09-24, latest_game_included `2026_03_ATL_GB`, 2026 = 33 games (W1, W2, Thu-W3 only), GBM n_train 2260, backend sklearn-hgbr, weights 0.4/0.5/0.1.
- **Fix 3:** `15_export_ui_json.py` embeds the sidecar as `provenance` in `predictions.json` (graceful stub if absent), and `teams.json` now carries per-team `season, week, data_as_of, latest_game_included` plus a strengthened note: *"2025 final pre-game ratings… NOT current-season ratings: the V1 Week 4 predictions used freshly recomputed ratings through 2026-09-24 (see predictions.json provenance)."* Verified by re-running the export (all existing fields unchanged — additive only).
- Per-team values in teams.json: NE `season 2025, week 18, data_as_of 2025-12-29, latest_game_included 2025_17_NE_NYJ`.

## 8. F — Classification

| Issue | Class | Rationale |
|---|---|---|
| Retired players in props | **B — EXPORT_PIPELINE_BUG** | Projection models fine; universe construction in `build_week_frame` lacked an eligibility gate. Fixed. |
| Patriots "best offense" | **B — EXPORT_PIPELINE_BUG** | Dashboard Teams page rendered a stale 2025-final ratings object; prediction path uses fresh ratings where NE is below average. Labeled via provenance. |
| 2026 W1–3 in predictions | **No bug** | Proven by exact 16/16 reproduction: W1–2 + Thu-W3 included; Sun/Mon W3 correctly excluded (not yet played). |
| Model core (V1) | **Clean** | No evidence of staleness, inversion, or misjoin in the prediction path. |

No DASHBOARD_ONLY_BUG (the Teams issue is the export feeding the dashboard a stale object, not a dashboard rendering error) and no MODEL_PRODUCTION_BUG.

## 9. Implemented vs awaiting-Cale

**Implemented (both authorized fixes):**
- D: eligibility filter in `scripts/16_prod_player_projection.py` (+ verification).
- E: provenance sidecar in `07`, backfilled W4 sidecar, provenance in `15` export (+ verification).
- Re-ran `15_export_ui_json.py` — ui_json outputs refreshed with additive fields only.

**Awaiting Cale (not authorized / judgment calls):**
- Whether the dashboard Teams page should show *current-season* ratings instead of the 2025 baseline (a product decision; the audit only made the as-of explicit).
- The name-duplicate artifacts in props (`J.Daniels|TB`, `G.Minshew` variants, `Jos.Allen`) — cosmetic, out of scope.
- Publishing the redesigned dashboard (still held for his approval).

## 10. Unknowns & limitations

- The original Sep-25 cache state is unrecoverable directly (caches refreshed Sep 29); the data state was instead *proven* by exact 16/16 reproduction of all predictions, which is stronger than a log claim but is still an inference about which nflverse pull the run saw.
- `generated_at` on the backfilled W4 sidecar is the CSV mtime (Sep 25 23:34); the 07 step itself ran earlier that evening (11_injury_adjust rewrote the file at 23:34). The ratings content is unaffected by this distinction.
- The two voided games (ARI@NYG, IND@WAS) were excluded from paper plays by the unchanged void rule; void logic was not in audit scope beyond confirming `model_spread` values are pre-void.
- Reproduction scripts preserved in this directory: `audit_trace.py`, `audit_variants.py`, `audit_counterfactual.py`; removal list: `prop_removals_w4.csv` (779 rows).
