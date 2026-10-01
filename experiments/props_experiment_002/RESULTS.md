# Props Experiment 002 — RESULTS

**Date:** 2026-09-30
**Protocol:** `experiment_002_protocol.md` (frozen 2026-09-30, before any fitting)
**Verdict:** **NULL — preregistered bar NOT cleared. No production change.**

## Primary result

No ladder model clears the §9 win bar (≥5% pooled MAE reduction vs M0 in
≥2/3 markets; no market worse than −2%; ≥2% in 2023 AND 2024; 95% bootstrap
CI excludes zero). The largest test improvement by any challenger in any
market is **−0.7%** (M6/rush), an order of magnitude below the bar.

### Locked-test D MAE (2023–2024 pooled; relative vs M0)

| Rung | Added family | Pass (n=1010) | Rush (n=1528) | Receiving (n=3625) |
|---|---|---|---|---|
| M0 | — (frozen Model D) | 60.62 | 24.83 | 24.13 |
| M1 | B team context | 60.47 (−0.2%) | 24.83 (0%) | 24.15 (+0.1%) |
| M2 | C opp defense | 61.64 (+1.7%) | 24.70 (−0.5%) | 24.21 (+0.3%) |
| M3 | D1 game env (scoring) | 60.59 (−0.0%) | 24.68 (−0.6%)† | 24.11 (−0.1%) |
| M4 | E pace | 61.01 (+0.6%) | 24.75 (−0.3%) | 24.12 (−0.0%) |
| M5 | F opportunity | 60.81 (+0.3%) | 24.76 (−0.3%) | 24.15 (+0.1%) |
| M6 | position quality | 60.66 (+0.1%) | 24.66 (−0.7%)† | 24.12 (−0.0%) |
| M7 | full QB family | 60.67 (+0.1%) | 24.74 (−0.4%) | 24.12 (−0.0%) |
| M8 | L OL/pressure | 60.84 (+0.4%) | 24.84 (+0.0%) | 24.16 (+0.1%) |
| M9 | N injuries | 60.73 (+0.2%) | 24.76 (−0.3%) | 24.17 (+0.2%) |
| M10 | D2 schedule/fatigue | 60.91 (+0.5%) | 24.76 (−0.3%) | 24.20 (+0.3%) |
| M11 | dev-selected (B+E pass) | 61.42 (+1.3%)‡ | 24.83 (0%) | 24.13 (0%) |
| M12 | all-family | — (dev gate FAIL) | — | — |

† 95% paired bootstrap CI excludes zero, but effect is <1% (not material).
‡ 95% CI excludes zero on the *worsening* side: dev-selected combo overfit.

### Win-bar check (§9)

No rung has ≥5% pooled improvement in any market, let alone ≥2 markets.
`clears_bar=False` for all 11 evaluated challengers. **VERDICT = NULL.**

## Dev → test shrinkage

The dev phase (2021–2022) showed two families passing the §7 screen for the
pass market: B (team context, −2.0%) and E (pace, −1.0%). On the locked test:
- M1/pass: −2.0% (dev) → −0.2% (test)
- M11/pass (B+E): −2.6% (dev) → **+1.3% (test, significantly worse)**

This is the expected dev→test shrinkage the protocol was designed to guard
against. The dev selection did not generalize.

## M12

Dev gate FAILED: pass +1.8%, rush −1.0%, receiving −2.9% vs M0. Per §7, M12
was not evaluated on the locked test. The all-family regularized model
overfits; more features ≠ better projections.

## Answers to protocol questions A–P

- **A. Team ELO:** No. M1/pass −0.2% on test (ns).
- **B. Team offensive EPA:** No (same rung; no separation).
- **C. Opponent defensive EPA:** No. M2 worsens pass by +1.7%.
- **D. Spread/total:** Not tested (excluded; already in M0 baseline).
- **E. Pace:** No. M4/pass +0.6% worse on test despite −1.0% on dev.
- **F. Opportunity beyond Model D:** No (M5 all ±0.3%).
- **G. Air yards/ADOT/advanced receiving:** No (M6/rec −0.0%).
- **H. Pressure/OL:** No (M8 all ±0.4%).
- **I. QB context:** No (M7 all ±0.4%).
- **J. Injuries/personnel:** No (M9 all ±0.3%). Note: feed-available injury
  info at Friday cutoff; see protocol §5 timing caveat.
- **K. Coverage:** Not tested (excluded; FTN 2022+ only).
- **L. Weather:** Not tested (excluded; no forecast-at-cutoff).
- **M. NGS/expected-opportunity:** No clean test (Q family via M12 only;
  M12 gate failed). xq_xYpt nonzero rate 61% on train+dev.
- **N. Any combination:** No. M11 overfit dev; M12 failed gate.
- **O. Uncertainty calibration:** Coverage 41–47% (within [40%,60%] but
  below nominal 50%). **Width labels are inverted:** narrowest-width
  tercile has the *highest* MAE on dev and test, all markets
  (e.g., rush dev: 26.8 / 25.4 / 23.9 narrow→wide). Per §10, the
  High/Medium/Low labels are NOT meaningful as confidence labels.
  **Recommendation: use HIGH / MEDIUM / LOW UNCERTAINTY wording** instead
  of confidence language, and do not treat narrow intervals as reliable.
- **P. Change production:** No. Verdict NULL; no production change.

## Directional signals (not wins; hypotheses only)

Two rush-market effects are statistically significant (95% CI excludes zero)
but <1% — far below the 5% materiality bar. Reported narrowly per the
PARTIAL/SIGNAL taxonomy, without claiming wins:
- M3 (game-environment scoring context)/rush: −0.6%, CI [+0.05, +0.26]
- M6 (rusher quality: YBC/YAC/broken tackles)/rush: −0.7%, CI [+0.04, +0.29]

These are the only challengers with CIs excluding zero in the improving
direction. They may merit future investigation with more data, but they do
not clear the bar and do not warrant production changes.

## Discipline notes

- Protocol frozen 2026-09-30 before any fitting (`PROTOCOL_FROZEN` marker).
- Dev phase never loaded the test slice (load() filters to train/dev).
- Test phase: single evaluation; refit on train with dev-selected
  hyperparams; no test iteration.
- 25 injury name-collisions (same ukey|team|posg, different players) dropped
  per protocol; counted in missingness.
- Families O/P/Q (exp_*, rec2_*, xq_*) have no standalone ladder rung per the
  frozen §6 table; they enter via M12's all-family set (M12 gate failed).
- Production (`scripts/16_prod_player_projection.py`), V1, dashboard, and
  Experiment 001 artifacts untouched.

## Artifacts

- `data/extended_features_2018_2024.parquet` (34,275 × 98; 51 new features)
- `data/experiment_002_dev.json` (dev MAEs, M11 selection, M12 gate, calibration)
- `data/experiment_002_test.json` (test MAEs, bootstrap CIs, win-bar, calibration)
- `data/experiment_002_test_predictions.parquet` (per-player-game predictions)
- `data/dev_phase.log`, `data/test_phase.log`
- `REPRODUCIBILITY.md` (environment, pipeline, seeds, clarifications)
