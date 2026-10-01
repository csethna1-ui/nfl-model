"""
Experiment 010 — Historical Inactives (information-timing measurement).
Frozen protocol: experiments/experiment_010_historical_inactives/PREREGISTRATION.md
(FROZEN, approved by Cale 2026-10-01).

ONE variable: signed gameday inactive burden (trailing-4-week snap-share weighted).
ONE coefficient: OLS of V1 residual on BURDEN + intercept, fit on 2021-2022 dev.
ONE locked application: 2023-2025 test, single pass.
Primary: dMAE = MAE(V1) - MAE(V1 + beta*BURDEN), 95% paired CI. Bar: >=0.15 and CI excludes 0.

Set EXP010_SMOKE=1 to run dev-side burden build + coverage assertion only
(no coefficient fit, no test touch).
"""
import os, sys, json, re
import numpy as np
import pandas as pd
import nfl_data_py as nfl

SMOKE = os.environ.get("EXP010_SMOKE") == "1"
EXP_DIR = os.path.expanduser("~/workspace/nfl-model/experiments/experiment_010_historical_inactives")
DATA = os.path.expanduser("~/workspace/nfl-model/data")
DEV_SEASONS = [2021, 2022]
TEST_SEASONS = [2023, 2024, 2025]
# (season, week, team) team-games with missing INA rows -> drop the whole game, no imputation
EXCLUDED_TG = {(2021, 16, "LAC"), (2025, 1, "NYG"), (2025, 1, "WAS")}

OFF_POS = {"QB", "RB", "FB", "WR", "TE", "C", "G", "T", "OT", "OG", "OL", "HB"}
DEF_POS = {"DE", "DT", "NT", "EDGE", "LB", "ILB", "OLB", "MLB", "CB", "S", "SS", "FS", "NB", "DB", "SAF", "DL"}

def norm_name(n):
    n = str(n).lower().strip()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\.?$", "", n).strip()
    n = n.replace(".", "").replace("'", "").replace("-", " ")
    return re.sub(r"\s+", " ", n)

def trailing_window(season, week):
    out = []
    s, w = season, week - 1
    while len(out) < 4:
        if w < 1:
            s -= 1
            w = 17 if s == 2020 else 18
        out.append((s, w))
        w -= 1
    return out

print("== loading games ==", flush=True)
g = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
g = g[(g.game_type == "REG") & (g.season.isin(DEV_SEASONS + TEST_SEASONS))].copy()
assert g["ens_margin"].notna().all(), "V1 margin missing for some 2021-2025 REG games"
sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
sched = sched[(sched.game_type == "REG") & (sched.season.isin(DEV_SEASONS + TEST_SEASONS))][
    ["game_id", "gameday", "weekday"]].copy()
g = g.merge(sched, on="game_id", how="left", validate="m:1")
assert g["gameday"].notna().all(), "gameday missing after schedule join"
g["gameday"] = pd.to_datetime(g["gameday"]).dt.date

print("== pulling nflverse rosters / snaps / injuries ==", flush=True)
seasons_all = [2020, 2021, 2022, 2023, 2024, 2025]
rosters = nfl.import_weekly_rosters([s for s in seasons_all if s >= 2021])
rosters = rosters[rosters.game_type == "REG"].copy()
snaps = nfl.import_snap_counts(seasons_all)
snaps = snaps[snaps.game_type == "REG"].copy()
inj = nfl.import_injuries(DEV_SEASONS + TEST_SEASONS)
print(f"rosters {rosters.shape} snaps {snaps.shape} injuries {inj.shape}", flush=True)

# ---- snap tables: bridge snap rows to GSIS via normalized name within (season,week,team)
rosters["nm"] = rosters["player_name"].map(norm_name)
snaps["nm"] = snaps["player"].map(norm_name)
rr = (rosters.groupby(["season", "week", "team", "nm"])["player_id"]
      .agg(lambda x: x.dropna().iloc[0] if x.notna().any() else None).reset_index())
