# DRAFT ONLY — Experiment Proposal: Special-Teams EPA Rating (weak candidate)

> **DRAFT-ONLY — NOT AUTHORIZED — NO LOCKED-TEST RUNS PERFORMED — WEAK CANDIDATE.**
> Written 2026-10-01 as part of the multi-repo GitHub external-method audit
> (mitch-avis/nfl-sos-ratings, `SaSTR`). NOT preregistered, NOT run, MUST NOT
> be run without Cale's explicit authorization. Locked 2023–2025 Vault
> untouched. Standing recommendation: **DO NOT PREREGISTER** — recorded only
> to prevent rediscovery under a different name. Expected gain ≈ 0.00–0.02.

## Origin
mitch-avis/nfl-sos-ratings publishes `SaSTR`, a special-teams rating from an
SRS solve over per-play ST EPA margin per team-game, carried at weight 0.0575
in their composite. V1 has no special-teams dimension at all, so this is
formally a distinct information family (D-weak).

## Exact definition (frozen before any computation)
1. Per team-game: `st_epa_margin_per_play = (Σ EPA on special-teams plays as
   posteam − Σ EPA as defteam) / (# special-teams plays)` from nflverse PBP.
2. SRS solve per season-week (strictly prior weeks): least-squares ratings r
   with `r_i − r_j` fitting the ST margin, centered to mean zero.
3. Entered as a small ADDITIVE term in the margin model (home − away), with the
   coefficient fit on 2018–2020 dev data only. V1 components and weights
   otherwise untouched.

## Data / availability / sample
nflverse PBP special-teams plays, 2018+. Friday 18:00 CT: yes (prior games
only). Dev 2021–2022 n=569; locked 2023–2025 n=816 single touch on gate pass.

## Overlap
None — V1 has no ST dimension. Distinct from all prior experiments.

## Why it could matter (thin)
Kicking and field-position edges are small but partly persistent; V1 is blind
to them by construction.

## Likely failure mode (expected)
ST EPA is high-variance and low-persistence; mitch-avis's own walk-forward
shows no separation from adding it (10.845 → 10.835 within their
within-season-only setup), and their full rating apparatus loses to plain
Elo/SRS. External null evidence is already against it. Expected gain 0.00–0.02.

## Baseline / split / win bar
Frozen V1; 2018–2020 fit, 2021–2022 dev, locked 2023–2025 single touch on gate
pass. Win bar: beat V1 by ≥0.15 MAE on dev AND beat market by ≥0.15; hold in
both dev seasons.

## Standing recommendation
**DO NOT PREREGISTER.** The external evidence is already negative and the
mechanism is weak. This file exists so the idea is marked "considered and
parked," not lost.
