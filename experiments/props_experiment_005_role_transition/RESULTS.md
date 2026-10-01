# RESULTS — Props Experiment 005: Player Role Transition Model

**Status: COMPLETE 2026-10-01. Single locked-test evaluation, run exactly once. No refitting, no parameter changes, no model selection on test.**
**M0 integrity:** reproduced from the frozen 001 procedure (fit on train only, frozen dev-selected hyperparameters) and verified **bit-identical** against the stored 001 test predictions (`experiment_001_test_predictions.parquet`, `pred_D`, max diff 0.00e+00) on all three markets before any candidate was evaluated.
**Locked parameters:** read from `LOCKED_PARAMETERS.json` / the fitted pickles; this run asserted struct/class/hyper/order equality for all 9 rung×target configs — no deviations.
**As-of discipline:** stint features built from strictly-prior completed games only (train+dev+test walk, no future leakage); market line never a feature.

## Verdict

**NULL on all three targets.** No rung clears any prong of the win bar on any target. M1–M3 underperform M0 everywhere — overall, on transfer stints, on every diagnostic slice, and in both seasons — with paired-bootstrap 95% CIs excluding zero *in the wrong direction* (challengers significantly worse). This is not a partial signal; it is a clean, preregistered null, and it is exactly what the dev 5-fold CV diagnostic predicted (CV MAE 7–12% worse than M0 on every rung×target; see `LOCKED_PARAMETERS.md`).

| Target | Best rung vs M0 (pooled) | Win bar | Verdict |
|---|---|---|---|
| pass_yards | M2: −6.6% (worse) | not cleared | NULL |
| rush_yards | M1: −11.2% (worse) | not cleared | NULL |
| receiving_yards | M2: −6.5% (worse) | not cleared | NULL |

## Locked-test MAE by target, rung, and slice

n = eligible test rows (2023–2024). Relative change = (M0 − rung)/M0; positive = rung better.

### pass_yards (n=1,010)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) | M3 (Δ%) |
|---|---|---|---|---|---|
| overall | 1010 | 60.6220 | 64.8331 (−7.0%) | 64.6209 (−6.6%) | 67.8929 (−12.0%) |
| transfer_stint | 423 | 62.4800 | 67.8987 (−8.7%) | 66.1361 (−5.9%) | 71.4884 (−14.4%) |
| stint games 1–3 | 100 | 69.8274 | 75.5561 (−8.2%) | 72.9460 (−4.5%) | 76.6241 (−9.7%) |
| stint games 4–6 | 78 | 64.7501 | 69.8892 (−7.9%) | 62.5836 (+3.3%) | 65.9792 (−1.9%) |
| stint games 7+ | 245 | 58.7584 | 64.1395 (−9.2%) | 64.4876 (−9.8%) | 71.1462 (−21.1%) |
| non_transfer | 587 | 59.2830 | 62.6240 (−5.6%) | 63.5290 (−7.2%) | 65.3020 (−10.2%) |
| 2023 | 503 | 61.2275 | 66.1884 (−8.1%) | 66.0582 (−7.9%) | 69.1058 (−12.9%) |
| 2024 | 507 | 60.0212 | 63.4885 (−5.8%) | 63.1950 (−5.3%) | 66.6897 (−11.1%) |
| transfer 2023 | 205 | 62.6167 | 68.6076 (−9.6%) | 67.0736 (−7.1%) | 71.4071 (−14.0%) |
| transfer 2024 | 218 | 62.3515 | 67.2320 (−7.8%) | 65.2544 (−4.7%) | 71.5649 (−14.8%) |

Paired bootstrap 95% CI of (M0 − rung) MAE, 2000 resamples, seed 1337:
- overall: M1 [−6.34, −2.19], M2 [−6.08, −1.96], M3 [−9.64, −5.00]
- transfer_stint: M1 [−8.81, −2.10], M2 [−7.07, −0.42], M3 [−12.75, −5.22]
(All exclude zero — challengers significantly *worse*.)

### rush_yards (n=1,528)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) | M3 (Δ%) |
|---|---|---|---|---|---|
| overall | 1528 | 24.8311 | 27.6081 (−11.2%) | 27.7929 (−11.9%) | 28.8309 (−16.1%) |
| transfer_stint | 652 | 25.7242 | 27.9874 (−8.8%) | 28.4555 (−10.6%) | 29.6224 (−15.2%) |
| stint games 1–3 | 167 | 26.6619 | 27.0848 (−1.6%) | 28.4637 (−6.8%) | 29.5524 (−10.8%) |
| stint games 4–6 | 120 | 24.0333 | 26.8662 (−11.8%) | 28.6439 (−19.2%) | 28.9210 (−20.3%) |
| stint games 7+ | 365 | 25.8511 | 28.7690 (−11.3%) | 28.3899 (−9.8%) | 29.8851 (−15.6%) |
| non_transfer | 876 | 24.1664 | 27.3257 (−13.1%) | 27.2997 (−13.0%) | 28.2417 (−16.9%) |
| 2023 | 765 | 23.5226 | 26.6896 (−13.5%) | 26.9205 (−14.4%) | 27.9410 (−18.8%) |
| 2024 | 763 | 26.1431 | 28.5289 (−9.1%) | 28.6676 (−9.7%) | 29.7230 (−13.7%) |
| transfer 2023 | 290 | 23.6772 | 25.9904 (−9.8%) | 26.6934 (−12.7%) | 27.6260 (−16.7%) |
| transfer 2024 | 362 | 27.3641 | 29.5872 (−8.1%) | 29.8672 (−9.1%) | 31.2218 (−14.1%) |

