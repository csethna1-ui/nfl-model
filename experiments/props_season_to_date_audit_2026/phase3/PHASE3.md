# Phase 3 — Prospective Props Audit, 2026 Weeks 1–3

**Status: MONITORING ONLY.** No retraining, no refitting, no tuning. W1–W3 are
strictly prospective out-of-sample for both frozen heads. This report grades
projection quality only; it makes no claim about betting value.

## Heads under audit

| Head | Script (frozen) | Model artifact | Locked-test MAE |
|---|---|---|---|
| Receptions | `scripts/19_prod_receptions.py` | 003A-M2-verified (23 feats) | 1.3496 |
| Rush attempts | `scripts/17_prod_rush_attempts.py` | 003B-M2-frozen (13 feats) | 2.981 |

Both ran verbatim via the Phase 3 driver
(`phase3/work/run_phase3_projections.py`), with `DATA`/`NGS_CACHE` redirected
to the phase-3 data mirror. All six runs validated through each script's own
`validate_output()`. Every row: M2 rung, `stale_ngs_used=false`,
`fallback_to_M1=false`.

Prediction timestamps (production Friday-18:00-CT rule, schedule-derived):
W1 = 2026-09-11 18:00 CT, W2 = 2026-09-18 18:00 CT, W3 = 2026-09-25 18:00 CT.
See PHASE3_NOTES.md for the as-of reconstruction log.

**Market lines:** the 2026 market-prop files carry no receptions or
rush-attempts lines (pass/rush/receiving yards only), so `market_line` is null
on all 751 rows. Model-vs-market grading was impossible; this audit grades
projection-vs-actual only.

## Headline aggregates

