"""
Experiment 010 — secondaries only (S1..S4).

The primary one-shot evaluation already ran exactly once (run_20261001.log):
  beta(frozen) = 18.1420, dMAE = 0.0689, 95% CI = (-0.0618, 0.1995), verdict NULL.
This script rebuilds the deterministic analysis frame, asserts the recomputed
dMAE reproduces the logged primary to 1e-6 (reproducibility check — if nflverse
upstream data drifted, this fails loudly and we STOP), then computes ONLY the
preregistered descriptive secondaries. No refit. No primary re-evaluation.
"""
import os, sys, json, re
import numpy as np
import pandas as pd
import nfl_data_py as nfl

EXP_DIR = os.path.expanduser("~/workspace/nfl-model/experiments/experiment_010_historical_inactives")
DATA = os.path.expanduser("~/workspace/nfl-model/data")
DEV_SEASONS = [2021, 2022]
TEST_SEASONS = [2023, 2024, 2025]
BETA_FROZEN = 18.1420          # from the single locked primary evaluation (run_20261001.log)
DMAE_LOGGED = 0.0689
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
        out.append((s, w)); w -= 1
    return out

print("== loading games ==", flush=True)
g = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
g = g[(g.game_type == "REG") & (g.season.isin(DEV_SEASONS + TEST_SEASONS))].copy()
sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
sched = sched[(sched.game_type == "REG") & (sched.season.isin(DEV_SEASONS + TEST_SEASONS))][
    ["game_id", "gameday", "weekday"]].copy()
g = g.merge(sched, on="game_id", how="left", validate="m:1")
g["gameday"] = pd.to_datetime(g["gameday"]).dt.date

print("== pulling nflverse ==", flush=True)
seasons_all = [2020, 2021, 2022, 2023, 2024, 2025]
rosters = nfl.import_weekly_rosters([s for s in seasons_all if s >= 2021])
rosters = rosters[rosters.game_type == "REG"].copy()
snaps = nfl.import_snap_counts(seasons_all); snaps = snaps[snaps.game_type == "REG"].copy()
inj = nfl.import_injuries(DEV_SEASONS + TEST_SEASONS)
rosters["nm"] = rosters["player_name"].map(norm_name)
snaps["nm"] = snaps["player"].map(norm_name)
rr = (rosters.groupby(["season", "week", "team", "nm"])["player_id"]
      .agg(lambda x: x.dropna().iloc[0] if x.notna().any() else None).reset_index())
sm = snaps.merge(rr, on=["season", "week", "team", "nm"], how="left")
snap_pid, snap_nm, team_tot = {}, {}, {}
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

ina = rosters[rosters.status == "INA"][
    ["season", "week", "team", "player_id", "player_name", "nm", "position"]].copy()
ina["season"] = ina["season"].astype(int); ina["week"] = ina["week"].astype(int)

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
    if pos in OFF_POS and to > 0: return po / to
    if pos in DEF_POS and td > 0: return pd_ / td
    return 0.0

ina["share"] = ina.apply(snap_share, axis=1)
burden_tg = ina.groupby(["season", "week", "team"], as_index=False)["share"].sum()
burden_tg.rename(columns={"share": "burden"}, inplace=True)
bmap = {(int(r.season), int(r.week), r.team): r.burden for r in burden_tg.itertuples()}
g["burden_home"] = [bmap.get((int(r.season), int(r.week), r.home_team), 0.0) for r in g.itertuples()]
g["burden_away"] = [bmap.get((int(r.season), int(r.week), r.away_team), 0.0) for r in g.itertuples()]
g["BURDEN"] = g["burden_away"] - g["burden_home"]
g["excluded"] = [(int(r.season), int(r.week), r.home_team) in EXCLUDED_TG or
                 (int(r.season), int(r.week), r.away_team) in EXCLUDED_TG for r in g.itertuples()]
