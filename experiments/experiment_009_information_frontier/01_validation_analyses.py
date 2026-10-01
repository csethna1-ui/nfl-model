"""Experiment 009 — validation analyses (frozen protocol, 2026-09-30).
Reads data/games_with_preds.parquet only. No locked-test (2023+) computation here.
Seed fixed for bootstrap."""
import pandas as pd, numpy as np, json
from sklearn.linear_model import LinearRegression

SEED = 42
rng = np.random.default_rng(SEED)
OUT = "experiments/experiment_009_information_frontier/"
g = pd.read_parquet("data/games_with_preds.parquet")
g["v1_err"] = (g["ens_margin"] - g["home_margin"]).abs()
g["mkt_err"] = (g["spread_line"] - g["home_margin"]).abs()
val = g[g.season.isin([2021, 2022])].copy().reset_index(drop=True)
res = {}

def boot_ci(a_err, b_err, n_iter=2000):
    """95% paired bootstrap CI for mean(a-b). Positive = b better."""
    d = a_err - b_err
    n = len(d)
    boots = rng.choice(d, size=(n_iter, n), replace=True).mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))

# ---------- A. Market anchoring ----------
A_mae = val["v1_err"].mean(); B_mae = val["mkt_err"].mean()
grid = {}
for w in np.arange(0, 1.001, 0.05):
    blend = w * val["ens_margin"] + (1 - w) * val["spread_line"]
    grid[round(float(w), 2)] = float((blend - val["home_margin"]).abs().mean())
w_star = min(grid, key=grid.get)
blend = w_star * val["ens_margin"] + (1 - w_star) * val["spread_line"]
C_mae = float((blend - val["home_margin"]).abs().mean())
ci_b = boot_ci(val["v1_err"].values, ((blend - val["home_margin"]).abs().values))
ci_m = boot_ci(val["mkt_err"].values, ((blend - val["home_margin"]).abs().values))
per_season = {}
for s, sub in val.groupby("season"):
    b = w_star * sub["ens_margin"] + (1 - w_star) * sub["spread_line"]
    per_season[int(s)] = {"n": len(sub), "V1": float(sub["v1_err"].mean()),
        "market": float(sub["mkt_err"].mean()), "blend": float((b - sub["home_margin"]).abs().mean())}
res["anchoring"] = {"n": len(val), "w_star": w_star, "A_V1": float(A_mae), "B_market": float(B_mae),
    "C_blend": C_mae, "delta_blend_vs_V1": float(A_mae - C_mae),
    "delta_blend_vs_market": float(B_mae - C_mae),
    "ci_blend_vs_V1": ci_b, "ci_blend_vs_market": ci_m, "per_season": per_season,
    "grid": grid}
print("A: w*=%.2f V1=%.4f mkt=%.4f blend=%.4f dV1=%.4f CI=%s dMkt=%.4f CI=%s" %
      (w_star, A_mae, B_mae, C_mae, A_mae - C_mae, tuple(round(x,4) for x in ci_b),
       B_mae - C_mae, tuple(round(x,4) for x in ci_m)))

# ---------- B. Training-window audit ----------
EPA_FEATS = ["off_epa_diff","def_epa_diff","off_pass_diff","off_rush_diff",
             "def_pass_diff","def_rush_diff","sr_off_diff","sr_def_diff"]
hist_all = g.copy()  # training pool for predicting S = all seasons < S (strict walk-forward)
windows = {
    "W0_frozen_2018_2020": lambda S: hist_all[hist_all.season.isin([2018,2019,2020])],
    "W1_roll2":           lambda S: hist_all[hist_all.season.isin([S-2,S-1])],
    "W2_roll1":           lambda S: hist_all[hist_all.season == S-1],
    "W3_expanding":       lambda S: hist_all[hist_all.season <= S-1],
    "W4_drop2018":        lambda S: hist_all[hist_all.season.isin([2019,2020])],
}
win_res = {}
for wname, wfn in windows.items():
    errs, per_s = [], {}
    for S in [2021, 2022]:
        tr = wfn(S)
        lr_elo = LinearRegression().fit(tr[["elo_diff"]], tr["home_margin"])
        lr_epa = LinearRegression().fit(tr[EPA_FEATS], tr["home_margin"])
        sub = val[val.season == S].copy()
        p_elo = lr_elo.predict(sub[["elo_diff"]]); p_epa = lr_epa.predict(sub[EPA_FEATS])
        ens = 0.4*p_elo + 0.5*p_epa + 0.1*sub["pred_gbm_m"].values
        e = np.abs(ens - sub["home_margin"].values)
        per_s[S] = {"n": len(sub), "MAE": float(e.mean()), "train_n": len(tr)}
        errs.append(e)
    eall = np.concatenate(errs)
    win_res[wname] = {"MAE": float(eall.mean()), "per_season": per_s,
        "ci_vs_W0": None}
e0 = None
base_errs = {}
for wname in windows:
    pass
