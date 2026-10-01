#!/usr/bin/env python3
"""verify_deployment.py — bit-for-bit deployment verification for 003A M2.

Loads the DEPLOYED model artifact (models/M2_verified_deployed.pkl),
predicts on the FROZEN locked-test feature slice using the VERBATIM
predict functions from scripts/run_003A.py, and compares against the
frozen reference data/experiment_003A_test_predictions.parquet.

Requirement (Cale 2026-10-01): if even one prediction differs, STOP and
report — do not ship. Writes DEPLOYMENT_VERIFICATION.md on success.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                   "003A_receptions")
TABLE = os.path.join(EXP, "data/features_003A_2018_2024.parquet")
REF = os.path.join(EXP, "data/experiment_003A_test_predictions.parquet")
MODEL = os.path.join(EXP, "models/M2_verified_deployed.pkl")
OUT_MD = os.path.join(EXP, "DEPLOYMENT_VERIFICATION.md")


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    import pickle
    print("loading deployed model...", flush=True)
    with open(MODEL, "rb") as f:
        model = pickle.load(f)
    print("importing verified predict functions from run_003A.py...",
          flush=True)
    R3A = _load_mod("run_003A", os.path.join(EXP, "scripts/run_003A.py"))

    print("loading frozen test slice...", flush=True)
    t = pd.read_parquet(TABLE)
    ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1) &
           (t["trail_targets_ewma"] > 0) &
           (t["g_receptions"].notna())].copy()
    te = ev[ev["period"] == "test"].reset_index(drop=True)

    print("predicting with deployed artifact...", flush=True)
    pA = R3A.pred_A(model["A"], te)
    pB = R3A.pred_B(model["B"], te)
    p50 = R3A.pred_C(model["C"], te, 0.5)
    p25 = R3A.pred_C(model["C"], te, 0.25)
    p75 = R3A.pred_C(model["C"], te, 0.75)
    pD = (pA + pB + p50) / 3.0

    print("comparing to frozen reference...", flush=True)
    ref = pd.read_parquet(REF)
    ref_m2 = ref[ref["rung"] == "M2"].reset_index(drop=True)
    assert len(ref_m2) == len(te) == 3625, \
        f"row count mismatch: ref={len(ref_m2)} test={len(te)}"
    # Identity keys must match exactly and in order.
    keys = ["player_name", "team", "opponent", "season", "week"]
    for k in keys:
        assert (ref_m2[k].astype(str) == te[k].astype(str)).all(), \
            f"identity key mismatch: {k}"

    diffs = {}
    for name, pred, col in [("pred_D", pD, "pred_D"),
                            ("pred_p25", p25, "pred_p25"),
                            ("pred_p75", p75, "pred_p75")]:
        d = np.abs(pred - ref_m2[col].to_numpy(float))
        diffs[name] = {"n_differ": int((d > 0).sum()),
                       "max_abs_diff": float(d.max())}
        print(f"  {name}: {diffs[name]['n_differ']}/{len(te)} differ, "
              f"max abs diff = {diffs[name]['max_abs_diff']}", flush=True)

    n_bad = sum(v["n_differ"] for v in diffs.values())
    if n_bad:
        raise SystemExit(
            f"DEPLOYMENT VERIFICATION FAILED: {n_bad} predictions differ "
            f"from the frozen reference. STOP — do not ship.")

    md = f"""# 003A Deployment Verification — PASS

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
| pred_D | {diffs['pred_D']['n_differ']} / 3,625 | {diffs['pred_D']['max_abs_diff']} |
| pred_p25 | {diffs['pred_p25']['n_differ']} / 3,625 | {diffs['pred_p25']['max_abs_diff']} |
| pred_p75 | {diffs['pred_p75']['n_differ']} / 3,625 | {diffs['pred_p75']['max_abs_diff']} |

**Verdict: PASS.** The deployed head reproduces the frozen experiment
bit-for-bit. This record is the deployment verification artifact required
by Cale's 2026-10-01 authorization.
"""
    with open(OUT_MD, "w") as f:
        f.write(md)
    print(f"VERIFICATION PASS — wrote {OUT_MD}", flush=True)


if __name__ == "__main__":
    main()