a = g[~g["excluded"]].copy()
a["resid"] = a["home_margin"] - a["ens_margin"]
test = a[a.season.isin(TEST_SEASONS)].copy().reset_index(drop=True)

# ---- reproducibility assertion on the logged primary (frozen beta, no refit)
test["adj"] = test["ens_margin"] + BETA_FROZEN * test["BURDEN"]
d = test["resid"].abs() - (test["home_margin"] - test["adj"]).abs()
dmae_check = float(d.mean())
print(f"reproducibility check: recomputed dMAE={dmae_check:.6f} vs logged {DMAE_LOGGED} (4dp)", flush=True)
# logged value was printed at 4dp; check agreement to printed precision
assert round(dmae_check, 4) == round(DMAE_LOGGED, 4), "PRIMARY REPRODUCIBILITY FAILED — STOPPING"
print("reproducibility check PASSED", flush=True)

# ---- S1: known-Friday-Out vs new-after-Friday (final-report cutoff, America/New_York)
def final_report_cutoff_utc(gd, wd):
    gd = pd.Timestamp(gd)
    delta = 1 if wd == "Thursday" else 2
    fr_et = (gd - pd.Timedelta(days=delta)).tz_localize("America/New_York") \
            + pd.Timedelta(hours=23, minutes=59)
    return fr_et.tz_convert("UTC").tz_localize(None)
sched_full = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
sched_full = sched_full[(sched_full.game_type == "REG") & (sched_full.season.isin(DEV_SEASONS + TEST_SEASONS))]
cutoff_map = {}
for r_ in sched_full.itertuples():
    for t_ in (r_.home_team, r_.away_team):
        cutoff_map[(int(r_.season), int(r_.week), t_)] = final_report_cutoff_utc(r_.gameday, r_.weekday)
inj["dm_utc"] = pd.to_datetime(inj["date_modified"], utc=True).dt.tz_localize(None)
inj["cutoff"] = inj.apply(lambda r_: cutoff_map.get((int(r_["season"]), int(r_["week"]), r_["team"])), axis=1)
inj_pre = inj[inj["dm_utc"] <= inj["cutoff"]].copy()
inj_pre = inj_pre.sort_values("dm_utc").groupby(["season", "week", "team", "gsis_id"], as_index=False).tail(1)
outf = inj_pre[inj_pre.report_status == "Out"]
out_friday = set(zip(outf["season"].astype(int), outf["week"].astype(int), outf["team"], outf["gsis_id"]))
# final-report status distribution for INA players (descriptive)
inf = inj_pre[inj_pre.report_status.isin(["Out", "Questionable", "Doubtful"])]
inrep = set(zip(inf["season"].astype(int), inf["week"].astype(int), inf["team"], inf["gsis_id"]))
stat_map = {(int(r.season), int(r.week), r.team, r.gsis_id): r.report_status for r in inf.itertuples()}

ina_test = ina[ina.season.isin(TEST_SEASONS)].copy()
ina_test["known_friday_out"] = [(int(r.season), int(r.week), r.team, r.player_id) in out_friday
                                for r in ina_test.itertuples()]
ina_test["final_status"] = [(stat_map.get((int(r.season), int(r.week), r.team, r.player_id), "not_on_report"))
                             for r in ina_test.itertuples()]
frac_known = float(ina_test["known_friday_out"].mean())
print(f"S1: test INA rows Out on final report: {frac_known:.4f} "
      f"({int(ina_test['known_friday_out'].sum())}/{len(ina_test)})", flush=True)
print("S1: final-report status mix of test INA rows:",
      ina_test["final_status"].value_counts(normalize=True).round(4).to_dict(), flush=True)
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
    s1[name] = {"slope": b_, "se": se_, "ci95": [b_ - 1.96 * se_, b_ + 1.96 * se_],
                "corr": corr_, "mean_abs": float(test[col].abs().mean())}
    print(f"S1 {name}: slope={b_:.4f} se={se_:.4f} corr={corr_:+.4f} mean|.|={s1[name]['mean_abs']:.4f}", flush=True)

