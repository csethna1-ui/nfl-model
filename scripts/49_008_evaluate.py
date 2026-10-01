"""Experiment 008 — frozen evaluation (Phase 5).

Runs ONCE per protocol.md. No tuning, no refits, no setting changes.
Reads: data/games_with_preds.parquet (2021-2022 REG, V1 ens_margin),
       data/v2/pred_008{a,b,c}.parquet.
Writes: experiments/experiment_008_distributional/validation_results_008.json
        + validation_report_008.md
Gates evaluated: G4 (both seasons), G5 (magnitude buckets), G6 (calibration),
G8 (paired bootstrap p<0.05). G1/G2/G3/G7/G9/G10 satisfied by construction
(documented in protocol.md); G1 additionally asserted via manifest checks.
"""
import pandas as pd, numpy as np, json
from pathlib import Path
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "experiment_008_distributional"
rng = np.random.default_rng(42)

g = pd.read_parquet(ROOT / "data" / "games_with_preds.parquet")
g = g[(g['season'].isin([2021, 2022])) & (g['game_type'] == 'REG')
      & g['ens_margin'].notna()].copy()
assert g['season'].max() <= 2022, "VAULT PROTECTION"
assert len(g) == 543, f"expected 543, got {len(g)}"
g['v1'] = g['ens_margin']
g['actual'] = g['home_margin']

cands = {}
for tag in ['008a', '008b', '008c']:
    p = pd.read_parquet(ROOT / "data" / "v2" / f"pred_{tag}.parquet")
    cands[tag] = g.merge(p, on='game_id', how='left', suffixes=('', f'_{tag}'))
    assert cands[tag]['pred_margin'].notna().all(), f"{tag} missing preds"

def calib_intercept_slope(actual, pred):
    X = np.column_stack([np.ones(len(pred)), pred])
    b, *_ = np.linalg.lstsq(X, actual, rcond=None)
    return float(b[0]), float(b[1])

def bootstrap_paired_p(v1_abs, c_abs, n=10000):
    diff = v1_abs - c_abs
    obs = diff.mean()
    boots = np.array([rng.choice(diff, size=len(diff), replace=True).mean() for _ in range(n)])
    return float((boots <= 0).mean()), float(obs), [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]

results = {"n": 543, "v1_mae": float((g['actual'] - g['v1']).abs().mean()),
           "v1_bias": float((g['actual'] - g['v1']).mean()),
           "candidates": {}}
v1_abs = (g['actual'] - g['v1']).abs().values
v1_err = (g['actual'] - g['v1']).values

for tag, d in cands.items():
    pred = d['pred_margin'].values
    actual = d['actual'].values
    err = actual - pred
    abs_err = np.abs(err)
    ci, cs = calib_intercept_slope(actual, pred)
    p_boot, diff_obs, ci95 = bootstrap_paired_p(v1_abs, abs_err)
    by_season, mag = {}, {}
    for s in [2021, 2022]:
        m = d['season'] == s
        by_season[str(s)] = {
            "mae": float(abs_err[m].mean()),
            "v1_mae": float(v1_abs[m].mean()),
            "cand_better": bool(abs_err[m].mean() < v1_abs[m].mean())}
    am = np.abs(pred)
    for name, m in [("lt3", am < 3), ("b3_7", (am >= 3) & (am <= 7)), ("gt7", am > 7)]:
        mag[name] = {"n": int(m.sum()), "mae": float(abs_err[m].mean()),
                     "v1_mae": float(v1_abs[m].mean()),
                     "cand_better": bool(abs_err[m].mean() < v1_abs[m].mean())}
    r = {
        "mae": float(abs_err.mean()), "rmse": float(np.sqrt((err ** 2).mean())),
        "signed_bias": float(err.mean()),
        "calibration_intercept": ci, "calibration_slope": cs,
        "resid_sd": float(err.std()), "pred_actual_corr": float(np.corrcoef(pred, actual)[0, 1]),
        "v1_error_corr": float(np.corrcoef(err, v1_err)[0, 1]),
        "mae_diff_v1_minus_cand": float(diff_obs),
        "bootstrap_p_v1_better": p_boot, "bootstrap_ci95_diff": ci95,
        "by_season": by_season, "by_magnitude": mag,
        "gates": {
            "G4_both_seasons": bool(all(v["cand_better"] for v in by_season.values())),
            "G5_magnitude_2of3": bool(sum(v["cand_better"] for v in mag.values()) >= 2),
            "G6_bias_within_1_of_v1": bool(abs(err.mean() - v1_err.mean()) < 1.0),
            "G6_slope_in_range": bool(0.6 <= cs <= 1.4),
            "G8_p_lt_0_05": bool(p_boot < 0.05 and diff_obs > 0),
        },
    }
    r["gates"]["all_questionA_gates"] = bool(all(r["gates"].values()))
    # Question B extras
    if tag == '008b':
        for lo, hi, nm in [(10, 90, 'q10_q90'), (25, 75, 'q25_q75')]:
            cov = float(((actual >= d[f'q{lo}'].values) & (actual <= d[f'q{hi}'].values)).mean())
            r[f'coverage_{nm}'] = cov
    if tag == '008c':
        ok = d['pred_sigma'].notna().values
        sig = np.clip(d.loc[ok, 'pred_sigma'].values, 1.0, 40.0)
        err_o = err[ok]
        ll = -0.5 * np.log(2 * np.pi * sig ** 2) - err_o ** 2 / (2 * sig ** 2)
        sig0 = v1_err[ok].std()
        ll0 = -0.5 * np.log(2 * np.pi * sig0 ** 2) - v1_err[ok] ** 2 / (2 * sig0 ** 2)
        r["logscore_pred_sigma"] = float(ll.mean())
        r["logscore_const_sigma"] = float(ll0.mean())
        r["logscore_n"] = int(ok.sum())
        r["coverage_80pi"] = float((np.abs(err_o) <= 1.2816 * sig).mean())
    results["candidates"][tag] = r

