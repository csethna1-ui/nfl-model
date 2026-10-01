# 003A Receptions — Experimental Integration Summary

**Date:** 2026-10-01
**Authorization:** Cale, 2026-10-01 — integrate 003A as additive EXPERIMENTAL market, mirroring 003B pattern, then STOP.

## What was built

**`scripts/19_prod_receptions.py`** (new, standalone):
- Weekly production pipeline for 003A receptions projections.
- Loads verified M2 artifact (`003A-M2-verified`); M1 degradation rung (`003A-M1-degraded`) on full NGS feed failure.
- Feature pipeline replicates the experiment exactly:
  - Player trailing over predictable games only (001 base convention; Thursday/pre-Friday games excluded from player history).
  - Base rows from `player_games.parquet` (includes 0-target games, matching 001).
  - Team pace trailing over ALL games; QB trailing over ALL games; NGS trailing over all NGS weeks.
  - Name-collision grouping by `player_name` (documented 001/002 convention).
- As-of: Friday 18:00 CT; NGS trailing strictly prior weeks; missing NGS → 0.
- Full provenance per row; `status: "experimental"` everywhere.
- Output: `data/prop_v2_2026_w4_receptions.json` (221 WRTE projections for 2026 W4).

**`scripts/18_export_experimental_markets.py`** (extended):
- Now exports live receptions alongside rush_attempts to `data/ui_json/v1/experimental_markets.json`.
- Receptions: 221 rows, `003A-M2-verified`, status experimental.

## Verification

1. **Model deployment** (DEPLOYMENT_VERIFICATION.md): 0/3,625 rows differ, max abs diff 0.0 vs frozen test predictions.
2. **Feature pipeline** (check_features_historical.py): Historical check on 2024 W18 vs frozen table. Residual max diffs confined to name-collision players (same-week duplicate row-ordering nuance in 002's row_id convention); production target weeks have no same-week history rows, so the convention is exact there.
3. **Script 16 regression**: 16 is untouched (mtime Sep 30) and self-consistent (identical output on re-run modulo generated_at). Note: the 18:05 `prop_v2_2026_w4.json` contained an `eligibility_note` key not emitted by current script 16 — this predates my work; I restored the file after testing.
4. **Language grep**: No +EV/edge claims, no "High Confidence". All 223 "edge" mentions are in "No verified betting edge" disclaimers.

## Key findings during integration

- The experiment's player trailing excludes Thursday games (predictable-game filter from 001). This was caught by the historical check and fixed.
- The 001 base includes 0-target games (from player_stats); pbp-only history would skew trails. Fixed by using player_games.parquet as the base.
- 002's `trail_frame_player` uses row_id-order prior (not season/week prior) for same-week collisions. Documented; moot for production.

## Outputs

- `data/prop_v2_2026_w4_receptions.json` — 221 projections, M2 rung, no market lines (market JSON empty).
- `data/ui_json/v1/experimental_markets.json` — 53 rush + 221 receptions, both experimental.

## Standing constraints honored

- Scripts 16 and Props v2 untouched. No retraining. No feature changes (frozen definitions replicated).
- Experimental status everywhere; corrected uncertainty terminology; no edge language.
- Not promoted to production-validated. Stop after 003A+003B per Cale's order.
