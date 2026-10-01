# V2 Research Report — 2026-09-29 (final)

**Status: V2_UNPROVEN.** No candidate passed the frozen gates. V1 remains
production. The 2023–2025 vault was never touched. No V2_FINAL_* files were
produced — there is no V2 to lock.

## What was tested

The governing question was whether a component-based architecture (separate
offense/defense scoring blocks + matchup interactions + player/pressure/
possession/explosiveness structure) contains predictive information the
V1 scalar-strength ensemble fundamentally cannot represent.

Four preregistered candidates were built on a shared frozen harness
(`scripts/39_v2_harness.py`), all Ridge on home margin, Tuesday 08:00 ET
information set, walk-forward standardization/imputation, weekly refits,
cold-start = V1 fallback:

| Candidate | Design | Frozen α | 2021–22 MAE |
|---|---|---|---|
| V2-A | component blocks (10 reg + int) | 100.0 | 10.555 |
| V2-B | A + 8 matchup interactions (18 reg + int) | 100.0 | 10.573 |
| V2-C | A + 7 QB/player features (17 reg + int) | 100.0 | 10.395 |
| V2-D | A + 37 possession/explosiveness/pressure (47 reg + int) | 100.0 | 10.673 |
| V1 (same 543 games) | — | — | **10.059** |

## The result

**Every candidate is significantly worse than V1** (paired bootstrap,
n=10,000): MAE differences V1−V2 of −0.34 to −0.61, all p < 0.05 in V1's
favor. G1, G2 failed on all four. V2-C (QB/player features) was least bad;
V2-D (47 regressors) was worst. All four froze α at the grid maximum
(100.0) — the heaviest shrinkage — and still lost.

Error correlations with V1 are 0.946–0.959: the V2s are NOT near-identical
twins (G5 passes everywhere). The architecture genuinely produces different
predictions — they are simply worse predictions. This rules out "V2 was
just V1 in disguise" as an explanation of the null.

## Important qualification on G3

All candidates failed the preregistered calibration gate (G3, |bias| < 1.0):
V2 signed bias +1.13 to +1.21. But V1 on the same 543 games has signed bias
**+1.21** — the bias is a property of the 2021–2022 sample (the ~+1.3 home
drift identified in the V1 architecture audit), not a V2 defect. The gate
as preregistered would fail V1 itself; noted as a gate-design flaw. The
outcome does not hinge on G3 — G1/G2 failed decisively.

## What this means

1. **The component architecture is not the answer.** Separating offense
   and defense, adding matchup interactions, historical QB value,
   continuity, pressure, explosiveness shape, and possession structure —
   153 inventoried features' worth of structure — did not beat V1's simple
   ELO/EPA/GBM scalar blend. The extra information either duplicates what
   the scalar strength signal already captures or is noise.
2. **Consistent with the audit hypothesis.** The V1 architecture audit found
   the scalar point-estimate target may be the binding constraint (GBM with
   a feature superset performed worst alone). V2 attacked the feature side
   and failed; the binding constraint, if it exists, is elsewhere.
3. **A market-beating V2 was not manufactured.** Per the directive: no
   post-hoc tuning, no V2-E, no vault run, no production change.

## Retained / rejected

- **Retained (research infrastructure):** the rebuilt Tuesday-safe modeling
  table (PFR W−2 shift, row-level injury cutoff), the walk-forward harness,
  the QB historical-value builder, the timestamp policies. All reusable.
- **Rejected as a production architecture:** V2-A, V2-B, V2-C, V2-D. The
  families they tested (matchup, QB/player, pressure, explosiveness,
  possession) carry no incremental margin-prediction value in this linear
  framework on 2021–2022.
- **Quarantined throughout:** qb_value_poll (2026-anchored), 2025/26 injury
  rows (no date_modified), qb_pressured_pct_rw (Friday-safe only).

## Decisions made

- V1 remains the production model, unchanged (V1 code was read-only
  throughout; verified unmodified).
- Vault 2023–2025 stays pristine — never read, listed, or computed on.
- Experiment 006 continues independently, untouched.
- No further V2 work is authorized under this directive.

## Files

- Research: `v2_research/protocol.md` (frozen, §10 amendments A1–A3),
  `v2_research/blocker_resolution.md`, `v2_research/family_overlap_matrix.json`,
  `v2_research/leakage_audit_v2_final.md`, `v2_research/validation_results.json`,
  `v2_research/validation_report.md`, this report.
- Build scripts: `scripts/30`–`36` (feature builders), `37_v2_qb_value.py`,
  `38_v2_rebuild_table.py`, `38_v2_overlap_matrix.py`, `39_v2_harness.py`,
  `40_v2a.py`, `41_v2b.py`, `42_v2c.py`, `43_v2d.py`, `44_v2_evaluate.py`.
- Artifacts: `data/v2/team_features_pred_v2.parquet` (rebuilt table),
  `data/v2/qb_value_pred.parquet`, `data/v2/pred_v2{abcd}.parquet`,
  `data/v2/manifest_v2{abcd}.json`.

## Limitations

- 2021–2022 validation only; the vault was deliberately not used.
- Calibration gate G3 was miscalibrated against the sample's home drift.
- The frozen α grid's upper bound (100.0) bound all four candidates —
  unacted on per protocol, but the optimum lying at/above the boundary is
  evidence the features wanted maximum shrinkage, i.e., carried little signal.
- Week-grain feature tables cannot reflect the four 2020 post-batch
  kickoffs (frozen pipeline limitation, documented in manifest_v2a).
- Injuries: 2025/26 files lack date_modified and were excluded.
