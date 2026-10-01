# NFL Model Research Program — Frozen Baseline

**Date:** 2026-09-29
**Status:** Research tree frozen. V1 is the validated baseline for the free-data pregame margin problem.

## The baseline

**V1** (ELO + EPA-linear + GBM, 0.4/0.5/0.1, direct home-margin prediction) is the
benchmark model for the free-data pregame margin problem.

- It is not called optimal or proven. It is the current validated baseline.
- V1 is production and unchanged.
- The 2023–2025 vault is pristine and locked. It was never spent.

## The research tree

```
                    V1
                     │
       ┌─────────────┼──────────────┐
       │             │              │
   Features      Architecture     Target
       │             │              │
   001–007        V2-A–D          008
       │             │              │
      NULL          NULL           NULL
```

### Branch 1 — Add information (001–007): NULL

| Experiment | Result |
|---|---|
| 001 Market residual | Null — lost to market-only |
| 002 Opponent-adjusted EPA | Null — 10.019 vs market 9.727 |
| 003 Dynamic O/D strength | Null — 10.105; V1-candidate error corr 0.985 |
| 005 Non-QB availability | Null — 10.077; error corr 0.985 |
| 007 Offensive strategy (PROE/pace/early-down) | Null — 10.157; error corr 0.995, worst |
| 004 Information/timing audit | Verdict A — V1 info state ~Tuesday AM vs undated market snapshot |

Candidate–V1 error correlations 0.985–0.995: these tested recovering information
from a residual that behaves like irreducible game variance.

### Branch 2 — Change the architecture (V2-A–D): NULL

| Candidate | MAE (2021–22, n=543) | Δ vs V1 (10.059) |
|---|---|---:|
| V2-A component blocks | 10.555 | −0.496 (p=0.0042) |
| V2-B + matchup interactions | 10.573 | −0.514 (p=0.0018) |
| V2-C + QB/player (historical QB value) | 10.395 | −0.336 (p=0.0236) |
| V2-D + possession/explosiveness/pressure | 10.673 | −0.613 (p=0.0006) |

All significantly worse than V1. All froze at α=100 (maximum shrinkage).
V2–V1 error correlations 0.946–0.959: genuinely different information that does
not improve margin prediction. All five blockers resolved honestly (historical
QB value, row-level injury cutoffs, PFR one-week lag, Weeks 1–4 preserved,
walk-forward standardization).

### Branch 3 — Change the target (008): NULL

- Variance diagnostic: walk-forward corr(predicted |resid|, actual |resid|) =
  **0.055**, R² = 0.021. Game-level error scale is essentially unpredictable
  from pregame information.
- 008-A separate home/away scores: 10.366, significantly worse than V1.
- 008-B quantile-regression median: 10.084, tied with V1; error corr 0.995 —
  the conditional median recovers the same predictable component as V1's mean.
- 008-C heteroskedastic variance: variance modeling hurt.

## Consolidated conclusion

Across the tested free pregame information and several fundamentally different
model architectures, we have not found evidence that the remaining margin
error is recoverable through conventional feature engineering or target/model
redesign.

The precise statement is:

> **V1 is the ceiling given this information set.**

Not "V1 is the ceiling." The information-set qualifier is essential.

Known gap: market MAE ≈ 9.73 vs V1 ≈ 10.06 (~0.33) on the historical sample.
The market's advantage may come from later information, proprietary
information, news/injury interpretation, lineup information, or market
aggregation — not necessarily reproducible from our available data. V1 signed
errors correlate 0.967 with market errors (market timestamp caveat applies).

## What was not spent

- **2023–2025 vault:** pristine. Never read, listed, or computed on. It is now
  extraordinarily valuable precisely because a large research program ran
  without spending it.
- **Experiment 006:** independent, untouched, collecting. It is now the most
  important remaining experiment: it tests whether information *timing* (Tuesday
  → Friday) rather than architecture is the remaining bottleneck.
- **Failed experiments:** preserved as evidence. Do not delete them.

## Standing rules going forward

1. V1 is the research baseline and production model. It is not modified.
2. No new model/algorithm attempts on the same free pregame information:
   no XGBoost variants, neural nets, random forests, deeper EPA models, more
   injury/matchup features, Bayesian re-runs, larger feature sets,
   hyperparameter searches, or alternative regression algorithms —
   **unless new information is discovered**, not merely a new way to process
   existing information. The "better math on the same free pregame data"
   hypothesis is exhausted.
3. Experiment 006 continues unchanged. Its results arrive prospectively.
4. The next research frontier is **new information**: what the market knows
   that our free/keyless historical system cannot know, where the source is
   both historically reconstructable and genuinely available before the
   prediction timestamp.
5. The 2023–2025 vault is not opened for a candidate that did not pass
   preregistered validation gates. There is no such candidate.
6. Any future serious modeling attempt must be justified by a genuinely new
   information source, with the same gate discipline (preregistered protocol,
   frozen before validation, one locked vault test).
