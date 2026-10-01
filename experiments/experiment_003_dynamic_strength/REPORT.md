# Experiment 003 — dynamic offensive/defensive team-strength ratings: REPORT

**GATE FAILED — vault remains untouched.**

## What was tested
One candidate architecture, preregistered before any validation evaluation
(`config.json`): strictly-pregame dynamic offensive/defensive strength
ratings with weekly batch updating, recency weighting (K selected on
2019–2020 training), 1/3 offseason regression, and a point-denominated
margin formula. No market inputs, no division/late-season/edge corrections,
no ATS or threshold tuning. A sign error in the first implementation run
(calibration slope −0.011) was caught, documented in `config.json`
corrections_log, fixed, and re-run — the numbers below are from the
corrected, faithful implementation.

## Validation results (2021–2022, n=569)

| Model | MAE | RMSE | Calib slope | MAE 2021 | MAE 2022 |
|---|---|---|---|---|---|
| Market-only | 9.727 | 12.562 | 0.939 | 10.667 | 8.784 |
| V1 (frozen) | 10.043 | 12.937 | 0.941 | 11.082 | 8.999 |
| Candidate | 10.105 | 12.986 | 0.857 | 11.072 | 9.135 |

## Gate decision (all five required)

- A. Materially improve over V1 MAE → **FAIL** (10.105 vs 10.043 — worse, not better)
- B. Beat market by ≥0.15 MAE → **FAIL** (loses to market by 0.38)
- C. Improvement in both seasons → **FAIL** (no improvement in either)
- D. Calibration slope in [0.8, 1.2] → pass (0.857)
- E. Diversified from V1 (error corr < 0.95) → **FAIL** (V1-vs-candidate error correlation 0.985)

**ALL_PASS: false. The 2023–2025 vault was never touched — zero evaluations.**

## Error-correlation analysis
- market vs V1 errors: 0.967
- market vs candidate errors: 0.967
- V1 vs candidate errors: **0.985** — the candidate reproduces V1's mistakes
  almost exactly. It carries no genuinely different information.

## Diagnostics (descriptive only, no filters built)
- The candidate is marginally less bad than V1 only in the |edge| ≥ 4 bucket
  (gap to market 0.46 vs 1.00) and trivially in division games (0.59 vs 0.62);
  it is worse than V1 everywhere else, including weeks 5–9 where V1 beats the
  market. These bucket differences are noise-scale and were not acted on.
- Component-level model disagreement was unavailable in the dataset
  (no per-component margin predictions stored); edge buckets used as proxy.

## The three concepts, kept separate
1. **Prediction accuracy.** Candidate predicts actual margin at 10.105 MAE —
   worse than V1 (10.043) and well behind the market (9.727). No evidence the
   dynamic representation captures team strength better.
2. **Market-residual accuracy.** Not the target of this experiment; note the
   candidate's errors correlate 0.967 with the market's errors — it misses
   where the market misses.
3. **Tradable-signal evidence.** None. Nothing here beats the market, so
   there is no actionable signal. **Limitation:** historical lines are
   nflverse proxy/opening lines (`line_provenance='nflverse_proxy_open'`),
   not verified executable closes; even a positive result would need live
   2026 CLV as a separate prospective check before any claim of tradability.

## Verdict
Dynamic offensive/defensive ratings do not fix V1's team-strength
representation — the candidate is a slightly worse, nearly identical twin
of V1 (error correlation 0.985) and loses clearly to the market. Combined
with Experiment 002 (opponent-adjusted EPA: null) and Experiment 001
(market-residual modeling: null), three different angles have now failed to
improve on V1 without the vault ever being touched. V1 remains production;
nothing earns a V2 label. The standing gap — market 9.79 vs V1 10.22 on the
untouched test — remains the problem to explain, and the answer is not in
how team strength is represented by these approaches.