sm = snaps.merge(rr, on=["season", "week", "team", "nm"], how="left")
snap_match_rate = (sm["player_id"].notna().mean())
print(f"snap rows bridged to GSIS: {snap_match_rate:.4f}", flush=True)

# player snap lookup: (season, week, pid) and fallback (season, week, nm)
snap_pid = {}
snap_nm = {}
team_tot = {}
for _, r_ in sm.iterrows():
    k = (int(r_["season"]), int(r_["week"]))
    off, dfn = float(r_["offense_snaps"] or 0), float(r_["defense_snaps"] or 0)
    tk = (k[0], k[1], r_["team"])
    t = team_tot.get(tk, [0.0, 0.0]); t[0] += off; t[1] += dfn; team_tot[tk] = t
    if pd.notna(r_["player_id"]):
        kk = (k[0], k[1], r_["player_id"])
        v = snap_pid.get(kk, [0.0, 0.0]); v[0] += off; v[1] += dfn; snap_pid[kk] = v
    else:
        kk = (k[0], k[1], r_["nm"])
        v = snap_nm.get(kk, [0.0, 0.0]); v[0] += off; v[1] += dfn; snap_nm[kk] = v

# in-season presence sets (for the coverage diagnostic)
gsis_presence = {(int(r_["season"]), r_["player_id"]) for _, r_ in sm.iterrows() if pd.notna(r_["player_id"])}
nm_presence = {(int(r_["season"]), r_["nm"]) for _, r_ in sm.iterrows()}

ina = rosters[rosters.status == "INA"][
    ["season", "week", "team", "player_id", "player_name", "nm", "position"]].copy()
ina["season"] = ina["season"].astype(int); ina["week"] = ina["week"].astype(int)
print(f"INA rows total: {len(ina)}", flush=True)
print("position values:", sorted(ina["position"].dropna().unique().tolist()), flush=True)

def snap_share(row):
    po = pd_ = to = td = 0.0
    for (ss, ww) in trailing_window(row["season"], row["week"]):
        v = snap_pid.get((ss, ww, row["player_id"]))
        if v is None:
            v = snap_nm.get((ss, ww, row["nm"]), [0.0, 0.0])
        po += v[0]; pd_ += v[1]
        t = team_tot.get((ss, ww, row["team"]), [0.0, 0.0])
        to += t[0]; td += t[1]
    pos = str(row["position"])
    if pos in OFF_POS and to > 0:
        return po / to
    if pos in DEF_POS and td > 0:
        return pd_ / td
    return 0.0

ina["share"] = ina.apply(snap_share, axis=1)

# ---- coverage assertion on DEV (frozen data-availability gate)
dev_ina = ina[ina.season.isin(DEV_SEASONS)].copy()
dev_ina["linked"] = [(s_, p_) in gsis_presence or (s_, n_) in nm_presence
                     for s_, p_, n_ in zip(dev_ina["season"], dev_ina["player_id"], dev_ina["nm"])]
link_rate = dev_ina["linked"].mean()
unlinked = dev_ina[~dev_ina["linked"]]
print(f"DEV INA rows: {len(dev_ina)}, linked to snap data (GSIS or name): {link_rate:.4f}", flush=True)
print(f"DEV INA rows with zero in-season snap presence: {len(unlinked)} "
      f"({len(unlinked)/len(dev_ina):.4f})", flush=True)
# variant-name miss diagnostic: fuzzy-check unlinked names against snap names
from difflib import get_close_matches
snap_names_by_season = {}
for (s_, n_) in nm_presence:
    snap_names_by_season.setdefault(s_, set()).add(n_)
variant_like = 0
for _, r_ in unlinked.iterrows():
    cands = get_close_matches(r_["nm"], list(snap_names_by_season.get(r_["season"], [])), n=1, cutoff=0.85)
    if cands:
        variant_like += 1
