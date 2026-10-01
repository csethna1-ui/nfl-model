# Experiment 004 — Market Provenance Audit

## What `spread_line` is, precisely

- Source: nflverse schedules release, ingested into `data/games.csv` (46 columns), then `data/schedules_2018_2025.parquet`.
- One scalar per game. Zero nulls across 2018–2025 (2,330 reg+playoff games; experiment dataset uses 2,227 after backtest filters).
- No timestamp column, no source-book column, no line-history columns exist anywhere in the repo's data.

## Internal consistency check (this repo)

| Location | Claim |
|---|---|
| `backtest_report.md:65` | "provenance is likely consensus/opening" |
| `scripts/08_grade_week.py:68` | "nflverse spread_line is a close proxy" |
| `scripts/15_export_ui_json.py:78` | "CLV is measured vs the nflverse close proxy" |
| `scripts/16_build_experiment_dataset.py:78,139` | stamps `line_provenance='nflverse_proxy_open'`, "NOT a verified executable line" |

The repo describes the same field three different ways. The experiment-001/002/003 reports inherited the "opening proxy" framing.

## External evidence (third-party, not nflverse documentation)

1. Independent measurement (nfl_py3 repo docs): nflverse `spread_line` vs captured Tuesday opener — mean abs gap 0.998, exact match 24.7%; vs captured close — mean abs gap 0.196, exact match 68.1%. Conclusion stated: "It behaves as a closing line."
2. Independent design doc (espechtsoftware): nflverse `load_schedules()` "Includes closing spread, total, moneyline — free Vegas history."

Neither is nflverse itself. nflverse publishes no timing documentation for the field.

## Audit conclusion

- **Provenance: UNVERIFIED.** Cannot be established from any available source.
- Best-supported hypothesis: close/consensus-ish snapshot — but "best-supported" is not "verified."
- Consequence: every historical "market MAE" number in this project (9.727 validation, 9.79 test) is measured against a line of **unknown vintage**. It is valid as a coarse benchmark (same line for V1 and market within each comparison) but **not** as a timestamped tradable baseline.
- The `line_provenance='nflverse_proxy_open'` stamp in the experiment dataset encodes the repo's *assumption*, not a verified fact. Recommendation: restamp as `'nflverse_unverified_single_snapshot'` in future dataset builds to stop the assumption from hardening into treated-as-fact.
- Do not attempt to "correct" the historical line statistically (e.g., modeled line-movement adjustments). The limitation is documented, not fixable from inside the dataset.
