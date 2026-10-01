# RESULTS — Props Experiment 003D: Anytime Touchdown Scorer

**Status: COMPLETE — single locked-test evaluation performed 2026-10-01.**
**VERDICT: PARTIAL/SIGNAL — no production change.**

Preregistration frozen and approved by Cale 2026-10-01 12:25 CDT; the
protocol below was executed exactly once, with no deviations, no retries,
and no family selection after results.

---

## 1. Verdict

**PARTIAL/SIGNAL. No rung clears the preregistered win bar. No production
change.**

- Pooled 2023–2024 Brier reduction vs M0: M1 −1.36%, M2 −1.42%, M3 −1.61%
  (bar: ≥5%). **Fail.**
- Per-season ≥2% in both 2023 and 2024: M1 (1.83% / 0.91%), M2 (2.02% /
  0.84%), M3 (1.90% / 1.32%). **Fail** (no rung clears both seasons).
- Calibration (all rungs): max n≥100 bucket deviation ≤0.050, slope in
  [1.10, 1.13] ⊂ [0.85, 1.15]. **Pass.**
- 95% paired bootstrap CI of the Brier difference excludes zero for all
  three rungs. **Pass.**

The expected-opportunity model carries **real but small** incremental
information over trailing TD rate: the gains are statistically significant
per the preregistered bootstrap criterion, but at ~1.4–1.6% they are less
than a third of the 5% materiality bar. NGS adds nothing beyond M1
(M2 ≈ M1 on test; M2 was marginally worse than M1 on dev). Team/matchup/
game-context (M3) is the best rung at −1.61% — still far below the bar.

Per the shared protocol's verdict taxonomy this is PARTIAL/SIGNAL
("significant but sub-bar → reported narrowly, no production change"),
not a MATERIAL WIN and not a clean NULL: the signal is significant, so it
is reported narrowly rather than dismissed.

## 2. Locked-test metrics (2023–2024, single evaluation)

Evaluated rows: **n = 5,153 player-games, 1,563 TD events, base rate 0.3033**
(2023: n=2,611 / 756 events; 2024: n=2,542 / 807 events). Clears the
≥3,000 player-games / ≥500 events minimum comfortably.

| Rung | Brier | rel Δ vs M0 | log loss | ROC-AUC | PR-AUC | mean p | event rate |
|---|---|---|---|---|---|---|---|
| M0 (baseline) | 0.20375 | — | 0.59630 | 0.6185 | 0.4147 | 0.2969 | 0.3033 |
| M1 opportunity | 0.20097 | −1.36% | 0.58932 | 0.6387 | 0.4230 | 0.3224 | 0.3033 |
| M2 + NGS | 0.20085 | −1.42% | 0.58915 | 0.6391 | 0.4259 | 0.3250 | 0.3033 |
| M3 + context | 0.20047 | −1.61% | 0.58819 | 0.6406 | 0.4270 | 0.3188 | 0.3033 |

Per-season Brier (win-bar condition 2):

| Rung | 2023 Brier (M0) | 2023 rel Δ | 2024 Brier (M0) | 2024 rel Δ |
|---|---|---|---|---|
| M1 | 0.19571 (0.19936) | −1.83% | 0.20638 (0.20827) | −0.91% |
| M2 | 0.19533 (0.19936) | −2.02% | 0.20653 (0.20827) | −0.84% |
| M3 | 0.19556 (0.19936) | −1.90% | 0.20552 (0.20827) | −1.32% |

Paired bootstrap (2000 resamples, seed 1337) of per-row Brier difference
(M0 − rung), 95% CI:

| Rung | CI low | CI high | excludes zero |
|---|---|---|---|
| M1 | 0.00053 | 0.00511 | yes |
| M2 | 0.00078 | 0.00526 | yes |
| M3 | 0.00104 | 0.00555 | yes |

## 3. Calibration (test)

10 equal-width predicted-probability buckets on [0,1]; slope from logistic
regression of outcome on logit(p). Buckets with n<100 reported but excluded
from the bar.

**M3 (best rung):**

| Bucket | n | mean p | event rate | |dev| |
|---|---|---|---|---|
| 0.0–0.1 | 9 | 0.0910 | 0.0000 | 0.0910 (n<100, excluded) |
| 0.1–0.2 | 379 | 0.1744 | 0.1425 | 0.0319 |
| 0.2–0.3 | 2125 | 0.2531 | 0.2311 | 0.0220 |
| 0.3–0.4 | 1645 | 0.3417 | 0.3271 | 0.0147 |
| 0.4–0.5 | 661 | 0.4419 | 0.4554 | 0.0134 |
| 0.5–0.6 | 290 | 0.5384 | 0.5379 | 0.0004 |
| 0.6–0.7 | 44 | 0.6278 | 0.5227 | 0.1051 (n<100, excluded) |

