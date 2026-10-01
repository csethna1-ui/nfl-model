# Results — V1 Ensemble Weight Generalization (2023–2025)

**Date run:** 2026-09-29
**Preregistration:** `PREREGISTRATION.md` (binding; followed exactly)
**Sample:** 2023–2025 regular season, n = 816 games
**Method:** frozen components — ELO-linear and EPA-linear fit on 2018–2020 only;
GBM walk-forward on strictly pre-week history. Reused `data/games_with_preds.parquet`
after verifying its generation script (`scripts/04_backtest.py`) matches the
preregistered methodology: linears fit on seasons ≤ 2020, GBM trained per-week on
`hist = games strictly before the prediction week`. No refitting on 2023–2025.
No weight optimization on 2023–2025 — the grid below is diagnostic only.

## MAE on 2023–2025 (predicted home margin vs actual)

| Blend | 2023–25 MAE (n=816) |
|---|---:|
| ELO alone | 10.293 |
| EPA alone | 10.374 |
| GBM alone | 10.350 |
| **V1 frozen 0.4 / 0.5 / 0.1** | **10.187** |
| Equal weights (1/3 each) | 10.190 |
| Market spread (reference only) | 9.745 |

## Full 0.1-step grid (66 combinations) — diagnostic only

- Min: 10.175 (blend 0.5 ELO / 0.4 EPA / 0.1 GBM)
- Median: 10.228
- Max: 10.374 (EPA alone)
- Std: 0.048
- **V1 (0.4/0.5/0.1) ranks 10th of 66 — 86th percentile.**
- The best grid blend beats V1 by **0.012 MAE** — negligible, inside noise.
- Equal weights (10.190) is virtually identical to V1 (10.187).
- The grid is flat: the entire 66-combination range spans only 0.20 MAE
  (std 0.048). Weighting barely matters because the three components are
  highly correlated views of the same latent team-strength signal
  (consistent with the V1 architecture audit: component error corr ~0.95).

**No weight is recommended.** Per the binding decision rule, no weight change
results from this analysis regardless of outcome.

## Regime comparison: component rank order flipped

| Component | 2021–22 MAE (n=543 REG) | 2023–25 MAE (n=816 REG) | Rank 21–22 → 23–25 |
|---|---:|---:|---|
| ELO | 10.250 | 10.293 | 2nd → **1st** |
| EPA | 10.149 | 10.374 | **1st** → 3rd |
| GBM | 10.446 | 10.350 | 3rd → 2nd |
| V1 0.4/0.5/0.1 | 10.059 | 10.187 | — |

(2021–22 values recomputed from repo data, regular season only, matching the
n=543 sample used across the research program. `backtest_report.md` quotes
10.20 / 10.15 / 10.46 / 10.04, which reproduce exactly when playoff games are
included, n=569. Rank order is identical either way: EPA < ELO < GBM.)

## Matched preregistered scenario: **Scenario 2, with a Scenario 1 caveat**

- **Scenario 2 matches on its stated criterion:** the component rank order
  flipped between regimes. EPA went from best (10.149) to worst (10.374);
  ELO went from second to first. The relationship that justified 0.4/0.5/0.1
  in 2021–2022 — "EPA is the strongest component, weight it most" — does not
  hold in 2023–2025. The fixed ensemble weights are not robust in the sense
  the tuning assumed.
- **But the Scenario 1 property also holds:** V1 remains a near-optimal blend
  out of sample (10th of 66, 0.012 behind the best fixed blend, effectively
  tied with equal weights). The ensemble *construction* generalized fine;
  what didn't generalize is the *component story* behind the weights.

Correct language, per the preregistration: "The V1 architecture has not been
improved, but its fixed ensemble weights may not be robust across regimes."
The practical implication is mild — because the grid is flat (std 0.048),
no fixed re-weighting available in 2021–2022 hindsight would have materially
changed 2023–2025 performance. This is evidence *for* keeping the frozen
weights, not against them: the blend sits in a broad, flat optimum.

## Secondary observations

- Market spread MAE 9.745 vs V1 10.187 on this sample: gap ≈ 0.44, wider than
  the ~0.33 quoted on the earlier sample — same direction, market still ahead.
  (Market timestamp caveat from Experiment 004 applies.)
- GBM improved slightly across regimes (10.446 → 10.350) while EPA degraded
  (10.149 → 10.374). Neither move is large relative to game-level noise, but
  the EPA degradation is the largest component-level regime shift observed.

## What this does NOT authorize

No production weight change. No re-tuning on 2023–2025. Experiment 009
(ensemble weight robustness) is not authorized by this analysis; it requires
its own preregistration and Cale's explicit approval. The vault remains
unspent for model selection — this was a second reporting use of 2023–2025
(MAE diagnostics), after the frozen V1 ATS record report.

Raw numbers: `analysis_output.json` (same folder).

## Verdict (2026-09-29, Cale)

The weight question is closed. The ensemble is robust to reasonable weight
choices (flat optimum, V1 10th/66, equal weights effectively tied), so no
research capital goes to weight optimization — Experiment 009 is not pursued.
The market gap (~0.44 MAE on 2023–2025) is not explained by ensemble weights.
The frontier is information, not construction. The PFT news-timing pilot is
the most consequential open item.
