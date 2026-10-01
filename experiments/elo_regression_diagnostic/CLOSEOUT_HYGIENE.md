# DATA HYGIENE — retired stale 2025 state file (2026-09-30)

**Classification:** data hygiene / artifact cleanup. NOT a model change.

## Action
- `data/final_2025_state.pkl` (Sep 11, 2026; 2025 final ELO/EPA ratings snapshot,
  up to ~94 pts off recomputed production 2025 finals) → moved to
  `data/retired/final_2025_state.pkl.retired-20260930` with a README explaining why.
- No new live state artifact created. The file is kept (not deleted) for audit trail.

## Why it was obsolete
- Written only by `scripts/03_ratings.py` main() — not run by the weekly pipeline
  (`07_update_weekly.py` imports `run_elo` from `03_ratings` as a library function only).
- Read only by `scripts/06_week1.py` — one-time Week 1 2026 script with hardcoded
  Sept-10 bet365 markets, superseded by `07_update_weekly.py` (documented
  double-regression bug, fixed in 07); Week 1 is over.
- Not read by: `07_update_weekly.py`, `15_export_ui_json.py`, the dashboard data flow,
  any cron, any runbook. Provenance audit (2026-09-30) independently confirmed
  "no production code reads a 2025/preseason artifact."
- Post-move re-grep: only remaining references are the 03 write and 06 read
  (both non-production) plus historical docs. No live references.

## Validation
- md5 of all 10 UI JSON files (`data/ui_json/v1/*.json` + `versions.json`) before
  and after: ALL OK — byte-for-byte identical.
- Strict JSON parse + NaN/Infinity guard: PASS on all 10 files.
- Blend check on export-rounded values: max |0.4·elo+0.5·epa+0.1·gbm − spread| = 4e-3
  (export rounding only; exact reconciliation on unrounded values was verified
  separately during calibration work).
- V1 spec intact: weights 0.4/0.5/0.1, pick threshold 3.0, 16 Week 4 games,
  5 live picks (ATL +3.5, TB +1.5, JAX +2.5, SEA −6.5, CHI −3.0).

## Conclusion
V1 predictions and outputs demonstrably unchanged. ELO diagnostic verdict
(KEEP V1 UNCHANGED, 1/3 regression frozen) stands.
