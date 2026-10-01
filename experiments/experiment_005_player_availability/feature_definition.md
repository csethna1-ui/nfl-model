# Experiment 005 — Feature Definition (preregistered)

Source: nflverse `import_injuries()` via nfl_data_py 0.3.3, seasons 2018–2022, pulled 2026-09-29.
2021–2022 validation pool: 12,454 rows with `report_status` in {Out, Doubtful, Questionable},
non-QB positions, zero nulls in `date_modified`/`position`/`team`.

## Position groups (locked before evaluation)

| Group | Positions |
|---|---|
| OL | C, G, T |
| SKILL | RB, WR, TE, FB (FB: 73 rows in 2021–22, absent 2018–20; assigned to SKILL before any validation evaluation) |
| FRONT7 | DE, DT, LB |
| DB | CB, S |
| ST | K, P, LS |

QB excluded entirely.

## Designation encoding (locked before evaluation)

Separate count feature per designation — no assumed severity ordering:
- `Out`, `Doubtful`, `Questionable` each get their own count.
- Questionable is **included** as its own feature (preregistered treatment: include, not dropped, not fractional).
- Rows with null `report_status` (practice-only entries) excluded.

## Aggregation (locked before evaluation)

Per game, per team: count of qualifying players
(`report_status` in {Out, Doubtful, Questionable}, `date_modified < min(kickoff, Friday 12:00 ET)`)
in each (position group × designation) cell.

Features signed from the home perspective:
`X[group_designation] = away_team_count − home_team_count`
(positive = away team more injured → favors home margin).

30 features total (5 groups × 3 designations × 1 signed count each).

Missing data: team-game with no qualifying rows → all zeros. No imputation.

## Model (locked before evaluation)

`candidate_margin = v1_margin + ridge_pred`
- `ridge_pred` = Ridge(α=1.0, fit_intercept=True) predicting `(actual_margin − v1_margin)`
  from the 30 signed injury-count features. No feature scaling (counts already comparable).
- Two-fold season cross-fit (preregistration amendment 2026-09-29 — see config.json):
  fit on 2021 → predict 2022; fit on 2022 → predict 2021.
  (2018–2020 unusable: frozen-V1 margins do not exist pre-2021.)
