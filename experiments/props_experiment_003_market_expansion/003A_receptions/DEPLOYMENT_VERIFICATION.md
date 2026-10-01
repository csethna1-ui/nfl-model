# 003A Deployment Verification — PASS

Date: 2026-10-01. Verifier: `scripts/verify_deployment.py`.

Deployed artifact: `models/M2_verified_deployed.pkl`
(fit on train 2018–2020 with frozen hyperparams via the verbatim
`run_003A.py` fit functions — no selection, no feature changes).

Reference: `data/experiment_003A_test_predictions.parquet` (frozen,
single locked-test evaluation).

Method: predicted on the frozen locked-test feature slice (n=3,625)
with the deployed artifact using the verbatim `run_003A.py` predict
functions (`pred_A`, `pred_B`, `pred_C`; D = equal-weight mean of
A/B/C point projections). Identity keys matched exactly on all rows
in order before comparison.

| Output | Rows differing | Max abs diff |
|---|---|---|
| pred_D | 0 / 3,625 | 0.0 |
| pred_p25 | 0 / 3,625 | 0.0 |
| pred_p75 | 0 / 3,625 | 0.0 |

**Verdict: PASS.** The deployed head reproduces the frozen experiment
bit-for-bit. This record is the deployment verification artifact required
by Cale's 2026-10-01 authorization.