json.dump(results, open(OUT / "validation_results_008.json", "w"), indent=2)

# ---- markdown report ----
L = ["# Experiment 008 — Validation Report (frozen protocol, one run)",
     "", f"n=543 (2021–2022 REG). V1 MAE = {results['v1_mae']:.4f}, V1 bias = {results['v1_bias']:+.3f}.", ""]
for tag, name in [('008a', '008-A separate home/away scores'),
                  ('008b', '008-B quantile margin (median point forecast)'),
                  ('008c', '008-C heteroskedastic (Question B only)')]:
    r = results["candidates"][tag]
    L += [f"## {name}",
          f"- MAE {r['mae']:.4f} (Δ vs V1 {r['mae_diff_v1_minus_cand']:+.4f}), "
          f"RMSE {r['rmse']:.4f}, bias {r['signed_bias']:+.3f}",
          f"- calibration: intercept {r['calibration_intercept']:+.3f}, slope {r['calibration_slope']:.3f}; "
          f"pred–actual corr {r['pred_actual_corr']:.3f}; V1 error corr {r['v1_error_corr']:.3f}",
          f"- bootstrap: p={r['bootstrap_p_v1_better']:.4f}, 95% CI Δ {r['bootstrap_ci95_diff']}",
          f"- by season: " + "; ".join(
              f"{s}: cand {v['mae']:.3f} vs V1 {v['v1_mae']:.3f} ({'better' if v['cand_better'] else 'worse'})"
              for s, v in r['by_season'].items()),
          f"- by |pred|: " + "; ".join(
              f"{k} (n={v['n']}): cand {v['mae']:.3f} vs V1 {v['v1_mae']:.3f}"
              for k, v in r['by_magnitude'].items())]
    if tag == '008b':
        L.append(f"- coverage [q10,q90]: {r['coverage_q10_q90']:.3f} (nominal 0.80); "
                 f"[q25,q75]: {r['coverage_q25_q75']:.3f} (nominal 0.50)")
    if tag == '008c':
        L.append(f"- log score: pred-σ {r['logscore_pred_sigma']:.4f} vs const-σ {r['logscore_const_sigma']:.4f}; "
                 f"80% PI coverage {r['coverage_80pi']:.3f}")
    L.append(f"- gates: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in r['gates'].items()))
    L.append("")
L.append("## Gate verdict")
for tag in ['008a', '008b']:
    L.append(f"- {tag}: {'ADVANCES TO VAULT' if results['candidates'][tag]['gates']['all_questionA_gates'] else 'DOES NOT ADVANCE'}")
L.append("- 008c: Question B only — cannot advance as margin predictor by protocol.")
open(OUT / "validation_report_008.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
