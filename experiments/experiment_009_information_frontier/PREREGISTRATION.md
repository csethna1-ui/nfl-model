# Experiment 009 — Preregistration Protocol: NFL Information-Frontier & Market-Residual Audit

**Status:** FROZEN 2026-09-30, before any 2023–2025 locked-test computation in this experiment.
**Scope:** research only. No V1 changes, no dashboard/artifact changes, no pipeline changes,
no modification of Experiments 001/002/004/005/007/008, feature_discovery_audit, v1_architecture_audit,
or the closed research tree. New artifacts only under `experiments/experiment_009_information_frontier/`.

## 0. Numbering note (record hygiene)

"009" was previously the slot for a deprioritized ensemble-weight experiment that was never
pursued (the weight question was closed by the preregistered 2023–25 generalization diagnostic on
2026-09-29 instead). Cale reassigned 009 to this audit on 2026-09-30. There is no weight
experiment under this number; nothing from that slot is inherited.

## 1. Role and principle

Independent audit of (a) whether frozen V1 is missing pregame information that could materially
improve margin prediction, and (b) whether predicting market residuals is a better target than
predicting raw margin. Skeptical by default. "Nothing we can validate" is a legitimate outcome.
No invented data, sources, or availability. If a dataset/timestamp cannot be obtained, document
the limitation and stop that branch.

## 2. Reconciled baseline (reproduced 2026-09-30 from `data/games_with_preds.parquet`)

Sign convention: `ens_margin` and `spread_line` are both home-perspective predicted margins
(positive = home favored). Verified: corr(spread_line, home_margin) = +0.446.

| Window | n | V1 MAE | Market MAE | Gap |
|---|---|---:|---:|---:|
| Validation 2021–22 (all, incl. playoffs) | 569 | 10.0425 | 9.7267 | 0.3158 |
| Validation 2021–22 (REG only) | 543 | 10.0592 | 9.7634 | 0.2958 |
| Locked 2023–25 (REG only) | 816 | 10.1867 | 9.7445 | 0.4422 |
| Locked 2023–25 (all, incl. playoffs) | 857 | 10.2285 | 9.7905 | 0.4380 |

Reconciliation: `backtest_report.md`'s 10.22/9.79 = all-games sample (n=857, reproduced 10.2285/9.7905).
The brief's "V1 ~10.19 / market ~9.75 / gap ~0.44" = the weight-generalization diagnostic's
regular-season sample (reported 10.187/9.745, n=816; reproduced 10.1929/9.7494, n=818 — 2-game /
0.005-MAE difference, immaterial, likely a pipeline filter nuance; documented, not investigated
further). **Canonical baseline for this experiment: V1 10.1929, market 9.7494, gap 0.4435 on
2023–25 REG (n=818).** Validation reference: V1 10.0425 vs market 9.7267 (n=569).

Market-spread provenance caveat (from Experiment 004, carried forward): historical `spread_line`
is an nflverse single undated snapshot per game — suitable as a coarse benchmark, NOT a
timestamp-verified tradable line. All historical model-vs-market comparisons are timestamp-unknown.
Do not "correct" this statistically; do not present residual improvements as tradable edge.

## 3. Data split and vault discipline

- TRAIN: 2018–2020. VALIDATION: 2021–2022. LOCKED TEST: 2023–2025. 2026: monitoring only.
- The locked test may be touched **exactly once**, for **one preregistered diagnostic only**:
  the fixed market-anchored blend (§5A) with its single weight fit on validation. This is a
  diagnostic confirmation of incremental information, NOT a production candidate (it consumes the
  market spread as an input and therefore cannot be deployed as a standalone predictor).
- Everything else in this experiment is validation-only (2021–2022), descriptive, or read-only
  synthesis of prior experiments. No tuning, selection, or debugging decisions on the locked test.

## 4. Statistical standard and decision rules

- Primary metric: MAE. Also: RMSE, median AE, bias, season-by-season MAE, n.
- Every claimed improvement: `challenger MAE − baseline MAE` with 95% paired bootstrap CI
  (≥1000 iterations, fixed seed 42).
- **Materiality threshold (preregistered): ≥0.15 MAE** — the project's established noise guard
  (Experiment 004). A challenger is "meaningful" only if the 95% CI excludes zero AND
  |delta| ≥ 0.15 AND the effect holds in both validation seasons (2021 and 2022) individually.
- For the locked-test blend confirmation: meaningful only if the same bar clears on 2023–2025.

## 5. Preregistered analyses

### A. Market-anchoring experiment (Part 3) — validation 2021–22 (n=569), then §5G confirmation
- A) frozen V1 (`ens_margin`).
- B) market-only (predicted margin = `spread_line`; residual defined as 0).
- C) blend: `w·V1 + (1−w)·market`, single weight w chosen by 0.05-grid MAE minimization on
  validation. This is the preregistered diagnostic of V1's incremental information over the market.
- D) V1 + market + selected features: **NOT RUN** — no feature family survived prior gates
  (Experiments 001–005, 007, V2-A–D all null); there is no validated feature to add. Documented as
  a deliberate omission, not an oversight.
- E) residual model: **cited, not re-run** — Experiment 001 (ridge on residual, validation):
  market-only won; vault untouched by design. Re-running it would be redundant.

