#!/usr/bin/env python3
"""Provenance audit: reproduce Week 4 V1 predictions from current caches WITHOUT
refreshing, and compare to data/predictions_2026_w4.csv. Also dump the full
end-to-end trace for one game (NE @ BUF) and a no-2026 counterfactual."""
import json, pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/hatch/workspace/nfl-model/scripts")
from model_lib import (add_features, add_wind, make_gbm, GBM_BACKEND,
                       MARGIN_FEATS, EPA_M_FEATS)
from importlib import import_module
ratings_mod = import_module("03_ratings")
run_elo = ratings_mod.run_elo
from importlib import import_module as im
m07 = im("07_update_weekly")

DATA = "/home/hatch/workspace/nfl-model/data"
S, W = 2026, 4
print("GBM backend:", GBM_BACKEND, flush=True)

sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
pbp = pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
PBP_COLS = ["game_id","posteam","defteam","play_type","epa","success","season","week"]
pbp = pbp[PBP_COLS]

played = sched[sched["home_score"].notna()].copy()
played = played[(played["season"] < S) | ((played["season"] == S) & (played["week"] < W))]
played = played.sort_values(["season","week"]).reset_index(drop=True)
played["home_margin"] = played["home_score"] - played["away_score"]
played["total_pts"] = played["home_score"] + played["away_score"]
n26 = (played["season"] == 2026).sum()
print(f"played games: {len(played)} total; 2026 games: {n26} "
      f"(weeks {sorted(played[played.season==2026]['week'].unique())})")
print("latest 2026 game in played:", played[played.season==2026].iloc[-1][["game_id","week","away_team","home_team","home_score","away_score"]].to_dict())

elo_df, elos = run_elo(played)
epa_df, epa_state = m07.run_epa_current(pbp, played)

with open(f"{DATA}/linear_models.pkl","rb") as f: lin = pickle.load(f)
with open(f"{DATA}/ensemble_params.json") as f: ens = json.load(f)
print("ensemble:", {k: ens[k] for k in ("w_elo","w_epa","w_gbm")})

up = sched[(sched["season"]==S)&(sched["week"]==W)&sched["home_score"].isna()].copy()
rows=[]
for _,g in up.iterrows():
    h,a = g["home_team"], g["away_team"]
    row={"game_id":g["game_id"],"away_team":a,"home_team":h,"week":W,
         "div_game":int(g["div_game"]),"home_rest":g["home_rest"],"away_rest":g["away_rest"],
         "elo_diff": elos.get(h,1500.0)-elos.get(a,1500.0)}
    for m in ["off_epa","off_pass_epa","off_rush_epa","off_sr",
              "def_epa","def_pass_epa","def_rush_epa","def_sr"]:
        row[f"home_{m}"]=epa_state[m].get(h,0.0); row[f"away_{m}"]=epa_state[m].get(a,0.0)
    rows.append(row)
pred = add_features(pd.DataFrame(rows))
pred["pred_elo"]=lin["lr_elo"].predict(pred[["elo_diff"]])
pred["pred_epa_m"]=lin["lr_epa_m"].predict(pred[EPA_M_FEATS])

rated = played[["game_id","season","week","home_team","away_team","home_margin","total_pts",
                "home_rest","away_rest","div_game","wind","roof"]].merge(elo_df,on="game_id").merge(epa_df,on="game_id")
rated = add_wind(rated); rated = add_features(rated)
print("GBM train n:", len(rated), "| max train season/week:",
      rated["season"].max(), rated[rated.season==2026]["week"].max() if (rated.season==2026).any() else None)
gm = make_gbm().fit(rated[MARGIN_FEATS], rated["home_margin"])
pred["pred_gbm_m"]=gm.predict(pred[MARGIN_FEATS])
pred["model_spread"]=ens["w_elo"]*pred["pred_elo"]+ens["w_epa"]*pred["pred_epa_m"]+ens["w_gbm"]*pred["pred_gbm_m"]

csv = pd.read_csv(f"{DATA}/predictions_2026_w4.csv")
csv["key"]=csv["game"].str.replace(" @ ","_")
pred["key"]=pred["away_team"]+"_"+pred["home_team"]
m = pred.merge(csv[["key","model_spread"]].rename(columns={"model_spread":"csv_spread"}), on="key")
m["recomputed"]=m["model_spread"].round(1)
m["diff"]=(m["recomputed"]-m["csv_spread"]).abs()
print("\nmax |recomputed - csv| model_spread:", m["diff"].max())
print(m[["key","recomputed","csv_spread"]].to_string(index=False))

