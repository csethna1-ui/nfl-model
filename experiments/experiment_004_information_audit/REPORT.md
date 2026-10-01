# Experiment 004 — Information-Set / Market-Timing Audit: REPORT

Diagnostic only. No predictive model was fitted. The 2023–2025 vault was not touched (zero evaluations). V1 unmodified. No V2 label created.

## Context

Three predictive experiments failed without contaminating the vault: market-residual modeling (001), opponent-adjusted EPA (002), dynamic offensive/defensive strength (003). Experiment 003's candidate had **0.985 error correlation with V1** — a different representation learning the same mistakes. Market–V1 error correlation is 0.967. The question for this audit: is the persistent gap (market MAE 9.727 vs V1 ~10.04 on 2021–22) a modeling problem, or an information-timing problem?

## Phase 1 — Timeline audit (summary)

- **Model side:** V1's effective information timestamp is ~Tuesday morning of game week — weekly-batched ELO/EPA/GBM ratings through the previous week's games, schedule-derived rest/division. No within-week updates. QB injury news exists only in the 2026 production void filter, not historically. Non-QB injuries, weather, and line movement are absent entirely. Information state well-defined by construction, not timestamped.
- **Market side:** `spread_line` is one undated scalar per game from nflverse schedules. nflverse documents no timing. This repo describes it three contradictory ways ("likely consensus/opening" in `backtest_report.md:65`; "close proxy" in `08_grade_week.py:68` and `15_export_ui_json.py:78`; `'nflverse_proxy_open'` stamp in the experiment dataset). Independent third-party measurements suggest close/consensus-like behavior (68% exact match to captured close vs 25% to opener).
- **Classification:** every historical model-vs-market comparison is **timestamp unknown** (alignment never inferred). The 2026 live pipeline is **timestamp aligned** (Friday-AM research for lines, predictions, and QB news).
- **Central finding:** if the market snapshot is close-ish, every backtest compares V1's Tuesday-morning information against the market's Sunday-morning information — a **4–5 day information gap** (Wed–Fri injury news, weather forecasts, late sharp action) that no team-strength representation can close. The three nulls are consistent with this.

## Phase 2 — Information-gap inventory (summary)

Ranked by expected value × feasibility × timestampability, free/keyless only. Full table in `information_gap_inventory.json`.

1. **Non-QB player availability** — the largest untested gap. nflverse `load_injuries()` verified working 2026-09-29: 11,269 rows (2021–22), Out/Doubtful/Questionable designations, all positions, `date_modified` UTC timestamps with zero nulls. Fundamentally different information from ELO/EPA ("who is playing" vs "how the team performed").
2. QB availability (historical extension) — partially covered already (void filter; v2 QB feature failed). Only with preregistered non-overlap.
3. Roster/depth-chart changes — likely subsumed by (1).
4. Weather — already tested (wind null on spreads). Player-level EPA disaggregation — representation, not information. Line movement, coaching/scheme — infeasible under the constraint.

## Phase 3 — Data-quality verdict

- The historical spread comparison is **suitable as a coarse benchmark, unsuitable as a timestamped tradable baseline**. Suitable for architecture screening with the existing ≥0.15 MAE noise guard; not suitable for fine-grained model selection. Do not "correct" it statistically.
- The **live 2026 Friday stream** (researched Friday-AM lines + same-morning predictions + close-proxy CLV) is the cleaner evaluation substrate and should carry increasing weight as weeks accumulate — it is the project's only timestamp-aligned comparison.
- `line_provenance` should be restamped `'nflverse_unverified_single_snapshot'` in future builds; the current `'nflverse_proxy_open'` stamp encodes an unverified assumption.

## Leakage assessment (summary)

Injury designations are safe pregame features under a hard rule: `date_modified` < defined prediction time (recommended Friday 12:00 ET, mirroring the live pipeline). Verified: median 28.3h pre-kickoff, 99.86% strictly pregame. Preregister Questionable treatment and QB non-overlap before validation. Full assessment in `leakage_assessment.md`.

## Verdict

**A. INFORMATION-SET IS ADEQUATELY ALIGNED — proceed to one preregistered predictive candidate:**

**Experiment 005 — non-QB player-availability model.** Test whether adding verified-pregame injury designations (Out/Doubtful/Questionable, non-QB positions, `date_modified` < Friday 12:00 ET) to frozen V1 closes the market gap on 2021–2022 validation, under the standard gate (≥0.15 MAE vs market, beats V1, both seasons, calibrated, diversified from V1). No division/late-season corrections, no ATS tuning, no vault access unless the full gate passes.

Qualifications carried forward: historical MAE deltas are coarse benchmarks; the live 2026 stream is the prospective arbiter; nothing is labeled V2 until the full promotion bar clears.
