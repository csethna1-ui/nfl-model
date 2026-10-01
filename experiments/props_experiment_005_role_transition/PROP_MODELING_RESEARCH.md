# Player-Prop Modeling Research: Handling Team/Role Change

**Date:** 2026-10-01. **Context:** Experiment 005 NULLed cleanly — naive "weight current-team more" via learned blend/decay weights added no value over frozen Model D and the dev procedure selected overfit max-capacity GBMs. This report surveys how serious NFL prop modelers handle the team/role-change problem, and proposes concrete, keyless-nflverse-implementable mechanisms that avoid the 005 overfitting trap.

## 1. Repos surveyed

| Repo | What it is | Relevance |
|---|---|---|
| [crollila/nfl-adaptive-forecasting](https://github.com/crollila/nfl-adaptive-forecasting) | Walk-forward player-performance forecasting study, 17,110 held-out player-games, pre-specified promotion rule | **Highest.** +3.8% MAE from dynamic role features. Mechanism code read in full. |
| [ctrax68-hash/nfl-prop-model](https://github.com/ctrax68-hash/nfl-prop-model) | Full prop betting engine (nflverse → baselines → projections → distributions → Kelly), replay 2023–24 | Honest validation discipline; measured findings on share normalisation and sigma modeling |
| [tucknub/nfl-prop-war-room](https://github.com/tucknub/nfl-prop-war-room) | Multi-market prop projection framework (receptions, yards, carries, attempts) | Explicit opportunity×efficiency decomposition; role/depth-chart as gate layer |
| [sspam1189-stack/model](https://github.com/sspam1189-stack/model) | Props engine design spec with per-player Kalman filter | Concrete Kalman mechanism spec (design, not validated results) |
| [crumblip/nflhelper](https://github.com/crumblip/nflhelper) | Projection methodology notes with measured tests | **Negative result:** vacated volume does not predict next share |
| [f6pjoe/nfldata](https://github.com/f6pjoe/nfldata) (ff_projections notes) | Top-down projection methodology synthesis | "Volume is projectable, production is not" |
| [mattleonard16/nflalgorithm](https://github.com/mattleonard16/nflalgorithm) | Position-specific stacking ensemble, walk-forward | Less mechanism detail; standard pipeline |
| Prior art (already audited): Damepivot/nfl-game-model, gmalbert/nfl-predictions | Game model / props with shuffled train/test | n/(n+6) blending = same info as our 003 dynamic updating (NULL); shuffled splits invalid |

## 2. The universal decomposition (everyone does this)

Nobody projects a stat line directly. The skeleton, from f6pjoe's synthesis of four professional methodologies:

```
team play volume → pass/run split → player market share → efficiency rates → yards
```

Concrete instances:
- **war-room:** `projected_team_pass_attempts × projected_player_target_share × projected_catch_rate = projected_receptions`
- **nfl-prop-model** (`volume.ts`): `projectedTargets = projectedTeamTargets × baselineTargetShare`; `projectedCarries = projectedRushAttempts × baselineRushShare`
- **sspam1189:** `rush_yds = (team_rush × rush_share) × YPC`; `rec_yds = (dropbacks × target_share × catch_rate) × YPR`
- **f6pjoe:** "Market share and play volume are stable year-over-year; yards-per-carry, catch rate, and especially touchdowns are mostly noise. So you project the stable thing and apply league-average-ish rates to it." Player target/carry share is rated the **highest-stability** input; efficiency low-medium.

This matches our 005 M3 intuition (opportunity × efficiency) — the decomposition is not the problem. The problem is how the *share* is estimated when the regime changed.

## 3. How they weight in-season vs prior-season games

- **crollila (the validated one):** features built at **multiple horizons** — last game, last 3, last 5, season-to-date, exponentially weighted — so the model "can distinguish a durable role from a one-week spike." No single window is chosen; the learner sees all horizons.
- **sspam1189:** per-player Kalman filter; **season reset — state starts fresh each season, no carryover.** Process noise `gameDrift = 0.5` chosen *higher than NBA's 0.3* explicitly because of "weekly cadence, more regime changes." `minGamesForKalman = 3`.
- **mattleonard16:** trains position-specific models on strictly earlier weeks (walk-forward); EWMA volatility features.
- **ctrax68:** trailing baselines (window not documented as carefully as the distribution work).

## 4. Team/role-change handling — the honest answer

**No repo surveyed does explicit team-change regime detection.** The two closest things:

1. **crollila lists it as explicit future work:** *"Explicit regime detection for structural role change, instead of inferring it from a moving average"* and *"Hierarchical pooling so thin-history players borrow strength rather than defaulting to a league prior."* Their +3.8% came from *inferring* role change from moving averages of snap share — not from detecting team changes.
2. **war-room** has a **current-team verification gate** — historical team identifies where a stat row was earned; current team is the latest verified roster team; a team mismatch *blocks* forward projection rather than adjusting it. That's a live-mode safety gate, not a historical modeling mechanism.

**Negative result worth preserving (crumblip, measured):** "vacated volume" does not predict who gets the work. Regressing next-season share on prior share + vacated share: every vacated coefficient ≈ 0 or negative, none reaches t=2. *"What actually happens is that teams REPLACE departed volume"* — Round 1 draft picks take 20.2% of targets / 56.0% of carries. *"Vacancy is variance, not a forecast."* **Do not build vacated-carries features.**

## 5. Regime-change machinery from sports modeling (transferable)

- **DARKO-style per-player Kalman filters** (NBA; documented in sportsdataverse methods): latent skill state, predict step with empirically-fit aging drift, process variance `q`, observation variance `r_t = obs_base / weight[t]` (low-minute observations get less update weight). Noise params `(q, obs_base)` MLE-fit by maximizing **one-step-ahead forecast log-likelihood** — 2 scalars, not a model-selection grid.
- **EvanMiya (CBB):** stat-specific dynamic linear models over game-by-game histories.
- **portalpoint (CBB state-space plan):** *"Different skills can have different stability. Three-point shooting should usually move slower than assist rate."* — i.e., **stat-specific process noise**: shares fast, efficiency slow.
- The transferable pattern: the Kalman gain *is* the recency-weighting mechanism, derived from the noise ratio, with 2–3 global parameters fit by predictive likelihood. No per-player learned weights.

## 6. Validation discipline (what the serious ones do)

- **crollila:** refit every week on strictly-earlier data; single `expanding_lagged` function concentrates the no-leakage rule (exhaustively testable); **week-block bootstrap** (player-weeks within a week share environments); pre-specified promotion rule (≥0.15 MAE, bootstrap lower bound > 0, no position degrades); **family-level ablation** (hypotheses counted in families, not columns); promote the *smallest* clearing subset (118 inputs, not 267).
- **ctrax68:** replays 2023–24 (~21,000 props), reports **calibration** (mean error 3.16pp) rather than ROI against synthetic lines, which they correctly call circular. Sigma *modeled* as `σ = w·σ_player + (1−w)·σ_league(μ)`, `w = n/(n+k)` — shrinkage, not raw sample SD.
- **war-room:** walk-forward mandatory; *"Random train/test splits across the same season are not used."*
- **ctrax68 measured finding relevant to us:** normalizing target/rush shares to team volume *without a real inactives list* biased every skill-position projection low by 11–16% (a fifth of the candidate roster is inactive). Only safe with real availability data.

## 7. Snap share / depth charts as role signals

- **crollila (promoted family):** `snap_offense_pct` at multiple horizons plus two contrast features: `snap_share_change = last1 − season-to-date` and `snap_share_jump = last1 − last5`. The docstring: *"what lets the model recognise a player whose role jumped from 35 percent to 80 percent instead of treating him as his season average."*
- **usage trends:** `trend_targets/carries/target_share = last3 − season-to-date`.
- **quantasy/gridev feature lists:** snap_pct, route_participation (needs PFF — not keyless), redzone shares.
- **Depth charts:** nobody models them historically. war-room treats role/depth-chart as a **manually-verified gate layer** (template CSVs, overrides, never hardcoded in model math). Consistent with our audit: no historical depth-chart data exists keyless.

## 8. Why our 005 failed where crollila's similar idea worked

1. We learned **one global blend weight** on dev; they gave the learner **per-player contrast features** at multiple horizons and let a regularized model respond to them.
2. We **selected max-capacity GBM in-sample on dev** (the overfitting trap); they used walk-forward refit + family ablation + smallest-clearing-subset.
3. Their contrast features (`last1 − season-to-date`) directly encode "role jumped" — the mechanism is in the *features*, and the learner is deliberately ordinary.
4. Caveats: their target was fantasy points (composite), they included market features (excluded by our protocol), population 2023–2025.

## 9. Concrete mechanism ideas worth preregistering (all keyless-nflverse-implementable)

### Idea 1 — Recent-vs-baseline contrast features + low-capacity learner (from crollila)
Per player-week, construct **contrast features**: `snap_share_last3 − snap_share_trailing16`, `carries_last3 − carries_trailing16`, `target_share_last3 − target_share_trailing16`, `rush_share_last1 − rush_share_season`, plus `stint_games` and a team-change indicator. Feed to **Ridge or a heavily-regularized GBM** (depth ≤ 3, or better: Ridge only) **stacked on frozen M0** — M0 stays a feature, the learner is deliberately weak. The contrast *is* the regime detector; no learned regime parameter exists to overfit.
- *Why it dodges the 005 trap:* capacity is constrained by construction (Ridge has one alpha; no 8-combo GBM grid selected in-sample). Dev is used only for the alpha, or walk-forward refit per crollila.
- *Evidence:* the closest thing to validated — crollila's +3.8% (MAE 4.5917→4.4181, bootstrap CI [+0.1409,+0.2087], all four positions improve).

### Idea 2 — Per-player Kalman filter on shares and rates, stat-specific process noise (from sspam1189 spec + DARKO/EvanMiya)
Track `rush_share`/`target_share` with **high** process noise (roles change fast) and `YPC`/`catch_rate`/`YPR` with **low** process noise (efficiency is sticky); observation variance ∝ 1/games played. **Team change = inflate the share state's variance** (or reset its prior to the new team's positional prior) while **keeping the efficiency state intact** — the formal version of "talent carries over, role does not." Projection = projected team volume × filtered share × filtered rate. Only **2–3 global noise parameters**, fit by one-step-ahead predictive likelihood on dev — the Kalman gain derives the weighting, nothing is selected from a grid.
- *Why it dodges the 005 trap:* the weighting mechanism is analytic given the noise ratio; there is no high-capacity selection step. A null here would be informative, not an overfitting artifact.
- *Evidence:* design-stage (sspam1189 is a spec), but the DARKO/EvanMiya lineage is production-proven in other sports.

### Idea 3 — Top-down share reconciliation with a fixed team budget (from war-room / flintcap/endzone)
Project team rush attempts; allocate to RB-room members by **current-team rush shares normalized to sum to 1**. For Rodriguez: his share of Jacksonville's backfield comes from JAX games only — the Washington history structurally cannot enter the share. Efficiency from the longer history. No learned weights at all.
- *Caveat (ctrax68, measured):* normalizing across inactives biased projections 11–16% low. Requires the as-of inactives/availability input (we have the 002 Family L convention) or shares must be computed over players with snaps>0 only.
- *Why it's listed third:* it's structural and safe, but it's essentially a hand-built version of what Ideas 1–2 learn; preregister only if 1–2 null.

### Explicitly NOT recommended
- **Vacated-volume features** (crumblip measured ≈ 0 effect).
- **Another learned global blend weight** (that's 005, NULLed).
- **Max-capacity GBM with in-sample dev selection** (the documented failure mode, twice: our 005 and 002's B+E).

## 10. Assessment: what to preregister next

**Preregister Ideas 1 and 2 as the next props experiment** (one experiment, two candidates, same frozen bar as 005: ≥5% pooled / ≥2% per season / bootstrap CI / regression guard). Idea 1 has the closest validated precedent; Idea 2 is the principled formalization of the "talent transfers, role doesn't" hypothesis and its 2-parameter fit cannot reproduce the 005 overfitting failure. Both run on keyless nflverse data (player stats, snap counts, pbp-derived shares), respect the Friday 18:00 CT cutoff, keep the market line out, and leave Model D untouched. Depth-chart signals remain 2026-prospective-only per the audit.
