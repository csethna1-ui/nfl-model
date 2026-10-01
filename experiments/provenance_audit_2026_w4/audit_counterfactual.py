#!/usr/bin/env python3
"""Counterfactual: recompute Week 4 predictions with NO 2026 data at all.
If this matches predictions_2026_w4.csv, the production run used stale 2025 ratings."""
import json, pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/hatch/workspace/nfl-model/scripts")
from model_lib import (add_features, add_wind, make_gbm, GBM_BACKEND, MARGIN_FEATS, EPA_M_FEATS)
from importlib import import_module
ratings_mod = import_module("03_ratings"); run_elo = ratings_mod.run_elo
m07 = import_module("07_update_weekly")
DATA="/home/hatch/workspace/nfl-model/data"; S,W=2026,4
print("backend:", GBM_BACKEND, flush=True)
sched=pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
pbp=pd.read_parquet(f"{DATA}/pbp_2018_2025.parquet")
PBP_COLS=["game_id","posteam","defteam","play_type","epa","success","season","week"]; pbp=pbp[PBP_COLS]
played=sched[sched["home_score"].notna()].copy()
played=played[played["season"]<S].copy()   # <-- NO 2026
played=played.sort_values(["season","week"]).reset_index(drop=True)
played["home_margin"]=played["home_score"]-played["away_score"]
played["total_pts"]=played["home_score"]+played["away_score"]
print("played:",len(played),"max:",played["season"].max(),played[played.season==2025]["week"].max())
# week-1 regression like 07 does for W==1? No: for W=4 there is no regression step in 07.
# But 2026 W1 in 07's run_epa_current/run_elo DOES apply offseason regression (week==1 branch).
elo_df,elos=run_elo(played)
epa_df,epa_state=m07.run_epa_current(pbp,played)
with open(f"{DATA}/linear_models.pkl","rb") as f: lin=pickle.load(f)
with open(f"{DATA}/ensemble_params.json") as f: ens=json.load(f)
up=sched[(sched["season"]==S)&(sched["week"]==W)&sched["home_score"].isna()].copy()
rows=[]
for _,g in up.iterrows():
    h,a=g["home_team"],g["away_team"]
    r={"game_id":g["game_id"],"away_team":a,"home_team":h,"week":W,"div_game":int(g["div_game"]),
       "home_rest":g["home_rest"],"away_rest":g["away_rest"],
       "elo_diff":elos.get(h,1500.0)-elos.get(a,1500.0)}
    for m in ["off_epa","off_pass_epa","off_rush_epa","off_sr","def_epa","def_pass_epa","def_rush_epa","def_sr"]:
        r[f"home_{m}"]=epa_state[m].get(h,0.0); r[f"away_{m}"]=epa_state[m].get(a,0.0)
    rows.append(r)
pred=add_features(pd.DataFrame(rows))
pred["pred_elo"]=lin["lr_elo"].predict(pred[["elo_diff"]])
pred["pred_epa_m"]=lin["lr_epa_m"].predict(pred[EPA_M_FEATS])
rated=played[["game_id","season","week","home_team","away_team","home_margin","total_pts","home_rest","away_rest","div_game","wind","roof"]].merge(elo_df,on="game_id").merge(epa_df,on="game_id")
rated=add_wind(rated); rated=add_features(rated)
print("GBM train n:",len(rated))
gm=make_gbm().fit(rated[MARGIN_FEATS],rated["home_margin"])
pred["pred_gbm_m"]=gm.predict(pred[MARGIN_FEATS])
pred["model_spread"]=ens["w_elo"]*pred["pred_elo"]+ens["w_epa"]*pred["pred_epa_m"]+ens["w_gbm"]*pred["pred_gbm_m"]
csv=pd.read_csv(f"{DATA}/predictions_2026_w4.csv")
pred["key"]=pred["away_team"]+"_"+pred["home_team"]; csv["key"]=csv["game"].str.replace(" @ ","_")
m=pred.merge(csv[["key","model_spread"]].rename(columns={"model_spread":"csv"}),on="key")
m["rec"]=m["model_spread"].round(1); m["d"]=(m["rec"]-m["csv"]).abs()
print("max |no2026 - csv|:", m["d"].max())
print(m[["key","rec","csv"]].to_string(index=False))
print("\nelo BUF/NE (no-2026):", round(elos["BUF"],1), round(elos["NE"],1))
print("off_epa BUF/NE (no-2026):", round(epa_state["off_epa"].get("BUF",0),4), round(epa_state["off_epa"].get("NE",0),4))
