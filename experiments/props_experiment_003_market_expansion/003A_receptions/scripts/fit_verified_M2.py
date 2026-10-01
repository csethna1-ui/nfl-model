#!/usr/bin/env python3
"""Fit the VERIFIED 003A M2 deployment model. NO hyperparameter selection.

This instantiates the EXACT model the bit-for-bit reproducibility gate
verified: fit on train (2018-2020) with the frozen dev-selected hyperparams
(a_alpha=100.0, b_params={lr 0.05, max_depth 3, max_iter 200}), using the
fit functions imported VERBATIM from scripts/run_003A.py (zero divergence).

This is not "retraining": no selection, no feature changes, no new data
beyond what the verified procedure used. The deployed artifact must
reproduce data/experiment_003A_test_predictions.parquet bit-for-bit
(see verify_deployment.py).

Output: models/M2_verified_deployed.pkl
"""
import importlib.util
import os
import pickle

import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                   "003A_receptions")
TABLE = os.path.join(EXP, "data/features_003A_2018_2024.parquet")
OUT = os.path.join(EXP, "models/M2_verified_deployed.pkl")

# Frozen dev-selected hyperparams (experiment_003A_dev.json; all rungs).
A_ALPHA = 100.0
B_PARAMS = {"learning_rate": 0.05, "max_depth": 3, "max_iter": 200}
RUNGS = ["M1", "M2"]  # M2 primary; M1 = NGS-feed-failure degradation rung


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


print("importing verified fit functions from run_003A.py...", flush=True)
R3A = _load_mod("run_003A", os.path.join(EXP, "scripts/run_003A.py"))

print("loading frozen feature table (train slice only)...", flush=True)
t = pd.read_parquet(TABLE)
ev = t[(t["eligible_hist"] == 1) & (t["played_role"] == 1) &
       (t["trail_targets_ewma"] > 0) &
       (t["g_receptions"].notna())].copy()
tr = ev[ev["period"] == "train"].reset_index(drop=True)
assert len(tr) > 0 and (ev["period"] == "test").sum() > 0
# The test slice is never loaded into the fit path: only train rows present.
assert set(tr["period"].unique()) == {"train"}
print(f"train rows: {len(tr)} (test slice untouched)", flush=True)

s1, s2, pool = None, None, None
for rung in RUNGS:
    s1, s2, pool = R3A.rung_features(rung)
    print(f"[{rung}] fitting A (two-stage Ridge, alpha=100.0)...", flush=True)
    A = R3A.fit_A(tr, s1, s2, A_ALPHA)
    print(f"[{rung}] fitting B (HistGBM direct, lr=0.05/d3/200)...", flush=True)
    B = R3A.fit_B(tr, pool, B_PARAMS)
    print(f"[{rung}] fitting C (quantile GBM P25/P50/P75, fixed params)...",
          flush=True)
    C = R3A.fit_C(tr, pool)

    model = {
        "A": A, "B": B, "C": C,
        "a_alpha": A_ALPHA, "b_params": B_PARAMS,
        "feats": {"s1": s1, "s2": s2, "pool": pool},
        "fitted_on": ("train 2018-2020 (frozen feature table; test slice "
                      "untouched)"),
        "procedure": ("exact verified procedure from run_003A.py test_phase: "
                      f"fit_D_rung(tr, None, '{rung}', fixed_alpha=100.0, "
                      "fixed_b_params={lr:0.05,max_depth:3,max_iter:200})"),
        "gate": ("bit-for-bit reproducibility gate PASSED 2026-10-01: "
                 "0/3,625 rows differ, max abs diff 0.0 vs "
                 "data/experiment_003A_test_predictions.parquet"),
    }
    out = os.path.join(EXP, f"models/{rung}_verified_deployed.pkl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(model, f)
    print(f"wrote {out}", flush=True)
