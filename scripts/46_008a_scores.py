"""008-A: separate home/away score model -> margin = E[home] - E[away].

Preregistered (protocol.md frozen 2026-09-29; bug-fix 2026-09-29: single
chronological pass — ratings for week w come from state BEFORE week w games;
training history records (features-as-of-that-week, outcomes) pairs).

- Team scoring ratings per team-week from STRICTLY prior games:
  points scored (offense) / allowed (defense), exp-weighted half-life 8 games,
  split home/away. <1 prior game -> league average. No opponent adjustment.
- OLS: home_score ~ home_off_home + away_def_away (+const);
       away_score ~ away_off_away + home_def_home (+const).
- Expanding window from 2018 REG, refit weekly. Predict 2021-2022 REG.
"""
import pandas as pd, numpy as np, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "experiment_008_distributional"
ALPHA = 1 - 0.5 ** (1 / 8)  # 8-game half-life

g = pd.read_parquet(ROOT / "data" / "games_with_preds.parquet")
g = g[(g['season'].between(2018, 2022)) & (g['game_type'] == 'REG')].copy()
g = g.sort_values(['season', 'week']).reset_index(drop=True)
assert g['season'].max() <= 2022, "VAULT PROTECTION: season > 2022 present"

lg = g['home_score'].mean()
state = {}

def get_ratings(team, venue):
    s = state.get(team)
    if s is None or s[f'n_{venue}'] == 0:
        return lg, lg
    return s[f'{venue}_off'], s[f'{venue}_def']

def update(team, venue, scored, allowed):
    s = state.setdefault(team, {'home_off': lg, 'home_def': lg, 'away_off': lg,
                                'away_def': lg, 'n_home': 0, 'n_away': 0})
    s[f'{venue}_off'] = ALPHA * scored + (1 - ALPHA) * s[f'{venue}_off']
    s[f'{venue}_def'] = ALPHA * allowed + (1 - ALPHA) * s[f'{venue}_def']
    s[f'n_{venue}'] += 1

def ols_pred(Xtr, ytr, Xte):
    Xtr1 = np.column_stack([np.ones(len(Xtr)), Xtr])
    Xte1 = np.column_stack([np.ones(len(Xte)), Xte])
    beta, *_ = np.linalg.lstsq(Xtr1, ytr, rcond=None)
    return Xte1 @ beta

hist = []   # (home_off, away_def, away_off, home_def, home_score, away_score)
preds = []
weeks = sorted(g[['season', 'week']].drop_duplicates().values.tolist())
for s, w in weeks:
    te = g[(g['season'] == s) & (g['week'] == w)]
    cur = []
    for _, r in te.iterrows():
        ho, hd = get_ratings(r['home_team'], 'home')
        ao, ad = get_ratings(r['away_team'], 'away')
        cur.append((r['game_id'], ho, ad, ao, hd,
                    r['home_score'], r['away_score']))
    if s >= 2021 and len(hist) > 200:
        H = np.array(hist)
        Xh_tr, yh_tr = H[:, [0, 1]], H[:, 4]
        Xa_tr, ya_tr = H[:, [2, 3]], H[:, 5]
        C = np.array(cur)
        ph = ols_pred(Xh_tr, yh_tr, C[:, [1, 2]].astype(float))
        pa = ols_pred(Xa_tr, ya_tr, C[:, [3, 4]].astype(float))
        for gid, hh, aa in zip(C[:, 0], ph, pa):
            preds.append({'game_id': gid, 'pred_home': float(hh),
                          'pred_away': float(aa), 'pred_margin': float(hh - aa)})
    for gid, ho, ad, ao, hd, hs, aws in cur:
        hist.append((ho, ad, ao, hd, hs, aws))
        r = te[te['game_id'] == gid].iloc[0]
        update(r['home_team'], 'home', hs, aws)
        update(r['away_team'], 'away', aws, hs)

p = pd.DataFrame(preds)
assert len(p) == 543, f"expected 543, got {len(p)}"
p.to_parquet(ROOT / "data" / "v2" / "pred_008a.parquet", index=False)
json.dump({"n": len(p), "alpha_half_life_games": 8,
           "model": "OLS home_score~home_off+away_def; away_score~away_off+home_def; weekly expanding refit from 2018 REG; single chronological pass (bug-fix 2026-09-29)"},
          open(OUT / "manifest_008a.json", "w"), indent=2)
print(f"008-A: wrote {len(p)} predictions")
