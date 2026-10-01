#!/usr/bin/env python3
"""Power-ranking experiment — 02: walk-forward candidate comparison.

Development: 2018-2020 (learn composite weights + margin mappings).
Validation:  2021-2022 (compare candidates; nothing refit).
Vault 2023-2025: never touched. No 2026 data.

READ-ONLY: writes only into experiments/power_ranking_experiment/.
"""
import numpy as np
import pandas as pd
from scipy import stats

OUT = "/home/hatch/workspace/nfl-model/experiments/power_ranking_experiment"
DEV = [2018, 2019, 2020]
VAL = [2021, 2022]
EVAL_WEEKS = range(4, 19)   # primary snapshots; capped per-season by max week

snaps = pd.read_parquet(f"{OUT}/snapshots_2018_2022.parquet")
g = pd.read_parquet("/home/hatch/workspace/nfl-model/data/games_with_ratings.parquet")
reg = g[(g["game_type"] == "REG") & (g["season"].isin(DEV + VAL))].copy()

# ---------- 1. standardized components per snapshot week ----------
def add_components(df):
    df = df.copy()
    df["netsr"] = df["off_sr"] - df["def_sr"]
    df["ndef_epa"] = -df["def_epa"]
    for col, zc in [("elo", "z_elo"), ("off_epa", "z_off"), ("ndef_epa", "z_def"),
                    ("netsr", "z_netsr"), ("win_pct", "z_wl"), ("pd_pg", "z_pd")]:
        df[zc] = df.groupby(["season", "week"])[col].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else 0.0)
    return df

snaps = add_components(snaps)
COMPS = ["z_elo", "z_off", "z_def", "z_netsr", "z_wl", "z_pd"]

# ---------- 2. rest-of-season team futures (for weight learning + rank corr) ----------
# team-game results
res = []
for _, r in reg.iterrows():
    hm = r["home_margin"]
    res.append((r["season"], r["week"], r["home_team"], r["home_score"] - r["away_score"],
                1 if hm > 0 else (0.5 if hm == 0 else 0)))
    res.append((r["season"], r["week"], r["away_team"], r["away_score"] - r["home_score"],
                1 if hm < 0 else (0.5 if hm == 0 else 0)))
res = pd.DataFrame(res, columns=["season", "week", "team", "pd", "w"])

fut_rows = []
for (season, week), grp in snaps.groupby(["season", "week"]):
    f = res[(res["season"] == season) & (res["week"] > week)]
    if f.empty:
        continue
    agg = f.groupby("team").agg(fut_pd_pg=("pd", "mean"), fut_win=("w", "mean"),
                                fut_n=("pd", "size")).reset_index()
    agg["season"], agg["week"] = season, week
    fut_rows.append(agg)
fut = pd.concat(fut_rows, ignore_index=True)
snaps = snaps.merge(fut, on=["season", "week", "team"], how="left")

# ---------- 3. learned composite weights (development only) ----------
dev = snaps[snaps["season"].isin(DEV) & (snaps["week"] >= 4) & snaps["fut_pd_pg"].notna()]
X = dev[COMPS].values
y = dev["fut_pd_pg"].values
X1 = np.column_stack([np.ones(len(X)), X])
beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
LEARNED = dict(zip(["intercept"] + COMPS, beta))
print("Learned weights (dev 2018-2020, pooled):")
for k, v in LEARNED.items():
    print(f"  {k}: {v:+.3f}")

# per-season stability
per_season = {}
for s in DEV:
    d = dev[dev["season"] == s]
    Xs = np.column_stack([np.ones(len(d)), d[COMPS].values])
    b, *_ = np.linalg.lstsq(Xs, d["fut_pd_pg"].values, rcond=None)
    per_season[s] = dict(zip(["intercept"] + COMPS, b))

# ---------- 4. candidate scores ----------
def score_candidates(df):
    df = df.copy()
    df["c1_elo"] = df["z_elo"]
    df["c2_off"] = (df["z_elo"] + df["z_off"]) / 2
    df["c3_def"] = (df["z_elo"] + df["z_off"] + df["z_def"]) / 3
    df["c4_netsr"] = (df["z_elo"] + df["z_off"] + df["z_def"] + df["z_netsr"]) / 4
    df["c5_wl"] = (df["z_elo"] + df["z_off"] + df["z_def"] + df["z_netsr"] + df["z_wl"]) / 5
    df["c6_pd"] = (df["z_elo"] + df["z_off"] + df["z_def"] + df["z_netsr"] + df["z_wl"] + df["z_pd"]) / 6
    df["c7_learned"] = LEARNED["intercept"] + sum(LEARNED[c] * df[c] for c in COMPS)
    return df

