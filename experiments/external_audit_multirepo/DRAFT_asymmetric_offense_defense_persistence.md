# DRAFT ONLY — Experiment Proposal: Asymmetric Offense/Defense Offseason Persistence

> **DRAFT-ONLY — NOT AUTHORIZED — NO LOCKED-TEST RUNS PERFORMED.**
> Written 2026-10-01 as part of the multi-repo GitHub external-method audit
> (Cale's broader scan; lead repo Damepivot/nfl-game-model). It has NOT been
> preregistered, NOT been run, and MUST NOT be run without Cale's explicit
> authorization. The locked 2023–2025 Vault has not been touched for this
> proposal. Under the current research freeze (RESEARCH_PROGRAM_FREEZE.md) and
> the 009 binding direction (information-timing sequence first), the standing
> recommendation is **DEFER — do not authorize** until the timing sequence is
> exhausted.

## Origin
Damepivot/nfl-game-model fits offseason carryover slopes on pre-holdout seasons:
opponent-adjusted EPA persists at ≈0.48 season-to-season on offense but only
≈0.31 on defense (`fit_carryover` in `02_build_ratings.py`; `PRIOR_FIT_LAST_SEASON
= 2022`; usage in `build_priors`: `prior = prior_season_rating × slope` per side).
Offensive ratings are therefore regressed ~52% toward league average each
offseason; defensive ratings ~69%. Our system currently uses a SYMMETRIC
convention (1/3 offseason regression for both sides — Exp 003; ELO hygiene
confirmed symmetric). Asymmetric persistence is NOT in V1 and has NOT been
tested. Independent corroboration: ryanpmcintire/nfl_py3 docs report the same
asymmetric O/D persistence pattern.

## Exact definition (frozen before any computation)
For each side s ∈ {off, def} and each EPA-based rating r ∈ {off_epa, def_epa,
pass_epa, rush_epa, success_rate, explosive_rate} (offense ratings for s=off,
defense ratings for s=def):
1. Build full-season, league-centered, opponent-adjusted EPA ratings per
   team-season for 2018, 2019, 2020 (using our existing EPA-rating construction;
   strictly completed seasons).
2. Estimate persistence slope β_s = Cov(r_t, r_{t+1}) / Var(r_t) over the 96
   team-season pairs (32 teams × 3 transitions: 2018→19, 2019→20, 2020→21).
   Fit ONCE on 2018–2020. NO hand-set coefficients — do NOT copy Damepivot's
   0.48/0.31; fit our own on our construction.
3. Offseason prior for season N ≥ 2021: `prior_{s,r,N} = β_s × rating_{s,r,N−1}`.
   This replaces ONLY the symmetric keep-2/3 carryover feeding the EPA-linear
   component's offseason initialization. ELO component, GBM component, and
   ensemble weights (0.40/0.50/0.10) are untouched.
4. In-season updating thereafter is unchanged (existing EPA-linear pipeline).

## Data requirements
nflverse PBP EPA per play, 2018+. No market input. No outcome-dependent
selection. β_s are preseason-frozen constants (re-estimated never within the
experiment).

## Earliest reconstructable season
1999 in principle (PBP start); practical window 2018+ to match V1 component fit.
β fit requires 2018–2020 complete seasons; evaluation from 2021 onward.

## Friday 18:00 CT availability
YES. β_s are frozen before the season; the prior needs only the completed prior
season, known months ahead. No within-week information required.

## Expected sample size
β_s fit: 96 team-season pairs per side per rating (2018–2020). Dev: 2021–2022
walk-forward, n=569 games (report 2021 and 2022 separately). Locked: 2023–2025,
n=816 — single touch ONLY if dev gates pass.

## Overlap with existing experiments
Distinct from Exp 003 (symmetric 1/3 regression, weekly batch updating —
NULL, error corr 0.985 with V1) and Exp 002 (in-season opponent-adjustment
method — NULL). Touches exactly one new parameter family: the offseason
carryover slopes. Binding weight rule (009) is respected — this changes no
ensemble weights.

## Why it could contain information beyond V1
V1's features are outcome-based; the carryover slope is a fact about the
INFORMATION SET — how much last season's measurement still means. If defense
truly persists at ~0.31 while we carry it at ~0.67 (keep-2/3), we overweight
stale defensive ratings exactly when the prior dominates the information set
(weeks 1–4, before current-season data accumulates). This is genuinely new
information about information decay, not repackaged EPA.

## Likely failure mode
Leverage is concentrated in weeks 1–4 (~120 dev games); expected overall MAE
gain 0.02–0.06, well under the bar. EPA-linear is only 50% of the ensemble,
diluting further. Damepivot's own adjustment-gain measurements were ~0.01
correlation. High probability of a clean null — which would still be a useful
verdict (symmetric carryover confirmed adequate).

## Exact baseline
Frozen V1 (0.40/0.50/0.10), all else identical — the ONLY change is the
offseason carryover slopes in the EPA-linear component's initialization.

## Proposed dev/test split
- Fit β_s on 2018–2020 (pre-dev, never revisited).
- Walk-forward evaluation on 2021–2022 dev (n=569), both seasons reported.
- Single locked-test touch (2023–2025, n=816) only if dev gates pass.

## Proposed win bar (all required to open the vault)
1. Beat frozen V1 by ≥0.15 MAE on 2021–2022 dev;
2. Beat the market proxy by ≥0.15 MAE on dev (required to justify a vault touch);
3. Improvement holds in 2021 AND 2022 separately (no single-season fluke).

## Preregistration requirements
Freeze before any dev evaluation: the rating set r, the β_s estimation method
(OLS slope on team-season pairs, league-centered), the exact application point
(offseason initialization of EPA-linear only), and the win bar above. No
tuning on dev. No hand-set coefficients. No post-hoc redefinition of the
rating set. Outcome-independent: β_s are fit on 2018–2020 only.

## Standing recommendation
**DEFER.** The candidate is cheap, preregistrable, and single-touch-safe, but
Cale's binding direction is the information-timing sequence first
(PFT verdict → inactives → transactions → Exp 006 prospective). Revisit only
after that sequence exhausts AND Cale explicitly authorizes. Expected value of
running now is negative under the freeze.
