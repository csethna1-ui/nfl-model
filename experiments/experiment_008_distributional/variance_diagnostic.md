# Experiment 008 — Phase 2 variance diagnostic

**Question:** can pregame information predict game-level margin error scale?

**Method:** expanding walk-forward within 2021–2022 REG (n=543 games;
V1 `ens_margin` exists only for 2021–2022, so no 2018–2020 training was possible
for V1 residuals). Each week, OLS of `|resid|` and `log(resid²)` on pregame
features using only prior weeks; predict the current week. Diagnostic only.

**Features:** ens_margin_abs, ens_total, elo_diff_abs, off_epa_diff_abs, def_epa_diff_abs, rest_diff, div_game, home_plays_per_drive, away_plays_per_drive

## Results
- Walk-forward corr(predicted |resid|, actual |resid|): **0.055**
- In-sample R²(|resid| ~ features): 0.021
- Gaussian log-score, constant σ: -3.9731; predicted σ: -5.0553 (Δ -1.0822)

### Quintiles of predicted |resid| → actual mean |resid|
q
0    11.429682
1     8.354040
2     7.877175
3    11.812238
4    10.521045

## Verdict: WEAK
Pregame information carries essentially no predictable signal about
game-level error scale. Per the directive: reduce emphasis on complex variance
models; 008-C is retained as a Question-B (uncertainty calibration) test only,
not as a path to better margin prediction. Heteroskedasticity alone cannot
change the optimal point forecast.