# recompute per-game errors for CI vs W0
def window_errors(wname):
    errs = []
    for S in [2021, 2022]:
        tr = windows[wname](S)
        lr_elo = LinearRegression().fit(tr[["elo_diff"]], tr["home_margin"])
        lr_epa = LinearRegression().fit(tr[EPA_FEATS], tr["home_margin"])
        sub = val[val.season == S].copy()
        ens = (0.4*lr_elo.predict(sub[["elo_diff"]]) + 0.5*lr_epa.predict(sub[EPA_FEATS])
               + 0.1*sub["pred_gbm_m"].values)
        errs.append(np.abs(ens - sub["home_margin"].values))
    return np.concatenate(errs)
errW0 = window_errors("W0_frozen_2018_2020")
for wname in windows:
    e = window_errors(wname)
    win_res[wname]["ci_vs_W0"] = boot_ci(errW0, e) if wname != "W0_frozen_2018_2020" else [0.0, 0.0]
    win_res[wname]["delta_vs_W0"] = float(errW0.mean() - e.mean())
res["windows"] = win_res
for wname, d in win_res.items():
    print("B: %s MAE=%.4f dW0=%+.4f CI=%s %s" % (wname, d["MAE"], d["delta_vs_W0"],
        tuple(round(x,4) for x in d["ci_vs_W0"]), {k: round(v["MAE"],3) for k,v in d["per_season"].items()}))

# ---------- D. Segment analysis ----------
def seg(df, name):
    return {"n": len(df), "V1": float(df["v1_err"].mean()) if len(df) else None,
            "mkt": float(df["mkt_err"].mean()) if len(df) else None,
            "delta": float(df["v1_err"].mean()-df["mkt_err"].mean()) if len(df) else None}
segs = {}
segs["weeks_1_4"] = seg(val[val.week<=4], "w14"); segs["weeks_5_9"] = seg(val[val.week.between(5,9)], "w59")
segs["weeks_10_18"] = seg(val[val.week>=10], "w1018")
segs["home_fav"] = seg(val[val.spread_line>0], "hf"); segs["home_dog"] = seg(val[val.spread_line<0], "hd")
segs["road_fav"] = seg(val[val.spread_line<0], "rf"); segs["road_dog"] = seg(val[val.spread_line>0], "rd")
av = val.spread_line.abs()
segs["spread_0_3"] = seg(val[av<3], "s03"); segs["spread_3_7"] = seg(val[av.between(3,7)], "s37")
segs["spread_7p"] = seg(val[av>7], "s7p")
segs["div"] = seg(val[val.div_game==1], "div"); segs["nondiv"] = seg(val[val.div_game==0], "nondiv")
segs["2021"] = seg(val[val.season==2021], "2021"); segs["2022"] = seg(val[val.season==2022], "2022")
res["segments"] = segs
for k, d in segs.items():
    print("D: %-12s n=%3d V1=%.3f mkt=%.3f d=%+.3f" % (k, d["n"], d["V1"], d["mkt"], d["delta"]))

# ---------- E. Edge buckets ----------
val["edge"] = val["ens_margin"] - val["spread_line"]
val["cover_margin"] = val["home_margin"] - val["spread_line"]  # >0 home covers
def ats(sub):
    n = len(sub); pushes = int((sub["cover_margin"]==0).sum())
    dec = sub[sub["cover_margin"]!=0]
    w = int((((sub["edge"]>0)&(sub["cover_margin"]>0))|((sub["edge"]<0)&(sub["cover_margin"]<0))).sum())
    l = len(dec) - w
    wp = w/len(dec) if len(dec) else None
    return {"n": n, "W": w, "L": l, "pushes": pushes, "winpct": wp}
buckets = {"e_0_1": val[val.edge.abs()<1], "e_1_2": val[val.edge.abs().between(1,2)],
           "e_2_3": val[val.edge.abs().between(2,3)], "e_3_4": val[val.edge.abs().between(3,4)],
           "e_4p": val[val.edge.abs()>=4]}
eb = {}
for k, sub in buckets.items():
    a = ats(sub)
    a["mean_abs_model_err"] = float(sub["v1_err"].mean())
    eb[k] = a
op = val[val.edge.abs()>=3.0]
eb["operating_ge3"] = ats(op)
res["edge_buckets"] = eb
for k, a in eb.items():
    print("E: %-12s n=%3d %d-%d-%d winpct=%s mean|err|=%.3f" % (k, a["n"], a["W"], a["L"], a["pushes"],
        ("%.3f"%a["winpct"]) if a["winpct"] else None, a.get("mean_abs_model_err", float('nan'))))

# ---------- C. ELO-EPA correlations (validation) ----------
res["elo_epa_corr"] = {"pred_corr": float(val["pred_elo"].corr(val["pred_epa_m"])),
    "err_corr": float((val["pred_elo"]-val["home_margin"]).corr(val["pred_epa_m"]-val["home_margin"]))}
print("C: ELO-EPA pred corr=%.3f err corr=%.3f" % (res["elo_epa_corr"]["pred_corr"], res["elo_epa_corr"]["err_corr"]))

json.dump(res, open(OUT+"results_validation.json","w"), indent=1)
print("saved", OUT+"results_validation.json")
