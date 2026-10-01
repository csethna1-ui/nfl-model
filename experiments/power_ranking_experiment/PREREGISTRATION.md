# Power-Ranking Experiment — Preregistration

Date: 2026-09-30. Written BEFORE any candidate-comparison computation was run.

## Research question
Should the dashboard's "Overall" team ranking be a composite of validated
team-strength signals rather than ELO-only? The current UI labels the ELO
ordering as "Overall", which misleads users into reading "#9" as
"#9 overall team strength" when it is "#9 ELO".

## What "power ranking" means here (Step 1 — target definition)
Three candidate interpretations were considered:

- (A) Predictive team strength: the ranking estimates latent current strength;
  validated by how well it predicts FUTURE point differential / game margins.
- (B) Game-outcome strength: validated by predicting future game results.
  (A) and (B) are nearly the same objective for a margin-based sport; (B) is
  the binarized version of (A).
- (C) Descriptive current-season strength: the ranking summarizes
  already-observed performance; validated by internal coherence/stability.

Position adopted: the PRIMARY validation target is (A) predictive team
strength. Rationale: "true current strength" is unobservable, so predictive
validity against future results is the only non-circular criterion. A purely
descriptive ranking (C) can always be made to "fit" the past and therefore
cannot adjudicate between ELO-only and a composite. (C)-style properties
(stability, coherence) are reported as SECONDARY diagnostics only.

This does NOT assume the ranking must optimize V1's objective. V1 predicts
pregame margin for betting-adjacent research; the power ranking summarizes
"how good is this team right now" for display. The experiment tests whether a
composite is a better estimate of current strength than ELO alone — it changes
no game-prediction model regardless of outcome.

## Candidate inputs (Step 2)
All from the frozen production pipeline / already-exported values. No new
data sources.

| Input | Exact definition | Info cutoff | Prior-season info? | Current-season only? | Used in V1? | Leakage risk |
|---|---|---|---|---|---|---|
| ELO | Pre-week ELO rating (production `run_elo`, K=20, HFA=55, MOV, 1/3 offseason regression) | Through prior week | Yes (1/3 regression carries prior seasons) | No — blended | Yes (40%) | None: pre-week snapshot |
| Off EPA | Pre-week offensive EPA/play EWMA rating (`run_epa`, ALPHA=0.25, 35% offseason regression to 0) | Through prior week | Yes (35% regression carries prior seasons) | No — blended | Yes (via EPA-linear, 50%) | None: pre-week snapshot |
| Def EPA | Pre-week defensive EPA/play allowed EWMA rating (negated so higher=better) | Through prior week | Yes (same) | No — blended | Yes (via EPA-linear, 50%) | None: pre-week snapshot |
| Net Success Rate | off_sr − def_sr from the same pre-week EWMA ratings | Through prior week | Yes (same) | No — blended | No (success rate not a V1 feature) | None: pre-week snapshot |
| W-L (win%) | Wins + 0.5·ties over games played, regular season, through prior week | Through prior week | No | Yes | No | None |
| Point differential | (Points for − points against) / games played, regular season, through prior week | Through prior week | No | Yes | No | None |

All snapshots are pre-week (weekly batching: week W games use only data
through week W−1). Bye-week teams carry forward their prior-week values.

## Candidate specifications (Step 3)
Components are cross-sectional z-scores across the 32 teams at each snapshot
week (no lookahead; uses only that week's values). Defense components negated
so higher = better for all.

1. ELO only: `z_elo`
2. ELO + Off EPA: mean(z_elo, z_off)
3. ELO + Off EPA + Def EPA: mean(z_elo, z_off, z_def)
4. + Net Success Rate: mean(z_elo, z_off, z_def, z_netsr)
5. + W-L: mean(z_elo, z_off, z_def, z_netsr, z_wl)
6. + Point differential: mean(z_elo, z_off, z_def, z_netsr, z_wl, z_pd)
7. Learned composite: OLS weights from development data (see below), applied
   to the six standardized components.

Equal weighting for specs 2–6 is the preregistered neutral choice (not tuned).
If a component has zero cross-sectional variance at a snapshot week (W-L and
point differential at week 1, when all teams are 0–0), that spec is skipped
for that week and noted.

## Walk-forward protocol (Step 4)
- Snapshots: every regular-season week W = 1..17 (2018–2020) / 1..18 (2021–2022),
  seasons 2018–2022 ONLY. 2023–2025 (locked vault) is never touched.
- Development: seasons 2018–2020. Used to (a) fit per-candidate OLS margin
  mappings `home_margin ~ score_diff` (pooled), and (b) fit learned-composite
  OLS weights: team rest-of-season point-differential/game ~ six components
  (pooled across development snapshots).
- Validation: seasons 2021–2022. Candidates compared here; nothing is refit
  except the application of development-fit parameters.
- PRIMARY evaluation weeks: snapshots at weeks 4–17/18 (enough current-season
  data for all components). Weeks 1–3 reported separately as early-season
  sensitivity (specs 5–6 excluded at week 1; see above).
- For each snapshot week W, each candidate's score differential
  (score_home − score_away) predicts every future regular-season game
  (weeks W+1 through end of season) via the development-fit mapping.

No future games, no end-of-season ratings, no post-cutoff information, no 2026
data anywhere in this experiment. The 2026 NE/GB/PHI diagnostic
(experiments/elo_regression_diagnostic/) is used as a descriptive case study
only — never for tuning or selection.

## Metrics (Step 5)
- PRIMARY: future game-margin MAE on validation (2021–2022), snapshots weeks
  4+, pooled. Paired comparison vs ELO-only.
- Secondary: per-season MAE; early (weeks 1–3) / mid (4–12) / late (13+)
  splits; Spearman rank correlation between composite rank at week W and
  team's rest-of-season win% and rest-of-season PD/game; week-to-week rank
  stability (Spearman of consecutive weekly ranks); learned-weight stability
  (per-season OLS fits on development years compared).
- Descriptive: for validation-season teams with large |ELO rank − efficiency
  rank| at week 4, which candidate's rank was closer to the team's future
  performance rank. No selection based on this.

## Decision rules (preregistered)
- ADOPT A VALIDATED COMPOSITE POWER RANKING: the best composite beats
  ELO-only on the primary metric by ≥0.15 MAE pooled on validation AND wins
  in BOTH validation seasons individually AND learned-weight signs are stable
  across development seasons.
- OPEN COMPOSITE POWER-RANKING SPECIFICATION FOR FURTHER VALIDATION: beats
  ELO-only pooled but fails the both-seasons or the 0.15 bar, or the winner
  is not robust across early/mid/late splits.
- KEEP ELO AS EXPLICIT ELO RANKING: otherwise. (Dashboard implication then is
  to rename the lens from "Overall" to "ELO", not to change any model.)

## Research-integrity rules
No 2026 tuning. No changes to V1, ELO parameters (K/HFA/MOV/regression),
weights, QB logic, or props. No future information. No hand-selected weights
from standings. No visual-judgment ranking. Implementation/hygiene work kept
separate. This experiment changes at most the dashboard's descriptive ranking
label/architecture — never the game prediction model.