Paired bootstrap 95% CI of (M0 − rung) MAE:
- overall: M1 [−3.42, −2.16], M2 [−3.67, −2.27], M3 [−4.74, −3.29]
- transfer_stint: M1 [−3.29, −1.30], M2 [−3.89, −1.62], M3 [−5.09, −2.66]

### receiving_yards (n=3,625)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) | M3 (Δ%) |
|---|---|---|---|---|---|
| overall | 3625 | 24.1309 | 25.7074 (−6.5%) | 25.6922 (−6.5%) | 26.5412 (−10.0%) |
| transfer_stint | 1454 | 23.5344 | 25.0555 (−6.5%) | 24.9897 (−6.2%) | 25.9571 (−10.3%) |
| stint games 1–3 | 274 | 22.1412 | 25.1244 (−13.5%) | 25.1165 (−13.4%) | 24.1429 (−9.0%) |
| stint games 4–6 | 204 | 22.5477 | 24.9909 (−10.8%) | 24.8013 (−10.0%) | 26.0744 (−15.6%) |
| stint games 7+ | 976 | 24.1317 | 25.0497 (−3.8%) | 24.9934 (−3.6%) | 26.4419 (−9.6%) |
| non_transfer | 2171 | 24.5305 | 26.1440 (−6.6%) | 26.1627 (−6.7%) | 26.9323 (−9.8%) |
| 2023 | 1846 | 24.3073 | 26.0385 (−7.1%) | 26.0573 (−7.2%) | 26.8857 (−10.6%) |
| 2024 | 1779 | 23.9479 | 25.3639 (−5.9%) | 25.3134 (−5.7%) | 26.1836 (−9.3%) |
| transfer 2023 | 749 | 24.3541 | 26.2999 (−8.0%) | 26.4266 (−8.5%) | 26.7881 (−10.0%) |
| transfer 2024 | 705 | 22.6635 | 23.7334 (−4.7%) | 23.4631 (−3.5%) | 25.0742 (−10.6%) |

Paired bootstrap 95% CI of (M0 − rung) MAE:
- overall: M1 [−1.94, −1.23], M2 [−1.93, −1.20], M3 [−2.81, −2.01]
- transfer_stint: M1 [−2.08, −0.96], M2 [−2.06, −0.90], M3 [−3.09, −1.72]

## Win-bar adjudication (per target, each rung independently)

| Condition | pass_yards | rush_yards | receiving_yards |
|---|---|---|---|
| 1. Pooled ≥5% reduction, overall | FAIL (best −6.6%) | FAIL (best −11.2%) | FAIL (best −6.5%) |
| 2. Pooled ≥5% reduction, transfer_stint | FAIL (best −5.9%) | FAIL (best −8.8%) | FAIL (best −6.2%) |
| 3. ≥2% in 2023 AND 2024 (overall) | FAIL | FAIL | FAIL |
| 4. 95% bootstrap CI excludes zero, overall + transfer_stint | FAIL (excludes zero the wrong way) | FAIL | FAIL |
| 5. Regression guard: non-transfer degradation ≤1% | FAIL (5.6–10.2%) | FAIL (13.0–16.9%) | FAIL (6.6–9.8%) |

**Verdict per target: NULL.** No rung on any target clears any prong.

## Narrow interpretation

1. **The mechanism was tested, not assumed — and it lost cleanly.** The preregistered hypothesis (current-role opportunity should dominate after a team change; efficiency carries over) was implemented exactly as designed, with all structural parameters learned on dev and frozen. On the locked test it underperforms frozen Model D on every target, every rung, every slice — including transfer-stint games 1–3, the mechanism's home turf (e.g. receiving: M1 −13.5% there). A null here does not prove role transitions don't matter; it proves *these reconstructable signals, combined this way*, add no value over the frozen engine.

2. **The failure mode is visible in the dev record.** In-sample dev MAE for the locked configs (e.g. pass M3: 26.33) was less than half the 5-fold CV MAE (63.84) — the in-sample selection procedure picked maximum-capacity GBMs that memorized dev. The locked test is the honest evaluation the protocol was built for, and it worked as designed: dev optimism did not survive contact with 2023–2024.

3. **The audit's exclusion of depth charts is unaffected.** The null concerns only the reconstructable signals in the ladder. It neither validates nor invalidates the 2026-prospective depth-chart track (§7 of the preregistration), which remains a separate, untested question.

4. **The regression guard fired as designed.** Non-transfer rows degraded 5.6–16.9% — the candidates did not merely fail to help transfers; they hurt ordinary players too. This is precisely the failure mode the ≤1% guard was written to catch.

5. **Sample adequacy is not the story.** Transfer-stint populations (423 / 652 / 1,454) and per-season transfer slices (all ≥150/season) are adequately powered; the stint 4–6 slice is underpowered for pass (78) and rush (120) and is reported directionally per the preregistration. The null is not a power artifact — the point estimates are uniformly negative with tight CIs.

## Reproducibility

- `scripts/run_005_locked_test.py` — the single evaluation (run once 2026-10-01)
- `data/test_predictions.parquet` — M0/M1/M2/M3 predictions on all eligible test rows
- `data/locked_test_metrics.json` — full slice metrics, RMSE/bias, bootstrap CIs
- `models/M{1,2,3}_{pass_yards,rush_yards,receiving_yards}_fitted.pkl` — frozen fitted models (unchanged)
- `LOCKED_PARAMETERS.json` — frozen parameters (unchanged; asserted equal at eval time)

## Production consequence

**None.** Per the preregistered production gate: no candidate cleared the bar, so no production-change package is produced and nothing in production changes. Frozen Model D stands untouched, as does Experiment 004.
