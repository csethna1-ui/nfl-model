#!/usr/bin/env python3
"""Step 51: Phase 2 fit + dev selection (PREREGISTRATION.md, frozen 2026-09-30).

- Fits candidates A-D on TRAIN 2018-2020 (predictions exist from 2019; seed 42):
    A: Ridge(alpha=1.0, fit_intercept=True) on 18 position-group x designation counts
    B: Ridge(alpha=1.0, fit_intercept=True) on 6 snap-share-weighted features
    C: OLS on 2 starter-missing-snap-fraction features
    D: OLS on 2 aggregate burden features
  Target: V1 residual r = home_margin - v1_margin. No hand-assigned values.
- Evaluates A-E on DEV 2021-2022. E = equal-weight average of frozen A-D adjustments.
  E-variant: dev-learned nonneg weights, reported separately, never replaces E.
- Dev selection: which candidates clear the preregistered bar (§7) on dev.
- Coefficient-stability diagnostic: fit A/B on 2019 vs 2020, report sign flips.
- Writes frozen bundle: injury_candidates_frozen.pkl + JSON manifest + SHA256SUMS.

HARD: asserts season <= 2022. Never reads 2023+. Writes only to EXP/data.
"""
import hashlib
import json
import os
import pickle
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge

warnings.filterwarnings("ignore")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = REPO_ROOT
DATA = f"{REPO}/data"
EXP = f"{REPO}/experiments/injury_adjustment_experiment"
OUTDIR = f"{EXP}/data"
SEED = 42
MAX_SEASON = 2022
ALPHA = 1.0  # preregistered

FEATA = [f"{g}_{d}" for g in ("QB", "OL", "SKILL", "FRONT7", "DB", "ST")
         for d in ("Out", "Doubtful", "Questionable")]
FEATB = [f"snap_{u}_{d}" for u in ("off", "def") for d in ("Out", "Doubtful", "Questionable")]
FEATC = ["miss_starter_off", "miss_starter_def"]
FEATD = ["burden_off", "burden_def"]

def mae(a, p):
    return float(np.abs(np.asarray(a) - np.asarray(p)).mean())

def boot_ci_diff(actual, p_base, p_cand, n_boot=10000, seed=SEED):
    rng = np.random.RandomState(seed)
    a = np.asarray(actual); b = np.asarray(p_base); c = np.asarray(p_cand)
    db = np.abs(a - b) - np.abs(a - c)  # positive = candidate better
    idx = rng.randint(0, len(a), size=(n_boot, len(a)))
    means = db[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))

