"""008-B: distributional margin via linear quantile regression.

Preregistered (protocol.md frozen 2026-09-29):
- statsmodels QuantReg, tau in {0.10, 0.25, 0.50, 0.75, 0.90}.
- Features: pred_epa_m, elo_diff, off_epa_diff, def_epa_diff, ens_total,
  rest_diff (all available 2018-2022, all pregame). Standardized with
  expanding-window mean/sd (walk-forward safe).
- Expanding window from 2018 REG, refit weekly. Predict 2021-2022 REG.
- Point forecast = median (tau=0.50).
"""
import pandas as pd, numpy as np, json, warnings
from pathlib import Path
from statsmodels.regression.quantile_regression import QuantReg

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "experiment_008_distributional"
TAUS = [0.10, 0.25, 0.50, 0.75, 0.90]
# AMENDMENT 2026-09-29 (pre re-run; bug fix, not tuning): ens_total is entirely
# NaN for 2018-2020 (EPA-linear total model has no backfill there), which made
# the standardized design matrix all-NaN and diverged the first QuantReg fits.
# Dropped from the feature set; 5 features remain.
FEATS = ['pred_epa_m', 'elo_diff', 'off_epa_diff', 'def_epa_diff', 'rest_diff']

g = pd.read_parquet(ROOT / "data" / "games_with_preds.parquet")
g = g[(g['season'].between(2018, 2022)) & (g['game_type'] == 'REG')].copy()
g = g.sort_values(['season', 'week']).reset_index(drop=True)
assert g['season'].max() <= 2022, "VAULT PROTECTION: season > 2022 present"
g[FEATS] = g[FEATS].fillna(g[FEATS].median())
y_all = g['home_margin'].values

def fit_predict(Xtr, ytr, Xte, tau):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Xtrs = np.column_stack([np.ones(len(Xtr)), (Xtr - mu) / sd])
    Xtes = np.column_stack([np.ones(len(Xte)), (Xte - mu) / sd])
    res = QuantReg(ytr, Xtrs).fit(q=tau)
    return Xtes @ res.params

preds = []
weeks = sorted(g[['season', 'week']].drop_duplicates().values.tolist())
n_weeks = len([1 for s, w in weeks if s >= 2021])
done = 0
for s, w in weeks:
    te = (g['season'] == s) & (g['week'] == w)
    tr = ((g['season'] < s) | ((g['season'] == s) & (g['week'] < w)))
    if s >= 2021 and tr.sum() > 100:
        Xtr = g.loc[tr, FEATS].values; Xte = g.loc[te, FEATS].values
        ytr = y_all[tr.values]
        q = {t: fit_predict(Xtr, ytr, Xte, t) for t in TAUS}
        for i, gid in enumerate(g.loc[te, 'game_id']):
            row = {'game_id': gid, 'pred_margin': float(q[0.50][i])}
            for t in TAUS:
                row[f'q{int(t*100)}'] = float(q[t][i])
            preds.append(row)
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{n_weeks} weeks done", flush=True)

p = pd.DataFrame(preds)
p.to_parquet(ROOT / "data" / "v2" / "pred_008b.parquet", index=False)
json.dump({"n": len(p), "taus": TAUS, "features": FEATS,
           "model": "statsmodels QuantReg, weekly expanding refit from 2018 REG, walk-forward standardization"},
          open(OUT / "manifest_008b.json", "w"), indent=2)
print(f"008-B: wrote {len(p)} predictions")
