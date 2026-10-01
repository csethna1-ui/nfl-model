# Prospective 2026 Protocol — Information Cutoff and Evaluation Rules

**Status: FROZEN 2026-10-01 (Cale).** Applies to all prospective 2026 evaluation
from Week 4 onward. Weeks 1–3 are monitoring-only and retain their documented
conventions; they are NOT re-cut under this protocol.

## 1. The cutoff

**Friday 18:00 CT** is the information freeze for each week's predictions.

- Everything used by a model to produce that week's projection must have been
  available at or before Friday 18:00 CT.
- Anything arriving after the cutoff is unavailable to that week's prediction,
  no exceptions. It enters the observation stream (Experiment 006 timing study)
  instead.
- The cutoff is a fixed calendar time. It does not move for holidays, late
  data releases, or manual research delays.

## 2. Week definition (pins the audit's Friday-convention inconsistency)

- The prediction week covers all games scheduled for the NFL week (Thursday
  through Monday).
- **Thursday games are excluded from the prospective prediction set.** By the
  Friday 18:00 CT cutoff their outcomes are known, so they cannot be
  predicted prospectively. They are graded as finals and enter trailing
  history for the following week only (the 001 predictable-game convention).
- This resolves the W1–W3 convention split: future audits use the fixed
  calendar Friday 18:00 CT cutoff, never a schedule-derived date.

## 3. Deterministic treatment of late/arriving data

| Information type | Rule |
|---|---|
| NGS updates after cutoff | Unavailable. Use the prior-week release. Set `stale_ngs_used=true` and record the release that was used. |
| NGS full pull failure | Degrade to the frozen M1 rung (process-only model). Never silently to M0. Record `fallback_to_M1=true`. |
| NGS partial/missing for a player | Missing → 0 for the NGS features, recorded per row. Never impute from outcomes. |
| Injury updates after cutoff | Unavailable to the prediction. The injury/QB availability freeze is the same Friday 18:00 CT (`availability_friday_2026_w<N>.json`, per INJURY_PIPELINE_RUNBOOK.md). Post-cutoff news is observation-stream only. |
| QB changes after cutoff | Same rule: the expected-QB layer is frozen at the cutoff. A Saturday QB scratch does not change that week's projection; it is graded as-is and the miss is recorded honestly. |
| Market lines | Captured hourly (timestamped, append-only). The **evaluation snapshot** for model-vs-line comparison is the latest snapshot at or before Friday 18:00 CT. Later snapshots feed CLV/line-movement tracking only and never change the projection. |
| Missing/stale data feeds (general) | Deterministic degradation only: use the last available pre-cutoff value, flag it as stale, and record what was missing. Never forward-fill from post-cutoff data. Never fail silently — a missing feed the pipeline depends on fails the run loudly. |
| Late manual research | Anything not in the frozen Friday file by the cutoff does not exist for that week's prediction. |

## 4. Eligibility / DNP rule (preregistered 2026-10-01)

A player projection is evaluated against actual performance **only when the
player was eligible to participate under the defined pregame availability
rule**. The rule:

- **Eligible:** the player was on the active roster/gameday-eligible per the
  Friday 18:00 CT availability freeze (or, once available, the official
  gameday inactive list) and recorded at least one snap or touch opportunity
  stat (target, carry, or pass attempt, as appropriate to the market).
- **DNP (did not participate):** any projected player who was inactive,
  did not dress, or recorded zero opportunities. DNPs are **classified
  separately** — they are not scored as zero-yard/zero-reception outcomes
  in MAE/RMSE/bias aggregates.
- **Late scratch (eligible Friday, out Sunday):** classified as DNP under
  this rule (the projection stands; the outcome is not the model's error).
  Recorded in the DNP bucket with the reason where known.
- This rule was documented **before** applying it to future evaluation, per
  Cale's 2026-10-01 decision. It is not retroactively tuned to flatter
  results. Weeks 1–3 retain their original all-rows scoring for
  comparability, reported alongside the new eligible-only cut.

## 5. Standing model rules

- **Model D yards heads:** unchanged. No retraining, no refit, no threshold
  changes from 2026 outcomes.
- **003A/003B:** frozen artifacts stay deployed as experimental. No retraining
  or refitting from 2026 outcomes. The prospective stream is the evaluation;
  it does not modify the models.
- **Weeks 1–3 status:** Locked historical test: PASS → Live prospective
  validation: IN PROGRESS → Weeks 1–3: below locked-test performance →
  insufficient sample to overturn the preregistered result.

## 6. Required reporting for each future audit

Report separately, never pooled into a single MAE:
1. Eligible participants (n)
2. DNPs (n, with reasons where known)
3. Missing/stale NGS rows (n)
4. Full-NGS rows (n)
5. Fallback rows (n, by rung)
6. Model D yards MAE (pass / rush / receiving)
7. 003A receptions MAE
8. 003B rush-attempts MAE
9. Performance by week
10. Performance by workload/volume bucket
11. NGS availability breakdown (full / partial / fallback-or-zero)

## 7. Language

- 003A/003B showed a material locked-test improvement; live persistence has
  not yet been established.
- NGS-availability results are encouraging and directionally consistent with
  locked testing, but remain observational, not causal.
- Dashboard: experimental / being monitored. Not "proven," not prematurely
  labeled failures.

## 8. Change control

This protocol is frozen. Changes require Cale's explicit approval and are
recorded here with a date. Changes never apply retroactively to already-
graded weeks.
