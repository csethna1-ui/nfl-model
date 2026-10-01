# Experiment 004 — Leakage Assessment

Applies to any future experiment using the recommended information source (nflverse injury designations). No model was fitted in this experiment.

## The safe construction

For a defined prediction time T (recommendation: **Friday 12:00 ET**, mirroring the live pipeline's Friday-morning research):

1. Pull `load_injuries()` for the relevant seasons.
2. Keep only rows with `date_modified < T` for the game being predicted.
3. Use `report_status` (Out / Doubtful / Questionable / null) as the availability feature.
4. Join players to teams via weekly rosters; weight by position/snaps only with pregame-known quantities.

Verified 2026-09-29 on 2021 data: median `date_modified` is 28.3h before kickoff; 99.86% of rows are strictly pre-kickoff. The final injury report is legitimate pregame truth — using it is not leakage.

## Leakage risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Using final `report_status` for a game when the prediction time is *before* the final report (e.g., Friday AM prediction vs Saturday injury update) | Medium | Hard filter: `date_modified < T`. The feature is "what the Friday report said," not "what the final report said" |
| Mid-week `practice_status` oscillations (DNP → LP → FP) used as features | Medium | Exclude unless each practice entry is timestamped before T; simplest preregistered choice: final-status-only |
| Game-day inactive list (90 min before kickoff) | Low | It IS pregame truth, but it postdates the Friday prediction time — exclude for the Friday-T design, or preregister a separate game-day model |
| Retroactive corrections to historical injury files | Low | `date_modified` reflects report modification; verify no post-kickoff bulk rewrites (0.14% of rows at/after kickoff in 2021 — negligible, drop them) |
| Double-counting QB | Medium | The 2026 production void filter and any historical QB feature must be preregistered as non-overlapping; v2 showed QB info adds noise, so default to non-QB focus |
| `Questionable` noise | Medium | Largest bucket (3,024/11,269 in 21–22). Preregister treatment (e.g., fractional availability or exclude) BEFORE validation |

## What is NOT leakage (common misconception)

- Using the final Out/Doubtful designation for a game is not leakage **as long as the designation timestamp precedes the prediction time**. "Pregame" is defined by the clock, not by how early the information arrived.
- The market at close also knew these designations — so this experiment tests whether *V1's ratings* fail to price absences, not whether the information was secret.
