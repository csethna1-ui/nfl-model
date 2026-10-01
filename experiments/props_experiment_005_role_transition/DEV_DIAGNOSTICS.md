# DEV DIAGNOSTICS — Props Experiment 005: Player Role Transition Model

**Scope: development period 2021–2022 ONLY. No 2023–2024 (locked test) data was loaded, inspected, or summarized at any point in this phase.**
**Status: dev complete 2026-10-01. Parameters locked in `LOCKED_PARAMETERS.md` / `LOCKED_PARAMETERS.json`.**

## M0 verification

M0 = frozen Props Model D (Experiment 001: equal-weight mean of A/B/C). No saved
fitted 001 artifacts exist on disk, so M0 dev predictions were obtained by
re-executing the frozen 001 training procedure on train (2018–2020) with the
frozen dev-selected hyperparameters from `dry_run_dev.json`
(alpha=10.0, GBM lr=0.05/depth=3/iter=200 for all three markets). Reproduction
verified **bit-identical**: reproduced dev MAE matches the recorded 001 dev MAE
to <1e-6 on all three targets (57.7740 / 25.1478 / 23.9767). No 001 pipeline
code or artifact was modified.

## Headline finding: dev "gains" are in-sample overfitting

Per the frozen procedure, candidates were fit on dev AND selected on dev
(in-sample). Every one of the 9 rung×market selections picked the
maximum-capacity GBM in the grid (learning_rate=0.1, max_depth=5,
max_iter=500). In-sample dev MAE shows 21–54% "improvements" over M0 — but the
reported 5-fold CV MAE (honesty diagnostic, seed 1337; does not affect
selection) is **worse than M0 for all 9 combos**:

| Target | Rung | M0 dev | In-sample dev MAE | 5-fold CV MAE | CV vs M0 |
|---|---|---|---|---|---|
| pass_yards | M1 | 57.77 | 35.79 (−38%) | 63.56 | **+10.0% worse** |
| pass_yards | M2 | 57.77 | 35.49 (−39%) | 63.98 | **+10.7% worse** |
| pass_yards | M3 | 57.77 | 26.33 (−54%) | 63.84 | **+10.5% worse** |
| rush_yards | M1 | 25.15 | 17.48 (−30%) | 27.90 | **+11.0% worse** |
| rush_yards | M2 | 25.15 | 17.16 (−32%) | 28.03 | **+11.5% worse** |
| rush_yards | M3 | 25.15 | 13.51 (−46%) | 27.87 | **+10.8% worse** |
| receiving_yards | M1 | 23.98 | 18.90 (−21%) | 25.84 | **+7.8% worse** |
| receiving_yards | M2 | 23.98 | 18.89 (−21%) | 25.83 | **+7.7% worse** |
| receiving_yards | M3 | 23.98 | 16.49 (−31%) | 25.69 | **+7.1% worse** |

Interpretation (narrow, as required):
- The in-sample dev MAEs are **not evidence of signal**. They are selection
  optimism from fit-on-dev/select-on-dev with a high-capacity model class.
- CV being uniformly worse than M0 is, however, evidence of **no leakage**:
  a leaking feature would survive cross-validation. The features are clean;
  the model class simply memorized dev noise.
- The locked parameters are therefore "fit noise aggressively" configs. They
  are locked as-is per the frozen procedure ("the ladder does not change
  after dev results are seen"). The locked test is the honest evaluation; a
  null there is a legitimate, preregistered outcome.

## Slice diagnostics (in-sample dev MAE; same prereg slices)

n = eligible dev rows. Transfer slices are thin on dev (pass: 72).

**pass_yards** (n=986; M0=57.77)

| Slice | n | M0 | M1 | M2 | M3 |
|---|---|---|---|---|---|
| overall | 986 | 57.77 | 35.79 | 35.49 | 26.33 |
| transfer_stint | 72 | 53.47 | 29.41 | 33.63 | 24.21 |
| stint games 1–3 | 25 | 64.03 | 36.88 | 38.42 | 29.86 |
| stint games 4–6 | 21 | 52.45 | 26.38 | 28.93 | 20.63 |
| non_transfer | 914 | 58.11 | 36.29 | 35.64 | 26.50 |

**rush_yards** (n=1500; M0=25.15)

| Slice | n | M0 | M1 | M2 | M3 |
|---|---|---|---|---|---|
| overall | 1500 | 25.15 | 17.48 | 17.16 | 13.51 |
| transfer_stint | 184 | 24.50 | 17.31 | 16.04 | 12.57 |
| stint games 1–3 | 76 | 20.93 | 15.05 | 13.62 | 11.63 |
| stint games 4–6 | 37 | 22.51 | 17.45 | 15.63 | 10.93 |
| non_transfer | 1316 | 25.24 | 17.51 | 17.31 | 13.64 |

**receiving_yards** (n=3689; M0=23.98)

| Slice | n | M0 | M1 | M2 | M3 |
|---|---|---|---|---|---|
| overall | 3689 | 23.98 | 18.90 | 18.89 | 16.49 |
| transfer_stint | 586 | 28.10 | 20.77 | 20.91 | 17.80 |
| stint games 1–3 | 193 | 28.96 | 22.28 | 21.94 | 18.34 |
| stint games 4–6 | 139 | 25.24 | 17.34 | 17.65 | 16.91 |
| non_transfer | 3103 | 23.20 | 18.55 | 18.51 | 16.24 |

All slice "improvements" carry the same in-sample-optimism caveat as the
overall numbers. No slice-level claim is made at the dev stage.

## Artifacts

- `scripts/build_005_dev.py` — dev feature-construction + fitting code.
- `data/dev_predictions.parquet` — per-row M0/M1/M2/M3 dev predictions (dev rows only).
- `models/M{1,2,3}_{pass_yards,rush_yards,receiving_yards}_fitted.pkl` — locked fitted models.
- `LOCKED_PARAMETERS.json` / `LOCKED_PARAMETERS.md` — frozen parameters.
- `dev_run.log` — full run log.

## Implementation notes / deviations (reported, not silent)

1. **M0 reproduction** (see above): re-executed frozen 001 training code
   read-only; verified bit-identical. Not a refit or modification of Model D.
2. **Additive operationalization**: M1–M3 are stacking corrections with the
   frozen M0 prediction as an input feature alongside the role/opportunity
   features. The prereg's additive-candidate rule forbids altering Model D's
   internals; this keeps the causal question ("does role treatment add
   information beyond the frozen projection?") clean.
3. **M3's opportunity×efficiency**: implemented as separately-identified
   opportunity and efficiency blend components plus their explicit product
   (`opp_blend × eff_blend`) as model inputs, rather than a literal
   two-stage multiply. The product term is the prereg's multiplicative
   hypothesis in feature form.
4. **Name collisions**: nflverse abbreviated `player_name` collides across
   real players (~1% of rows; e.g. three different "D.Harris" in 2020 w4).
   The stint-history walk uses the max-`actual_att` row per player-week;
   the evaluated dev set keeps every 001 row (namesakes share the chain's
   features via an m:1 join). M0 comparability is exact.
5. **CV honesty diagnostic** added as a reported diagnostic only; selection
   followed the frozen in-sample procedure unchanged.
6. First background run died to an infrastructure kill mid-way (no output
   corruption; partial models discarded); the full run was re-executed
   cleanly end-to-end (EXIT:0, 684s).
