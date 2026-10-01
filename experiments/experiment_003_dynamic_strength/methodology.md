# Experiment 003 — methodology

## Hypothesis
V1's ELO/EPA ratings update too crudely as teams evolve within a season. A
strictly-pregame dynamic offensive/defensive strength representation with
weekly updating and recency weighting may capture evolving team strength
better than V1's ensemble.

## Representation
Per team, two point-denominated ratings, both 0 = league average:
- `off[T]`: expected points scored above league average vs a league-average defense.
- `def[T]`: expected points allowed above league average vs a league-average
  offense (higher = worse defense).

Initialized 0 for all teams at the 2018 season start. Total offense/defense
only — no pass/rush split (preregistered single-concept change).

## Prediction (preregistered)
Using pre-week ratings:
- `pred_home_pts = L + off[home] + def[away] + Hf/2`
- `pred_away_pts  = L + off[away] + def[home] - Hf/2`
- `candidate_margin = off[home] - off[away] + def[away] - def[home] + Hf`

## Weekly batch update (preregistered)
All games of week W are predicted with pre-week-W ratings; updates applied
after the week:
- `e_h = home_score - pred_home_pts`, `e_a = away_score - pred_away_pts`
- `off[home] += K*e_h`, `def[away] += K*e_h`
- `off[away] += K*e_a`, `def[home] += K*e_a`

At each season boundary (2019–2025, before week 1):
`off *= (1-r)`, `def *= (1-r)`, `r = 1/3` (V1 ELO convention, fixed).

No post-fit calibration: ratings are point-denominated by construction.

## Frozen parameters (training 2018–2020 only)
- `L = 23.627` pts/team-game (mean, 2018–2020)
- `Hf = 0.783` pts home edge (mean home margin, 2018–2020; depressed in part
  by the fan-less 2020 COVID season — a known property of the frozen rule,
  not adjusted)
- `K = 0.08`, selected by preregistered grid {0.03, 0.05, 0.08, 0.12, 0.18}
  minimizing MAE on 2019–2020 (2018 = rating burn-in; ties → smaller K).
  Grid MAEs: 10.41 / 10.23 / 10.19 / 10.32 / 10.61 — stable, U-shaped.

## Correction log
The first implementation run had a sign error (defense terms subtracted in
the prediction equations, contradicting the stated convention). It produced
a validation calibration slope of −0.011 — the ratings carried no signal —
and was discarded as a non-test of the hypothesis. The corrected equations
above are the first faithful implementation. No design choices (K rule, r,
L/Hf rules, gate, baselines) changed. See `config.json` corrections_log.

## Evaluation
Validation 2021–2022 only (n=569). Baselines: market-only (market_spread),
frozen V1 (v1_margin), candidate. Primary: MAE, RMSE, calibration slope.
Diagnostics (phase, division, edge bucket, bet direction) are descriptive
only — no filters built. Vault (2023–2025) never touched.