snaps = score_candidates(snaps)
CANDS = ["c1_elo", "c2_off", "c3_def", "c4_netsr", "c5_wl", "c6_pd", "c7_learned"]
CNAMES = {"c1_elo": "ELO only", "c2_off": "ELO+OffEPA", "c3_def": "ELO+Off+Def EPA",
          "c4_netsr": "+NetSR", "c5_wl": "+W-L", "c6_pd": "+PtDiff", "c7_learned": "Learned"}

# ---------- 5. game-level future-margin evaluation ----------
# future games per snapshot
games = reg[["season", "week", "home_team", "away_team", "home_margin"]].copy()

def game_eval_rows(seasons, weeks):
    rows = []
    sub = snaps[snaps["season"].isin(seasons) & snaps["week"].isin(weeks)]
    smap = sub.set_index(["season", "week", "team"])
    for (season, week), _ in sub.groupby(["season", "week"]):
        fg = games[(games["season"] == season) & (games["week"] > week)]
        if fg.empty:
            continue
        for _, r in fg.iterrows():
            try:
                hs = smap.loc[(season, week, r["home_team"])]
                aws = smap.loc[(season, week, r["away_team"])]
            except KeyError:
                continue
            row = {"season": season, "snap_week": week,
                   "home_margin": r["home_margin"]}
            for c in CANDS:
                row[c] = hs[c] - aws[c]
            rows.append(row)
    return pd.DataFrame(rows)

dev_games = game_eval_rows(DEV, EVAL_WEEKS)
print("dev game-snapshot pairs:", len(dev_games))

# margin mappings fit on development, per candidate
maps = {}
for c in CANDS:
    d = dev_games[[c, "home_margin"]].dropna()
    Xd = np.column_stack([np.ones(len(d)), d[c].values])
    (a, b), *_ = np.linalg.lstsq(Xd, d["home_margin"].values, rcond=None)
    maps[c] = (a, b)

val_games = game_eval_rows(VAL, EVAL_WEEKS)
print("val game-snapshot pairs:", len(val_games))
for c in CANDS:
    a, b = maps[c]
    val_games[f"pred_{c}"] = a + b * val_games[c]
    val_games[f"ae_{c}"] = (val_games["home_margin"] - val_games[f"pred_{c}"]).abs()

# ---------- 6. primary results ----------
prim = []
for c in CANDS:
    mae = val_games[f"ae_{c}"].mean()
    d = val_games[f"ae_c1_elo"] - val_games[f"ae_{c}"]  # + means c beats ELO-only
    diff = d.mean()
    se = d.std(ddof=1) / np.sqrt(len(d))
    t = diff / se if se > 0 else 0
    p = 2 * (1 - stats.t.cdf(abs(t), len(d) - 1)) if se > 0 else 1.0
    prim.append({"candidate": CNAMES[c], "n": len(val_games),
                 "mae": mae, "mae_vs_elo": diff, "se": se, "t": t, "p": p})
prim = pd.DataFrame(prim).sort_values("mae")
prim.to_csv(f"{OUT}/table_primary_mae.csv", index=False)
print("\nPRIMARY — validation future-margin MAE (2021-2022, snapshots wk 4+):")
print(prim.to_string(index=False, float_format="%.4f"))

# per-season
ps = []
for s in VAL:
    v = val_games[val_games["season"] == s]
    for c in CANDS:
        d = v[f"ae_c1_elo"] - v[f"ae_{c}"]
        ps.append({"season": s, "candidate": CNAMES[c], "n": len(v),
                   "mae": v[f"ae_{c}"].mean(), "mae_vs_elo": d.mean()})
ps = pd.DataFrame(ps)
ps.to_csv(f"{OUT}/table_season_mae.csv", index=False)
print("\nPer-season MAE:")
print(ps.to_string(index=False, float_format="%.4f"))

# early / mid / late splits (by snapshot week)
def split(w):
    return "early(1-3)" if w <= 3 else ("mid(4-12)" if w <= 12 else "late(13+)")
val_early = game_eval_rows(VAL, [1, 2, 3])
for c in CANDS:
    a, b = maps[c]
    val_early[f"pred_{c}"] = a + b * val_early[c]
    val_early[f"ae_{c}"] = (val_early["home_margin"] - val_early[f"pred_{c}"]).abs()
val_early["split"] = val_early["snap_week"].apply(split)
val_games["split"] = val_games["snap_week"].apply(split)
sp = []
for df, tag in [(val_early, "early(1-3)"), (val_games, "mid/late")]:
    for spl, gdf in df.groupby("split"):
        for c in CANDS:
            d = gdf[f"ae_c1_elo"] - gdf[f"ae_{c}"]
            sp.append({"split": spl, "candidate": CNAMES[c], "n": len(gdf),
                       "mae": gdf[f"ae_{c}"].mean(), "mae_vs_elo": d.mean()})
