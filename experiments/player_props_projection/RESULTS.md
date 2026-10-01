# RESULTS — Player Projection Experiment 001

**Status: COMPLETE 2026-09-30. Single locked-test evaluation, no iteration on test results.**
Binding spec: `PREREGISTRATION.md` (approved and re-frozen 2026-09-30, with the Model D
equal-weight amendment). Fit on train (2018–2020) only; selected on dev (2021–2022) only;
evaluated on the locked test (2023–2024) exactly once. 2025 excluded (spent, reference-only).
V1, Experiment 006, and the PFT corpus untouched. No PFT/news data, no prop lines,
no game-time weather anywhere in this experiment.

Script: `scripts/run_experiment_001.py`. Raw outputs:
`data/experiment_001_results.json`, `data/experiment_001_test_predictions.parquet`.

---

## 1. Dev selection (2021–2022) — what was frozen before the test

| Market | Choice |
|---|---|
| Model A ridge α | 10.0 for all three markets (dev-MAE selection over {0.1, 1, 10, 100}) |
| Model B GBM params | lr=0.05, max_depth=3, max_iter=200 for all three markets (8-combo grid, dev-MAE) |
| Model C quantile GBM | Fixed a priori: lr=0.1, max_depth=3, max_iter=300, min_samples_leaf=20 (no selection) |
| D-variant NNLS weights (dev-fit, frozen) | pass [0.515, 0.465, 0.020], rush [0.712, 0.222, 0.066], rec [0.407, 0.568, 0.025] (A/B/C) |

Dev MAE (for context; selection ground, not the verdict):

| Model | Pass (n=986) | Rush (n=1500) | Receiving (n=3689) |
|---|---|---|---|
| Baseline (EWMA, no matchup adj) | 65.75 | 26.82 | 25.01 |
| A: opportunity × efficiency | 58.69 (−10.7%) | 25.32 (−5.6%) | 24.43 (−2.3%) |
| B: GBM | 58.52 (−11.0%) | 25.78 (−3.9%) | 24.23 (−3.1%) |
| C: quantile median | 59.26 (−9.9%) | 25.37 (−5.4%) | 23.98 (−4.1%) |
| D: equal-weight A/B/C | 57.77 (−12.1%) | 25.15 (−6.2%) | 23.98 (−4.1%) |
| D-variant (dev weights) | 57.65 (−12.3%) | 25.22 (−6.0%) | 24.19 (−3.3%) |

---

## 2. Locked-test MAE (2023–2024, pooled) — the preregistered table

| Model | Pass Yds MAE (n=1010) | Rush Yds MAE (n=1528) | Rec Yds MAE (n=3625) | Meets bar? |
|---|---|---|---|---|
| Baseline (EWMA, no matchup adj) | 65.32 | 25.82 | 24.70 | — |
| A: opportunity × efficiency | 61.28 (**−6.2%**) | 25.46 (−1.4%) | 24.57 (−0.5%) | **No** |
| B: GBM | 61.51 (**−5.8%**) | 25.49 (−1.3%) | 24.45 (−1.0%) | **No** |
| C: distributional (median) | 61.91 (**−5.2%**) | 24.70 (−4.3%) | 24.05 (−2.6%) | **No** |
| D: ensemble (equal-weight) | 60.62 (**−7.2%**) | 24.83 (−3.8%) | 24.13 (−2.3%) | **No** |
| D-variant (dev weights, separate) | 60.59 (−7.2%) | 25.18 (−2.5%) | 24.38 (−1.3%) | **No** |

Reference (published, not a clean test): 2025 current system 63.1 / 25.4 / 22.5.

---

## 3. Win-bar checklist (per model; all four conditions must hold)

Bar: (1) ≥5% reduction in ≥2 of 3 markets pooled; (2) no market regresses >2%;
(3) ≥2% in 2023 and 2024 individually for each claimed market; (4) 95% paired
bootstrap CI of the MAE difference excludes zero (pooled, per claimed market).
Min-n: 1010/1528/3625 ≥ 700/1000/2500 ✓. Per-season n ≥ 150 ✓.

