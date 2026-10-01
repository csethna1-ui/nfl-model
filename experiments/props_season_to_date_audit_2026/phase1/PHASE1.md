# Phase 1 — Prospective Season-to-Date Props Audit: 2026 W1–W3

Monitoring only. No retraining, no refitting, no threshold changes, no tuning.
W1–W3 are strictly prospective out-of-sample for the frozen Model D
(equal-weight A/B/C; fit 2018–2020, selected 2021–2022).

## Headline (narrowly stated)

Over 2026 Weeks 1–3, 796 player-week-markets scored (of 1,600 projected).
Pooled MAE: **pass 72.4** (n=108), **rush 27.2** (n=189), **receiving 25.1**
(n=499) — against the frozen experiment's locked-test MAE of 60.6 / 25.1 /
24.0. The pass-market gap is largely accounted for by two artifacts, not
model degradation: (1) W1 team-assignment staleness — the pipeline has no
roster input, so 2026 offseason moves (heavy QB movement in this universe)
put 21.7% of scored W1 rows on the wrong team/game; (2) projections for
players who recorded no in-game opportunity (backups who dressed but did not
play their market's role). Removing team-mismatched and zero-opportunity
rows brings pass MAE to ~62–63, near the locked-test figure; rush/receiving
were already within ~1–2 yards of locked test. A **consistent positive bias**
(model projects high) appears in all three markets in every week
(pooled +24.9 / +12.4 / +8.5); it shrinks but does not fully vanish after
artifact removal. Samples are small — especially pass (n=108) — so these are
observations to carry into Phase 2/3, not verdicts. No betting-edge language
applies; nothing here was tuned.

## Aggregate error table

signed_error = projection − actual (bias > 0 means the model projected high).

| market | week | n (proj/unscored) | MAE | RMSE | bias |
|---|---|---|---|---|---|
| pass_yards | W1 | 35 (73/38) | 77.06 | 98.92 | +27.03 |
| pass_yards | W2 | 37 (74/37) | 73.37 | 92.50 | +31.38 |
| pass_yards | W3 | 36 (74/38) | 66.75 | 90.27 | +16.18 |
| pass_yards | **pooled** | **108** | **72.36** | **93.91** | **+24.90** |
| rush_yards | W1 | 61 (129/68) | 28.28 | 35.18 | +8.17 |
| rush_yards | W2 | 65 (130/65) | 28.28 | 32.24 | +14.47 |
| rush_yards | W3 | 63 (131/68) | 25.16 | 30.23 | +14.21 |
| rush_yards | **pooled** | **189** | **27.24** | **32.58** | **+12.35** |
| receiving_yards | W1 | 166 (327/161) | 25.72 | 31.41 | +10.58 |
| receiving_yards | W2 | 165 (329/164) | 25.27 | 32.43 | +7.43 |
| receiving_yards | W3 | 168 (333/165) | 24.37 | 29.67 | +7.45 |
| receiving_yards | **pooled** | **499** | **25.12** | **31.18** | **+8.48** |

Reference (frozen Experiment 001 locked test, 2023–2024): pass 60.6 (n=1010),
rush 25.1 (n=1500), receiving 24.0 (n=3689).

Artifact sensitivity (pooled): excluding team-mismatched rows →
pass 70.0 / rush 27.4 / receiving 24.9; excluding team-mismatched AND
zero-in-game-opportunity rows → pass ~62.5 (n≈94) / rush ~26.3 / receiving
~24.8, with residual bias +8.4 / +10.5 / +8.1. (Computed with dup-actual
rows deduplicated; directionally, not a refit of anything.)

## Deep diagnostics (pooled W1–W3; MAE / bias)

**(a) Trailing opportunity volume** (tertiles of trailing opportunity EWMA
within market; cutoffs in `outputs/phase1_aggregates.json`):

| market | low | med | high |
|---|---|---|---|
| pass | 98.2 / +68.7 (n=36) | 54.3 / +14.9 (n=36) | 64.6 / −8.9 (n=36) |
| rush | 26.0 / +25.0 (n=63) | 28.5 / +12.5 (n=63) | 27.2 / −0.5 (n=63) |
| receiving | 22.2 / +14.0 (n=167) | 23.6 / +9.7 (n=166) | 29.6 / +1.7 (n=166) |

Low-opportunity pass rows (mostly backup QBs) err far more and drive the
positive bias; receiving inverts (high-volume targets err more).

**(b) Projection size** (within-market tertiles):

| market | low | med | high |
|---|---|---|---|
| pass | 93.6 / +60.7 (n=36) | 66.9 / +3.2 (n=36) | 56.6 / +10.8 (n=36) |
| rush | 24.9 / +22.0 (n=63) | 27.6 / +13.9 (n=63) | 29.3 / +1.2 (n=63) |
| receiving | 21.0 / +13.2 (n=167) | 24.3 / +9.3 (n=166) | 30.1 / +2.9 (n=166) |

Small projections carry the positive bias in all three markets — consistent
with backups/role players projected for meaningful work they did not get.

**(c) Uncertainty bucket** (pipeline `confidence` inverted per the dashboard
contract: High confidence → Low uncertainty):

| market | Low unc. | Med unc. | High unc. |
|---|---|---|---|
| pass | 82.6 / +23.3 (n=47) | 44.0 / +15.0 (n=26) | 79.7 / +34.5 (n=35) |
| rush | 28.9 / +7.3 (n=41) | 27.8 / +17.8 (n=58) | 26.2 / +11.1 (n=90) |
| receiving | 27.1 / +7.3 (n=149) | 24.9 / +6.4 (n=172) | 23.7 / +11.5 (n=178) |

No clean MAE ordering by uncertainty bucket at these sample sizes; the
pass-market Medium cell (n=26) is noise. The uncertainty flag fired on
80/97/95 projections per week (272 total).

**(d) Model−market gap** (only where a historical line exists; sparse):

| market | model_low (<−5) | close (±5) | model_high (>+5) |
|---|---|---|---|
| pass (n=17) | 65.3 / −64.4 (n=6) | 58.7 / +1.3 (n=4) | 48.3 / +41.0 (n=7) |
| rush (n=20) | 47.0 / −44.3 (n=4) | 45.5 / −16.1 (n=10) | 16.5 / +7.2 (n=6) |
| receiving (n=24) | 37.6 / −35.4 (n=5) | 36.2 / +3.4 (n=9) | 34.4 / −19.4 (n=10) |

61 lined projections scored (of 64 historical lines; 3 lined players fell
outside the projected universe). Samples are far too small for inference;
reported for completeness only.

**(e) Position:** pass=QB only, rush=RB only, receiving=WRTE only (by
pipeline design — one market per player).

**(f) Week:** no strong week trend; W3 marginally best in all markets
(pass 66.8 vs 77.1/73.4; small n).

**(g) Rookie vs established:** zero rookies scored in any market — rookies
cannot pass the MIN_GAMES=3 trailing guard this early (expected; the
diagnostic is degenerate by construction for W1–W3).

**(h) Rich-pbp (NGS-adjacent) coverage:** all 796 scored rows had **full**
rich-pbp coverage of their trailing games — no partial/fallback cases in the
scored sample. (Model D does not consume NGS features; this diagnostic
tracks the rich-pbp-derived trailing features air_yards/yac/rz_targets/
rz_carries/completions, which are zero-filled when missing. No missingness
was observed among scored rows.)

## Data problems encountered

1. **nflverse weekly file 404.** `import_weekly_data([2026])` fails — the
   `player_stats_2026.parquet` release asset does not exist at the version's
   expected URL (checked 2026-10-01). Actuals use local
   `data/player_games.parquet` (nflverse-pbp-derived, 313/320/318 rows).
2. **Duplicate actual rows (name collisions).** 23 player-weeks have 2+
   actual rows under one abbreviated name on different teams (J.Love ARI/GB,
   M.Evans CAR/SF, K.Allen IND/WAS, J.Williams DAL/DET, K.Williams LA/NE,
   D.Moore BUF/CAR, T.Johnson NYG/TB/BUF, K.Coleman BUF/MIA, J.Lane BAL/WAS,
   M.Washington LV/MIA). Attributed to the projection-team row; 1 row
   unscorable. Flagged `dup_actual_teams` (22 scored rows). Same collisions
   double-count those players' trailing histories (pre-existing behavior).
3. **W1 team staleness.** 57/262 scored W1 rows projected for the wrong team
   (2026 offseason moves; e.g. J.Love GB→ARI, K.Cousins ATL→LV, A.Brown
   PHI→NE). Faithful to the frozen pipeline (no roster input); a real 9/4
   run would show the same. Mismatched rows: MAE 36.4 vs 32.0 overall.
4. **Scored-sample conditioning.** 796/1600 projections score; the rest are
   backups/DNPs with no actual row (expected). 28 scored rows recorded zero
   in-game opportunity; 93 recorded zero yards in the market column.
5. **Game lines are reconstructed, not Friday-observed.** Schedule
   spread/total lines are the 2026-09-30 nflverse cache, not guaranteed
   Friday-18:00 values (affects ENV features only).

## Files

- `outputs/phase1_errors_2026_w1w3.parquet` — 796 scored rows; columns:
  player, week, market, position, team_proj/opp_proj, team_actual,
  team_mismatch, dup_actual_teams, projection, p25/median/p75, confidence,
  uncertainty (inverted labels), uncertainty_flag, baseline_ewma,
  trailing_games, trail_opp_ewma, actual, abs_error, signed_error
  (projection−actual), line, model_minus_market, lean, line_source, rookie,
  rich_coverage(_bucket), opp_volume_bucket, proj_size_bucket, gap_bucket,
  prediction_timestamp.
- `outputs/phase1_aggregates.json` — per-market×week MAE/RMSE/bias/n,
  pooled, all diagnostics, bucket cutoffs, data-quality counts, artifact
  accounting.
- `inputs/asof_w{W}/prop_v2_2026_w{W}.json` + `week_frame_2026_w{W}.parquet`
  — regenerated as-of projection sets (529/533/538 projections; 36/14/11
  market lines attached).
- `code/16_prod_player_projection_asof.py`, `code/phase1_audit.py` —
  runnable reconstruction + audit code; `diff` vs the frozen script shows
  only the documented as-of adaptations.
- `PHASE1_NOTES.md` — full as-of reconstruction notes.

## Caveats for downstream phases

- n is small (pass n=108 total); week-to-week moves are noise.
- The positive bias is the most consistent signal; artifact removal shrinks
  it but a residual ~+8/year-market remains — worth watching in Phase 2,
  not acting on.
- The scored sample conditions on playing; DNP projections are unscored by
  construction, so this audit says nothing about backup-QB projection
  quality beyond the zero-opportunity sensitivity.
- Market-line diagnostics (d) rest on 61 rows and historical captures of
  unknown capture time — descriptive only.
