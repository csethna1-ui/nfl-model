# Source references — Feature Discovery Audit (2026-09-29)

Every externally sourced claim below is tied to its source URL and what the source actually says.
These are discovery inputs, not endorsements: a feature's presence in another model is not evidence it beats the line.

## Data documentation (nflverse / nflfastR)

1. **nflreadr NEWS.md — participation gains time_to_throw / was_pressure / coverage fields**
   https://github.com/nflverse/nflreadr/blob/HEAD/NEWS.md
   Claims: `load_participation()` now returns `time_to_throw`, `was_pressure`, `defense_man_zone_type`, `defense_coverage_type` (nflreadr 1.4.1, #233).
   Also documents: participation pre-2023 is NFL NGS; 2023+ is FTN, released after postseason, CC-BY-SA 4.0.

2. **nflfastR NEWS.md — xpass / pass_oe added by default**
   https://rdrr.io/cran/nflfastR/f/NEWS.md
   Claims: `build_nflfastR_pbp()` runs `add_xpass()` by default, adding `xpass` and `pass_oe` (pass rate over expected). Verified present in local `data/pbp_2018.parquet`.

3. **nflfastR 6.0.0 NEWS — raw PBP source moved to nflverse-pbp**
   https://github.com/nflverse/nflfastr/blob/HEAD/NEWS.md
   Claims: nflfastR now loads raw PBP from season-based releases in `nflverse/nflverse-pbp`; legacy `nflfastR-raw` deprecated (matters for 2026+ downloads).

4. **awesome-nfl-data — feed cadence and in-season limitations**
   https://github.com/jovanipink/awesome-nfl-data/blob/HEAD/README.md
   Claims: nflverse PBP updates nightly in-season; "Do not depend on nflverse participation or injury files for current in-season reporting. Participation data from 2023 onward is released only after the postseason, and the nflverse injury source currently stops after 2024."

5. **nflverse release probes (verified by download 2026-09-29)**
   - PFR advstats weekly pass 2018 and 2026: HTTP 200 (pressure fields: `times_pressured_pct`, `times_blitzed/hurried/hit`, `def_times_blitzed/hurried/hitqb`).
   - FTN charting 2024 and 2026: HTTP 200 (fields: `is_motion`, `is_play_action`, `n_blitzers`, `is_contested_ball`, `is_drop`, `date_pulled`, …).
   - Snap counts 2024 and 2026: HTTP 200 (in-season updating).
   - NextGen Stats passing 2024: HTTP 200.
   - Participation 2025: HTTP 200 (post-season release).

## Open-source models and their claims

6. **chmoses98/nfl-edge-finder — RESULTS.md**
   https://github.com/chmoses98/nfl-edge-finder/blob/HEAD/research/game_model/RESULTS.md
   Claims (pooled 2014–2025): closing spread RMSE 12.88 / MAE 9.95; football-only EPA model 13.26 / 10.31; market-residual model 12.92. Encompassing regression `result ~ spread + model`: 1.01 on spread, 0.03 on model. Model-vs-spread ATS when disagreeing >3 pts: 50.0% (n=928). Conclusion: "A team-level EPA rating model of this kind carries no information beyond the closing line."
   Relevance: independent replication of our Experiments 001–005 pattern.

7. **colemason6524/nfl_props — PLAN.md (v2 shadow ablation)**
   https://github.com/colemason6524/nfl_props/blob/HEAD/docs/PLAN.md
   Claims: ablation backtest (tune 2015–2022, holdout 2023–2025, vs de-vigged close): adding schedule + pass/rush opponent-adjusted EWMAs + lag-starter QB delta + CPOE shaved ~0.02 MAE but stayed at market parity. "The closing line already prices schedule, pass/rush splits, and QB quality." Kept v1; "a real pregame QB/injury source is the only remaining lever with plausible upside, and even that is unproven."

8. **howlscastle97/nfl-model-hq — CLAUDE.md**
   https://github.com/howlscastle97/nfl-model-hq/blob/HEAD/CLAUDE.md
   Claims: per-QB EPA/dropback rating (empirical-Bayes prior −0.076) tested 2026-09-14 and NOT shipped — improved the linear model on selection but held-out difference on the deployed ensemble was −0.0002 [−0.0131, +0.0123]. "The likeliest reading is that the ensemble already extracts quarterback quality from team EPA, CPOE and qb_fam_diff together." Kept as foundation for injury work ("the listed starter is out, rate his backup"). Also uses QB familiarity: share of team's last 16 starts by today's listed starter.

9. **wadefuller/nfl_predictor — HANDOFF.md (ablation log)**
   https://github.com/wadefuller/nfl_predictor/blob/HEAD/docs/HANDOFF.md
   Claims (all reverted): PFR pressure rate "landed at rank 41 (real signal) but displaced starter_pass_epa features; substitution, not net addition." ESPN QBR: 0.79 correlation with qb_epa; 0 of 4 metrics improved. Travel distance + timezone: 6 of 12 cols earned XGB rank but displaced starter_qb_epa; 0 of 4 metrics improved. "Even a spatially-orthogonal feature hits the saturation wall."

10. **harsh4873/pickledger — nfl-model-plan.md**
    https://github.com/harsh4873/pickledger/blob/HEAD/docs/plans/nfl-model-plan.md
    Claims: planned features include EPA + success + explosive-play rate + early-down EPA, rest/travel/dome/surface, starting-QB-change flag ("the single biggest single-player effect in NFL"), and market-anchored residual heads. Honest expectation: "beating closing lines consistently is near-impossible."

11. **saiemgilani/game-on-paper-app (rbsdm) — NFL branch design**
    https://github.com/saiemgilani/game-on-paper-app/blob/HEAD/docs/superpowers/specs/2026-09-09-nfl-branch-design.md
    Claims (derivations, not predictive claims): QB composite `0.5·z(EPA/db)+0.5·z(CPOE)`; `pass_oe`/`xpass` already on the frame; luck indicators `luck_fumble_rec_pct`, `luck_fg_pct`, `luck_int_rate` from `fumble`/`fumble_lost`/`field_goal_result`/`interception`; fourth-down go-rate over expected; series success from `series`/`series_result`.

12. **dgrifka/nfl_simulator — research docs (02-skill-vs-luck, 04-bayesian-results, 01-descriptive-eda, 14-special-teams)**
    https://github.com/dgrifka/nfl_simulator/blob/HEAD/docs/research/02-skill-vs-luck.md
    Claims: 2,761 games / 320 team-seasons / 200 split-half draws. Fumble recovery is the ONLY component with no team skill (split-half +0.055); FG results, penalties, INTs carry real repeatable skill. "Stripping luck did not improve out-of-sample prediction. Not for any component, not in any combination."
    https://github.com/dgrifka/nfl_simulator/blob/HEAD/docs/research/14-special-teams.md
    Claims: ST partly unobservable — PBP records one spot per punt, so `kick_distance` mixes flight and roll inseparably; kickoff eras never pooled (return rate 0.25 in 2023 → 0.33 in 2024 → 0.74 in 2025; two structural breaks in two years).
    https://github.com/dgrifka/nfl_simulator/blob/HEAD/README.md
    Claims: special teams, field position, penalties, charting data deliberately excluded; opponent adjustment "turned out to be shrinkage toward the league mean rather than information."

13. **Wharton — "Evaluating the Impact of Special Teams on Winning"**
    https://wsb.wharton.upenn.edu/wp-content/uploads/2024/05/Impact-of-Special-Teams-Paper-FINAL.pdf
    Claims: public method for ST EPA — punt EPA vs yardage-expectation model; FG EPA from distance+wind make-probability model; missed-FG field-position accounting. Method reference only, not a predictive claim.

14. **gesmith0606/nfl_data_engineering — VISION.md / SOTA_RESEARCH.md**
    https://github.com/gesmith0606/nfl_data_engineering/blob/HEAD/.planning/VISION.md
    Claims: identifies "player-level signal" as the single biggest gap ("A backup QB starting swings a game 3-7 points"); plans QB quality differential, positional replacement quality, depth-chart deltas, personnel/formation data. SOTA notes: "53–55% selective / +CLV vs openers is the actual frontier; nothing public beats the close."

15. **sspam1189-stack/model — pyNFL README + design spec**
    https://github.com/sspam1189-stack/model/blob/HEAD/pyNFL/README.md
    Claims: Kalman-filtered team EPA states, injury-adjusted projections with positional EPA deltas (QB/WR1/pass rusher/CB1/OL), exponential decay ~0.85/week. Design doc tiers: Tier 1 efficiency (EPA splits, success rate); Tier 2 passing game (CPOE, air yards/aDOT, pressure rate allowed, QB EPA/dropback); Tier 3 defensive detail (pressure created, red-zone D); Tier 4 situational (3rd down, turnover-adjusted efficiency, pace). No verified predictive claims published.

16. **jwallace115/mlb-model — nfl_project_brief.md**
    https://github.com/jwallace115/mlb-model/blob/HEAD/research/nfl/nfl_project_brief.md
    Claims (philosophy, not results): three-layer approach — descriptive state engine, market-relative test ("Does the market already price this? If yes, move on"), decision framework. Uses CPOE, expected YAC, pressure probability, route/coverage data.

## Academic

17. **Nelson (Old Dominion) — "The Performance of Betting Lines for Predicting…"**
    https://export.arxiv.org/pdf/1211.4000
    Claims (2002–2011, n=2560): line movement (open→close) predicts division winners ≥75%; home underdogs covered 53.5% (above 52.38% break-even) in that window. Dated; cited for the line-movement literature only, not as a current edge.
