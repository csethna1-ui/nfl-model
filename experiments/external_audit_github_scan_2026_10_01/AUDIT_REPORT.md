# Broad GitHub scan — AUDIT REPORT (2026-10-01)

> **RESEARCH-ONLY. No Vault touch, no production changes, no model code touched.**
> This audit records a broad GitHub scan commissioned after the targeted
> multi-repo audit (`../external_audit_multirepo/`). Read the reliability
> section first: the delegated researcher's specific claims FAILED live
> verification, so nothing in its report may be presented as verified.

## What was commissioned
A broad survey of every category of NFL prediction model on GitHub with real
results (spread/margin, win probability, totals, player props, QB modeling,
team-strength decomposition, O/D persistence, role features, draft transfer),
judged against the frozen market-free V1 baseline (ELO + EPA + GBM, locked
2023–25 MAE 10.1867, n=816). Researcher report retained at
`~/workspace/research_notes/github-nfl-prediction-models-audit-20261001-2003/report.md`
— UNVERIFIED, do not cite its numbers.

## Researcher reliability check (live GitHub API verification, 2026-10-01)
The researcher claimed, as its headline answer, that the three named leads
"do not exist on GitHub." All three exist — verified live:

| Claim | Live result |
|---|---|
| Damepivot/nfl-game-model does not exist | EXISTS (created 2026-08-27; "Predicts win probability, final margin and total points for NFL games from opponent-adjusted EPA, quarterback form and situational factors") |
| crollila/nfl-adaptive-forecasting does not exist | EXISTS (created 2026-09-14; "Walk-forward forecasting research on 17,110 NFL player-games: feature-family ablation, bootstrap-validated model promotion, and two hypotheses tested and rejected") |
| JMutammara/NFL does not exist | EXISTS (created 2026-09-15; default branch `claude/nfl-prediction-pipeline-9yor6n`) |
| akushwarrior/rice (BRADY continuous QB rating, the researcher's #1 "importable candidate") | 404 — DOES NOT EXIST. Card is fabricated. |
| ryanpmcintire/nfl_py3 (offseason retention 0.337/0.379/0.400) | Repo EXISTS (2018, 16 stars, pushed 2026-10-01) — doc contents NOT verified |
| sbuermeyer1/nfl-games | EXISTS (2026-07-25) — results NOT verified |
| chmoses98/nfl-edge-finder | EXISTS (2026-09-04) — results NOT verified |

Note: the three named-lead repos are all 0-star accounts created within ~5
weeks of the scan (Aug 27, Sep 14, Sep 15 2026). JMutammara/NFL's default
branch is named `claude/nfl-prediction-pipeline-9yor6n`. Treat all three as
unvetted novelty accounts; their numbers were already audited on substance
in `../external_audit_multirepo/`.

## Verdict
**No additional verified importable candidates beyond the multi-repo audit.**
The multi-repo audit (Cale's 10-repo scan, completed 2026-10-01) remains the
authoritative result: exactly ONE genuinely-new item —
**D1 asymmetric offense/defense offseason persistence** (off ≈0.48 / def ≈0.31
carryover slopes), DRAFT saved at
`../external_audit_multirepo/DRAFT_asymmetric_offense_defense_persistence.md`,
standing DEFER under the research freeze. Parked, not recommended: special-teams
EPA rating, kickoff-hour circadian covariate.

The broad scan's shortlist (continuous-QB additive expert, shrunk ST EPA,
offseason retention re-tune, usage-over-efficiency features) is NOT verified:
its #1 card is fabricated and its headline claim was wrong. Any of these may
be re-investigated by direct live repo reads in a future audit — they are
leads, not findings.

## Consensus observation (directional only, unverified numbers)
Across the repos whose cards look structurally honest, nothing market-free
claims to beat the closing line; our V1's locked MAE sits in the middle of
the honest public pack. Directionally consistent with Experiment 009's
verdict. Not a substitute for verified numbers.

## Do-not-test (from this scan)
- akushwarrior/rice — repo does not exist; any "BRADY" numbers attributed to it are fabricated.
- Any repo card from the broad-scan report — unverified; re-verify by live read before use.