Max |dev| over n≥100 buckets: **0.0319** (≤0.06 ✓). Slope: **1.096** ∈
[0.85, 1.15] ✓.

**M1:** max |dev| (n≥100) = 0.0356 ✓, slope 1.101 ✓.
**M2:** max |dev| (n≥100) = 0.0504 ✓, slope 1.130 ✓.
**M0:** max |dev| (n≥100) = 0.0534 ✓, slope **0.755** ✗ — the naive
baseline is over-shrunk toward the mean (probabilities too compressed),
as expected; the challengers repair this.

## 4. Dev diagnostics (2021–2022; hyperparameter selection ground only)

n_train = 6,860 evaluated (2,209 events); n_dev = 5,189 (1,594 events).

| Rung | dev Brier | dev slope | dev-selected C | dev-selected GBM |
|---|---|---|---|---|
| M0 | 0.20768 | 0.669 | — | — |
| M1 | 0.20465 | 0.985 | 0.1 | lr=0.05, depth=3, iter=200 |
| M2 | 0.20476 | 1.009 | 0.01 | lr=0.05, depth=3, iter=200 |
| M3 | 0.20386 | 1.025 | 0.01 | lr=0.05, depth=3, iter=200 |

Dev→test shrinkage is modest and in the expected direction (M1 dev −1.46%
vs M0 → test −1.36%). The ladder is fixed, so dev served only for
hyperparameter selection and procedure checks — no family selection.

## 5. What was and was not claimed

**Claimed (established by this experiment):**
- Expected TD opportunity as specified (red-zone/goal-line/inside-10/
  end-zone usage, target/carry share, snap share, team scoring environment,
  opponent red-zone defense, pre-week ELO game-script proxy) contains
  small but statistically significant incremental information over trailing
  TD rate for predicting whether a WR/TE/RB scores an offensive TD:
  −1.4% to −1.6% Brier reduction, 95% bootstrap CIs excluding zero, on
  5,153 locked-test player-games.
- The challenger probabilities are well-calibrated on the locked test
  (slopes 1.10–1.13; no n≥100 bucket deviates more than 0.05 from the
  diagonal).
- NGS tracking (separation, cushion, intended air yards, rushing
  efficiency, rush yards over expected/att — trailing only) adds no
  incremental value for anytime-TD prediction beyond the opportunity model
  (M2 ≈ M1 on test; M2 < M1 on dev).

**NOT claimed:**
- **This establishes projection quality ONLY. It cannot establish betting
  edge.** No timestamped historical anytime-TD markets exist keyless, so
  model-vs-market was not and could not be tested.
- **"Likely to score" is NOT a betting recommendation.** The experiment
  produces probabilities, not picks. No wagering implication may be drawn
  without validated calibration AND a prospective market comparison
  against timestamped lines (shared protocol §7). A well-calibrated 0.35
  is information; it is not a bet.
- Raw TD history was never used as a predictive feature (M0 baseline
  only); return/special-teams TDs are out of scope (target covers rushing
  + receiving TDs from offensive role).
- The sub-bar result does not mean "touchdowns are unpredictable" — it
  means *expected opportunity as specified* did not beat trailing TD rate
  by the preregistered materiality bar.

## 6. Protocol interpretation notes (frozen choices, documented)

These readings of the prereg were fixed before any locked-test computation
and applied identically to all rungs:
- **M0 shrinkage form:** M0 = (w·ewma_TD + k·pos_base) / (w + k), where
  ewma_TD is the trailing TD-binary EWMA (half-life 3, max 16 games,
  most-recent-first, strictly prior rows), w is the EWMA weight sum,
  k = 4 pseudo-games, and pos_base is the position (RB/WRTE) base rate on
  train evaluated rows (RB 0.4053, WRTE 0.2905). No-history rows → pos_base.
  Deterministic; nothing fitted.
