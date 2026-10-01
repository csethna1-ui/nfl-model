# DEV DIAGNOSTICS — Props Experiment 006: Role-Change Mechanisms

**Scope: development period 2021–2022 ONLY. No 2023–2024 (locked test) data was
loaded, inspected, or summarized at any point in this phase (asserted in code;
the script aborts if test-period or 2023/2024 rows appear).**
**Status: dev complete 2026-10-01. Parameters locked in `LOCKED_PARAMETERS.md` / `.json`.**

## M0 verification

M0 = frozen Props Model D (Experiment 001), reproduced read-only by re-executing
the frozen 001 training procedure on train (2018–2020) with the frozen
dev-selected hyperparameters from `dry_run_dev.json` (same procedure as 005 dev).
Reproduction verified **bit-identical**: reproduced dev MAE matches the recorded
001 dev MAE to <1e-6 on all three targets (57.7740 / 25.1478 / 23.9767).
No 001 pipeline code or artifact was modified.

## Headline: M1 is a small, honest signal on pass only; M2 fails badly on dev

Per the frozen procedure, M1's alpha was selected on dev (in-sample) from the
4-value grid. The 5-fold CV honesty diagnostic (seed 1337; reported only, does
not affect selection) is row-shuffle for M1 and player-level for M2 (the filter
is per-player, so player-level folds are the correct honesty unit; each fold
refits (q_share, q_eff, r) from scratch on 4/5 of players).

| Target | M0 dev | M1 (locked α) in-sample | M1 5-fold CV | M2 (locked) in-sample | M2 player-5fold CV |
|---|---|---|---|---|---|
| pass_yards | 57.7740 | 56.7608 (−1.75%), α=100 | 57.1444 (−1.08%) | 75.7710 (**+31.1%**) | 77.0210 |
| rush_yards | 25.1478 | 25.0537 (−0.37%), α=0.1 | 25.2563 (+0.43%) | 31.0712 (**+23.6%**) | 30.9137 |
| receiving_yards | 23.9767 | 24.0158 (+0.16%), α=0.1 | 24.1212 (+0.60%) | 32.4238 (**+35.2%**) | 32.2922 |

Interpretation (narrow, as required):
- **M1/pass** is the only rung×target with a directionally consistent dev signal:
  CV confirms ~1.1% of the 1.75% in-sample gain survives out-of-fold. Small, and
  far below the 5% win bar — but unlike 005's GBM selections, the CV diagnostic
  does not contradict the in-sample result. Whether it generalizes is the locked
  test's question.
- **M1/rush and M1/receiving are null on dev**: in-sample ≈ M0, CV slightly worse.
- **M2 is decisively worse than M0 on dev, in-sample and under CV, on all three
  targets.** The CV diagnostic agrees with the in-sample result (no hidden
  optimism story — the spec itself underperforms). Per the frozen procedure the
  locked (q_share, q_eff, r) stand as fit; the locked test renders the honest
  verdict on the spec as written.

## Why M2 fails: a specification pathology, not a coding error

The fitted parameters diagnose the failure (locked values in
`LOCKED_PARAMETERS.md`):

- `q_share` fit to ≈ 0 (6e-6 … 2e-3): the share state is nearly frozen — the
  "roles change fast" half of the hypothesis is entirely unrealized.
- `q_eff` fit huge (7.5 … 20.1): the efficiency state whipsaws game to game.
- `r` fit small (0.03 … 0.30): observation variance pinned to the share scale.

Mechanism: the frozen spec uses a **single** observation-variance scalar `r` for
both states. The MLE pins `r` to the share scale (shares in [0,1], per-game
noise var ~0.005), giving R = r/n ≈ 0.001–0.008. For the efficiency state
(YPC/YPA/yards-per-target, per-game var ~4–9) that R is 100–1000× too small, so
the filter treats every per-game efficiency observation as nearly noiseless
(Kalman gain K≈1). The MLE then **inflates q_eff** to cover efficiency outliers —
under a tiny predictive variance a single outlier incurs a catastrophic
log-likelihood penalty, so the optimizer buys its way out with process noise.
Net effect: the efficiency prediction degenerates to chasing the last game's
noisy per-game efficiency, and the multiplicative projection
(team_vol × share × eff) amplifies that noise into yards errors 24–35% worse
than M0. The implementation was verified correct against the spec (update
equations, team-change share reset with efficiency carryover, <3-games prior,
dev-only likelihood, deterministic L-BFGS-B); the CV refits independently agree.
A null on the locked test would be informative about the 3-parameter
specification as written (prereg §6), not about Kalman approaches generally —
a per-state observation variance (4th parameter) is the obvious untested
variant, and it is **not** part of this experiment.

## Slice diagnostics (dev MAE; prereg slices)

High-contrast slice = top decile of the market's primary opportunity-contrast
magnitude: rush → |contrast_carries|, receiving → |contrast_tshare|,
pass → |contrast_snap| (see implementation note 6). All numbers in-sample on dev.

**pass_yards** (n=986; M0=57.7740)

