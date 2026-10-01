# Experiment 006 — Prospective 2026 Information-Timing Study: Initial Report

**Date:** 2026-09-29. **Status:** infrastructure live, collection in progress.
**Nature:** observational only. No model fitted, nothing optimized, no V2
promotion possible from this experiment alone. Vault untouched (not applicable).

## Why this exists

Experiments 001–005 closed null. The audit (004) reframed the problem: V1's
effective information state is ~Tuesday AM, while the historical market
benchmark is an undated snapshot — the market–V1 gap may be substantially a
4–5 day information-timing difference rather than a modeling deficiency. The
historical data cannot resolve this. This study measures it prospectively on
the timestamped 2026 live stream.

## What was built (2026-09-29)

| Artifact | Path |
|---|---|
| Tuesday snapshot script | `scripts/22_tuesday_snapshot.py` |
| Friday snapshot script | `scripts/23_friday_snapshot.py` |
| Postgame grading script | `scripts/24_timing_grade.py` |
| Methodology + weekly procedure | `experiments/experiment_006_information_timing/methodology.md` |

All three scripts smoke-tested: 23 verified against the Week 4 Friday pipeline
(model spreads match to 0.0, market/edge match, 16 games); 22 ran end-to-end
for Week 4 (subprocess 07, file restore guard, ratings recompute); 24 tested
end-to-end on synthetic Week 3 snapshots (test artifacts removed afterward).

**Safety properties verified:**
- 22 refuses to run if the Friday predictions CSV exists (unless `--force`,
  which backs up and restores it) — the Tuesday model-only run can never
  clobber Friday outputs.
- Tuesday market lines are never backfilled; absence is recorded as missing.
- Late (non-Tuesday) runs are kept but flagged `timing_flag=LATE`.
- Thursday games are flagged `already_played` and excluded from movement analysis.

## Collection status

- **Week 4:** Tuesday model snapshot captured live 2026-09-29 (timing OK, no
  Tuesday market lines — not researched). Friday snapshot consolidated from
  pipeline outputs generated 2026-09-25. First inverted-order observation:
  mean |model "move"| (Sep-25 → Sep-29) = 0.99 pts, driven by Week 3's late
  games entering ratings — already demonstrating the mechanism under study.
- **Week 5** (Tue 2026-10-06): first fully scheduled week.
- Weeks 1–3: not reconstructed (cold start, documented).

## The four concepts, kept separate

- **A. Prediction accuracy** — Tue/Fri model error vs actual margin (graded.csv).
- **B. Information timing** — what changed in the model's information set
  Tue→Fri (ratings refresh, injury news, weather) and how much predictions moved.
- **C. Market movement** — Tue→Fri line movement, observed only.
- **D. Tradable-signal evidence** — eventual CLV on graded picks, kept separate;
  this study does not manufacture betting signals.

## Guardrails

- No fitting, no coefficient optimization, no threshold/ATS tuning.
- No winners declared on small samples (descriptive until n≈200+).
- Historical 2021–22 validation results stay separate from this stream.
- Nothing here can promote to V2.

## Next

Weekly collection per `methodology.md`. Analysis when the sample supports it.
If Tue→Fri market movement proves substantial while V1 barely moves, we will
have identified a concrete, timestamped missing dimension — without touching
the vault or fooling ourselves with another validation-set improvement.
