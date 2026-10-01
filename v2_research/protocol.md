# V2 Research Protocol — FROZEN

**Frozen: 2026-09-29. This protocol may not be changed after validation
results are examined.** Any change after results requires a new protocol
version and a written justification; the results obtained under this version
stand as recorded.

## 1. Timeline and data discipline

| Period | Role |
|---|---|
| 2018–2020 | Development: hyperparameter selection (ridge alpha), pipeline sanity checks, missingness audits. No 2021–2022 data used for any decision. |
| 2021–2022 | Controlled validation: frozen specs, one evaluation per candidate, no re-tuning after seeing results. |
| 2023–2025 | Pristine locked vault: touched ONLY for the single locked evaluation after `V2_FINAL_*` is complete AND at least one candidate passed all gates. Otherwise it stays pristine. |
| 2026 | Production/prospective only. Never used for fitting, selection, or architecture decisions. Experiment 006 continues independently and is never an input. |

Vault outcomes are never used to select features, models, hyperparameters,
thresholds, transformations, architecture, or weighting. V1 code, scripts,
and predictions are read-only throughout.

## 2. Prediction information set

The Tuesday-AM set per `timestamp_policy.md`: every feature, scaler,
imputation statistic, and prior uses only information strictly before
`08:00 ET on the most recent Tuesday before the team's kickoff`. PFR
features lag one additional week (usable through W−2). Injury rows obey
`date_modified < min(cutoff, kickoff)`; the Tuesday availability set is
identically zero (documented).

## 3. Model form (all candidates)

Ridge regression on the home margin (home perspective, no perspective
doubling needed — the form below is fitted once per game in home terms):

```
y_home = α + Σ_k βA_k·(home_off_k − away_off_k)
            + Σ_k βB_k·(away_def_k − home_def_k)
            + βR·(home_rest − away_rest)
            + [candidate-specific additions, same differential form]
```

- `off` features are offensive measures (higher = better offense);
  `def` features are "allowed" measures (higher = worse defense), hence
  `away_def − home_def`.
- This is a component model: offense advantages and defense advantages get
  separate coefficient blocks — it does not collapse to a single
  team-strength scalar. V2-B adds genuine interaction terms.
- All features standardized walk-forward per `standardization_spec.md`
  (league-wide expanding, |S(W)| ≥ 30, ≥4 prior games/team, cross-season
  option A continuous expanding, NaN propagation on gate failure).
- Feature-level missingness: walk-forward median imputation over S(W);
  missingness fractions recorded per game and per candidate.
