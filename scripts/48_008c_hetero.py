"""008-C: heteroskedastic margin model — Question B ONLY.

Preregistered (protocol.md frozen 2026-09-29):
- Mean = frozen V1 ens_margin (not refit).
- log(sigma^2) = linear in [ens_total, |ens_margin|, pace_sum, explos_sum],
  OLS on log(resid^2), walk-forward within 2021-2022 (min 40 games).
- Evaluated on log score vs constant-sigma and 80% PI coverage.
- NEVER a margin-prediction candidate; cannot advance to vault.
"""
import pandas as pd, numpy as np, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "experiment_008_distributional"

g = pd.read_parquet(ROOT / "data" / "games_with_preds.parquet")
g = g[(g['season'].isin([2021, 2022])) & (g['game_type'] == 'REG')
      & g['ens_margin'].notna()].copy()
g = g.sort_values(['season', 'week']).reset_index(drop=True)
assert g['season'].max() <= 2022, "VAULT PROTECTION: season > 2022 present"
g['resid'] = g['home_margin'] - g['ens_margin']

v2 = pd.read_parquet(ROOT / "data" / "v2" / "games_v2_features.parquet")
pace = [c for c in v2.columns if 'plays_per_drive' in c][:2]
expl = [c for c in v2.columns if 'explosive' in c.lower()][:4]
v2s = v2[['game_id'] + pace + expl].copy()
g = g.merge(v2s, on='game_id', how='left')
g['pace_sum'] = g[pace].sum(axis=1)
g['explos_sum'] = g[expl].sum(axis=1)
g[['pace_sum', 'explos_sum']] = g[['pace_sum', 'explos_sum']].fillna(
    g[['pace_sum', 'explos_sum']].median())
g['ens_margin_abs'] = g['ens_margin'].abs()
FEATS = ['ens_total', 'ens_margin_abs', 'pace_sum', 'explos_sum']

def ols(Xtr, ytr, Xte):
    Xtr1 = np.column_stack([np.ones(len(Xtr)), Xtr])
    Xte1 = np.column_stack([np.ones(len(Xte)), Xte])
    beta, *_ = np.linalg.lstsq(Xtr1, ytr, rcond=None)
    return Xte1 @ beta

preds = []
weeks = sorted(g[['season', 'week']].drop_duplicates().values.tolist())
for s, w in weeks:
    te = (g['season'] == s) & (g['week'] == w)
    tr = ((g['season'] < s) | ((g['season'] == s) & (g['week'] < w)))
    if tr.sum() < 40:
        for gid in g.loc[te, 'game_id']:
            preds.append({'game_id': gid, 'pred_margin': float(g.loc[g.game_id == gid, 'ens_margin'].iloc[0]),
                          'pred_sigma': np.nan})
        continue
    Xtr = g.loc[tr, FEATS].values; Xte = g.loc[te, FEATS].values
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    plv = ols((Xtr - mu) / sd, np.log(g.loc[tr, 'resid'].values ** 2 + 1e-6), (Xte - mu) / sd)
    sig = np.sqrt(np.exp(plv))
    for gid, m, sg in zip(g.loc[te, 'game_id'], g.loc[te, 'ens_margin'], sig):
        preds.append({'game_id': gid, 'pred_margin': float(m), 'pred_sigma': float(sg)})

p = pd.DataFrame(preds)
p.to_parquet(ROOT / "data" / "v2" / "pred_008c.parquet", index=False)
json.dump({"n": len(p), "features": FEATS,
           "model": "mean=frozen V1 ens_margin; log(sigma^2) OLS on log(resid^2), walk-forward within 2021-2022",
           "question": "B only"},
          open(OUT / "manifest_008c.json", "w"), indent=2)
print(f"008-C: wrote {len(p)} predictions")
