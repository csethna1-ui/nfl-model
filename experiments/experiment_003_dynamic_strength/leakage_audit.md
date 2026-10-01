# Experiment 003 — leakage audit

- rows: 2227; seasons 2018-2025
- weekly batching: week W predictions use only pre-week-W ratings (verified in run_ratings: predictions computed before updates within each (season, week) group)
- offseason regression r=1/3 applied at every season boundary 2019-2025 before week 1
- frozen params (L, Hf, K) derived from 2018-2020 only; K selected on 2019-2020
- no market spread, closing line, future result, postgame, or injury inputs used
- no validation-derived (2021-2022) quantities used anywhere in ratings or params
- vault seasons >= 2023: never used for fitting, selection, or evaluation in this script
