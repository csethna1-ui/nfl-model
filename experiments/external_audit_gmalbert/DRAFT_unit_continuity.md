# DRAFT ONLY — Experiment Proposal: Unit Continuity Features (external audit candidate)

> **DRAFT-ONLY — NOT AUTHORIZED — NO LOCKED-TEST RUNS PERFORMED.**
> This is a paper proposal written 2026-10-01 as part of the gmalbert/nfl-predictions
> external-method audit. It has NOT been preregistered, NOT been run, and MUST NOT be
> run without Cale's explicit authorization. The locked 2023–2025 Vault has not been
> touched for this proposal. Under the current research freeze (RESEARCH_PROGRAM_FREEZE.md)
> and the 009 binding direction (timing-program-first; no vault touches for
> theoretically-plausible-but-underpowered sources), the standing recommendation is
> **DEFER — do not authorize** until the information-timing sequence is exhausted.

## Origin
gmalbert/nfl-predictions V2 feature catalog lists "Unit continuity: OL returning snaps,
secondary continuity, receiver continuity" as a **schema-ready, never-implemented**
roadmap family. The repo therefore contributes the *idea*, not a method — there is no
repo result to audit. Our own frontier audit independently listed "OL/skill continuity
via snap counts" as Tier 2 / UNTESTED ("feasible; thin evidence") in
`experiments/experiment_009_information_frontier/frontier_table.csv` and
`experiments/feature_discovery_audit/REPORT.md`. This proposal formalizes it so the
idea is not lost and cannot be rediscovered under a different name later.

## Exact feature definitions (frozen before any computation)
All features are computed at the Friday 18:00 CT cutoff using ONLY completed prior
games and roster state published before the cutoff. Team-game grain; home/away
perspective then differenced (home − away) like existing V1 features.

1. `ol_returning_snap_share`: fraction of the team's offensive snaps over the prior
   8 completed games taken by offensive linemen on the current 53-man roster.
2. `secondary_continuity`: same construction for defensive-back snaps.
3. `receiver_continuity`: same construction for WR/TE snaps (or targets — snap
   version primary; target version preregistered as a single alternate, not both).
4. `ol_starter_churn_8g`: 1 − (snaps by the 5 most-snapped OL of the prior 8 games ÷
   total OL snaps in the prior 8 games), i.e., how dispersed OL work has been.

Source: nflverse snap counts + weekly rosters. No market input. No outcome-dependent
selection. Coefficients fit on 2018–2020 only; no hand-set coefficients.

## Historical availability / earliest usable season
nflverse snap counts available 2012+; weekly rosters 2018+ verified. Prior-8-game
windows require the 2017 season for early-2018 games (available). **Earliest usable
season: 2018** — the 2018–2020 training window is intact.

## Friday 18:00 CT reconstructability
Yes in principle. Snap counts publish with the completed game; rosters are weekly.
Required leakage audit before any run: verify weekly roster *publication* timing vs
the Friday 18:00 CT cutoff (a roster published Saturday describing Friday's state
is unavailable). Mid-week signings after the cutoff are excluded by construction
(prior-games-only snap attribution + cutoff roster snapshot).

## Expected sample size
Validation 2021–2022 REG: n=569. Locked 2023–2025 REG: n=816 (single touch only if
validation gates pass).

## Overlap with existing experiments
None directly. Exp 005 tested *availability* (Out/Doubtful/Questionable by position)
— null. Exp 010 tested *inactive burden* — null. Exp 011 (roster transactions)
shelved as underpowered. This is *compositional stability*, not availability: who
has been producing the snaps, not who is listed as out. Distinct family.

## Why it could contain information beyond V1
V1's ELO/EPA/GBM features are outcome-based: they measure points and efficiency
produced, not *who* produced them. A team with top-5 EPA but three new OL starters
and a rebuilt secondary is a different offensive/defensive entity than the same EPA
with full continuity; ELO/EPA adjust to composition breaks only slowly (they are
backward-looking averages). Lineup-composition information is genuinely absent from
V1's feature set — this is new information, not a repackaging of EPA.

## Likely failure mode
Continuity is slow-moving and highly correlated with team quality (good teams keep
lineups; bad teams churn) — most of its variance is likely already spanned by ELO.
True composition breaks are rare events, so effective signal is sparse: expect an
underpowered test with wide CIs, the same pathology that shelved Exp 011 (±0.3 CI
vs the 0.15 bar). The market plausibly prices major OL news already (cf. 009 §6:
the V1–market gap concentrates in late-season/division games where news flow is
richest). Prior odds: low.

## Comparison against Experiment 008
008 tested distributional *targets* (separate score regressions, quantiles,
heteroskedastic variance) and found game-level error scale unpredictable from
pregame info. Continuity is an *information family* (a new input), not a target
architecture — orthogonal to 008. Nothing in 008's null bears on whether
composition carries *location* signal. This is not 008 under a different name.

## Exact baseline
Frozen V1: validation 2021–22 MAE 10.0425; locked 2023–25 REG MAE 10.1867.
Market reference: 9.7267 / 9.7445 (diagnostic only — no market input to the model).

## Proposed validation window
2021–2022 REG walk-forward (n=569), same sample as 008/V2-A–D. Candidate: V1 +
continuity features (linear or GBM per preregistered spec — one spec, no variants).

## Proposed locked-test treatment
Open the Vault **only** if validation clears preregistered gates: ΔMAE ≥ 0.15 vs
frozen V1, paired 95% CI excludes zero, improvement in both seasons separately.
Single locked computation, fixed spec, no tuning. If gates fail, Vault stays shut.

## Preregistration requirements
1. Feature definitions above frozen verbatim before any validation computation.
2. Historical reconstructability audit completed first: roster publication-timing
   audit, snap-count revision audit, one chronological pass.
3. 2018–2020 training / 2021–2022 development / 2023–2025 locked test.
4. Frozen V1 baseline; no market input; no tuning on the locked test;
   no outcome-dependent feature selection; no post-hoc feature engineering;
   no hand-set coefficients.
5. Negative-result registry entry required if null.

## Standing recommendation
**DEFER.** Formally category D (genuinely new, reconstructable), but authorization
is not recommended under the current program state: the research freeze and 009's
binding timing-first direction prohibit vault touches for
theoretically-plausible-but-underpowered sources, and this candidate's prior is
low (adjacent nulls 005/010, shelved 011). Revisit only after the information-timing
sequence (PFT verdict → inactives → transactions → 006 prospective) is exhausted
AND Cale explicitly authorizes.
