"""Experiment 008, Phase 2 — variance predictability diagnostic.

Question: can pregame information predict game-level margin error scale?
Method: walk-forward expanding window WITHIN 2021-2022 (V1 ens_margin only
exists for 2021-2022). For each week, fit OLS of |resid| (and log(resid^2))
on pregame features using only prior weeks, predict the current week.
Diagnostic only — not used for model selection.
"""
import pandas as pd, numpy as np, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "experiment_008_distributional"

g = pd.read_parquet(ROOT / "data" / "games_with_preds.parquet")
g = g[(g['season'].isin([2021, 2022])) & (g['game_type'] == 'REG')
      & g['ens_margin'].notna()].copy()
g['resid'] = g['home_margin'] - g['ens_margin']
g['abs_resid'] = g['resid'].abs()
g = g.sort_values(['season', 'week']).reset_index(drop=True)

# Merge a few V2 structure features (walk-forward-safe by construction)
v2 = pd.read_parquet(ROOT / "data" / "v2" / "games_v2_features.parquet")
pace_cols = [c for c in v2.columns if 'plays_per_drive' in c or 'drive' in c and 'rate' not in c]
exp_cols = [c for c in v2.columns if 'explosive' in c.lower() or 'epa_per_drive' in c]
keep = ['game_id'] + [c for c in v2.columns if 'plays_per_drive' in c][:2] \
    + [c for c in v2.columns if 'explosive' in c.lower()][:4]
v2s = v2[keep].copy()
g = g.merge(v2s, on='game_id', how='left')

FEATS = ['ens_margin_abs', 'ens_total', 'elo_diff_abs', 'off_epa_diff_abs',
         'def_epa_diff_abs', 'rest_diff', 'div_game'] + [c for c in keep if c != 'game_id']
g['ens_margin_abs'] = g['ens_margin'].abs()
g['elo_diff_abs'] = g['elo_diff'].abs()
g['off_epa_diff_abs'] = g['off_epa_diff'].abs()
g['def_epa_diff_abs'] = g['def_epa_diff'].abs()
FEATS = [f for f in FEATS if f in g.columns]
g[FEATS] = g[FEATS].fillna(g[FEATS].median())

def ols_fit_predict(Xtr, ytr, Xte):
    Xtr1 = np.column_stack([np.ones(len(Xtr)), Xtr])
    Xte1 = np.column_stack([np.ones(len(Xte)), Xte])
    beta, *_ = np.linalg.lstsq(Xtr1, ytr, rcond=None)
    return Xte1 @ beta

pred_abs, pred_logvar = [], []
weeks = sorted(g[['season', 'week']].drop_duplicates().values.tolist())
for s, w in weeks:
    te = (g['season'] == s) & (g['week'] == w)
    tr = ((g['season'] < s) | ((g['season'] == s) & (g['week'] < w)))
    if tr.sum() < 40:
        pred_abs.extend([np.nan] * te.sum()); pred_logvar.extend([np.nan] * te.sum())
        continue
    Xtr = g.loc[tr, FEATS].values; Xte = g.loc[te, FEATS].values
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Xtrs, Xtes = (Xtr - mu) / sd, (Xte - mu) / sd
    pa = ols_fit_predict(Xtrs, g.loc[tr, 'abs_resid'].values, Xtes)
    plv = ols_fit_predict(Xtrs, np.log(g.loc[tr, 'resid'].values ** 2 + 1e-6), Xtes)
    pred_abs.extend(pa); pred_logvar.extend(plv)

g['pred_abs_resid'] = pred_abs
g['pred_logvar'] = pred_logvar
ev = g[g['pred_abs_resid'].notna()].copy()
print(f"evaluable weeks: {ev.shape[0]} / {len(g)}")

corr = ev['pred_abs_resid'].corr(ev['abs_resid'])
print(f"corr(predicted |resid|, actual |resid|): {corr:.4f}")

