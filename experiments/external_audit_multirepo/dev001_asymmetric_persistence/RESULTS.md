# DEV-001 RESULTS — asymmetric offense/defense offseason persistence (DEV-ONLY)

Date: 2026-10-01. Authorization: Cale, dev-only 2021–2022. Vault untouched.
No production files modified; all outputs in this directory.

## Estimated betas (pre-dev fit, 64 transitions per side: 2018→19, 2019→20)

| rating | offense β | defense β |
|---|---|---|
| EPA (total) | 0.280 | 0.275 |
| passing EPA | 0.160 | 0.280 |
| rushing EPA | 0.406 | 0.066 |
| success rate | 0.139 | 0.212 |

League-centered season-end ratings from OUR walk-forward construction,
no-intercept OLS. Note: aggregate EPA persistence is essentially SYMMETRIC
(0.280 vs 0.275) — Damepivot's 0.48/0.31 asymmetry does NOT reproduce in our
rating construction. Sub-component asymmetries exist (rush off 0.406 vs rush
def 0.066) but are estimated on 64 pairs and are noisy.

Fit-window decision (2020→21 excluded — dev endpoint; 2017→18 unavailable):
FIT_WINDOW_DECISION.md, written before computation.

## The 15 requested metrics (dev = 2021–2022, n=569)

1. V1 MAE: **10.0425** (reproduces frozen validation number exactly)
2. Candidate MAE: **10.0158**
3. ΔMAE (cand − V1): **−0.0267**
4. Relative change: **−0.266%**
5. 2021 ΔMAE: **−0.0047** (n=285)
6. 2022 ΔMAE: **−0.0488** (n=284)
7. Paired 95% CI: **[−0.0737, +0.0203]**, two-sided p = 0.265
8. n games: 569
9. Weeks 1–4 ΔMAE: **−0.0799** (n=128)
10. Weeks 5–18 ΔMAE: **−0.0112** (n=441)
11. EPA component: V1 10.1460 → cand 10.1614, Δ **+0.0155 (worse)**;
    splits: 2021 +0.0438, 2022 −0.0129, W1–4 −0.0015, W5–18 +0.0204
12. Full ensemble: 10.0425 → 10.0158, Δ −0.0267
13. Market MAE (same games): **9.7267**
14. Candidate − market: **+0.2890** (still ~0.29 behind the market)
15. Consistent across seasons: **NO** — 2021 contributes nothing (−0.0047);
    the pooled gain is all 2022 (−0.0488), concentrated in weeks 1–4.

Diagnostics: GBM component 10.4625 → 10.2729 (Δ −0.1896); ELO component
10.2031 (identical both runs, untouched). Recomputed V1 walk-forward GBM
matches saved production pred_gbm_m bit-for-bit (max abs diff 0.0).

## Classification: NULL (with unstable structure)

- Pooled Δ −0.0267, 95% CI crosses zero, p = 0.265 → **not statistically
  distinguishable from zero**. Not a positive signal by the stated rule.
- The EPA-linear component — the object the hypothesis targets — got
  **worse** (+0.0155), flat in weeks 1–4 (−0.0015) where a better prior should
  help most. The small ensemble move flows through the GBM's refit on
  altered early-season features, not through improved EPA priors — a fragile
  mechanism that does not support the persistence hypothesis.
- Unstable structure: 2021 −0.005 vs 2022 −0.049; no cross-season replication.
- Vault gate (≥0.15): nowhere near. **No Vault touch** (was never authorized).

## Answers to the final questions

- Does it improve V1 on 2021–2022? Not established: −0.0267 pooled, CI
  includes zero, p=0.265.
- How large? −0.27% relative; an order of magnitude below the vault gate.
- Consistent across 2021 and 2022? No.
- Concentrated in weeks 1–4? The apparent gain is (−0.080 W1–4 vs −0.011
  later), but the EPA component shows no W1–4 gain (−0.0015) — the
  concentration lives in the GBM refit, not the prior.
- Does it improve the EPA component itself? No: +0.0155 (worse).
- Does it improve the final ensemble? Nominally −0.0267, not significant.
- Statistically distinguishable from zero? No (p=0.265).
- Meet the stronger threshold for a future Vault touch? No.

## Verdict on the underlying idea

Asymmetric offseason persistence, as estimated from our own construction, is
**not useful for our model**: aggregate EPA persistence is symmetric in our
ratings (0.28/0.275), and swapping in the fitted asymmetric slopes does not
improve the EPA component it was meant to fix. The candidate is CLOSED as a
dev null. Per-game errors preserved in per_game_errors.csv.
