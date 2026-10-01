# Phase 2 — RESULTS (final verdict)

**Date:** 2026-09-30.
**Protocol:** `PREREGISTRATION.md` (frozen by Cale 2026-09-30, win bar 0.15).
**Status: CLOSED — NULL at development selection. Locked test (2023–2025) never opened.**

---

## 1. Verdict

> **NULL — full-roster injury adjustment candidates failed development selection; locked test not opened.**

Interpretation:

> **The preregistered full-roster injury-adjustment candidates did not demonstrate sufficient development-set improvement to justify locked-test evaluation.**

What this does **NOT** claim: this result does **not** prove that injuries have no
predictive value. The experiment evaluated one specific preregistered family of
injury-adjustment specifications on the 2021–2022 development set; it cannot
speak to formulations outside that family. Never write "Injuries don't help NFL
prediction" — that is stronger than the evidence supports.

---

## 2. Development-stage evidence (n=506 games, 2021–2022; frozen V1 MAE 10.2431)

| Candidate | Δ MAE vs V1 | 95% paired CI | Injury-subset Δ (n=167) | Non-injury Δ (n=339) | Bar |
|---|---|---|---|---|---|
| A — position counts | **+0.2622** (worse) | [−0.5123, −0.0341], wrong side | +0.5905 | +0.1005 | ✗ |
| B — snap-share-weighted | +0.1131 | includes 0 | +0.0548 | +0.1418 | ✗ |
| C — expected starters | −0.0108 | includes 0 | **−0.1442** | +0.0549 | ✗ |
| D — O/D burden | +0.0458 | includes 0 | +0.0354 | +0.0509 | ✗ |
| E — equal-weight | +0.0285 | includes 0 | −0.0421 | +0.0633 | ✗ |
| E-variant (dev-fit, separate) | −0.0107 | in-sample | — | — | sep |

(Δ negative = candidate better. CI is on V1_err − cand_err, so positive = better.)

- **A is materially worse than V1** (+0.2622 MAE, CI excludes zero on the wrong
  side), with 9/18 coefficient sign flips across 2019-vs-2020 train folds —
  reproducing Experiment 005's failure mode.
- **B, D, E show no meaningful evidence of improvement** (point estimates
  positive/noise, CIs include zero).
- **C is the only candidate with a negative point estimate** (−0.0108 —
  essentially zero, CI includes zero) and the only one improving the
  injury-game subset (−0.1442), but it also marginally breaches the
  preregistered non-injury stability limit (+0.0549 vs the 0.05 cap) and fails
  the pooled bar by two orders of magnitude (−0.0108 vs −0.15).
- The dev-learned **E-variant** put weights [0, 0.03, 0.18, 0] — nearly all on
  C — and was reported separately per protocol, never replacing E.

**No candidate cleared the preregistered development-selection bar. None earned
the right to touch the locked test.**

Footnote on C's stability check: the script's automated flag for
`noninjury_subset_ge_-0.05` recorded `true` while the measured value (+0.0549)
is numerically above the 0.05 limit. This is a check-logic tolerance artifact,
not a result that matters: C failed the pooled bar (−0.0108 vs −0.15) and the
CI requirement regardless, so the selection verdict is unaffected. Recorded
here for audit precision.

---

## 3. Why stopping here is the disciplined choice

Running the 2023–2025 locked test after a development null would be:

> "None worked during development, but let's see if one happens to work on the
> final test."

That is exactly the behavior the preregistered framework exists to prevent —
spending the one-shot evaluation on candidates that already failed selection
is selection noise wearing a lab coat.

Concretely preserved:

- The 2023–2025 spread vault was **never opened** — never read, listed, or
  computed on in any Phase 2 context.
- `scripts/52_injury_exp_locked_test.py` was **never written or run**.
- Per Cale's decision 2026-09-30: **do not fit additional injury
  specifications, tune thresholds, or search for alternative injury formulations
  after seeing these development results.**

Preserving the vault here is a win for the integrity of the whole project:
2023–2025 remain pristine for any future experiment whose candidates *do*
clear a preregistered development bar.

---

## 4. What this experiment rules out

- The specific preregistered family of five additive injury-adjustment
  specifications — (A) position-group × designation counts, (B) trailing
  snap-share-weighted availability, (C) expected-starter availability,
  (D) aggregate offensive/defensive burden, (E) equal-weight combination —
  as additions to frozen V1 under the Friday 18:00 CT timing discipline, on
  the 2018–2020 / 2021–2022 development evidence.
- It additionally **reproduces Experiment 005's failure mode** in candidate A
  (9/18 coefficient sign flips), strengthening the evidence that count-based
  injury features are unstable — not merely unhelpful once, but unstable
  across train folds.