| Slice | n | M0 | M1 | M2 |
|---|---|---|---|---|
| overall | 986 | 57.7740 | 56.7608 | 75.7710 |
| transfer_stint | 427 | 58.3249 | 56.3507 | 77.7461 |
| stint games 1–3 | 89 | 56.9310 | 52.5743 | 84.2139 |
| stint games 4–6 | 78 | 63.7908 | 60.9861 | 76.7193 |
| high_contrast | 99 | 58.2685 | 58.4360 | 79.7139 |
| non_transfer | 559 | 57.3532 | 57.0741 | 74.2623 |

**rush_yards** (n=1500; M0=25.1478)

| Slice | n | M0 | M1 | M2 |
|---|---|---|---|---|
| overall | 1500 | 25.1478 | 25.0537 | 31.0712 |
| transfer_stint | 558 | 22.4534 | 22.3728 | 28.0685 |
| stint games 1–3 | 136 | 21.9374 | 21.5716 | 27.4074 |
| stint games 4–6 | 82 | 20.0942 | 19.3175 | 26.9038 |
| high_contrast | 150 | 28.1460 | 27.8314 | 34.8647 |
| non_transfer | 942 | 26.7438 | 26.6417 | 32.8499 |

**receiving_yards** (n=3689; M0=23.9767)

| Slice | n | M0 | M1 | M2 |
|---|---|---|---|---|
| overall | 3689 | 23.9767 | 24.0158 | 32.4238 |
| transfer_stint | 1509 | 24.6253 | 24.6262 | 33.0554 |
| stint games 1–3 | 353 | 27.3600 | 27.3372 | 34.9487 |
| stint games 4–6 | 249 | 22.9027 | 22.9700 | 30.2336 |
| high_contrast | 369 | 25.1198 | 25.3927 | 36.5699 |
| non_transfer | 2180 | 23.5277 | 23.5933 | 31.9866 |

Notes: transfer-stint slices are thin on dev (pass stint 1–3: n=89 — underpowered
per the prereg rule, diagnostic only). M1's pass-yards gain concentrates
modestly in transfer_stint (−3.4%) and stint 1–3 (−7.7%) without an offsetting
non-transfer degradation (−0.5%) — the pattern the mechanism predicts, at a
magnitude far below the win bar. No slice-level claim is made at the dev stage.

## Artifacts

- `scripts/build_006_dev.py` — dev feature-construction + fitting code.
- `data/dev_predictions.parquet` — per-row M0/M1/M2 dev predictions (dev rows only).
- `data/dev_results.json` — machine-readable diagnostics.
- `models/M1_{market}_fitted.pkl` — locked Ridge + scaler + feature order.
- `models/M2_{market}_params.json` — locked (q_share, q_eff, r) + priors.
- `LOCKED_PARAMETERS.json` / `LOCKED_PARAMETERS.md` — frozen parameters.
- `dev_run.log` — full run log (final clean run: 77s).

## Implementation notes / deviations (reported, not silent)

1. **M0 reproduction** (see above): re-executed frozen 001 training code read-only;
   verified bit-identical. Not a refit or modification of Model D.
2. **Additive operationalization**: M1 is a stacking correction with the frozen M0
   prediction as an input feature alongside the contrast features (same
   operationalization as 005). M2 is a standalone projection
   (team_vol × share × eff); it does not consume M0. Both respect the
   additive-candidate rule (Model D internals untouched).
3. **Kalman likelihood population**: eligible dev rows only (2021–2022), per the
   prereg. Caught during dev: the first two runs accidentally included
   train-period rows in the eval mask (the filter state is correctly walked over
   the full history; only the likelihood/prediction mask was wrong). Fixed;
   the final run is dev-only. The locked parameters come from the fixed run.
4. **MAE-consistency fix**: the first fixed run computed the headline M2 dev MAE
   on unique player-weeks while slices used all evaluated rows (namesake
   duplicates share predictions m:1, the documented 005 deviation #4 convention).
   Fixed so headline, slice, and parquet MAEs agree exactly (verified to 1e-9).
   The likelihood fit itself uses unique player-weeks (avoids double-counting
   the same game); evaluation uses the full evaluated set, as for M0/M1.
5. **Duplicate-column crash**: the predictions write listed stint_games/
   transfer_ind twice (once explicitly, once via M1_ORDER[1:]); crashed the
   first full run at the final write step after all fits completed. Fixed;
   deterministic re-run.
6. **High-contrast slice mapping**: the prereg names "|carries/target-share
   contrast|". Implemented per-market primary opportunity contrast:
   rush→|contrast_carries|, receiving→|contrast_tshare|,
   pass→|contrast_snap| (QBs have no meaningful target-share contrast; snap
   share is the QB role-change analog).
7. **M2 likelihood target**: one-step-ahead predictive log-likelihood of the
   observed share AND efficiency (the filter's native quantities, DARKO-style),
   summed over eligible dev rows with n>0 — the implemented reading of the
   prereg's "predictive log-likelihood".
8. **seen<3 wart**: in a player's first 3 walk games the predictive distribution
   is the positional prior AND the posterior update is discarded on the next
   step (state restarts from the prior). Affects only career-start games in
   2018; negligible for 2021–2022 predictions. Documented, not altered —
   the frozen spec mandates the prior for <3 trailing games.
9. **M2 projections clipped at 0** (same convention as 005's rung predictions).
10. **No 2023–2024 data** was loaded, inspected, or summarized at any point.
    The locked test has not been run.
