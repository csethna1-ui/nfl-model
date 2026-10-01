# REPORT — Experiment 010: Historical Inactives (Information-Timing Measurement)

**Protocol:** `PREREGISTRATION.md` (FROZEN, approved by Cale 2026-10-01 11:20 CDT).
**Run date:** 2026-10-01. Single locked application; no refit, no selection, no retries.
**Artifacts:** `run_experiment_010.py` (primary), `run_experiment_010_secondaries.py`
(S1–S4), `results.json`, `run_20261001.log`, `run_secondaries_20261001.log`.
No writes were made to `data/` or any V1 artifact — V1 is untouched.

## Research question (binding)

> How much incremental predictive information does the final historical inactive
> information contain relative to the information available at our existing V1 freeze?

## Primary result — NULL

| Quantity | Value |
|---|---|
| Frozen β̂ (OLS of V1 residual on BURDEN + intercept, dev 2021–2022 REG, n=542) | **18.1420** (se 5.07, dev R² = 0.0232; intercept α̂ = 1.21, not applied per protocol) |
| Locked test (2023–2025 REG, n=815) | |
| MAE(V1) | 10.1878 |
| MAE(V1 + β̂·BURDEN) | 10.1190 |
| **ΔMAE** | **0.0689** |
| 95% paired CI | **(−0.0618, 0.1995)** |
| Preregistered bar (material) | ΔMAE ≥ 0.15 **and** CI excludes zero |
| **Verdict** | **NULL** — bar not cleared on either prong |

**Reading (per the frozen decision rule):** the T-90 inactive list, as measured by the
single prespecified snap-weighted burden, contains no *material* incremental
information beyond V1's freeze. Narrow claim only: it does not rule out finer
formulations, and it does not claim "injuries don't matter."

**One honest nuance, reported as observation not verdict:** the burden *is*
directionally associated with V1's residual on the locked test (univariate slope
14.66, 95% CI 6.61–22.70, corr +0.12; the dev-fit β̂ = 18.14 generalizes in sign and
magnitude). The signal is real but small — about 0.07 MAE, less than half the
lab's 0.15 materiality bar. Detectable ≠ material.

## What BURDEN is (frozen operationalization)

- Per team-game: Σ over `status == 'INA'` players (nflverse weekly rosters) of the
  player's offensive/defensive snap share over the trailing 4 weeks through the prior
  week (nflverse snap counts; offense share for offensive positions, defense share
  for defensive, 0 for K/P/LS per the protocol's "offensive/defensive" spec).
- Signed away−home in home-margin convention (positive = away more depleted).
- Week-1 trailing windows roll into the prior season's final 4 REG weeks.
- Coverage gate (frozen): ≥99% of dev INA rows resolvable to a computable share.
  Observed 99.36% (91.6% linked to snap data; 8.4% legitimate in-season zeros;
  ≤42/6573 possible name-variant misses, bounded). **Gate passed.**

## Exclusions

2 games dropped entirely (no imputation), per protocol: 2021 W16 LAC@HOU and
2025 W1 NYG@WAS (the 3 team-games missing INA rows). Zero non-excluded team-games
had zero INA rows. Postseason excluded.

## Secondaries (preregistered, descriptive)

**S1 — known-Friday vs new-after-Friday.** Final-report status = latest nflverse
injury row with `date_modified` ≤ Friday 23:59 ET before the game (Thursday games:
Wednesday 23:59 ET; America/New_York used — see deviations).
- Test INA rows already **Out** on the final report: **14.86%** (1,523/10,252).
  Full mix: 75.2% never on the report (healthy scratches), 14.9% Out, 7.3%
  Questionable, 2.7% Doubtful.
- Association with V1 residual (test): known-Out slope 14.07 (se 6.82);
  new-after-Friday slope 12.52 (se 4.72, CI excludes 0); total 14.66 (se 4.10).
  The genuinely-new component carries most of the mass (mean |burden| 0.068 vs
  0.040) with a similar per-unit slope — the T-90 list's information is mostly
  *not* the Friday report restated.

**S2 — base rates.** 99.5% of test games have nonzero new-after-Friday burden
(healthy scratches guarantee this). BURDEN (test): mean 0.000, sd 0.111,
range (−0.594, 0.489).

**S3 — position groups** (Phase 2's locked groups; descriptive, no selection).
Test INA rows / total snap-share: QB 803 / 9.01 (mean share 0.011 — mostly
third-string/practice-squad QBs; the snap weighting correctly downweights them),
OL 2,105 / 41.48, SKILL 2,533 / 43.07, FRONT7 2,848 / 45.76, DB 1,891 / 46.16,
ST 72 / 0.00 (protocol spec: no ST share).

**S4 — market-gap exploratory (SUGGESTIVE ONLY).** MAE(market, undated
`spread_line`) = 9.7454. V1-vs-market gap: 0.4424 → 0.3736 after the inactive
adjustment, i.e. inactive timing *plausibly* explains **~15.6%** of the gap.
The 004/009 timestamp caveat rides along: `spread_line` is an undated nflverse
snapshot, not a timestamp-verified tradable line — this is descriptive, never a
tradable-edge claim. The official-inactive → market-reaction leg remains
documented as **inaccessible-only** for the historical window (no timestamped
intraday lines reconstructable).

## What is and is not claimed

- **Claimed:** one prespecified burden variable, one frozen coefficient, one
  locked application: ΔMAE = 0.069 (−0.06, 0.20) — below the 0.15 materiality bar.
  The inactive list carries detectable but immaterial incremental information vs
  the V1 freeze. ~15% of the V1-vs-(undated)-market gap is plausibly timing-related.
- **Not claimed:** no tradable edge; no "injuries don't matter"; no Phase 2
  re-litigation (untouched); no PFT combination (reserved); no market-reaction
  attribution (inaccessible-only historically).

## Deviations / build notes (none changed the spec)

1. **DL position bug** — caught in the dev-only smoke run (roster positions are
   coarse: DL/DB/LB, not DE/DT/CB): DL was missing from the defensive set and
   mis-binned to ST in S3. Fixed *before* the one-shot; no test data involved.
2. **`np.linalg.lstsq(ddof=...)` TypeError** — crashed after the coverage gate but
   *before* the dev fit. Fixed the call signature; reran. The locked test was first
   touched in the successful run only.
3. **Missing `US/Eastern` zoneinfo** in the venv (no tzdata) — crashed S1 after the
   primary had completed. Used `America/New_York` (identical) in the secondaries
   script. Primary values were never recomputed for the verdict.
4. **Reproducibility assertion** — the secondaries script rebuilds the deterministic
   frame with the frozen β̂ = 18.1420 (no refit) and asserts the recomputed ΔMAE
   rounds to the logged 0.0689. Passed (0.068859). This guards against upstream
   nflverse drift; it is verification, not a second evaluation.
5. nflverse snap→GSIS name bridge: 82.6% of snap rows (multi-season; 2021 alone was
   98.3%), with a normalized-name fallback for the rest. Residual variant-miss risk
   is bounded (≤0.6% of dev INA rows) and conservative (forces shares toward 0).

## Bottom line for the timing chain

known injury info (Friday) → official inactive info (T-90) → ~~market reaction~~
(inaccessible historically) → outcome. This experiment measured the first two
links' joint incremental content vs V1's freeze: **real, small, immaterial by the
lab's bar (ΔMAE 0.07 < 0.15)**. The natural follow-up, when Cale authorizes it, is
the PFT × inactives combination design — PFT is the earlier-arriving layer, and
this result suggests the T-90 list alone is not where the missing market
information lives.