print(f"unlinked rows resembling a snap-data name (possible variant miss): {variant_like}", flush=True)
coverage = 1.0 - variant_like / len(dev_ina)
print(f"effective coverage (computable share): {coverage:.4f}", flush=True)
assert coverage >= 0.99, f"COVERAGE GATE FAILED: {coverage:.4f} < 0.99 — STOPPING, test untouched"
print("COVERAGE GATE PASSED", flush=True)

if SMOKE:
    print("SMOKE DONE — no coefficient fit, test untouched.", flush=True)
    sys.exit(0)

# ---- burden per team-game, signed away-home
burden_tg = ina.groupby(["season", "week", "team"], as_index=False)["share"].sum()
burden_tg.rename(columns={"share": "burden"}, inplace=True)
# diagnostic: non-excluded team-games with zero INA rows
tg_all = g[["season", "week", "home_team", "away_team"]].copy()
have = set(zip(burden_tg.season.astype(int), burden_tg.week.astype(int), burden_tg.team))
zero_tg = []
for _, r_ in tg_all.iterrows():
    for t_ in (r_["home_team"], r_["away_team"]):
        if (int(r_["season"]), int(r_["week"]), t_) not in EXCLUDED_TG and \
           (int(r_["season"]), int(r_["week"]), t_) not in have:
            zero_tg.append((int(r_["season"]), int(r_["week"]), t_))
print(f"non-excluded team-games with zero INA rows: {len(zero_tg)} {zero_tg[:5]}", flush=True)

bmap = {(int(r.season), int(r.week), r.team): r.burden for r in burden_tg.itertuples()}
g["burden_home"] = [bmap.get((int(r.season), int(r.week), r.home_team), 0.0) for r in g.itertuples()]
g["burden_away"] = [bmap.get((int(r.season), int(r.week), r.away_team), 0.0) for r in g.itertuples()]
g["BURDEN"] = g["burden_away"] - g["burden_home"]
g["excluded"] = [(int(r.season), int(r.week), r.home_team) in EXCLUDED_TG or
                 (int(r.season), int(r.week), r.away_team) in EXCLUDED_TG for r in g.itertuples()]
print(f"games excluded (missing INA team-game): {g['excluded'].sum()}", flush=True)
a = g[~g["excluded"]].copy()
a["resid"] = a["home_margin"] - a["ens_margin"]
dev = a[a.season.isin(DEV_SEASONS)].copy()
test = a[a.season.isin(TEST_SEASONS)].copy()
print(f"dev n={len(dev)} test n={len(test)}", flush=True)
print("BURDEN descriptives (dev):", dev["BURDEN"].describe()[["mean","std","min","max"]].to_dict(), flush=True)

# ---- ONE coefficient: OLS resid ~ BURDEN + intercept on dev
X = np.column_stack([np.ones(len(dev)), dev["BURDEN"].to_numpy()])
y = dev["resid"].to_numpy()
coef, *_ = np.linalg.lstsq(X, y, rcond=None)
alpha, beta = float(coef[0]), float(coef[1])
yhat = X @ coef
ss_res = ((y - yhat) ** 2).sum(); ss_tot = ((y - y.mean()) ** 2).sum()
r2 = 1 - ss_res / ss_tot
n_, p_ = len(dev), 2
se_beta = float(np.sqrt(ss_res / (n_ - p_) * np.linalg.inv(X.T @ X)[1, 1]))
print(f"DEV FIT: alpha={alpha:.4f} beta={beta:.4f} se(beta)={se_beta:.4f} R2={r2:.4f}", flush=True)

# ---- ONE locked application to test
test = test.copy()
test["adj"] = test["ens_margin"] + beta * test["BURDEN"]
test["d"] = test["resid"].abs() - (test["home_margin"] - test["adj"]).abs()
dmae = float(test["d"].mean())
se = float(test["d"].std(ddof=1) / np.sqrt(len(test)))
ci_lo, ci_hi = dmae - 1.96 * se, dmae + 1.96 * se
mae_v1 = float(test["resid"].abs().mean())
mae_adj = float((test["home_margin"] - test["adj"]).abs().mean())
print(f"TEST: n={len(test)} MAE(V1)={mae_v1:.4f} MAE(adj)={mae_adj:.4f} "
      f"dMAE={dmae:.4f} 95%CI=({ci_lo:.4f},{ci_hi:.4f})", flush=True)
