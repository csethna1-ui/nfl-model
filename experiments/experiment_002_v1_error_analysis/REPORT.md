# Experiment 002 — V1 error decomposition + one gated team-strength candidate

**Status: CLOSED — null result. Vault (2023–2025) never touched.**

## What was tested

**Phase 1 — diagnosis.** Decomposed frozen V1's margin-prediction error on 2021–2022
validation (n=569) across season, week, |edge| bucket, side, division, rest,
season phase, component disagreement, and per-component performance.
No fitting, no selection, no ATS analysis. (`phase1_decomposition.json`)

**Phase 2 — one gated candidate.** Opponent-adjusted EPA: the 8 EPA/SR inputs to
the EPA-linear component were replaced with opponent-adjusted versions
(one-step adjustment using pre-week opponent ratings over the last 16 games
faced, league-centered; strictly walk-forward). ELO component, GBM component,
and ensemble weights (0.4/0.5/0.1) unchanged; linear refit on 2018–2020 only.
(`phase2_candidate.json`)

## Phase 1 findings — where V1 loses to the market

Overall validation: V1 MAE 10.042 vs market 9.727 (**−0.316**).

| Bucket | n | V1−Mkt MAE |
|---|---|---|
| Division games | 199 | **+0.621** |
| Non-division | 370 | +0.152 |
| Division × weeks 15–18 | 65 | **+1.335** |
| Non-division × weeks 15–18 | 62 | +0.072 |
| Rest disadvantage | 92 | +0.461 |
| \|edge\| ≥ 4 | 120 | +0.998 |
| High component disagreement | 190 | +0.456 |
| V1 on away side | 364 | +0.386 |
| Weeks 5–9 (V1 beats market) | 144 | −0.268 |

Components as standalone predictors vs market: ELO +0.476, EPA +0.419,
GBM +0.736 (worst, slope 0.643 — noise). Ensemble diversification helps
(+0.316) but every component loses to the market.

Mechanism evidence: in division games, V1's signed error grows with the raw
offensive EPA gap (slope +6.79 vs −2.20 in non-division) — raw offensive EPA
overstates true edge against familiar defenses. The division gap held in both
seasons (2021: +0.841, 2022: +0.403). The late-season gap is almost entirely a
*division* late-season gap. This is diagnosis, not a filter: no bucket was
selected or tuned.

## Phase 2 result — gate failed

| | MAE | RMSE | Calib slope |
|---|---|---|---|
| Candidate (opp-adj EPA) | 10.019 | 12.926 | 0.930 |
| V1 | 10.042 | 12.937 | 0.941 |
| Market | 9.727 | 12.562 | 0.939 |

Gate: (a) beat market by ≥0.15 → **fail** (10.019 vs 9.577 needed);
(b) beat V1 → pass (by 0.023, noise); (c) hold in 2021 and 2022 → **fail**;
(d) calibrated → pass. **Gate fails → no vault evaluation. Vault untouched.**

## The three concepts, kept separate

1. **Prediction accuracy.** The candidate predicts actual margin at MAE 10.019 on
   validation — 0.29 worse than the market, 0.02 better than V1 (noise).
2. **Market-residual accuracy.** Not directly optimized here; the candidate was
   judged on margin MAE against market-only and V1 baselines.
3. **Tradable-signal evidence.** None. Nothing in this experiment identifies an
   actionable edge at any available line.

## Limitations

- Historical market lines are nflverse consensus/opening **proxies**, not verified
  executable closes. Any residual-style reading of these results bakes in line
  movement toward close. Live 2026 CLV tracking is the separate prospective
  arbiter and was not combined with these results.
- Validation (2021–2022) was already used for Experiment 001 selection; repeated
  reuse erodes its cleanliness, which is why the vault gate carries the weight.
- n=569 validation games: small-sample noise dominates sub-bucket comparisons.

## Verdict

Opponent adjustment does not fix V1's team-strength representation — the
candidate is indistinguishable from V1 and loses clearly to the market. The
division-game weakness is real and stable, but it is not explained by missing
opponent adjustment. V1 remains production. The vault stays locked for the next
experiment.