- Cold start (frozen choice, Option C): if either team has < 4 prior games
  (`hist_games`), the candidate emits no prediction — V1's `ens_margin` is
  used as a logged fallback. Fallback games are EXCLUDED from the primary
  V2-vs-V1 comparison and reported separately (with V1's numbers).

## 4. Walk-forward procedure

For each validation week W (2021–2022): training set = all regular-season
games with kickoff < Tuesday 08:00 ET of week W, seasons 2018+. Fit
`Ridge(alpha*)` on the training games; predict W's games. `alpha*` is
selected per candidate on 2018–2020 walk-forward from {0.1, 1.0, 10.0,
100.0} by MAE, then frozen. No other hyperparameters. Deterministic
preprocessing; training window, feature availability, hyperparameters,
sample count, missingness, and model version recorded per fit.

## 5. Candidates and preregistered feature lists

Team-level base features come from `data/v2/team_features_pred.parquet`
(walk-forward, week < W); game-level rest from the games table.

**V2-A — component architecture.** Tests whether the component-structured
linear model on V2's own base features beats V1's scalar-strength ensemble.
- Offense block (5): points_per_drive, epa_per_drive, scoring_drive_rate,
  rz_trip_rate, gtg_td_rate
- Defense block (4): points_per_drive_allowed, epa_per_drive_allowed,
  scoring_drive_allowed, rz_trip_allowed
- Plus: α (intercept = home edge), βR·(home_rest − away_rest)
- 20 regressors + intercept.

**V2-B — V2-A + matchup interactions.** 8 preregistered terms, focal=home
perspective, each as net advantage (home-side minus away-side):
- pass offense × pass defense: expl_pass_rate × expl_pass_allowed (product
  and cross-differential)
- pass protection × pass rush: pressure_allowed_pct × def_pressures
  (product and cross-differential; def_pressures PFR-lagged through W−2)
- rush offense × rush defense: expl_rush_rate × expl_rush_allowed
  (product and cross-differential)
- explosive offense × explosive defense: big20_rate × big20_allowed
  (product and cross-differential)
- Form per pair (off_f, def_f):
  prod = home_off_f·away_def_f − away_off_f·home_def_f;
  xdiff = (home_off_f − away_def_f) − (away_off_f − home_def_f).
- No other pairwise interactions. No fishing through the 32 mx_* features.

**V2-C — V2-A + QB/player.** 7 features as (home − away) differentials:
qb_value_historical (from `data/v2/qb_value_pred.parquet`; `qb_pressured_pct_rw`
excluded — Friday-safe only), qb_nonqb1_share, snap_continuity_off,
ol_continuity, skill_continuity, avail_value_out, avail_n_out.
Availability is identically zero in the Tuesday set (documented); the model
must tolerate constant columns. `qb_value_poll` is quarantined and never
enters.

**V2-D — V2-A + pressure / explosiveness-shape / possession-structure.**
37 features as (home − away) differentials:
- Possession structure (7): three_and_out_rate, start_y100,
  plays_per_drive, drive_to_rate, three_and_out_forced, start_y100_allowed,
  drive_to_forced
- Explosiveness shape (15): epa_std, epa_median, epa_p10, epa_p90,
  expl_pass_rate, expl_rush_rate, big20_rate, big40_rate, air_per_att, adot,
  expl_pass_allowed, expl_rush_allowed, big20_allowed, big40_allowed,
  epa_std_allowed
- Pressure (15): pressure_allowed_pct, sack_rate, qb_hit_rate, hits_taken,
  hurries_taken, pressures_taken, blitzed_taken, drops, bad_throw_pct,
  def_blitzes, def_hurries, def_qb_hits, def_sacks, def_pressures,
  def_missed_tackles (PFR-sourced members lagged through W−2)
- No overlap with V2-A's base features (verified at freeze time).

**V2-E — full preregistered V2.** V2-A plus the families of candidates that
pass all gates in §7. If no candidate passes, V2-E is not built.

## 6. Evaluation metrics (every candidate, 2021–2022)

1. MAE 2. RMSE 3. signed bias (mean error) 4. calibration intercept/slope
   (actual ~ predicted) 5. error SD 6. prediction–actual correlation
7. error correlation with V1 8. paired absolute-error comparison vs V1
   (bootstrap) 9. season-by-season MAE (2021, 2022) 10. MAE by |prediction|
   buckets: [0,3), [3,7), [7,14), [14,∞) 11. family ablation — inherent in
   the ladder (V2-X vs V2-A); no additional refits 12. coefficient stability
   across walk-forward refits (SD of standardized coefficients over time)
13. missing-data impact (missingness fractions; MAE on fully-observed vs
   imputed subsets, descriptive) 14. leakage checks (code audit against
   `leakage_audit_v2_final.md` + the pre-modeling checklist).
Primary benchmark: V1 (`ens_margin`, same games). Secondary: historical
market MAE (`spread_line`) with the timestamp caveat disclosed — never a
gate. ATS, ROI, and market disagreement are NOT reported as selection
criteria and play no role in gating.

## 7. Pass/fail gates (all must pass for a candidate to advance)

- **G1:** MAE(V2) < MAE(V1), two-sided paired bootstrap (10,000 resamples),
  p < 0.05.
- **G2:** MAE(V2) < MAE(V1) in 2021 and in 2022 separately.
- **G3:** |signed bias| < 1.0; calibration slope ∈ [0.8, 1.2].
- **G4:** leakage audit passes (independent code audit of the modeling
  build against `leakage_audit_v2_final.md`).
- **G5:** error correlation with V1 < 0.98 (must not be a near-identical
  twin; the failed experiments sat at 0.985–0.995).
- **G6:** every feature's timestamp defensible per `timestamp_policy.md`.

A candidate advances only on evidence: improvement over V1, not driven by
one season, reasonable calibration, stable, no leakage, defensible
availability, incremental information vs V1, no hyperparameter overfitting.
Ties prefer: simpler model, fewer features, more stable coefficients,
cleaner timestamps, easier reproducibility. **Do not manufacture a winner
when evidence is ambiguous.**

## 8. Stopping rules

- One validation evaluation per candidate. No re-running with different
  settings because the result was disappointing.
- Failed gates stay failed. No new candidates invented after seeing results.
- The protocol is not changed after validation results are examined.

## 9. Vault policy

- The vault (2023–2025) is touched ONLY if at least one candidate passes
  all gates and `V2_FINAL_*` (spec, features, hyperparameters, leakage
  audit, research report) is complete. Otherwise the vault stays pristine
  and V2 is classified V2_UNPROVEN.
- Single locked run: frozen spec + frozen hyperparameters, expanding
  walk-forward refit (refit on all completed games before the prediction
  week: 2018–2022 plus completed vault games — refit, not re-selection).
  Vault feature tables are built with the frozen pipeline at vault time;
  vault outcomes are not inspected before or during construction.
- Report V1 vs V2 side-by-side: MAE, RMSE, calibration, signed bias,
  season-by-season, error distributions, V1/V2 error correlation,
  where V2 improves/worsens, bootstrap CIs.
- Vault gates: V2 MAE < V1 MAE (paired bootstrap p < 0.05) AND
  better-or-tied in ≥2 of 3 seasons → passes vault. Significantly worse
  (p < 0.05) → **V2_REJECTED**. Otherwise → **V2_UNPROVEN**.
- No tuning, feature removal, threshold changes, retraining decisions,
  architecture changes, or cherry-picking based on vault results. If V2
  loses: do not modify and rerun.
- "Better than V1" means demonstrably better out-of-sample predictive
  performance under this protocol. It never means better ATS, higher ROI,
  or a proven market edge.

## 10. Amendments (pre-validation — no validation results examined)

**A1 (2026-09-29):** §5 described V2-A as "20 regressors + intercept" but the
enumerated feature list under the §3 model form yields 10 regressors
(5 offense differentials + 4 defense differentials + rest_diff) + intercept.
The enumerated list governs; "20" was a typographical error. V2-A is
implemented as 10 regressors + intercept, home-perspective, no doubling.

**A2 (2026-09-29):** Clarification, not a change: V2-B's 8 matchup
interaction features are game-level constructs. Their walk-forward
standardization is the direct analog of the team-level rule — μ/σ (ddof=0)
computed over training games strictly before week W (≥30 games required),
built from raw team features, then standardized. This is the
standardization_spec applied at game grain, not a new transform.

**A3 (2026-09-29):** The "week < W ≡ kickoff < Tuesday 08:00 ET"
equivalence is empirically false for 4 COVID-rescheduled 2020 games
(verified in games.csv). The protocol-literal kickoff rule governs
(training = kickoff < Tuesday 08:00 ET of week W, Sunday-anchored batch);
week-grain feature tables cannot reflect post-batch kickoffs for those
games — a frozen pipeline limitation, documented in manifest_v2a.json.
