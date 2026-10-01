# V2 Leakage Audit — Final (Phase 1 Gate)

Date: 2026-09-29. Consolidates and supersedes the architecture-build
`leakage_audit.md` where they differ. Frozen for the research protocol.

## Verdict by family

| Family | Verdict | Notes |
|---|---|---|
| possession | SAFE | Strictly games with week < W; drive points from in-game score deltas only. |
| explosiveness | SAFE | Same walk-forward discipline; distribution-shape features are deterministic transforms of prior games. |
| pressure_pbp | SAFE | PBP-derived proxies, week grain, usable through W−1. |
| pressure_pfr | SAFE WITH LAG | All 17 features lagged one week (usable through W−2). Stored table must be shifted before use — consuming it raw is the 006-class information-time leak. |
| special_teams | SAFE | PBP-local ST EPA, week grain. |
| player_continuity | SAFE | Prior-week snap counts publish before Tuesday. |
| player_qb | SAFE (with quarantine) | `qb_value_historical` built only from prior games; identity is pregame-known; `qb_pressured_pct_rw` Friday-safe only; `qb_value_poll` QUARANTINED (never enters). |
| player_availability | SAFE UNDER POLICY | Row-level `date_modified < min(cutoff, kickoff)`; Tuesday set is identically zero (documented, not a bug); 2025/26 rows unusable. **Known gap:** `scripts/33` claims the filter but never applies it — rebuild must implement it. |
| matchup | SAFE (sign-disciplined) | Interactions built from walk-forward team features; `_awayoff` variants must be sign-flipped to the prediction perspective (the overlap-matrix build caught an unflipped version producing a spurious 0.00). |
| environment | SAFE (partial) | Schedule/rest/stadium pregame-safe; weather 36.8% missing, no frozen imputation. |

## Residual risks (accepted and documented)

1. **Schedule-data entry errors** (`herbery_j`, `murray_t`) — handled
   deterministically in script 37; the general class (schedule typos)
   cannot be fully eliminated, only logged.
2. **Name-key collisions** for QB identity — only same-person suffix
   variants observed; documented.
3. **PFR publication timing** rests on PFR's stated schedule, not per-row
   timestamps — the one-week lag is the conservative bound; Experiment 006's
   live stream may refine it independently.
4. **Intra-week injury history loss** — one last-update timestamp per row
   destroys interim states; unfixable with current data; the cutoff rule is
   the honest bound.
5. **Weather missingness** (36.8%) — no frozen imputation; weather features
   are excluded from the preregistered V2-A:E candidates.

## What changed vs the architecture-build audit

- PFR: from "consume in the Tuesday batch" to **lag one week** (blocker 3
  found PFR's Wednesday-morning publication statement).
- Availability: from "week grain with pre-kickoff discipline" to the
  **row-level cutoff rule** + the Tuesday-set-is-zero finding (blocker 2).
- `scripts/33`'s unapplied filter: newly flagged as a code-vs-docstring gap.
- Matchup: sign-discipline requirement added (caught empirically).
- `qb_value_poll`: formally quarantined.

## Pre-modeling checklist (must hold before V2-A:E)

- [x] No 2023–2025 data touched; no 2026 observations used; V1 untouched.
- [x] All derived tables asserted 2018–2022 only.
- [x] Timestamp policy frozen (`timestamp_policy.md`).
- [x] Standardization spec frozen (`standardization_spec.md`).
- [x] Cold-start policy frozen (Option C in the research protocol).
- [x] Overlap matrix computed (diagnostic).
- [ ] Modeling-stage rebuild implements: PFR one-week shift, injury
      row-level cutoff, QB-value table merge — verified by code audit before
      any validation evaluation.