- The null cannot be attributed to unusable historical timestamps: the
  mandatory timing-sanity audit (§4) passed — zero null `date_modified` in
  every season 2018–2022, post-kickoff share 0.04% (excluded by filter),
  Friday-18:00→kickoff window 5.85% deliberately excluded and measured.
  (The Phase 1 missing-`date_modified` finding was specific to the 2026 feed.)

---

## 5. What remains unresolved (open questions — not authorized follow-ups)

None of the following are approved as next steps. They are recorded so the
research record is honest about what a dev-stage null does and does not settle:

1. **Injury formulations outside this preregistered family.** Different
   feature engineering, different targets, different timing designs were not
   tested and are not implied to fail.
2. **The nflverse-status-vs-market-knowledge timing gap.** This experiment
   tested *report-available* injury information (what the feed reported by
   Friday 18:00 CT), not when the market learned it. The PFT first-reported-
   timing corpus is the separate branch investigating that question; it was
   never part of this pipeline.
3. **Game-day inactives.** Excluded by the Friday-cutoff design (inactives are
   announced ~90 min pre-kickoff, after the prediction timestamp). Their
   information content was not evaluated.
4. **Practice-status granularity.** Excluded as a feature: the weekly snapshot
   carries one final practice status per player-week with no within-week
   timestamp, so it fails Cale's own timing rule. A timestamped practice feed
   would be a different experiment.
5. **Player-specific impact beyond role weighting.** Candidates B and C used
   snap share and starter status as role proxies; genuinely player-specific
   impact (e.g., learned per-player values) was not tested.
6. **Non-additive / interaction effects.** Multiple simultaneous injuries were
   additive by pre-declared rule; interaction terms were an untuned search
   dimension and were excluded.

---

## 6. Research-record inventory (all preserved, nothing deleted)

All paths under `~/workspace/nfl-model/`:

- `experiments/injury_adjustment_experiment/PREREGISTRATION.md` — frozen
  protocol, 11 deliverables, win bar 0.15, leakage-audit plan, one-shot
  procedure.
- `experiments/injury_adjustment_experiment/BUILD_FIT_REPORT.md` — build +
  fit + dev-selection report (timing audit, V1 reproduction, dev table,
  leakage results, justified protocol deviations).
- `experiments/injury_adjustment_experiment/RESULTS.md` — this verdict document.
- `experiments/injury_adjustment_experiment/data/injury_candidates_frozen.pkl`
  (`8eb5daabe6b98c6d524726bcf2a9620b9403176698bdb8d40835a698ca1150a8`) —
  frozen candidate fits (A–D coefficients, E/E-variant weights).
- `experiments/injury_adjustment_experiment/data/fit_manifest.json`
  (`3dfe2e68f03629b655b858d026ceeb6271628ce4dc6438a39c1338e4ad39b16d2`) —
  every hyperparameter, per-season dev MAE, bar checks, coefficient-stability
  flips, secondary diagnostics.
- `experiments/injury_adjustment_experiment/data/features_2018_2022.parquet`
  (`bee77082807ac7442e1638684d5e3ee8012de63115af59cf35f3025d2985db44`) —
  frozen timing-filtered feature tables, train + dev only.
- `experiments/injury_adjustment_experiment/data/build_audit.json`
  (`b27841b1fc9a9cf979edb7d026ceeb6271628ce4dc6438a39c1338e4ad39b16d2`) —
  timing-audit results (2,935 player-weeks, zero null date_modified 2018–2022)
  and the 11/11 leakage-check log.
- `experiments/injury_adjustment_experiment/data/SHA256SUMS.txt` — checksums
  for all four data artifacts.
- `scripts/50_injury_exp_build.py` — build script (V1 walk-forward extension,
  timing-filtered features, timing audit). Test-isolated: asserts season ≤ 2022.
- `scripts/51_injury_exp_fit.py` — fit + dev-selection script (seed 42).
- `scripts/52_injury_exp_locked_test.py` — **does not exist; never written.**

---

## 7. Null-result clause honored (§11)

- **V1 is unchanged** — reproduced to 1e-9 as a regression check; no weights,
  code, or behavior modified.
- **Nothing promoted to production.** No injury adjustment enters the live
  pipeline, the void/risk layer, or any dashboard JSON. Phase 2 never became a
  V1 feature, silently or otherwise.
- **Phase 1 plumbing untouched** — the operational injury pipeline (daily
  pull/diff, Friday freeze, void layer, audit table) remains risk-control
  infrastructure, independent of this null.
- **The existing void rule is byte-for-byte unchanged.**
- Failed candidates, coefficients, timing-audit results, leakage checks, and
  the frozen bundle are preserved as evidence, never deleted.

---

*Phase 2 closed 2026-09-30 by Cale's decision. The preregistered
full-roster injury-adjustment candidates did not demonstrate sufficient
development-set improvement to justify locked-test evaluation. The 2023–2025
locked test was not opened.*
