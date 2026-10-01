#!/usr/bin/env python3
"""Power-ranking experiment — 03: preregistered vault confirmation.

Evaluates the ONE fixed adopted specification
    Power score = ( z(ELO) + z(offensive EPA/play) ) / 2
vs ELO-only = z(ELO)
on the locked 2023-2025 vault. Confirmation only: no tuning, no refitting,
no specification changes, no 2026 data.

Margin mappings are the development-fit (2018-2020) OLS mappings recomputed
deterministically (OLS is randomness-free) from the original code path.

READ-ONLY: reads data/games_with_ratings.parquet + the 2018-2022 snapshots
for the dev mappings; writes only NEW files into
experiments/power_ranking_experiment/ (never modifies existing ones).
"""
import numpy as np
import pandas as pd
from scipy import stats

DATA = "/home/hatch/workspace/nfl-model/data"
OUT = "/home/hatch/workspace/nfl-model/experiments/power_ranking_experiment"
DEV = [2018, 2019, 2020]
VAL_CHECK = [2021, 2022]   # reproduction check only; never used for fitting
VAULT = [2023, 2024, 2025]
EVAL_WEEKS = range(4, 19)

g = pd.read_parquet(f"{DATA}/games_with_ratings.parquet")
reg = g[(g["game_type"] == "REG") & (g["season"].isin(DEV + VAL_CHECK + VAULT))].copy()
reg = reg.sort_values(["season", "week"]).reset_index(drop=True)

# ---------- 1. build pre-week snapshots for vault seasons ----------
# (identical construction to 01_build_snapshots.py)
res = []
for _, r in reg.iterrows():
    hm = r["home_margin"]
    res.append({"season": r["season"], "week": r["week"], "team": r["home_team"],
                "pf": r["home_score"], "pa": r["away_score"],
                "w": 1 if hm > 0 else 0, "l": 1 if hm < 0 else 0, "t": 1 if hm == 0 else 0})
    res.append({"season": r["season"], "week": r["week"], "team": r["away_team"],
                "pf": r["away_score"], "pa": r["home_score"],
                "w": 1 if hm < 0 else 0, "l": 1 if hm > 0 else 0, "t": 1 if hm == 0 else 0})
res = pd.DataFrame(res)

snaps = []
for season in VAULT:
    gs = reg[reg["season"] == season]
    rs = res[res["season"] == season]
    max_week = gs["week"].max()
    carry = {}
    for week in range(1, max_week + 1):
        gw = gs[gs["week"] == week]
        wk_ratings = {}
        for _, r in gw.iterrows():
            wk_ratings[r["home_team"]] = {
                "elo": r["elo_home"], "off_epa": r["home_off_epa"],
                "def_epa": r["home_def_epa"], "off_sr": r["home_off_sr"],
                "def_sr": r["home_def_sr"]}
            wk_ratings[r["away_team"]] = {
                "elo": r["elo_away"], "off_epa": r["away_off_epa"],
                "def_epa": r["away_def_epa"], "off_sr": r["away_off_sr"],
                "def_sr": r["away_def_sr"]}
        carry.update(wk_ratings)
        past = rs[rs["week"] < week]
        agg = past.groupby("team").agg(w=("w", "sum"), l=("l", "sum"), t=("t", "sum"),
                                       pf=("pf", "sum"), pa=("pa", "sum"),
                                       gp=("w", "size")).reset_index()
        agg["win_pct"] = (agg["w"] + 0.5 * agg["t"]) / agg["gp"].replace(0, np.nan)
        agg["pd_pg"] = (agg["pf"] - agg["pa"]) / agg["gp"].replace(0, np.nan)
        agg = agg.fillna({"win_pct": 0.0, "pd_pg": 0.0, "gp": 0})
        ad = agg.set_index("team").to_dict("index")
        for team, rt in carry.items():
            a = ad.get(team, {"w": 0, "l": 0, "t": 0, "gp": 0, "win_pct": 0.0, "pd_pg": 0.0})
            snaps.append({"season": season, "week": week, "team": team,
                          "elo": rt["elo"], "off_epa": rt["off_epa"],
                          "def_epa": rt["def_epa"], "off_sr": rt["off_sr"],
                          "def_sr": rt["def_sr"], "w": a["w"], "l": a["l"],
                          "t": a["t"], "gp": a["gp"], "win_pct": a["win_pct"],
                          "pd_pg": a["pd_pg"]})
