# RESULTS — Props Experiment 006: Role-Change Mechanisms

**Status: COMPLETE 2026-10-01. Single locked-test evaluation (2023–2024), run once.**
**No fitting was performed. Locked parameters asserted equal to `LOCKED_PARAMETERS.json` at eval time.**

## Verdict

**NULL on all three targets, both rungs.** No rung clears any prong of the win bar on any target. M1 (contrast features + Ridge) is statistically indistinguishable from frozen Model D on pass yards (+0.33%, CI includes zero) and significantly-but-trivially worse on rush (−1.67%) and receiving (−0.34%), with bootstrap CIs excluding zero in the wrong direction. M2 (Kalman) is decisively worse everywhere (−19.8% to −32.9%), exactly as the dev specification pathology predicted. This is not a partial signal; it is a clean, preregistered null.

| Target | Best rung vs M0 (pooled) | Win bar | Verdict |
|---|---|---|---|
| pass_yards | M1: +0.3% | not cleared | NULL |
| rush_yards | M1: −1.7% (worse) | not cleared | NULL |
| receiving_yards | M1: −0.3% (worse) | not cleared | NULL |

## M0 integrity

Reproduced from the frozen 001 procedure (fit on train 2018–2020 only, frozen dev-selected hyperparameters) and verified **bit-identical** against the stored 001 test predictions (`experiment_001_test_predictions.parquet`, `pred_D`, max diff 0.00e+00) on all three markets before any candidate was evaluated:
- pass_yards: n=1,010 | rush_yards: n=1,528 | receiving_yards: n=3,625.

## Locked-test MAE by target, rung, and slice

n = eligible test rows (2023–2024). Relative change = (M0 − rung)/M0; positive = rung better.

### pass_yards (n=1,010)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) |
|---|---|---|---|---|
| overall | 1010 | 60.6220 | 60.4202 (+0.33%) | 77.6046 (−28.01%) |
| transfer_stint | 465 | — | (+1.47%) | (−27.49%) |
| stint games 1–3 | 101 | — | (−0.90%) | (−27.90%) |
| stint games 4–6 | 81 | — | (+2.33%) | (−26.75%) |
| high_contrast | 101 | — | (+0.60%) | (−31.76%) |
| non_transfer | 545 | — | (−0.71%) | (−28.50%) |
| 2023 | 503 | — | (+0.26%) | (−30.02%) |
| 2024 | 507 | — | (+0.40%) | (−25.98%) |

Paired bootstrap 95% CI of (M0 − rung) MAE, 2000 resamples, seed 1337:
- M1 overall: +0.20 [−0.46, +0.87] — includes zero.
- M1 transfer_stint: +0.93 [−0.18, +2.03] — includes zero.
- M2 overall: −16.98 [−20.35, −13.54]; transfer_stint: −17.35 [−22.60, −12.06].

### rush_yards (n=1,528)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) |
|---|---|---|---|---|
| overall | 1528 | 24.8311 | 25.2468 (−1.67%) | 29.7486 (−19.80%) |
| transfer_stint | 731 | — | (−1.48%) | (−20.20%) |
| stint games 1–3 | 160 | — | (+0.52%) | (−24.04%) |
| stint games 4–6 | 122 | — | (−0.68%) | (−22.98%) |
| high_contrast | 153 | — | (+2.84%) | (−21.29%) |
| non_transfer | 797 | — | (−1.87%) | (−19.40%) |
| 2023 | 765 | — | (−2.23%) | (−19.62%) |
| 2024 | 763 | — | (−1.17%) | (−19.97%) |

Paired bootstrap 95% CI of (M0 − rung) MAE:
- M1 overall: −0.42 [−0.68, −0.17] — excludes zero in the wrong direction.
- M1 transfer_stint: −0.39 [−0.75, −0.04] — excludes zero in the wrong direction.
- M2 overall: −4.92 [−6.16, −3.82]; transfer_stint: −5.26 [−7.20, −3.38].

### receiving_yards (n=3,625)

| Slice | n | M0 | M1 (Δ%) | M2 (Δ%) |
|---|---|---|---|---|
| overall | 3625 | 24.1309 | 24.2138 (−0.34%) | 32.0754 (−32.92%) |
| transfer_stint | 1528 | — | (−0.40%) | (−31.66%) |
| stint games 1–3 | 268 | — | (−0.35%) | (−24.90%) |
| stint games 4–6 | 198 | — | (−1.01%) | (−10.30%) |
| high_contrast | 363 | — | (−0.66%) | (−32.27%) |
| non_transfer | 2097 | — | (−0.30%) | (−33.80%) |
| 2023 | 1846 | — | (−0.34%) | (−34.03%) |
| 2024 | 1779 | — | (−0.35%) | (−31.76%) |

