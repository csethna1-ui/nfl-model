# Prospective Season-to-Date Props Audit — 2026 Weeks 1–3

**Status: MONITORING ONLY. No retraining, no refitting, no threshold changes,
no tuning on Weeks 1–3 outcomes. W1–W3 treated strictly as prospective
out-of-sample data.**
**No betting-edge language is used anywhere in this document.**

Completed 2026-10-01. Phase workers: phase1/ (Model D yards), phase3/ (003A/003B).
Phase 2 (market-line inventory) done by coordinator. Follow-on matchup
preregistration drafted separately (PREREGISTRATION_defensive_matchup.md — DRAFT, not run).

## 1. Method

- **Phase 1:** Complete Model D projection sets for 2026 W1–W3 regenerated from
  the frozen pipeline (byte-patched copy; frozen artifacts loaded untouched).
  As-of Fridays pinned to 2026-09-04 / 09-11 / 09-18 18:00 CT (override of the
  script's Sunday-anchored rule, which would have silently dropped 2 W1 games).
  Actuals from local pbp-derived `data/player_games.parquet` (nflverse has not
  published 2026 weekly player stats).
- **Phase 3:** Frozen 003A-M2-verified and 003B-M2-frozen heads applied to
  W1–W3. As-of Fridays per the production schedule-derived rule
  (09-11 / 09-18 / 09-25 18:00 CT), pre-Friday games excluded per game-week.
  Trailing-only NGS, week==0 rows excluded, missing NGS → 0-fill (flagged).
- **Caveat — Friday convention differs between phases.** Phase 1 used 09-04
  (keeps all 16 W1 games, cutoff a week early for Sunday games); Phase 3 used
  09-11 (true Friday-before-Sunday, excludes the Thursday kickoff). Both are
  defensible monitoring choices; cross-phase week alignment is approximate.
  **Recommendation: pin one convention for all future weekly audits.**
- **B-test scoping (Phase 2):** `data/market_props_2026_w{1,2,3}.json` contain
  only `player`/`market`/`line` keys — no in-file capture timestamps, no team
  field. File mtimes (Sep 11/18/25) are the only timing evidence. Model-vs-line
  for W1–W3 is therefore **descriptive only**, never a validated market
  backtest. The honest B-test begins with the Week 4+ timestamped stream.
  No receptions or rush-attempts lines exist in any W1–W3 file.

## 2. Aggregate results

MAE pooled over W1–W3; bias = mean(projection − actual); n = scored rows.

| Market | Model | W1 MAE (n) | W2 MAE (n) | W3 MAE (n) | Pooled MAE (n) | Pooled RMSE | Pooled bias | Locked-test MAE |
|---|---|---|---|---|---|---|---|---|
| Pass yards | Model D | 77.1 (35) | 73.4 (37) | 66.8 (36) | **72.4** (108) | 93.9 | +24.9 | 60.6 |
| Rush yards | Model D | 28.3 (61) | 28.3 (65) | 25.2 (63) | **27.2** (189) | 32.6 | +12.4 | 25.1 |
| Receiving yards | Model D | 25.7 (166) | 25.3 (165) | 24.4 (168) | **25.1** (499) | 31.2 | +8.5 | 24.0 |
| Receptions | 003A-M2 | 2.50 | 2.67 | 2.59 | **2.59** (610) / 2.28 excl. DNP (472) | — | +2.04 | 1.35 |
| Rush attempts | 003B-M2 | 6.66 | 6.38 | 6.06 | **6.35** (141) / 5.77 excl. DNP (129) | — | +4.21 | 2.98 |

## 3. Headline verdict (narrowly stated — three weeks is a tiny sample)

- **Model D yards: roughly holding.** Rush and receiving yards are within
  ~1–2 yards of locked-test MAE. Pass yards' gap (+12) is largely
  artifact-driven: W1 team-assignment staleness (pipeline has no roster input;
  57/262 scored W1 rows projected for the wrong team after 2026 offseason QB
  movement) plus projections for players with zero in-game opportunity.
  Removing both brings pass MAE to ~62–63, near locked test. A consistent
  positive bias (model projects high) appears in all markets/weeks — worth
  watching, not acting on.
- **003A/003B: NOT reproducing locked-test levels in W1–W3.** Even on the
  apples-to-apples excl.-DNP cut (locked tests required `played_role=1`),
  receptions 2.28 vs 1.35 and rush attempts 5.77 vs 2.98 are materially worse.
  The gap decomposes into (1) DNPs scored as zero — the heads project everyone
  with trailing history and have no inactive feed (138/610 reception rows);
  (2) systematic over-projection, uniform across weeks and volume terciles,
  with the biggest misses being real workload regime changes verified against
  raw pbp (e.g., Achane proj 18.8 vs 3 actual W3; Gibbs 15.7 vs 29 W1) —
  data is clean, the misses are real; (3) three early-season weeks vs two full
  seasons — descriptive only, no inference.
- **This does not overturn the 003 results.** It says the historical edge has
  not *yet* demonstrated persistence in three weeks of 2026 — which is exactly
  what the prospective stream is for. The correct response is continued
  accumulation, not retraining.

## 4. Deep diagnostics (summary; full tables in phase1/PHASE1.md, phase3/PHASE3.md)

- **Opportunity volume / projection size:** errors scale with volume as expected;
  no anomalous concentration in any tercile for Model D. For 003A/003B,
  over-projection is uniform across volume terciles (not a fringe-player artifact).
- **Uncertainty buckets:** no clean MAE ordering at these n's (Model D);
  003A/003B ship point projections with placeholder uncertainty labels.
- **Position:** standard patterns; nothing actionable at n≈100–500.
- **Week:** pass-yards MAE improves W1→W3 (77→67), consistent with early-season
  staleness burning off. 003B improves slightly W1→W3 (6.66→6.06).
- **Rookie vs established:** degenerate by construction (MIN_GAMES / trailing
  guards) — zero scored rookies; documented, not a finding.
- **NGS availability (the key cut):** raw MAE by NGS status is confounded by
  volume (NGS-missing rows are low-volume fringe). Volume-controlled
  (OLS abs_err ~ projection + I(ngs=full), no-DNP, observational):
  receptions ngs_full coef **−0.34 (se 0.15, t=−2.27)**; rush attempts
  **−1.32 (se 0.89, t=−1.47)**. Relative MAE full/partial/fallback:
  0.479/0.590/0.630 (rec), 0.361/0.533/0.472 (rush). **Directionally, full-NGS
  rows grade better relative to volume in both heads** — consistent with (not
  proof of) the locked-test M2-vs-M1 finding. Observational, not causal.
  Zero stale-NGS rows in W1–W3.

## 5. B-section: model vs sportsbook line (descriptive only)

- Where W1–W3 lines exist (36/16/12 rows, yards markets only), model−market
  gaps are tabulated in phase1 outputs — **descriptive, mtime-provenance only,
  never a validated backtest**. No timestamped capture exists for these weeks.
- No receptions or rush-attempts lines were captured in W1–W3 at all, so the
  two experimental markets are graded projection-vs-actual only.
- **No conclusion about beating the market is drawn or drawable from this
  audit.** The honest market test begins with the Week 4+ timestamped stream.

## 6. Data problems and flags (preserved, not fixed)

1. nflverse has not published 2026 weekly player stats; actuals are pbp-derived.
2. Name collisions (23 player-weeks, e.g., J.Love ARI/GB): attributed to the
   projection-team row, flagged `dup_actual_teams`; 1 row unscorable.
3. Schedule spread/total inputs are the 2026-09-30 nflverse cache, not
   guaranteed Friday-18:00 values (affects ENV features only).
4. Phase 3: `scripts/19_prod_receptions.py` was edited twice mid-task by the
   parent-side integration worker (tuple filter → game_id join + base rebuild
   from player_games.parquet). Re-run showed behavior-preserving
   (max |Δ| 0.7, mean ≈ 0.01); all Phase 3 aggregates reflect the final
   version. **Parent should confirm edit 2 is the intended verified deployment.**
   003B script unmodified.
5. 4 team-changed rows (2025 team vs 2026 actual) graded vs actual production,
   flagged.

## 7. What this audit establishes / does not establish

- Establishes: the prospective monitoring apparatus works end-to-end; Model D
  yards are performing near locked-test levels modulo known artifacts; 003A/003B
  have not yet shown their historical edge in 2026 W1–W3 (3 weeks, systematic
  over-projection, real regime-change misses).
- Does not establish: any betting edge; any reason to retrain; any defect in
  the frozen models (sample far too small); anything about market-beating.

## 8. Next

- Continue the prospective stream weekly (pin one Friday convention — see §1).
- Defensive matchup experiment: PREREGISTRATION_defensive_matchup.md drafted,
  **not frozen, not run** — awaiting the audit verdict and Cale's decision.

## Deliverables

- phase1/PHASE1.md, PHASE1_NOTES.md, outputs/phase1_errors_2026_w1w3.parquet (796 rows), outputs/phase1_aggregates.json, inputs/asof_w{1,2,3}/, code/
- phase3/PHASE3.md, PHASE3_NOTES.md, projections/ (6 JSONs, 751 rows), error_table_2026_w1w3.parquet, aggregates_2026_w1w3.json, work/
- PREREGISTRATION_defensive_matchup.md (draft, unrun)