snaps = pd.DataFrame(snaps)
snaps.to_parquet(f"{OUT}/snapshots_2023_2025.parquet", index=False)
print("vault snapshots:", snaps.shape)
chk = snaps.groupby(["season", "week"]).size()
assert (chk == 32).all(), chk[chk != 32]
print("32 teams x every week: OK")

# ---------- 2. standardized components + fixed candidates ----------
def add_components(df):
    df = df.copy()
    df["netsr"] = df["off_sr"] - df["def_sr"]
    for col, zc in [("elo", "z_elo"), ("off_epa", "z_off")]:
        df[zc] = df.groupby(["season", "week"])[col].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else 0.0)
    df["c1_elo"] = df["z_elo"]                          # ELO only
    df["c2_off"] = (df["z_elo"] + df["z_off"]) / 2      # FIXED adopted composite
    return df

snaps = add_components(snaps)
CANDS = ["c1_elo", "c2_off"]
CNAMES = {"c1_elo": "ELO only", "c2_off": "ELO+OffEPA (fixed composite)"}

# ---------- 3. development-fit margin mappings (recomputed, deterministic) ----------
dev_snaps = pd.read_parquet(f"{OUT}/snapshots_2018_2022.parquet")
dev_snaps = add_components(dev_snaps)
dev_reg = reg[reg["season"].isin(DEV)][["season", "week", "home_team", "away_team", "home_margin"]]

def game_eval_rows(snap_df, game_df, seasons, weeks):
    rows = []
    sub = snap_df[snap_df["season"].isin(seasons) & snap_df["week"].isin(weeks)]
    smap = sub.set_index(["season", "week", "team"])
    for (season, week), _ in sub.groupby(["season", "week"]):
        fg = game_df[(game_df["season"] == season) & (game_df["week"] > week)]
        if fg.empty:
            continue
        for _, r in fg.iterrows():
            try:
                hs = smap.loc[(season, week, r["home_team"])]
                aws = smap.loc[(season, week, r["away_team"])]
            except KeyError:
                continue
            row = {"season": season, "snap_week": week, "home_margin": r["home_margin"]}
            for c in CANDS:
                row[c] = hs[c] - aws[c]
            rows.append(row)
    return pd.DataFrame(rows)

dev_games = game_eval_rows(dev_snaps, dev_reg, DEV, EVAL_WEEKS)
print("dev game-snapshot pairs (mapping fit):", len(dev_games))
maps = {}
for c in CANDS:
    d = dev_games[[c, "home_margin"]].dropna()
    Xd = np.column_stack([np.ones(len(d)), d[c].values])
    (a, b), *_ = np.linalg.lstsq(Xd, d["home_margin"].values, rcond=None)
    maps[c] = (a, b)
    print(f"  dev mapping {CNAMES[c]}: intercept={a:+.3f} slope={b:+.3f}")

# sanity: dev mappings must reproduce the original experiment's applied values
# (original applied these same mappings to 2021-2022; check MAE matches REPORT)
chk_snaps = add_components(dev_snaps)
chk = game_eval_rows(chk_snaps, reg[reg["season"].isin([2021, 2022])][["season","week","home_team","away_team","home_margin"]], [2021,2022], EVAL_WEEKS)
for c in CANDS:
    a, b = maps[c]
    chk[f"ae_{c}"] = (chk["home_margin"] - (a + b*chk[c])).abs()
print("reproduction check vs REPORT (2021-2022 MAE):")
print(f"  ELO only: {chk['ae_c1_elo'].mean():.4f} (report 10.678)")
print(f"  ELO+OffEPA: {chk['ae_c2_off'].mean():.4f} (report 10.453)")

# ---------- 4. vault evaluation ----------
vault_games = game_eval_rows(snaps, reg[reg["season"].isin(VAULT)][["season","week","home_team","away_team","home_margin"]], VAULT, EVAL_WEEKS)
print("vault game-snapshot pairs:", len(vault_games))
for c in CANDS:
    a, b = maps[c]
    vault_games[f"pred_{c}"] = a + b * vault_games[c]
    vault_games[f"ae_{c}"] = (vault_games["home_margin"] - vault_games[f"pred_{c}"]).abs()

# primary: pooled
prim = []
for c in CANDS:
    mae = vault_games[f"ae_{c}"].mean()
    d = vault_games["ae_c1_elo"] - vault_games[f"ae_{c}"]
    diff = d.mean()
    se = d.std(ddof=1) / np.sqrt(len(d))
    t = diff / se if se > 0 else 0.0
    p = 2 * (1 - stats.t.cdf(abs(t), len(d) - 1)) if se > 0 else 1.0
    prim.append({"candidate": CNAMES[c], "n": len(vault_games),
                 "mae": mae, "mae_vs_elo": diff, "se": se, "t": t, "p": p})