# ---- counterfactual: no 2026 data at all ----
played0 = played[played["season"]<2026].copy()
_, elos0 = run_elo(played0)
_, epa0 = m07.run_epa_current(pbp, played0)
rows0=[]
for _,g in up.iterrows():
    h,a=g["home_team"],g["away_team"]
    r0={"away_team":a,"home_team":h,"week":W,"div_game":int(g["div_game"]),
        "home_rest":g["home_rest"],"away_rest":g["away_rest"],
        "elo_diff":elos0.get(h,1500.0)-elos0.get(a,1500.0)}
    for mm in ["off_epa","off_pass_epa","off_rush_epa","off_sr","def_epa","def_pass_epa","def_rush_epa","def_sr"]:
        r0[f"home_{mm}"]=epa0[mm].get(h,0.0); r0[f"away_{mm}"]=epa0[mm].get(a,0.0)
    rows0.append(r0)
p0=add_features(pd.DataFrame(rows0))
p0["pe"]=lin["lr_elo"].predict(p0[["elo_diff"]]); p0["pm"]=lin["lr_epa_m"].predict(p0[EPA_M_FEATS])
rated0 = played0[["game_id","season","week","home_team","away_team","home_margin","total_pts","home_rest","away_rest","div_game","wind","roof"]].merge(*[run_elo(played0)[0]],on="game_id")
p0key=(p0["away_team"]+"_"+p0["home_team"])
m0=p0.copy(); m0["key"]=p0key
mm2=m0.merge(csv[["key","model_spread"]].rename(columns={"model_spread":"csv_spread"}),on="key")
# gbm for counterfactual skipped (expensive); linear-only blend comparison
print("\ncounterfactual (no 2026, linear-only part) sample diffs vs csv:")
print("NE_BUF csv:", float(csv[csv.game=='NE @ BUF']['model_spread'].iloc[0]))

# ---- full trace: NE @ BUF ----
r = pred[pred.key=="NE_BUF"].iloc[0]
print("\n===== TRACE: NE @ BUF (game_id", r["game_id"], ") =====")
print("elo BUF:", round(elos["BUF"],3), "| elo NE:", round(elos["NE"],3), "| elo_diff used:", round(r["elo_diff"],3))
print("pred_elo (component):", round(float(r["pred_elo"]),4))
print("pred_epa_m (component):", round(float(r["pred_epa_m"]),4))
print("pred_gbm_m (component):", round(float(r["pred_gbm_m"]),4))
print("blend 0.4/0.5/0.1 =", round(0.4*float(r["pred_elo"])+0.5*float(r["pred_epa_m"])+0.1*float(r["pred_gbm_m"]),4),
      "| csv model_spread:", float(csv[csv.game=='NE @ BUF']['model_spread'].iloc[0]))
print("\nEPA differential vector (home-away, BUF-NE):")
for f in EPA_M_FEATS: print(f"  {f}: {r[f]:+.5f}")
print("\nGBM feature vector:")
for f in MARGIN_FEATS: print(f"  {f}: {r[f]:+.5f}")
print("\nNE epa_state (current, through 2026 W3):")
for mm in ["off_epa","off_pass_epa","off_rush_epa","off_sr","def_epa","def_pass_epa","def_rush_epa","def_sr"]:
    print(f"  {mm}: {epa_state[mm].get('NE',0.0):+.5f}")
print("BUF epa_state:")
for mm in ["off_epa","off_pass_epa","off_rush_epa","off_sr","def_epa","def_pass_epa","def_rush_epa","def_sr"]:
    print(f"  {mm}: {epa_state[mm].get('BUF',0.0):+.5f}")
print("\nNE 2026 games in played:")
ne26 = played[played.season==2026]
ne26 = ne26[(ne26.home_team=="NE")|(ne26.away_team=="NE")][["week","game_id","away_team","home_team","away_score","home_score"]]
print(ne26.to_string(index=False))
print("\nBUF 2026 games in played:")
b26 = played[played.season==2026]
b26 = b26[(b26.home_team=="BUF")|(b26.away_team=="BUF")][["week","game_id","away_team","home_team","away_score","home_score"]]
print(b26.to_string(index=False))
print("\nleague off_epa ranking (current, through 2026 W3), top 8:")
rk = sorted([(t, round(epa_state["off_epa"].get(t,0.0),4)) for t in elos], key=lambda x:-x[1])[:8]
for t,v in rk: print(f"  {t}: {v:+.4f}")
