# DEV-001 fit-window decision — documented BEFORE computation (2026-10-01)

## The inconsistency in the draft
The draft DRAFT_asymmetric_offense_defense_persistence.md said simultaneously:
- "fit on 2018–2020"
- "96 team-season pairs (32 teams × 3 transitions: 2018→19, 2019→20, 2020→21)"
- evaluation from 2021 onward.

The 2020→2021 transition requires the **2021 season-end rating** as its
endpoint. The dev period is 2021–2022. A persistence slope estimated with a
dev-period endpoint is estimated with dev outcomes — it would tune the
carryover to what actually persisted during the dev period. **Excluded.**

## Available seasons in our files
- `pbp_2018_2025.parquet`, `schedules_2018_2025.parquet`: first season = 2018.
- 2017→18 transition is unavailable (no 2017 play-by-play in our files).
- V1's EPA construction (`03_ratings.py::run_epa`) builds ratings from 2018.

## Decision: 64 transitions per side
Fit β on **2018→2019 and 2019→2020 only** (2 transitions × 32 teams = 64
observations per side per rating). Both endpoints of every transition are
pre-dev (2018, 2019, 2020 season-end ratings). No dev outcome enters the fit.

## Rating definition (our construction, not Damepivot's)
- Team-season rating = the **season-end value of V1's own weekly walk-forward
  EPA rating** (`run_epa` state after the final week of the season), built with
  the symmetric 0.65 offseason carryover — i.e., exactly the rating object V1
  uses. No new opponent-adjustment machinery (that would be a different
  information set / method, not "our EPA-rating construction").
- League-centered per season per metric (subtract the 32-team mean), then
  no-intercept OLS: β = Σ(x_t · x_{t+1}) / Σ(x_t²) over the 64 pairs.
- β estimated ONCE on pre-dev data; frozen; applied at 2021w1 and 2022w1 only.
  2019w1 and 2020w1 keep the symmetric 0.65 (identical to V1 pre-dev).

## Rating family actually tested
V1's EPA construction has 8 metrics:
offense side — off_epa, off_pass_epa, off_rush_epa, off_sr;
defense side — def_epa, def_pass_epa, def_rush_epa, def_sr.
One β per side per metric (8 β values). **Explosive rate is not in V1's EPA
construction** (no such metric in 03_ratings.py); adding it would be a new
feature family, which is forbidden. It is documented as out of scope here,
not silently dropped after seeing results.

## Application point
At week 1 of season N ∈ {2021, 2022}:
`prior_{side,r,N} = β_{side,r} × (end-of-season-(N−1) rating)`.
Replaces `ratings[m][t] *= 0.65` for the EPA metrics only. ELO untouched.
In-season EWMA (ALPHA=0.25) unchanged. Linear models (fit ≤2020 on symmetric
ratings) untouched. Walk-forward GBM procedure untouched (retrains on the
candidate's own rating history — the faithful one-change counterfactual).
Ensemble weights frozen at 0.40/0.50/0.10. No market input. No 2023+ data.

## What would change this decision
Nothing found in the data files. If 2017 play-by-play existed, 2017→18 could
be added as a third pre-dev transition (96 pairs); it does not, so 64 stands.