verdict = "PASS" if (dmae >= 0.15 and ci_lo > 0) else "NULL"
print(f"VERDICT: {verdict} (bar: dMAE>=0.15 and CI excludes 0)", flush=True)

# ---- S1: known-Friday-Out vs new-after-Friday decomposition (test set, descriptive)
sched_dt = sched.copy()
sched_dt["gameday"] = pd.to_datetime(sched_dt["gameday"])
def final_report_cutoff(gd, wd):
    gd = pd.Timestamp(gd)
    delta = 1 if wd == "Thursday" else 2
    friday = (gd - pd.Timedelta(days=delta)).tz_localize("US/Eastern")
    return friday + pd.Timedelta(hours=23, minutes=59)
# build cutoff per (season, week, team) from that team's game
sched_full = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
sched_full = sched_full[(sched_full.game_type == "REG") & (sched_full.season.isin(DEV_SEASONS + TEST_SEASONS))]
cutoff_map = {}
for r_ in sched_full.itertuples():
    gd = pd.Timestamp(r_.gameday)
    for t_ in (r_.home_team, r_.away_team):
        cutoff_map[(int(r_.season), int(r_.week), t_)] = final_report_cutoff(gd, r_.weekday)
inj["dm_et"] = pd.to_datetime(inj["date_modified"], utc=True).dt.tz_convert("US/Eastern")
inj["cutoff"] = inj.apply(lambda r_: cutoff_map.get((int(r_["season"]), int(r_["week"]), r_["team"])), axis=1)
inj_pre = inj[inj["dm_et"] <= inj["cutoff"]].copy()
inj_pre = inj_pre.sort_values("dm_et").groupby(["season", "week", "team", "gsis_id"], as_index=False).tail(1)
out_friday = set(zip(inj_pre[inj_pre.report_status == "Out"]["season"].astype(int),
                     inj_pre[inj_pre.report_status == "Out"]["week"].astype(int),
                     inj_pre[inj_pre.report_status == "Out"]["team"],
                     inj_pre[inj_pre.report_status == "Out"]["gsis_id"]))
ina_test = ina[ina.season.isin(TEST_SEASONS)].copy()
ina_test["known_friday_out"] = [(int(r.season), int(r.week), r.team, r.player_id) in out_friday
                                for r in ina_test.itertuples()]
frac_known = float(ina_test["known_friday_out"].mean())
print(f"S1/S2: test INA rows already Out on final Friday report: {frac_known:.4f} "
      f"({int(ina_test['known_friday_out'].sum())}/{len(ina_test)})", flush=True)
ina_test["share_known"] = ina_test["share"] * ina_test["known_friday_out"]
ina_test["share_new"] = ina_test["share"] * (~ina_test["known_friday_out"])
bt = ina_test.groupby(["season", "week", "team"], as_index=False)[["share_known", "share_new"]].sum()
bmap_k = {(int(r.season), int(r.week), r.team): r.share_known for r in bt.itertuples()}
bmap_n = {(int(r.season), int(r.week), r.team): r.share_new for r in bt.itertuples()}
test["BURDEN_known"] = [bmap_k.get((int(r.season), int(r.week), r.away_team), 0.0) -
                        bmap_k.get((int(r.season), int(r.week), r.home_team), 0.0) for r in test.itertuples()]
test["BURDEN_new"] = [bmap_n.get((int(r.season), int(r.week), r.away_team), 0.0) -
                      bmap_n.get((int(r.season), int(r.week), r.home_team), 0.0) for r in test.itertuples()]
def uni_slope(x, y):
    X1 = np.column_stack([np.ones(len(x)), x])
    c, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ c
    se1 = float(np.sqrt((resid ** 2).sum() / (len(x) - 2) * np.linalg.inv(X1.T @ X1)[1, 1]))
    return float(c[1]), se1, float(np.corrcoef(x, y)[0, 1])