### B. Training-window audit (Part 5) — validation only, no locked test
Refit the two frozen linear mappings (ELO→margin on `elo_diff`; EPA→margin on the 8 EPA/SR
differentials) under alternative walk-forward training windows and evaluate the resulting
ensemble (GBM component and 0.4/0.5/0.1 weights held fixed, isolating the window effect):
- W0 (frozen): fit on 2018–2020, applied to 2021–2022.
- W1 rolling-2: for season S, fit on [S−2, S−1].
- W2 rolling-1: for season S, fit on [S−1].
- W3 expanding: for season S, fit on [2018, S−1].
(Training pool for predicting S is all seasons < S — strict walk-forward. For S=2022 this
includes validation year 2021 in W1/W2/W3 training sets: legitimate, no future leakage for
2022 predictions; disclosed here.)
- W4 drop-2018: fit on 2019–2020.
OLS via the same linear form as `04_backtest.py`. Report validation MAE per window and per season.
Decision: the window matters only if a challenger clears the §4 bar vs W0.

### C. Model-specification synthesis (Part 6) — read-only, no new fitting except correlations
Synthesize from v1_architecture_audit + weight_generalization (both frozen artifacts):
- 40/50/10 vs ELO+EPA-only (0.5/0.5/0.0): 10.043 vs 10.045 on validation — GBM weight ~irrelevant.
- GBM alone: 10.463 (worst component). ELO–EPA prediction corr 0.763; signed-error corr 0.949.
- Add: ELO–EPA *prediction* correlation and *error* correlation recomputed on the locked sample
  is NOT permitted (would be a locked-test touch outside §5G) — report validation values only,
  plus the weight-diagnostic's locked component MAEs (already-frozen artifact, not a new evaluation).
- Ridge/regularized alternatives on the same information set: covered by the frozen research
  program (V2-A–D, Experiment 001 ridge) — all null; not re-run.

### D. Segment analysis (Part 7) — validation only, descriptive
Verify Experiment 002 Phase-1 segments from `games_with_preds.parquet` (do not re-tune):
weeks 1–4 / 5–9 / 10–18; home fav/dog, road fav/dog (fav = |spread_line|>0 side); spread-size
buckets 0–3 / 3–7 / 7+ (documented; the brief's 0–1/1–2/2–3/3+ bins are too fine for n=569 —
this amendment is preregistered here, rationale: bucket n≥60); season; divisional vs
non-divisional. Report V1 MAE, market MAE, delta per segment. Diagnosis only.

### E. Edge-bucket evaluation (Part 8) — validation only, buckets fixed a priori
Conventions (preregistered): edge = ens_margin − spread_line (home perspective).
Bet home if edge ≥ +t, away if edge ≤ −t. Home covers if (home_margin − spread_line) > 0;
push if == 0 (excluded from win%, counted separately).
Buckets on |edge|: [0,1), [1,2), [2,3), [3,4), [4,∞). Per bucket: n, mean |model error|,
ATS W–L, win%, push%, 95% Wilson CI on win%, and the operating threshold |edge|≥3.0 check
(must reproduce backtest_report's 103–88 as a convention sanity check).
CLV per bucket: NOT reported historically — no timestamp-valid lines (see §5F).
No bucket tuning on the locked test.

### F. CLV (Part 9)
Historical CLV: **cannot be reliably reconstructed** — the historical spread snapshot is
timestamp-unknown (Experiment 004), so "beat the close" has no defined close. State this
explicitly; do not fabricate.
Live 2026 CLV: report the production-tracked figures as observed (n=14 graded picks,
+0.32 avg CLV as of 2026-09-30) with the small-n caveat. This is the project's only
timestamp-aligned CLV substrate; it is reported, not evaluated, here.

### G. Locked-test confirmation (single touch)
Evaluate the §5A blend C with its validation-fit weight w on 2023–25 REG (n=818), exactly once:
blend MAE, delta vs market-only and vs V1, 95% paired bootstrap CI, per-season breakdown.
Meaningful only under the §4 bar. Any other locked-test computation is forbidden.

### H. Leakage audit (Part 10)
Feature-level table for every input to a serious candidate in this experiment. Serious
candidates: the §5A blend (inputs: ens_margin components, spread_line snapshot) and the §5B
window variants (inputs: elo_diff, 8 EPA/SR differentials, home_margin 2018–2020). All other
families were stopped at prior gates; their leakage assessments are cited from Experiments
001/004/005 and the frontier ledger, not re-audited.

## 6. Boundaries (binding)

- PFT news-timing corpus: do not use, model on, or disturb (separate track, verdict 2026-10-01).
- Experiment 006 (line-timing observational): do not touch.
- Betting-splits / line-movement feasibility audit: QUEUED as a separate track pending the PFT
  verdict — do NOT start it here. % tickets / % money / line-movement histories are
  hypothesized-inaccessible for this experiment; document as unavailable-pending-separate-audit.
- 2023–2025 power-ranking vault confirmation (2026-09-30): different target (team-strength
  ranking), fixed zero-parameter spec, no game-margin features tuned. Noted; does not contaminate
  the locked test for these candidates.
- 2026 data: monitoring/reporting only. Never for tuning or selection.

## 7. Required outputs

`experiments/experiment_009_information_frontier/`: this protocol, `frontier_table.csv`,
`results.json` (all computed numbers), `REPORT.md` (the 9 required sections), `leakage_audit.md`,
reproducibility manifest (scripts, seeds, file hashes/row counts).

## 8. Anti-overfit rule

Protocol frozen before the locked test. No test→fail→invent→retest loop. The §5G evaluation
runs exactly once with the preregistered weight. If it fails the §4 bar, the verdict is null
and no alternative weight, window, or specification is tried on the locked test.