| Model | (1) ≥5% in ≥2/3 | (2) no regression >2% | (3) per-season ≥2% | (4) bootstrap CI ≠ 0 | Verdict |
|---|---|---|---|---|---|
| A | 1/3 (pass 6.2 ✓; rush 1.4, rec 0.5 ✗) → **fail** | pass (worst +0.5%) | pass: 2023 +6.2, 2024 +6.2 ✓ | pass [+1.46, +6.56] ✓ | **Bar not cleared** |
| B | 1/3 (pass 5.8 ✓; rush 1.3, rec 1.0 ✗) → **fail** | pass | pass: 2023 +5.7, 2024 +6.0 ✓ | pass [+1.31, +6.43] ✓ | **Bar not cleared** |
| C | 1/3 (pass 5.2 ✓; rush 4.3, rec 2.6 ✗) → **fail** | pass | pass: 2023 +3.7, 2024 +6.7 ✓ | pass [+0.90, +5.91] ✓; rush [+0.53, +1.73] ✓; rec [+0.29, +1.02] ✓ | **Bar not cleared** |
| D (primary) | 1/3 (pass 7.2 ✓; rush 3.8, rec 2.3 ✗) → **fail** | pass (worst +2.3%) | pass: 2023 +6.9, 2024 +7.5 ✓ | pass [+2.30, +7.31] ✓; rush [+0.40, +1.59] ✓; rec [+0.21, +0.95] ✓ | **Bar not cleared** |
| D-variant | 1/3 → **fail** | pass | — | pass [+2.47, +7.10] ✓; rush [−0.00, +1.27] ✗; rec [−0.07, +0.72] ✗ | **Bar not cleared; reported separately per protocol** |

**Primary verdict: the preregistered bar is NOT cleared. No model achieves ≥5% in
two of three markets. On the preregistered primary question, this is a null.**

What is nevertheless real (narrowly stated, not a bar-clearing claim):
- The **pass market** improves 5.2–7.2% pooled for all four challengers, clears
  ≥2% in *both* 2023 and 2024 individually, and every bootstrap CI excludes zero.
  A genuine, consistent effect in one market.
- Rush (C +4.3%, D +3.8%, significant) and receiving (C +2.6%, D +2.3%,
  significant) show small, significant gains that fall short of the 5%
  materiality bar. A and B are ~1% on rush/receiving with CIs including zero —
  indistinguishable from noise there.
- Dev→test shrinkage was material (e.g. D pass −12.1% dev → −7.2% test),
  which is why the locked test exists.

---

## 4. Secondary hypothesis test (preregistered)

Hypothesis: *"Opportunity modeling reduces the big playing-time-driven misses
that dominate the current projector's error."*
Test: MAE on the **top decile of baseline absolute errors** (subset selected by
the fixed baseline — no challenger selection leaks in), vs the other 90%.

| Market | Subset | Baseline | A | B | C | D |
|---|---|---|---|---|---|---|
| Pass (thr 134.0, n_top=101) | top-decile MAE | 170.54 | 128.23 (**−24.8%**) | 123.46 (**−27.6%**) | 126.12 (**−26.0%**) | 125.56 (**−26.4%**) |
| | rest MAE | 53.63 | 53.84 (−0.4%) | 54.63 (−1.9%) | 54.78 (−2.1%) | 53.41 (+0.4%) |
| Rush (thr 55.1, n_top=153) | top-decile MAE | 74.33 | 65.76 (**−11.5%**) | 66.02 (**−11.2%**) | 68.32 (**−8.1%**) | 66.70 (**−10.3%**) |
| | rest MAE | 20.42 | 20.97 (−2.7%) | 20.98 (−2.7%) | 19.84 (+2.8%) | 20.17 (+1.2%) |
| Receiving (thr 53.6, n_top=363) | top-decile MAE | 74.07 | 65.43 (**−11.7%**) | 64.71 (**−12.6%**) | 68.06 (**−8.1%**) | 66.04 (**−10.8%**) |
| | rest MAE | 19.20 | 20.02 (−4.3%) | 19.97 (−4.0%) | 19.15 (+0.3%) | 19.47 (−1.4%) |

**The hypothesis gains support.** In all three markets the challengers shrink the
big-miss tail substantially (8–28%) while typical-error performance is roughly
flat (within ±4%). Model A — the pure opportunity × efficiency decomposition —
shows the preregistered pattern most cleanly on pass (−24.8% on the big misses,
−0.4% elsewhere). Note B matches A closely, so the data do not isolate the
decomposition as the *only* mechanism: there is predictive structure the GBM
finds that is roughly the same size as what the two-stage model captures.

---

## 5. Honest verdict

1. **The preregistered bar failed.** No model clears ≥5% in two of three
   markets. By the protocol's own terms, richer opportunity/efficiency
   information does not *materially* beat the EWMA projector across the board.
2. **The pass market is a real exception:** +5–7% for every challenger,
   consistent across both seasons, bootstrap-significant. If a follow-up is ever
   authorized, the pass market is where the signal lives.
3. **The mechanism hypothesis is supported:** big-miss errors shrink 8–28%
   while typical errors stay flat — the gains concentrate exactly where the
   opportunity story says they should.
4. **A ≈ B on pass** (+6.2% vs +5.8%): the simple two-stage decomposition
   captures essentially everything the GBM finds there. Interpretability comes
   nearly free in this market.
5. **Rush/receiving are near-nulls** on magnitude: small significant gains for
   C/D (2–4%), noise for A/B. The EWMA is a strong baseline in these markets.
6. The D-variant (dev-learned weights) adds nothing over equal weighting and,
   per protocol, does not replace primary D.

No further modeling on this branch without a new authorized protocol. The
2023–2024 test slice is now spent for these candidates.
