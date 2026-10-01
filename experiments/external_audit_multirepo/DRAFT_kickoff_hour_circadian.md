# DRAFT ONLY — Experiment Proposal: Kickoff-Hour Circadian Covariate (weak candidate)

> **DRAFT-ONLY — NOT AUTHORIZED — NO LOCKED-TEST RUNS PERFORMED — WEAK CANDIDATE.**
> Written 2026-10-01 as part of the multi-repo GitHub external-method audit
> (Damepivot/nfl-game-model `add_situational`). NOT preregistered, NOT run,
> MUST NOT be run without Cale's explicit authorization. Locked 2023–2025
> Vault untouched. Standing recommendation: **DO NOT PREREGISTER** — recorded
> only to prevent rediscovery under a different name. Expected gain ≈ 0.

## Origin
Damepivot's situational block includes `kickoff_hour` (scheduled kickoff hour
parsed from gametime) as a linear margin covariate. Every other situational
feature in their block is already A/B in our system (rest, division, travel,
indoor/surface, weather, week). Kickoff hour is the only uncovered one —
formally D-weak.

## Exact definition (frozen before any computation)
`kickoff_hour` = scheduled kickoff hour (local to home stadium) from the
nflverse schedule, entered as a single linear covariate (home − away is
degenerate — same kickoff; entered as a game-level term) in the margin model.
All else = frozen V1.

## Data / availability / sample
Schedules (gametime), any season. Friday 18:00 CT: yes. Dev 2021–2022 n=569;
locked 2023–2025 n=816 single touch on gate pass.

## Overlap
None in our system. Body-clock/scheduling effect is conceptually distinct from
`tz_delta` (travel-timezone, already evaluated as marginal).

## Likely failure mode (expected)
Effect ≈ 0; likely absorbed by home/away structure and week number; no repo
reports an isolated positive coefficient. Almost certainly fails the 0.15 bar.

## Baseline / split / win bar
Frozen V1; 2018–2020 fit, 2021–2022 dev, locked single touch on gate pass.
Win bar: beat V1 by ≥0.15 MAE on dev AND beat market by ≥0.15; hold in both
dev seasons.

## Standing recommendation
**DO NOT PREREGISTER.** Included for completeness as the only situational idea
not already classified A/B. Expected value ≈ 0.
