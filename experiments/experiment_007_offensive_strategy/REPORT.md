# Experiment 007 — Offensive Strategy: REPORT

**Status: CLOSED null. Vault untouched. V1 remains production. No V2.**

## Objective

Test whether offensive strategy/tendency information — *how a team chooses to
play* — provides genuinely new pregame information beyond frozen V1, which
knows only *how efficiently a team has played*. This was the Tier-1 candidate
from the Feature Discovery Audit and the first experiment to test a different
dimension of football rather than another representation of team strength.

## Preregistered design (locked before any validation computation)

- **Features (only these three):** offensive PROE, early-down pass rate,
  offensive pace (seconds/play). Full definitions: `feature_definition.md`.
- All computed strictly from games completed **before** the prediction week;
  weekly batching; min 2 games else differential = 0; hard offseason reset.
- **Candidate:** `candidate_margin = v1_margin + Ridge(α=1.0)` predicting
  `residual = actual_margin − v1_margin` from the 3 home−away differentials.
- **Training procedure:** two-fold season cross-fit within 2021–2022
  (fit 2021 → predict 2022; fit 2022 → predict 2021). Rationale, preregistered:
  frozen V1 predictions exist only for 2021+ (2018–2020 spine rows have null
  `v1_margin`), so 2018–2020 cannot supply the residual target. Same constraint
  and remedy as Experiment 005, stated upfront here rather than amended.
- **Baselines:** market-only, frozen V1, V1 + strategy candidate.
- **Gate A–F** per `config.json`. No tuning after results.
- Experiment 006 untouched; no 2026 observations used; vault never accessed.

## Validation results (2021–2022, n=569)

| Model | MAE | RMSE | Calibration | 2021 MAE | 2022 MAE |
|---|---|---|---|---|---|
| Market-only | 9.727 | 12.562 | 0.939 | 10.667 | 8.783 |
| Frozen V1 | 10.042 | 12.937 | 0.941 | 11.082 | 8.999 |
| V1 + strategy | 10.157 | 13.027 | 0.857 | 11.203 | 9.108 |

- **Error correlation:** V1–candidate **0.995** (prediction correlation 0.974).
  The candidate is V1 plus noise — the highest error correlation of any
  experiment run (003: 0.985, 005: 0.985).
- **Feature–residual correlations (full sample):** PROE +0.011, early-down
  +0.021, pace −0.012. Effectively zero.
- **Fold coefficients flip sign on every feature:**
  - PROE: +0.31 (fit 2021) → −0.38 (fit 2022)
  - Early-down: +0.93 → −0.48
  - Pace: +0.67 → −1.08
- **Ablations** (drop one feature, refit): 10.087–10.155, all worse than V1's
  10.042.

## Gate decision

| Criterion | Result |
|---|---|
| A. Materially beat V1 (≥0.10 MAE) | **FAIL** — candidate worse (10.157 vs 10.042) |
| B. Beat market by ≥0.15 MAE | **FAIL** — loses by 0.430 |
| C. Holds in both 2021 and 2022 | **FAIL** — worse in both |
| D. Calibration in [0.8, 1.2] | PASS (0.857) |
| E. Error correlation < 0.95 | **FAIL** (0.995) |
| F. Coefficient stability | **FAIL** — all three signs flip; ablations don't beat V1 |

**Vault evaluations: 0.**

## Diagnostics (descriptive only — no filters or corrections created)

- No bucket shows a meaningful candidate advantage: division 10.864 vs 10.663
  (worse); weeks 15+ 9.998 vs 10.100 (0.10, n=153, descriptive only);
  edge 5+ 9.809 vs 10.045 (n=73, descriptive only); home-dog 10.379 vs 10.261.
- The strategy differentials carry no stable linear relationship to V1's
  residual in either season.

## Verdict

The preregistered offensive-strategy representation — PROE, early-down
tendency, pace, as home−away differentials on a regularized residual
correction — did not provide stable out-of-sample improvement over V1. The
coefficients fit noise on ~285-game folds (every sign flips across seasons)
and the candidate's errors are nearly identical to V1's (0.995).

**What this tells us about the hypothesis.** The defensible conclusion is
narrow: *this* preregistered strategy representation gave no stable
out-of-sample improvement. It does not prove "strategy never matters," and it
does not close the door on the audit's other Tier-1 families (explosiveness,
pressure), which were explicitly excluded from 007 and remain untested. But
combined with Experiments 001–005, the pattern is now six attempts across
representations, information categories, and football dimensions — residual
modeling, opponent adjustment, dynamic strength, player availability, and now
play-calling tendency — with candidate–V1 error correlations of 0.985–0.995
every time a candidate was built. The model's mistakes are remarkably
invariant to what we add.

Per the authorization for this experiment: do **not** automatically proceed
to explosiveness or pressure as Experiment 008. Bring this report for human
review first, alongside the accumulating Experiment 006 timing evidence.

## Files

- `config.json` — preregistered design (locked pre-validation)
- `feature_definition.md` — exact feature construction rules
- `leakage_audit.md` — timing/leakage controls
- `validation_results.json` — baselines and splits
- `stability_analysis.json` — coefficient stability (gate F)
- `diagnostics.json` — contributions, ablations, buckets, correlations
- `gate_decision.json` — per-criterion gate record
- Build script: `scripts/25_experiment_007_strategy.py` (V1 code untouched)

---

GATE FAILED — vault remains untouched
