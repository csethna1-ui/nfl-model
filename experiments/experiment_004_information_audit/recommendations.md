# Experiment 004 — Recommendations

## For the audit verdict

**A. INFORMATION-SET IS ADEQUATELY ALIGNED — proceed to one preregistered predictive candidate**, with the following standing qualifications:

1. The historical market comparison is a **coarse benchmark, not a timestamped baseline**. Keep using it for architecture screening, but do not over-interpret small MAE deltas against a line of unknown vintage. The ≥0.15 MAE gate remains appropriate as a noise guard.
2. The **live 2026 stream is the cleaner evaluation substrate**: Friday-AM researched lines (known information state) + model predictions from the same morning + CLV vs the nflverse close proxy. As 2026 weeks accumulate, this stream should carry increasing weight in promotion decisions — it is the only timestamp-aligned comparison in the project.
3. Restamp `line_provenance` from `'nflverse_proxy_open'` to `'nflverse_unverified_single_snapshot'` in future dataset builds. The current stamp encodes an assumption contradicted by external evidence.

## The single recommended candidate

**Experiment 005: non-QB player-availability model.**

- Hypothesis: V1's ratings price team efficiency but not *who is actually playing*; the market's ~4–5 day information advantage (Wed–Fri injury news) is the structural source of the MAE gap.
- Data: nflverse `load_injuries()`, verified working, timestamped, pregame-reconstructable.
- Design sketch (to be preregistered in full): prediction time Friday 12:00 ET; availability features from `report_status` with `date_modified < T`; non-QB positions; preregistered treatment of Questionable; preregistered non-overlap with the QB void filter; baselines market-only / frozen V1 / availability-augmented V1; same gate structure as 002/003 (≥0.15 vs market, both seasons, calibrated, diversified).
- Explicitly NOT: another ELO/EPA/recency/GBM/ensemble variant; no division or late-season corrections; no edge shrinkage; no ATS tuning.

## What must NOT happen

- Do not build the availability feature inside this experiment's mandate — Experiment 005 is a separate preregistered run.
- Do not "fix" the historical line statistically.
- Do not rerun experiments 001–003 against a re-labeled line and treat the results as new evidence.
