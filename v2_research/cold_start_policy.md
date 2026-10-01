# V2 Cold-Start Policy — Weeks 1–4

Date: 2026-09-29. Documentation only; no fallback invented or chosen.

## Principle

Weeks 1–4 are **preserved**, not discarded. The cold start (few or zero prior
games) is a real prediction-time condition that any production model must
handle, so the research architecture must represent it explicitly rather than
pretend it does not exist. The current walk-forward assembler
(`scripts/35_v2_assemble.py`) emits NaN when a team has fewer than 4 prior
games; this policy documents the alternatives for what modeling-time code must
support. **Choosing among them belongs to a future modeling authorization.**

## Why the problem is real

- Walk-forward features use expanding means over games strictly before the
  prediction week. In Week 1 a team has 0 prior games; Week 2 has 1; Week 3
  has 2; Week 4 has 3.
- V1 handles this with an offseason regression + prior-season carryover. V2
  must have an explicit, documented equivalent — it may not silently inherit
  V1's approach without a decision.
- The 2026-anchored `qb_value_poll` quarantine (blocker 1) interacts here: a
  new QB with no prior dropbacks cannot get a historical value either.

## Alternatives (presented with trade-offs; none selected)

### Option A — prior_games bucketing with bucket-specific priors

Bucket: `prior_games ∈ {0, 1, 2, 3, 4+}`.

- For `4+`: full expanding-mean features (current behavior).
- For `0–3`: fall back to a defined prior that shrinks toward a league/team
  baseline as `prior_games → 0`. The prior must be estimated from information
  available at the prediction date (e.g. prior-season expanding means, decayed).
- Trade-off: honest and explicit, but requires defining the shrinkage rule and
  the prior source. Adds one architectural parameter (decay/shrinkage strength)
  that must be preregistered, not tuned on validation.

### Option B — defined preseason/offseason prior

- Carry a team's prior-season end-of-season rating forward, decayed toward
  league average by a documented offseason factor, as the Week 1 starting point.
- Subsequent weeks blend the prior with observed games (expanding mean seeded
  with the prior as pseudo-observations).
- Trade-off: mirrors V1's offseason handling; risk is importing V1's
  assumptions into V2, which partially defeats the architectural separation.
  The decay factor is a parameter that must be preregistered.

### Option C — V1 fallback for cold-start games

- For games where either team has < 4 prior games, the V2 candidate is not
  defined; evaluation and any future comparison uses V1's prediction for those
  games (documented as "V1 fallback", not silently).
- Trade-off: simplest and fully honest about what is being tested, but it
  reduces the effective V2 sample in early weeks and mixes architectures in
  any season-level comparison. Any future V2-A:E comparison must report
  cold-start games separately.

### Option D — exclude with documentation (NOT recommended)

- Drop weeks 1–4 from development/validation.
- Rejected as the default because it hides a real operating condition and
  shrinks the sample by ~25% of each season. Kept on the list only so the
  rejection is explicit.

## Requirements for modeling-time code

Whichever option is later authorized, the implementation must:

1. Expose `prior_games` (count of games strictly before the prediction week,
   per team) as a first-class column — already computable from the assembler.
2. Never fill NaN with a full-sample mean or any statistic that includes the
   prediction week's game or later games.
3. Log, per game, which cold-start branch was taken (prior / fallback / NaN),
   so any future comparison can be audited and cold-start games reported
   separately.
4. Keep the prior definition frozen within an experiment — the prior is part of
   the model specification, not a tuning knob.

## Interaction with other blockers

- **Blocker 1 (QB value):** new-to-team QBs and rookie QBs have the same cold
  start; the QB-value design must state its own minimum-dropback rule.
- **Blocker 5 (standardization):** scaling parameters in early weeks are
  estimated over very short histories; the spec must state the minimum history
  for scaling separately from the minimum history for the feature itself.
- **Blocker 2 (injuries):** no interaction; injury cutoff is per-experiment.

## Status

Documented. No fallback invented, none chosen. The current assembler behavior
(NaN under 4 prior games) remains the development default until a modeling
authorization selects an option.