- **Rung prediction rule:** per rung, LogisticRegression (C dev-selected
  from {10, 1, 0.1, 0.01} — the binary analog of 002's Ridge alpha grid
  {0.1, 1, 10, 100}) and HistGradientBoostingClassifier (log_loss,
  002's 8-combo grid dev-selected, random_state=11); rung probability =
  equal-weight mean of the two (mirrors 002's D = equal-weight mean of
  A/B/C). StandardScaler on logistic inputs; NaN→0 for all features per
  the trailing convention.
- **M1** = prereg §2/§4 opportunity features + `is_RB` position dummy +
  `trail_games` (mechanical pooled-model terms, documented; the position
  dummy is required because RBs score at materially higher base rates).
  "Expected game script" = `ctx_elo_adv` (pre-week ELO diff), the
  keyless timestamp-safe proxy per the leakage rule; spread/total/implied
  excluded everywhere.
- **M2** = M1 + NGS family exactly as audited (separation, cushion,
  intended air yards; rushing efficiency + rush yards over expected per
  attempt — all trailing-only EWMAs).
- **M3** = M1 + 002 context families B, C, D1, D2, E, J, L + QB family I
  (dedupe against M1 features).
- Calibration buckets are equal-width 10 on [0,1]; slope via logistic
  regression of y on logit(p) (p clipped to [1e-3, 1−1e-3]).
- 2025 was not evaluated (002 precedent: feature build covers 2018–2024;
  2025 is reference/robustness only and non-binding).

## 7. Data notes (no spec changes; nothing improvisational)

- **Test-set size vs prereg §1:** the prereg's audit-phase estimate was
  6,235 player-games / 1,830 events; the frozen build yields 5,153 /
  1,563 (base rate 0.303 vs 0.294). The difference is the Friday-18:00-CT
  "predictable game" filter inherited from the 001/002 base table
  (Thursday/early-kickoff games excluded per the as-of discipline) — the
  audit count appears to predate that filter. Population definition
  (WR/TE/RB, eligible_hist=1, played_role=1) was applied exactly as
  preregistered, and the ≥3,000 pg / ≥500 events minimum is cleared
  comfortably. Not a protocol deviation.
- **Target derivation:** td_binary from in-house pbp (rusher/receiver +
  touchdown==1); return/special-teams TDs excluded by construction, as
  preregistered.
- **New pbp derivations** (prereg "derivation needed"): inside-10
  carries/targets (yardline_100 ≤ 10), end-zone targets
  (air_yards ≥ yardline_100), opponent red-zone TD rate allowed per
  defensive play (yardline_100 ≤ 20), trailing EWMA. Opponent merge rate
  98.2% (remainder NaN→0 per convention).
- **NGS:** receiving cushion/intended-air-yards from the local
  2018–2024 parquet (merge rate 26.4% — NGS receiving covers targeted
  players); rushing efficiency pulled keyless via `nfl_data_py`
  `import_ngs_data('rushing', 2018–2024)` and cached at
  `data/ngs_rushing_2018_2024.parquet` (merge rate 11.1% — rushers only).
  All trailing-only; missingness NaN→0 per the trailing convention and
  recorded in `feature_audit.csv`.
- sklearn 1.9.1 (matches 002's frozen environment), seeds: bootstrap RNG
  1337, GBM random_state=11, logistic random_state=1337.

## 8. Reproducibility manifest

- `PREREGISTRATION.md` — frozen 2026-10-01 12:25 CDT (this run's binding
  spec; untouched).
- `scripts/build_003d_features.py` — data prep only, no fitting. Reads the
  frozen 002 table + in-house pbp + NGS; writes
  `data/003d_features_2018_2024.parquet` (30,291 rows × 119 cols) and
  `data/feature_audit.csv`.
- `scripts/run_experiment_003d.py --phase dev` — fit on train
  (2018–2020), hyperparameter selection on dev (2021–2022); writes
  `data/experiment_003d_dev.json`. Test slice untouched.
- `scripts/run_experiment_003d.py --phase test` — single locked-test
  evaluation (2023–2024); writes `data/experiment_003d_test.json` and
  `data/experiment_003d_test_predictions.parquet` (per-row predicted
  probabilities per rung + actuals).
- `data/ngs_rushing_2018_2024.parquet` — keyless NGS rushing pull,
  cached for reproducibility.
- `RESULTS.md` (this file) — verdict and full metrics.

## 9. Production gate

**No production changes.** Per the shared protocol §8, a MATERIAL WIN
would require a production recommendation package and then STOP for
authorization; this experiment did not clear the bar, so nothing is
proposed and nothing changes. The paper-tracking stream (shared protocol
§7) may log these probabilities against timestamped Bovada anytime-TD
lines prospectively, but that is future measurement, not a consequence of
this result.
