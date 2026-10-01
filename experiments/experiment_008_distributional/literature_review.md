# Experiment 008 — Phase 1: Literature Review

**Date:** 2026-09-29 | **Status:** RESEARCH_IN_PROGRESS (Phase 1 of 8)
**Question:** Does the scalar expected-margin target itself (V1: E[margin] by direct regression) discard information, because NFL margin is the difference of two distinct scoring processes?

This is a research survey only. No fitting, no data analysis, no edge claims.

---

## 1. NFL score/margin modeling literature

### 1.1 Stern — normal margin as the founding benchmark
Hal Stern's early work (seasons 1981, 1983, 1984) established that the NFL win margin is well approximated by a **normal distribution with mean equal to the pregame point spread and standard deviation slightly under 14 points** (reported via Stern's NFL win-probability chapter, e.g. Stern 1991 "On the Probability of Winning a Football Game," *The American Statistician* 45(3):179–183). This is the oldest defensible statement that the margin distribution's *location* is captured by the market and its *scale* is large and roughly constant (~13–14 pts). Any distributional candidate must be evaluated against this benchmark.

### 1.2 Glickman & Stern (1998) — dynamic state-space score model
Mark Glickman and Hal Stern, "A State-Space Model for National Football League Scores," *JASA* 93:25–35. Bayesian state-space model: each team's strength follows a first-order autoregressive process with **two time scales of variation** — week-to-week (injuries, random factors) and season-to-season (personnel changes) — plus team-varying home-field advantage, fitted by MCMC on 1988–1993 scores. Predictive: slightly beat the Las Vegas line on the last 110 games of 1993. Takeaways for 008: (a) modeling *scores* (not margins) is a published, credible NFL approach; (b) the authors explicitly flag injuries as missing information — consistent with our stale-QB filter motivation; (c) the 1993 holdout win is small and old — an architecture reference, not a launch gate. Glickman later extended the dynamic paired-comparison machinery (Glickman 1999, "Parameter Estimation in Large Dynamic Paired Comparison Experiments," underlying Glicko). Lopez, Matthews & Baumer (arXiv 1701.05976) compare state-space models across sports.

### 1.3 Dixon & Coles (1997) and the dependence literature (soccer, transferable)
Dixon & Coles, "Modelling Association Football Scores and Inefficiencies in the Football Betting Market," *Applied Statistics* — attack/defense-strength Poisson rate model for both teams' scores, with an **ad hoc correction term** because empirical joint score distributions showed the two teams' goals are *not* independent. Follow-ups: Karlis & Ntzoufras (2003) diagonal-inflated bivariate Poisson (captures only *positive* dependence); McHale & Scarf (2011) **copula** construction allowing arbitrary dependence between marginals. Directly transferable lesson: *home and away scoring processes are not necessarily independent*, and the right joint architecture needs a dependence mechanism rather than assuming independence by default.

### 1.4 Baker & McHale (2013) — NFL exact-score point-process model
Baker & McHale, "Forecasting exact scores in National Football League games," *Int J Forecasting* 29:122–130. A **point-process (event-level) model** of NFL scoring that forecasts *exact final scores* and reportedly **performed as well as the betting market**. This is the closest published proof that modeling the two scoring processes directly (rather than the margin) is viable in the NFL. Relevant both as validation of 008's premise and as a caution: it competes on *exact-score probabilities*, a different objective than expected-margin accuracy.

### 1.5 Skellam and Poisson-difference models
The Skellam distribution is the PMF of the difference of two independent Poissons; a related multi-option paired-comparison/Skellam family has been claimed valid for low-scoring sports including American football (Gyarmati/Mihálykó literature). Caveat for NFL: unlike soccer/hockey/baseball, NFL points are *not* unit-valued events (7/3/2/1), so a pure count-of-scores model maps awkwardly onto points without an events-to-points layer. Useful as a mathematical reference, not a turnkey NFL architecture.

### 1.6 Massey / least-squares ratings (target = score differential)
Kenneth Massey's least-squares ratings solve linear systems of score differentials (game differential = rating_A − rating_B). Targets the margin directly, as V1 does — it belongs in the "direct margin" family and shows that solving for expected margin via linear algebra is the classical baseline.

### 1.7 Recent stochastic analyses of the NFL spread distribution
- Bayesian comparison of NFL score distributions and home advantage (PMC8282683): documents the *shape* of actual NFL score/margin distributions, including mass at key numbers (3, 7) from FG/TD scoring structure.
- Stochastic analysis of the NFL point-spread distribution (PubMed 38476452): recent distributional treatment of spreads/margins.
- PLOS ONE 10.1371/journal.pone.0287601 ("A statistical theory of optimal decision-making in sports betting"): estimates margin-of-victory **quantiles** (0.476/0.524) stratified by spread and compares them to sportsbook values — direct evidence that quantile thinking about NFL margins is published and operational.

### 1.8 In-game normal Δscore models with modeled variance
Duke statistics thesis (Rappleye 2020, "Modeling Win Probability in NFL Games") models remaining-score Δ ~ N(μ, σ²) with **both μ and σ regressed on game-state features** (spread, score differential, timeouts, DVOA, QB grades) — a deployed heteroskedastic normal architecture for NFL scoring. Transferable: location-scale modeling of NFL score differentials with feature-driven variance is a working, published design (in-game; 008's version would be pregame).

### 1.9 Practitioner notes
- NFL margins carry mass at key numbers (3, 7); a normal approximation is a benchmark, not the truth — exact cover probabilities need discrete/empirical checks near 3 and 7.
- Home/away dependence: Dixon–Coles found dependence in soccer scores; in the NFL, game script (leading teams running clock, garbage time) creates plausible dependence, but the literature does not hand us a signed NFL estimate — Phase 2's diagnostics must measure it.
- Overdispersion: NFL team scores are count-like but generated by clustered, unequally-weighted events; raw Poisson under-fits both tails.

## 2. Key statistical facts constraining Experiment 008

1. **For MAE evaluation, the optimal point forecast is the conditional MEDIAN, not the conditional mean.** Any architecture that produces a better median estimate can beat V1 on MAE even with an identical conditional mean.
2. **Heteroskedasticity alone cannot improve a point forecast.** Modeling conditional variance changes the uncertainty representation, never the optimal point forecast (median/mean location). This cleanly separates the two 008 sub-questions: (A) does the architecture improve expected-margin prediction? vs (B) does it better represent uncertainty? A model that improves only calibration is a distributional improvement, *not* a superior margin predictor.
3. **Margin = home_score − away_score is exact.** Two-process architectures lose no information by construction; the only question is whether modeling the processes separately estimates the location (median/mean of the difference) better than modeling the difference directly.

## References (verifiable links from search)
- Glickman & Stern 1998 (JASA): https://www.glicko.net/research/nfl.pdf
- Lopez/Matthews/Baumer state-space comparison: https://arxiv.org/abs/1701.05976
- Bayesian NFL score distributions / home advantage: https://pmc.ncbi.nlm.nih.gov/articles/PMC8282683/
- NFL point-spread distribution analysis: https://pubmed.ncbi.nlm.nih.gov/38476452/
- Baker & McHale 2013: https://www.researchgate.net/publication/257026929_Forecasting_exact_scores_in_National_Football_League_games
- Skellam distribution: https://en.wikipedia.org/wiki/Skellam_distribution
- Bivariate Weibull/copula dependence discussion (soccer, transferable): https://pure.manchester.ac.uk/ws/files/49399144/ijfpaper.pdf
- PLOS ONE betting/margin-quantile paper: https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0287601&type=printable