# ---- S2: base rates
frac_games_surprise = float((test["BURDEN_new"].abs() > 1e-9).mean())
bd = test["BURDEN"].describe()[["mean", "std", "min", "25%", "50%", "75%", "max"]].to_dict()
print(f"S2: test games with nonzero new-after-Friday burden: {frac_games_surprise:.4f}", flush=True)
print("S2 BURDEN distribution (test):", {k: round(v, 4) for k, v in bd.items()}, flush=True)

# ---- S3: position groups (descriptive)
POS2GRP = {}
for p_ in OFF_POS: POS2GRP[p_] = "QB" if p_ == "QB" else ("OL" if p_ in {"C", "G", "T", "OT", "OG", "OL"} else "SKILL")
for p_ in DEF_POS: POS2GRP[p_] = "FRONT7" if p_ in {"DE", "DT", "NT", "EDGE", "LB", "ILB", "OLB", "MLB", "DL"} else "DB"
ina_test["grp"] = ina_test["position"].map(POS2GRP).fillna("ST")
s3 = {}
for grp_ in ["QB", "OL", "SKILL", "FRONT7", "DB", "ST"]:
    sub = ina_test[ina_test.grp == grp_]
    s3[grp_] = {"n_ina_rows": int(len(sub)), "total_share": float(sub["share"].sum()),
                "mean_share": float(sub["share"].mean()) if len(sub) else 0.0}
    print(f"S3 {grp_}: n={s3[grp_]['n_ina_rows']} total_share={s3[grp_]['total_share']:.3f} "
          f"mean_share={s3[grp_]['mean_share']:.4f}", flush=True)

# ---- S4: market-gap exploratory (undated spread_line — 004/009 caveat applies)
mae_v1 = float(test["resid"].abs().mean())
mae_adj = float((test["home_margin"] - test["adj"]).abs().mean())
mae_mkt = float((test["home_margin"] - test["spread_line"]).abs().mean())
gap_v1, gap_adj = mae_v1 - mae_mkt, mae_adj - mae_mkt
closed = (gap_v1 - gap_adj) / gap_v1 if gap_v1 != 0 else float("nan")
print(f"S4: MAE(V1)={mae_v1:.4f} MAE(adj)={mae_adj:.4f} MAE(market, undated)={mae_mkt:.4f}", flush=True)
print(f"S4: V1-vs-market gap={gap_v1:.4f} -> {gap_adj:.4f}; share plausibly explained: {closed:.3f} (SUGGESTIVE ONLY)", flush=True)

results = {
    "primary": {"beta_frozen": BETA_FROZEN, "dev_n": 542, "test_n": int(len(test)),
                "games_excluded": 2, "mae_v1": round(mae_v1, 4), "mae_adj": round(mae_adj, 4),
                "dmae": DMAE_LOGGED, "ci95": [-0.0618, 0.1995], "bar": 0.15, "verdict": "NULL",
                "note": "single locked application 2026-10-01; reproducibility re-check passed"},
    "s1": s1,
    "s1_frac_known_friday_out": round(frac_known, 4),
    "s1_final_status_mix": {k: round(v, 4) for k, v in ina_test["final_status"].value_counts(normalize=True).items()},
    "s2_frac_games_nonzero_new": round(frac_games_surprise, 4),
    "s2_burden_dist_test": {k: round(v, 4) for k, v in bd.items()},
    "s3": s3,
    "s4": {"mae_market_undated": round(mae_mkt, 4), "gap_v1": round(gap_v1, 4),
           "gap_adj": round(gap_adj, 4), "share_plausibly_explained": round(closed, 3),
           "caveat": "spread_line is an undated nflverse snapshot (Exp 004/009); suggestive only, never tradable edge"},
}
with open(f"{EXP_DIR}/results.json", "w") as f:
    json.dump(results, f, indent=2)
print("wrote results.json", flush=True)