s1 = {}
for name, col in [("known_friday_out", "BURDEN_known"), ("new_after_friday", "BURDEN_new"), ("total", "BURDEN")]:
    b_, se_, corr_ = uni_slope(test[col].to_numpy(), test["resid"].to_numpy())
    s1[name] = {"slope": b_, "se": se_, "ci": [b_ - 1.96 * se_, b_ + 1.96 * se_], "corr": corr_,
                "mean_abs": float(test[col].abs().mean())}
    print(f"S1 {name}: slope={b_:.4f} se={se_:.4f} corr={corr_:.4f} mean|.|={s1[name]['mean_abs']:.4f}", flush=True)
frac_games_surprise = float((test["BURDEN_new"].abs() > 1e-9).mean())
print(f"S2: test games with nonzero new-after-Friday burden: {frac_games_surprise:.4f}", flush=True)
print("S2 BURDEN distribution (test):", test["BURDEN"].describe()[["mean","std","min","25%","50%","75%","max"]].to_dict(), flush=True)

# ---- S3: position groups (test, descriptive)
POS2GRP = {}
for p_ in OFF_POS:
    POS2GRP[p_] = "QB" if p_ == "QB" else ("OL" if p_ in {"C","G","T","OT","OG","OL"} else "SKILL")
for p_ in DEF_POS:
    POS2GRP[p_] = "FRONT7" if p_ in {"DE","DT","NT","EDGE","LB","ILB","OLB","MLB","DL"} else "DB"
ina_test["grp"] = ina_test["position"].map(POS2GRP).fillna("ST")
s3 = {}
for grp_ in ["QB", "OL", "SKILL", "FRONT7", "DB", "ST"]:
    sub = ina_test[ina_test.grp == grp_]
    s3[grp_] = {"n_ina_rows": int(len(sub)), "total_share": float(sub["share"].sum()),
                "mean_share": float(sub["share"].mean()) if len(sub) else 0.0}
    print(f"S3 {grp_}: n={s3[grp_]['n_ina_rows']} total_share={s3[grp_]['total_share']:.3f}", flush=True)

# ---- S4: market-gap exploratory (undated spread_line; 004/009 caveat applies)
mae_mkt = float((test["home_margin"] - test["spread_line"]).abs().mean())
gap_v1 = mae_v1 - mae_mkt
gap_adj = mae_adj - mae_mkt
closed = (gap_v1 - gap_adj) / gap_v1 if gap_v1 != 0 else float("nan")
print(f"S4: MAE(V1)={mae_v1:.4f} MAE(adj)={mae_adj:.4f} MAE(market, undated)={mae_mkt:.4f}", flush=True)
print(f"S4: V1-vs-market gap={gap_v1:.4f}; share plausibly explained by inactive timing: {closed:.3f} (SUGGESTIVE ONLY)", flush=True)

results = {
    "dev_n": len(dev), "test_n": len(test),
    "games_excluded": int(g["excluded"].sum()),
    "coverage_dev": float(coverage), "snap_gsis_match_rate": float(snap_match_rate),
    "non_excluded_zero_ina_teamgames": len(zero_tg),
    "alpha": alpha, "beta": beta, "se_beta": se_beta, "r2_dev": r2,
    "mae_v1": mae_v1, "mae_adj": mae_adj, "dmae": dmae,
    "ci95": [ci_lo, ci_hi], "bar": 0.15, "verdict": verdict,
    "s1": s1, "frac_known_friday_out": frac_known,
    "frac_games_nonzero_new": frac_games_surprise,
    "s3": s3, "s4": {"mae_market_undated": mae_mkt, "gap_v1": gap_v1,
                     "gap_adj": gap_adj, "share_plausibly_explained": closed},
}
with open(f"{EXP_DIR}/results.json", "w") as f:
    json.dump(results, f, indent=2)
print("wrote results.json", flush=True)