sp = pd.DataFrame(sp)
sp.to_csv(f"{OUT}/table_split_mae.csv", index=False)
print("\nSplit MAE:")
print(sp.to_string(index=False, float_format="%.4f"))

# ---------- 7. rank correlations (secondary) ----------
vsub = snaps[snaps["season"].isin(VAL) & (snaps["week"] >= 4) & snaps["fut_pd_pg"].notna()]
rc = []
for c in CANDS:
    corrs_w, corrs_p = [], []
    for (_, _), grp in vsub.groupby(["season", "week"]):
        rk = grp[c].rank(ascending=False)
        corrs_w.append(stats.spearmanr(rk, grp["fut_win"]).statistic)
        corrs_p.append(stats.spearmanr(rk, grp["fut_pd_pg"]).statistic)
    rc.append({"candidate": CNAMES[c],
               # sign flipped: rank 1 = best, so raw spearman is negative when
               # the ranking works; report positive = better predictive ordering
               "spearman_vs_fut_win": -np.nanmean(corrs_w),
               "spearman_vs_fut_pdpg": -np.nanmean(corrs_p)})
rc = pd.DataFrame(rc).sort_values("spearman_vs_fut_pdpg", ascending=False)
rc.to_csv(f"{OUT}/table_rankcorr.csv", index=False)
print("\nRank correlations (mean over validation snapshots):")
print(rc.to_string(index=False, float_format="%.4f"))

# ---------- 8. week-to-week stability ----------
st = []
for c in CANDS:
    cors = []
    for s in VAL:
        ss = vsub[vsub["season"] == s].sort_values("week")
        weeks = sorted(ss["week"].unique())
        for w1, w2 in zip(weeks[:-1], weeks[1:]):
            a = ss[ss["week"] == w1].set_index("team")[c]
            b = ss[ss["week"] == w2].set_index("team")[c]
            common = a.index.intersection(b.index)
            cors.append(stats.spearmanr(a[common].rank(ascending=False),
                                        b[common].rank(ascending=False)).statistic)
    st.append({"candidate": CNAMES[c], "wk_to_wk_rank_spearman": np.nanmean(cors)})
st = pd.DataFrame(st).sort_values("wk_to_wk_rank_spearman", ascending=False)
st.to_csv(f"{OUT}/table_stability.csv", index=False)
print("\nWeek-to-week rank stability:")
print(st.to_string(index=False, float_format="%.4f"))

# ---------- 9. learned-weight stability + save ----------
lw = pd.DataFrame([{"scope": f"dev_{s}", **per_season[s]} for s in DEV] +
                  [{"scope": "dev_pooled", **LEARNED}])
lw.to_csv(f"{OUT}/table_learned_weights.csv", index=False)
print("\nLearned weights per development season:")
print(lw.to_string(index=False, float_format="%.3f"))

# ---------- 10. disagreement case studies (descriptive, validation wk4) ----------
wk4 = snaps[snaps["season"].isin(VAL) & (snaps["week"] == 4)].copy()
wk4["eff_score"] = (wk4["z_off"] + wk4["z_def"] + wk4["z_netsr"]) / 3
wk4["elo_rank"] = wk4.groupby("season")["z_elo"].rank(ascending=False)
wk4["eff_rank"] = wk4.groupby("season")["eff_score"].rank(ascending=False)
wk4["disagree"] = (wk4["elo_rank"] - wk4["eff_rank"]).abs()
wk4["fut_rank"] = wk4.groupby("season")["fut_pd_pg"].rank(ascending=False)
top = wk4.sort_values("disagree", ascending=False).groupby("season").head(5)
rows = []
for _, r in top.iterrows():
    row = {"season": r["season"], "team": r["team"],
           "elo_rank": int(r["elo_rank"]), "eff_rank": int(r["eff_rank"]),
           "fut_perf_rank": int(r["fut_rank"])}
    for c in CANDS:
        ssn = wk4[wk4["season"] == r["season"]]
        cr = ssn[c].rank(ascending=False)
        row[f"rank_{c}"] = int(cr[ssn["team"] == r["team"]].values[0])
    rows.append(row)
dc = pd.DataFrame(rows)
dc.to_csv(f"{OUT}/table_disagreement_cases.csv", index=False)
print("\nTop-5 ELO-vs-efficiency disagreements per validation season (week 4):")
print(dc.to_string(index=False))

print("\nAll tables saved to", OUT)
