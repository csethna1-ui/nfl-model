# Preregistration Addendum — Vault Confirmation of the Fixed Composite

Date: 2026-09-30. Written BEFORE any 2023–2025 computation was run.
Authorizes: Cale (user), 2026-09-30.

## Relationship to the original experiment
The original power-ranking experiment (`PREREGISTRATION.md`, `REPORT.md`)
deliberately excluded the 2023–2025 locked vault. Its protocol, results, and
claims stand as reported and are NOT retroactively modified by this addendum.
This document is a SEPARATE preregistered confirmation protocol for the one
fixed specification the original experiment adopted. It is confirmation, not
a second selection round.

## Fixed candidate specification (frozen — no alteration after seeing results)
- Composite: **Power score = ( z(ELO) + z(offensive EPA/play) ) / 2**,
  z-scores computed cross-sectionally across the 32 teams at each snapshot
  week (population std, ddof=0; zero if degenerate), rank descending.
- Baseline: **ELO-only = z(ELO)**, same z-scoring.
- The **learned-weight composite is REJECTED** (secondary component weights
  flip signs across development seasons; see REPORT §11) and is not
  evaluated here. Its rejection is not revisited.
- No components will be added or removed (no Def EPA, no Net SR, no W-L, no
  point differential) based on vault results. No weights will be retuned.
  No specification change of any kind will be made after seeing vault output.

## Data and information discipline
- Seasons 2023, 2024, 2025 ONLY, from `data/games_with_ratings.parquet`
  (pre-week ratings attached before each week's games are folded in —
  timestamp-valid per the original leakage audit).
- Pre-week snapshots, weekly batching, bye-week carry-forward — identical
  construction to `01_build_snapshots.py`, applied to the three vault seasons.
- Future games for evaluation: regular-season games with week > snapshot
  week. No post-cutoff information.
- **No 2026 data anywhere.** The 2026 rows in the parquet are not read.
- Margin mappings: the development-fit (2018–2020) OLS mappings
  `home_margin ~ score_diff` for the two candidates, recomputed
  deterministically from the original code path (OLS has no randomness).
  Nothing is refit on 2023–2025.

## Evaluation (same primary framework as the original experiment)
- PRIMARY: future game-margin MAE, snapshots at weeks 4+, pooled across
  2023–2025, paired t-test of per-pair absolute-error difference
  (ELO-only minus composite; positive = composite better).
- Season-by-season MAE (2023, 2024, 2025) for both candidates + delta.
- Early (snapshots wk 1–3) / mid (wk 4–12) / late (wk 13+) splits.
- Secondary (reported, not decisive): Spearman rank correlation of each
  candidate's rank vs rest-of-season PD/game and win%.

## Decision rules (binding)
- **CONFIRMED**: proceed to the dashboard change ONLY IF the fixed composite
  beats ELO-only on the primary pooled metric with paired p < 0.05 AND the
  delta is positive in at least 2 of the 3 vault seasons (not driven by a
  single season).
- **NOT CONFIRMED**: otherwise — STOP, report the result, touch nothing in
  production. A failed confirmation does not reopen candidate selection.

## Integrity
No tuning. No specification changes. No 2026 data. V1, ELO parameters
(K=20, HFA=55, MOV, 1/3 offseason regression), weights, QB logic, and props
untouched. The vault is used for confirmation only. All new outputs go to
new files (`03_vault_confirmation.py`, `snapshots_2023_2025.parquet`,
`table_vault_confirmation*.csv`); existing experiment files are not modified.