Actuals are nflverse-2026-pbp-derived (receptions = `complete_pass` sums per
the experiment's recipe; rush attempts exclude `qb_kneel`). Pbp-derived rush
attempts validate 100% exact vs `player_games.rush_att` (940/940 rows).

### Receptions (003A-M2-verified) — pooled MAE 2.5895 vs locked 1.3496

| Slice | n | MAE | RMSE | Bias | Mean proj | Mean actual |
|---|---|---|---|---|---|---|
| W1 | 190 | 2.4989 | 2.8357 | +2.0663 | 4.219 | 2.153 |
| W2 | 211 | 2.6687 | 3.0585 | +2.1000 | 4.218 | 2.118 |
| W3 | 209 | 2.5919 | 2.9209 | +1.9459 | 4.228 | 2.282 |
| **Pooled** | **610** | **2.5895** | **2.9434** | **+2.0367** | 4.222 | 2.185 |
| Pooled, excl. DNP | 472 | 2.2839 | 2.6350 | +1.5695 | 4.394 | 2.824 |

### Rush attempts (003B-M2-frozen) — pooled MAE 6.3532 vs locked 2.981

| Slice | n | MAE | RMSE | Bias | Mean proj | Mean actual |
|---|---|---|---|---|---|---|
| W1 | 44 | 6.6591 | 7.6889 | +4.1682 | 14.736 | 10.568 |
| W2 | 47 | 6.3830 | 7.5772 | +4.3149 | 14.783 | 10.468 |
| W3 | 50 | 6.0560 | 7.6716 | +4.1560 | 14.676 | 10.520 |
| **Pooled** | **141** | **6.3532** | **7.6457** | **+4.2128** | 14.730 | 10.518 |
| Pooled, excl. DNP | 129 | 5.7721 | 6.9360 | +3.4326 | 14.929 | 11.496 |

## Reading the gap vs the locked test (descriptive, small samples)

Neither head reproduced its locked-test MAE in 2026 W1–W3. The gap decomposes
into three documented pieces:

1. **DNPs scored as zero.** The frozen heads project every player with
   trailing history; they have no inactive feed. Players with no 2026 pbp row
   that week (verified genuinely absent — e.g. B.Bowers recorded zero W1–W2
   rows, 13 in W3) are graded actual=0. DNP rate: 138/610 (22.6%) for
   receptions, 12/141 (8.5%) for rush. The locked-test populations required
   `played_role=1`, so the **excl.-DNP row is the apples-to-apples comparison**:
   2.2839 vs 1.3496 (003A) and 5.7721 vs 2.981 (003B).
2. **Systematic over-projection.** Positive bias persists after removing DNPs
   (+1.57 receptions, +3.43 rush attempts), uniform across weeks and across
   opportunity-volume terciles. The largest misses are backfield/workload
   regime changes the trailing history did not capture (e.g. D.Achane projected
   18.8 vs 3 actual in W3; J.Gibbs projected 15.7 vs 29 actual in W1 — both
   verified against raw pbp, not data errors).
3. **Early-season, tiny samples.** Three September weeks (n=610 / n=141) vs a
   two-full-season locked test. W1 trailing is pure 2025 data. No inference is
   drawn; the numbers are reported as observed.

## NGS-availability diagnostic (Cale's key question)

Raw MAE by NGS status is **confounded by volume**: NGS-missing rows are
overwhelmingly low-volume fringe players, who have lower absolute error
mechanically (receptions: fallback-or-zero MAE 1.94 at mean proj 2.46 vs full
2.64 at mean proj 5.43; all 139 fallback rows sit in the low projection
tercile). The raw cut cannot answer whether the NGS contribution persists.

Volume-controlled diagnostic (no-DNP set; OLS `abs_err ~ projection +
I(ngs_status==full)`; observational — NGS availability correlates with veteran
role stability, so not causal):

| Head | ngs_full coef (se) | t | Relative MAE: full / partial / fallback |
|---|---|---|---|
| Receptions (n=472) | −0.338 (0.149) | −2.27 | 0.479 / 0.590 / 0.630 |
| Rush attempts (n=129) | −1.315 (0.893) | −1.47 | 0.361 / 0.533 / 0.472 |

Directionally, rows where the model actually had full NGS trailing graded
better relative to their volume in both heads. This does not contradict the
locked-test M2-vs-M1 finding; it is weaker, observational evidence pointing
the same way. The controlled M2-vs-M1 comparison remains the experimental
result — this audit cannot rerun M1 (monitoring only).

## Other cuts (all in `aggregates_2026_w1w3.json`)

- **Opportunity volume tercile** (trailing EWMA, strictly prior): bias positive
  in all terciles for both heads; no tercile recovers locked-test MAE.
- **Projection size tercile**: MAE rises with projection size, as expected for
  absolute error on larger counts.
- **Interval width tercile** (003A only): MAE 2.33 / 2.63 / 2.84 across
  low/mid/high — wider stated intervals correspond to larger realized errors
  (calibration direction correct), though bias is flat (~2.0).
- **Position / rookie / uncertainty bucket**: degenerate by construction —
  003A projects only WRTE, 003B only RB; the frame requires trailing history
  so no rookies are projected (n=0); both heads ship the "Medium Uncertainty"
  placeholder bucket on every row.
- **Team-changed rows** (4 receptions rows where the spine's 2025-team label
  differed from the 2026 actual team): graded against the player's actual
  production that week; kept in aggregates, flagged via `match_note`.
- **Ambiguous name collisions**: 0 rows excluded.

## Data limitations (not hidden)

- No receptions/rush-attempts market lines exist in the 2026 market files;
  model−market, over/under, and lean fields are null throughout.
- Pre-week ELO/EPA ratings for W1–W3 were reconstructed (only W4 existed) and
  verified byte-exact against the W4 file (max diff 0.0 on both components).
- NGS trailing was pulled fresh at audit time; the audit assumes each
  prior-week NGS release published before that week's Friday 18:00 CT cutoff
  (the feed carries no release timestamps). Required-release checks passed for
  all six runs.
- `scripts/19_prod_receptions.py` was edited by the parent **twice** during
  the audit (both 2026-10-01, UTC): edit 1 added a tuple-based
  predictable-game filter on the pbp-built player trailing; edit 2
  (18:34:47 UTC) refactored it to a game_id join and rebuilt the trailing
  base from `player_games.parquet` (includes 0-target games). The audit
  re-ran 003A against the final version (sha `b804ef81b5fbdd53`); edit-1
  vs edit-2 projections are near-identical (same 610 players, max |Δ|
  0.7, mean |Δ| ≈ 0.01; edit-1 outputs preserved under
  `phase3/work/projections_003A_pbp_version/`). The 003B script was
  unmodified.
- As-of Fridays follow the production schedule-derived rule (W1=09-11,
  W2=09-18, W3=09-25), not the 09-04/09-11/09-18 dates in the original task
  text; pre-Friday games are excluded per game-week per the production rule.

## Files

- `phase3/projections/prop_v2_2026_w{W}_{receptions,rush_attempts}.json` — 6
  validated projection files (751 rows total)
- `phase3/error_table_2026_w1w3.parquet` — per-row: projection, actual,
  absolute/signed error, market fields (null), player/team/opp/week, market,
  uncertainty bucket, NGS status, `stale_ngs_used`, `match_note`
- `phase3/aggregates_2026_w1w3.json` — pooled/by-week MAE/RMSE/bias/n, all
  cuts, DNP sensitivity, NGS diagnostic
- `phase3/PHASE3_NOTES.md` — as-of reconstruction log
- `phase3/work/` — driver, grading script, data mirror (symlinks +
  reconstructions), provenance JSONs