def main():
    f = pd.read_parquet(f"{OUTDIR}/features_2018_2022.parquet")
    assert int(f["season"].max()) <= MAX_SEASON, "VAULT LEAK"
    for col in FEATA + FEATB + FEATC + FEATD:
        assert col in f.columns, f"missing feature {col}"
    tr = f[f["season"] <= 2020].copy()
    dv = f[f["season"].isin([2021, 2022])].copy()
    print(f"train n={len(tr)} (seasons {sorted(tr.season.unique())}), "
          f"dev n={len(dv)} (seasons {sorted(dv.season.unique())})", flush=True)
    ytr = (tr["home_margin"] - tr["v1_margin"]).values

    models = {}
    adj_tr = {}
    # A/B: Ridge(alpha=1.0); C/D: OLS — all pre-declared
    for name, cols, cls, kw in [
            ("A", FEATA, Ridge, {"alpha": ALPHA, "fit_intercept": True}),
            ("B", FEATB, Ridge, {"alpha": ALPHA, "fit_intercept": True}),
            ("C", FEATC, LinearRegression, {}),
            ("D", FEATD, LinearRegression, {})]:
        m = cls(**kw)
        m.fit(tr[cols].values, ytr)
        models[name] = {"model": m, "cols": cols,
                        "cls": cls.__name__, "kwargs": kw}
        adj_tr[name] = m.predict(tr[cols].values)
        print(f"fit {name}: {cls.__name__}{kw} on {len(cols)} features", flush=True)

    # dev adjustments from frozen train-fit models
    adj_dv = {name: models[name]["model"].predict(dv[models[name]["cols"]].values)
              for name in "ABCD"}
    adj_dv["E"] = np.mean([adj_dv[n] for n in "ABCD"], axis=0)

    # E-variant: constrained least squares (w >= 0) on DEV residuals — reported separately
    from scipy.optimize import lsq_linear
    r_dv = (dv["home_margin"] - dv["v1_margin"]).values
    X = np.column_stack([adj_dv[n] for n in "ABCD"])
    lsq = lsq_linear(X, r_dv, bounds=(0, np.inf))
    w_evar = lsq.x
    adj_dv["E_variant"] = X @ w_evar
    print(f"E-variant dev weights (A,B,C,D): {np.round(w_evar, 4)} "
          f"(fit on dev: IN-SAMPLE, reported separately)")

    v1_dv = dv["v1_margin"].values
    actual = dv["home_margin"].values
    results = {}
    for name in ["A", "B", "C", "D", "E", "E_variant"]:
        cand = v1_dv + adj_dv[name]
        lo, hi = boot_ci_diff(actual, v1_dv, cand)
        seas = {}
        for se in (2021, 2022):
            m = dv["season"] == se
            seas[str(se)] = {"n": int(m.sum()),
                             "v1_mae": round(mae(actual[m], v1_dv[m]), 4),
                             "cand_mae": round(mae(actual[m], cand[m]), 4)}
        results[name] = {
            "n": int(len(dv)),
            "v1_mae": round(mae(actual, v1_dv), 4),
            "cand_mae": round(mae(actual, cand), 4),
            "delta_mae": round(mae(actual, cand) - mae(actual, v1_dv), 4),
            "boot_ci_95": [round(lo, 4), round(hi, 4)],
            "seasons": seas,
        }

    # dev bar (§7 adapted): all must hold
    print("\n=== DEV BAR EVALUATION (§7, on 2021-2022) ===")
    bar = {}
    for name in ["A", "B", "C", "D", "E"]:
        r = results[name]
        inj = injury_subset(dv, v1_dv, adj_dv[name])
        checks = {
            "pooled_delta_le_-0.15": r["delta_mae"] <= -0.15,
            "ci_excludes_zero": r["boot_ci_95"][0] > 0,
            "no_season_regress_0.05": all(
                s["cand_mae"] - s["v1_mae"] <= 0.05 for s in r["seasons"].values()),
            "injury_subset_le_-0.10": inj["delta"] <= -0.10,
            "noninjury_subset_ge_-0.05": inj["nondelta"] >= -0.05,
        }
        checks["ALL"] = all(checks.values())
        bar[name] = {"checks": {k: bool(v) for k, v in checks.items()}, **inj}
        flag = "CLEARS" if checks["ALL"] else "does not clear"
        print(f"  {name}: {flag} | delta={r['delta_mae']:+.4f} "
              f"ci=[{r['boot_ci_95'][0]:+.4f},{r['boot_ci_95'][1]:+.4f}] "
              f"inj_sub={inj['delta']:+.4f} (n={inj['n_inj']}) "
              f"noninj={inj['nondelta']:+.4f} (n={inj['n_noninj']})")

    # coefficient-stability diagnostic: fit A/B on 2019 vs 2020, sign flips
    print("\n=== COEFFICIENT STABILITY (2019 vs 2020 fits) ===")
    stab = {}
    for name, cols, cls, kw in [("A", FEATA, Ridge, {"alpha": ALPHA, "fit_intercept": True}),
                                ("B", FEATB, Ridge, {"alpha": ALPHA, "fit_intercept": True})]:
        coefs = {}
        for se in (2019, 2020):
            s = tr[tr["season"] == se]
            m = cls(**kw).fit(s[cols].values, (s["home_margin"] - s["v1_margin"]).values)
            coefs[str(se)] = m.coef_
        flips = [c for c, a, b in zip(cols, coefs["2019"], coefs["2020"])
                 if np.sign(a) != np.sign(b) and abs(a) > 1e-9 and abs(b) > 1e-9]
        stab[name] = {"n_flips": len(flips), "flipped": flips}
        print(f"  {name}: {len(flips)}/{len(cols)} sign flips {flips if flips else ''}")

    # secondary diagnostics: RMSE, calibration slope, concentration, ATS (diagnostic-only)
    print("\n=== SECONDARY DIAGNOSTICS (no bar) ===")
    diag = {}
    sched = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    sched = sched[sched["season"] <= MAX_SEASON][["game_id", "spread_line"]]
    dd = dv.merge(sched, on="game_id", how="left")
    for name in ["A", "B", "C", "D", "E"]:
        cand = v1_dv + adj_dv[name]
        e_c = actual - cand
        slope = float(np.polyfit(cand, actual, 1)[0])
        # concentration: share of total |improvement| from top 5% game-level improvements
        imp = np.abs(actual - v1_dv) - np.abs(actual - cand)
        top5 = np.sort(imp)[-max(1, int(0.05 * len(imp))):]
        conc = float(top5[ top5 > 0].sum() / imp[imp > 0].sum()) if (imp > 0).any() else 0.0
        # ATS diagnostic-only: pick side by sign(cand - line) at |edge|>=3
        line = dd["spread_line"].values
        edge = cand - line
        pk = edge >= 3.0
        ats = None
        if pk.sum() >= 20:
            win = ((actual - line) > 0) == (edge > 0)
            ats = {"n": int(pk.sum()), "win_rate": round(float(win[pk].mean()), 3)}
        diag[name] = {"rmse": round(float(np.sqrt((e_c ** 2).mean())), 4),
                      "calib_slope": round(slope, 3),
                      "concentration_top5": round(conc, 3),
                      "ats_edge3": ats}
        print(f"  {name}: rmse={diag[name]['rmse']} slope={slope:.3f} "
              f"conc={conc:.3f} ats={ats}")

    # frozen bundle
    bundle = {name: {"coef": models[name]["model"].coef_.tolist(),
                     "intercept": float(models[name]["model"].intercept_),
                     "cols": models[name]["cols"],
                     "cls": models[name]["cls"],
                     "kwargs": models[name]["kwargs"]}
              for name in "ABCD"}
    with open(f"{OUTDIR}/injury_candidates_frozen.pkl", "wb") as fh:
        pickle.dump(bundle, fh)
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "protocol": "PREREGISTRATION.md frozen 2026-09-30",
        "seed": SEED,
        "train": "2018-2020 (predictions from 2019)", "dev": "2021-2022",
        "target": "r = home_margin - v1_margin",
        "candidates": {
            "A": "Ridge(alpha=1.0, fit_intercept=True), 18 position-group x designation counts",
            "B": "Ridge(alpha=1.0, fit_intercept=True), 6 snap-share-weighted features",
            "C": "OLS, 2 starter-missing-snap-fraction features",
            "D": "OLS, 2 aggregate burden features (Out+Doubtful; Questionable excluded)",
            "E": "equal-weight average of frozen A-D adjustments (primary)",
            "E_variant": f"dev-learned nonneg weights {np.round(w_evar,4).tolist()} "
                         "(reported separately, never replaces E)",
        },
        "dev_results": results,
        "dev_bar": bar,
        "coef_stability": stab,
        "secondary_diagnostics": diag,
        "note": "Locked test NOT run. Awaiting Cale's re-confirmation.",
    }
    with open(f"{OUTDIR}/fit_manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    # leakage re-assertions (fit-time)
    assert int(f["season"].max()) <= MAX_SEASON
    import re as _re
    _src51 = open(__file__).read()
    _frag = "qb_point" + "_values"  # avoid self-match
    _loads = [ln.strip() for ln in _src51.splitlines()
              if _frag in ln and _re.search(r"\b(open|read_parquet|read_json|read_csv)\s*\(", ln)]
    assert not _loads, f"qb_point_values loaded: {_loads}"
    print("PASS: fit-time leakage re-assertions (season<=2022, no qb_point_values loads)")

    for p in [f"{OUTDIR}/injury_candidates_frozen.pkl", f"{OUTDIR}/fit_manifest.json",
              f"{OUTDIR}/features_2018_2022.parquet", f"{OUTDIR}/build_audit.json"]:
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        print(f"  {h[:16]}... {os.path.basename(p)}")
    with open(f"{OUTDIR}/SHA256SUMS.txt", "a") as fh:
        for p in [f"{OUTDIR}/injury_candidates_frozen.pkl", f"{OUTDIR}/fit_manifest.json"]:
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            fh.write(f"{h}  {os.path.basename(p)}\n")
    print("\nFIT COMPLETE. Frozen bundle written. Locked test NOT run.")

def injury_subset(dv, v1_dv, adj):
    """Games with >=1 timing-verified OUT/DOUBTFUL on either team, from the
    unsigned diagnostic column (signed features can cancel across teams)."""
    has = (dv["n_od_unsigned"] > 0).values
    actual = dv["home_margin"].values
    cand = v1_dv + adj
    d_all = np.abs(actual - cand) - np.abs(actual - v1_dv)
    return {
        "n_inj": int(has.sum()), "n_noninj": int((~has).sum()),
        "delta": round(float(d_all[has].mean()), 4) if has.sum() else None,
        "nondelta": round(float(d_all[~has].mean()), 4) if (~has).sum() else None,
    }

if __name__ == "__main__":
    main()