Paired bootstrap 95% CI of (M0 − rung) MAE:
- M1 overall: −0.08 [−0.15, −0.01] — excludes zero in the wrong direction.
- M1 transfer_stint: −0.09 [−0.19, +0.01] — includes zero.
- M2 overall: −7.94 [−8.75, −7.12]; transfer_stint: −7.44 [−8.76, −6.15].

Slice-power notes (prereg underpowered rule): stint games 4–6 are underpowered on all targets (n=81/122/198 pooled, far below 150/season) — directional only. Stint games 1–3 are underpowered for pass (n=101 pooled); borderline for rush/receiving. No slice-level claim is made.

## Win-bar adjudication (per target, each rung independently)

Bar (all must hold): (1) pooled ≥5% overall AND transfer-stint; (2) ≥2% in 2023 AND 2024; (3) bootstrap 95% CI excludes zero, overall and transfer-stint; (4) non-transfer degradation ≤1%.

| Target | Rung | (1) 5% pooled | (2) 2%/yr | (3) CI≠0 | (4) guard | Verdict |
|---|---|---|---|---|---|---|
| pass | M1 | ✗ (+0.3%/+1.5%) | ✗ | ✗ | ✓ | NULL |
| pass | M2 | ✗ | ✗ | ✗ (wrong dir.) | ✗ | NULL |
| rush | M1 | ✗ | ✗ | ✗ (wrong dir.) | ✗ (−1.9%) | NULL |
| rush | M2 | ✗ | ✗ | ✗ (wrong dir.) | ✗ | NULL |
| rec | M1 | ✗ | ✗ | ✗ (wrong dir.) | ✓ | NULL |
| rec | M2 | ✗ | ✗ | ✗ (wrong dir.) | ✗ | NULL |

**Verdict per target: NULL.** No rung on any target clears any prong. No PARTIAL-SIGNAL: no rung has a bootstrap CI excluding zero in the right direction.

## Narrow interpretation

1. **M1 is a whisper, not a signal.** The contrast features are directionally right on pass yards (+0.33% overall, +1.47% on transfer stints — the same pattern dev showed: −1.75% in-sample, −1.08% CV), but an order of magnitude below the 5% bar and statistically indistinguishable from zero. On rush and receiving it is flat-to-negative, with CIs excluding zero in the wrong direction by trivial amounts (−1.67%, −0.34%). Unlike 005, there is no in-sample-vs-CV contradiction here — the capacity discipline worked as designed; the locked test simply shows the mechanism is too small to matter. It does not clear the bar and does not earn production consideration.
2. **M2 fails exactly as diagnosed on dev.** The 3-parameter specification (single observation-variance scalar `r` shared across the share and efficiency states) degenerates: the filter chases noisy per-game efficiency and the multiplicative projection amplifies it into −20% to −33% MAE degradation. Per prereg §6, this null is informative about the specification as written, not about Kalman approaches generally — the per-state observation-variance variant remains untested and is explicitly not part of this experiment.
3. **Two preregistered role-mechanism experiments (005, 006) have now NULLed.** The reconstructable signals for team/role transitions — learned blends, transition decay, opportunity×efficiency separation, recent-vs-baseline contrasts, and a 3-parameter Kalman filter — do not improve on frozen Model D on the locked 2023–2024 test. The 2026-prospective depth-chart track remains a separate, untested question.
4. **No production-change package is produced.** Model D stands unchanged.

## Reproducibility

- `scripts/run_006_locked_test.py` — single-evaluation script (no fitting paths).
- `data/test_predictions.parquet` — M0/M1/M2 predictions on all evaluated test rows.
- `data/test_results.json` — machine-readable tables, bootstrap CIs, adjudication.
- `test_run.log` — full run log (17s).
- Seeds: 1337 throughout. Bootstrap: 2000 paired resamples.
- Hard rules honored: no 2023–2024 data in any fitting (none was performed); Model D artifacts, production scripts, and Experiments 004/005 untouched; market line never a feature; no vacated-volume features; Friday 18:00 CT as-of discipline via strictly-prior completed-game values.

## Production consequence

None. No candidate clears the bar; no architecture change is proposed. Per the shared protocol §8, the experiment stops here pending any new Cale-authorized direction.