# Quintile table
ev['q'] = pd.qcut(ev['pred_abs_resid'], 5, labels=False, duplicates='drop')
qt = ev.groupby('q')['abs_resid'].agg(['mean', 'count'])
print(qt.to_string())

# Log-score comparison: constant sigma vs predicted sigma
resid = ev['resid'].values
sig_const = resid.std()
ll_const = -0.5 * np.log(2 * np.pi * sig_const ** 2) - resid ** 2 / (2 * sig_const ** 2)
sig_pred = np.sqrt(np.exp(ev['pred_logvar'].values))
sig_pred = np.clip(sig_pred, 1.0, 40.0)
ll_pred = -0.5 * np.log(2 * np.pi * sig_pred ** 2) - resid ** 2 / (2 * sig_pred ** 2)
print(f"mean log-score const: {ll_const.mean():.4f}  predicted-sigma: {ll_pred.mean():.4f}  diff: {(ll_pred-ll_const).mean():.4f}")

# In-sample (descriptive) R^2 of |resid| on features, full 2021-2022 — context only
X = ev[FEATS].values; X1 = np.column_stack([np.ones(len(X)), (X - X.mean(0)) / (X.std(0) + 1e-9)])
beta, *_ = np.linalg.lstsq(X1, ev['abs_resid'].values, rcond=None)
r2 = 1 - ((ev['abs_resid'].values - X1 @ beta) ** 2).sum() / ((ev['abs_resid'] - ev['abs_resid'].mean()) ** 2).sum()
print(f"in-sample R^2(|resid| ~ features): {r2:.4f}")

res = {
    "n_games": int(len(g)), "n_evaluable": int(len(ev)),
    "walkforward_corr_pred_vs_actual_abs_resid": float(corr),
    "quintile_mean_abs_resid": {str(k): float(v) for k, v in qt['mean'].items()},
    "quintile_counts": {str(k): int(v) for k, v in qt['count'].items()},
    "logscore_const_sigma": float(ll_const.mean()),
    "logscore_pred_sigma": float(ll_pred.mean()),
    "logscore_diff_pred_minus_const": float((ll_pred - ll_const).mean()),
    "insample_r2_abs_resid": float(r2),
    "features": FEATS,
    "method": "expanding walk-forward within 2021-2022 REG; OLS of |resid| and log(resid^2) on pregame features",
    "verdict": ("WEAK" if abs(corr) < 0.15 else "MODERATE"),
}
json.dump(res, open(OUT / "variance_diagnostic.json", "w"), indent=2)
md = f"""# Experiment 008 — Phase 2 variance diagnostic

**Question:** can pregame information predict game-level margin error scale?

**Method:** expanding walk-forward within 2021–2022 REG (n={len(g)} games;
V1 `ens_margin` exists only for 2021–2022, so no 2018–2020 training was possible
for V1 residuals). Each week, OLS of `|resid|` and `log(resid²)` on pregame
features using only prior weeks; predict the current week. Diagnostic only.

**Features:** {', '.join(FEATS)}

## Results
- Walk-forward corr(predicted |resid|, actual |resid|): **{corr:.3f}**
- In-sample R²(|resid| ~ features): {r2:.3f}
- Gaussian log-score, constant σ: {ll_const.mean():.4f}; predicted σ: {ll_pred.mean():.4f} (Δ {(ll_pred-ll_const).mean():+.4f})

### Quintiles of predicted |resid| → actual mean |resid|
{qt['mean'].to_string()}

## Verdict: {res['verdict']}
Pregame information carries {"essentially no" if abs(corr) < 0.15 else "only modest"} predictable signal about
game-level error scale. Per the directive: reduce emphasis on complex variance
models; 008-C is retained as a Question-B (uncertainty calibration) test only,
not as a path to better margin prediction. Heteroskedasticity alone cannot
change the optimal point forecast.
"""
open(OUT / "variance_diagnostic.md", "w").write(md)
print("wrote variance_diagnostic.json/md")