prim = pd.DataFrame(prim).sort_values("mae")
prim.to_csv(f"{OUT}/table_vault_confirmation.csv", index=False)
print("\nPRIMARY — vault future-margin MAE (2023-2025, snapshots wk 4+, dev-fit mappings):")
print(prim.to_string(index=False, float_format="%.4f"))

# season-by-season
ps = []
for s in VAULT:
    v = vault_games[vault_games["season"] == s]
    for c in CANDS:
        d = v["ae_c1_elo"] - v[f"ae_{c}"]
        ps.append({"season": s, "candidate": CNAMES[c], "n": len(v),
                   "mae": v[f"ae_{c}"].mean(), "mae_vs_elo": d.mean()})
ps = pd.DataFrame(ps)
ps.to_csv(f"{OUT}/table_vault_confirmation_season.csv", index=False)
print("\nPer-season MAE:")
print(ps.to_string(index=False, float_format="%.4f"))

# early / mid / late splits
def split(w):
    return "early(1-3)" if w <= 3 else ("mid(4-12)" if w <= 12 else "late(13+)")
vault_early = game_eval_rows(snaps, reg[reg["season"].isin(VAULT)][["season","week","home_team","away_team","home_margin"]], VAULT, [1, 2, 3])
for c in CANDS:
    a, b = maps[c]
    vault_early[f"ae_{c}"] = (vault_early["home_margin"] - (a + b*vault_early[c])).abs()
vault_early["split"] = vault_early["snap_week"].apply(split)
vault_games["split"] = vault_games["snap_week"].apply(split)
sp = []
for df in [vault_early, vault_games]:
    for spl, gdf in df.groupby("split"):
        for c in CANDS:
            d = gdf["ae_c1_elo"] - gdf[f"ae_{c}"]
            sp.append({"split": spl, "candidate": CNAMES[c], "n": len(gdf),
                       "mae": gdf[f"ae_{c}"].mean(), "mae_vs_elo": d.mean()})
sp = pd.DataFrame(sp)
sp.to_csv(f"{OUT}/table_vault_confirmation_splits.csv", index=False)
print("\nSplit MAE:")
print(sp.to_string(index=False, float_format="%.4f"))

# secondary: predictive rank correlation
res2 = []
for _, r in reg[reg["season"].isin(VAULT)].iterrows():
    hm = r["home_margin"]
    res2.append((r["season"], r["week"], r["home_team"], r["home_score"] - r["away_score"],
                 1 if hm > 0 else (0.5 if hm == 0 else 0)))
    res2.append((r["season"], r["week"], r["away_team"], r["away_score"] - r["home_score"],
                 1 if hm < 0 else (0.5 if hm == 0 else 0)))
res2 = pd.DataFrame(res2, columns=["season", "week", "team", "pd", "w"])
fut_rows = []
for (season, week), grp in snaps.groupby(["season", "week"]):
    f = res2[(res2["season"] == season) & (res2["week"] > week)]
    if f.empty:
        continue
    agg = f.groupby("team").agg(fut_pd_pg=("pd", "mean"), fut_win=("w", "mean")).reset_index()
    agg["season"], agg["week"] = season, week
    fut_rows.append(agg)
fut = pd.concat(fut_rows, ignore_index=True)
vsub = snaps.merge(fut, on=["season", "week", "team"], how="left")
vsub = vsub[(vsub["week"] >= 4) & vsub["fut_pd_pg"].notna()]
rc = []
for c in CANDS:
    cw, cp = [], []
    for (_, _), grp in vsub.groupby(["season", "week"]):
        rk = grp[c].rank(ascending=False)
        cw.append(stats.spearmanr(rk, grp["fut_win"]).statistic)
        cp.append(stats.spearmanr(rk, grp["fut_pd_pg"]).statistic)
    rc.append({"candidate": CNAMES[c],
               "spearman_vs_fut_win": -np.nanmean(cw),
               "spearman_vs_fut_pdpg": -np.nanmean(cp)})
rc = pd.DataFrame(rc)
rc.to_csv(f"{OUT}/table_vault_confirmation_rankcorr.csv", index=False)
print("\nRank correlations (mean over vault snapshots):")
print(rc.to_string(index=False, float_format="%.4f"))

print("\nAll vault-confirmation tables saved to", OUT)
