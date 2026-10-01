#!/usr/bin/env python3
"""ELO regression diagnostic — Part 1: current-season snapshot, ELO-vs-performance
disagreement, Patriots case study, and preseason-information decomposition.

READ-ONLY diagnostic. Touches nothing in production.
"""
import sys, math, json, pickle
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/hatch/workspace/nfl-model/scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("r03", "/home/hatch/workspace/nfl-model/scripts/03_ratings.py")
r03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r03)

DATA = "/home/hatch/workspace/nfl-model/data"
OUT = "/home/hatch/workspace/nfl-model/experiments/elo_regression_diagnostic"

# ---------- 1. exact current snapshot V1 is using ----------
cur = pd.read_parquet(f"{DATA}/ratings_current_2026_w4.parquet")  # team, elo, off_epa..., def_epa...
# NOTE: data/final_2025_state.pkl is STALE (Sep-11 artifact, not used by current
# production which recomputes from scratch; differs up to ~94 pts). The true
# production 2025 finals are recomputed below via the verified code path and
# overwrite the pkl-sourced column after verification.

# ---------- 2026 W-L / point differential / games played ----------
import nfl_data_py as nfl
s26 = nfl.import_schedules([2026]).copy()
scored = s26[s26["home_score"].notna() & (s26["week"] <= 3)].copy()
print(f"2026 scored games weeks 1-3: {len(scored)}")
rec = {}
for _, g in scored.iterrows():
    h, a = g["home_team"], g["away_team"]
    hs, aws = g["home_score"], g["away_score"]
    for t, pf, pa in ((h, hs, aws), (a, aws, hs)):
        d = rec.setdefault(t, {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "gp": 0})
        d["gp"] += 1; d["pf"] += pf; d["pa"] += pa
        if pf > pa: d["w"] += 1
        elif pf < pa: d["l"] += 1
        else: d["t"] += 1
recdf = pd.DataFrame.from_dict(rec, orient="index").reset_index().rename(columns={"index": "team"})
recdf["wl"] = recdf.apply(lambda r: f"{int(r['w'])}-{int(r['l'])}" + (f"-{int(r['t'])}" if r["t"] else ""), axis=1)
recdf["pt_diff"] = recdf["pf"] - recdf["pa"]
cur = cur.merge(recdf[["team", "wl", "w", "l", "t", "pt_diff", "gp"]], on="team", how="left")

# ---------- ranks ----------
cur["elo_rank"] = cur["elo"].rank(ascending=False, method="min").astype(int)
cur["off_epa_rank"] = cur["off_epa"].rank(ascending=False, method="min").astype(int)
cur["def_epa_rank"] = cur["def_epa"].rank(ascending=True, method="min").astype(int)  # lower allowed = better
cur["net_sr"] = cur["off_sr"] - cur["def_sr"]
cur["net_sr_rank"] = cur["net_sr"].rank(ascending=False, method="min").astype(int)
cur["win_pct"] = (cur["w"] + 0.5 * cur["t"]) / cur["gp"]
cur["wl_rank"] = cur["win_pct"].rank(ascending=False, method="min").astype(int)

# overall current-performance rank: rank-average of exported current-season efficiency metrics only
for c, asc in (("off_epa", False), ("def_epa", True), ("off_sr", False), ("def_sr", True)):
    cur[f"_{c}_r"] = cur[c].rank(ascending=asc, method="min")
cur["perf_rank"] = cur[["_off_epa_r", "_def_epa_r", "_off_sr_r", "_def_sr_r"]].mean(axis=1).rank(method="min").astype(int)

# ---------- 2. disagreements ----------
cur["d_off"] = cur["elo_rank"] - cur["off_epa_rank"]
cur["d_def"] = cur["elo_rank"] - cur["def_epa_rank"]
cur["d_sr"] = cur["elo_rank"] - cur["net_sr_rank"]
cur["d_wl"] = cur["elo_rank"] - cur["wl_rank"]
cur["d_perf"] = cur["elo_rank"] - cur["perf_rank"]
cur["abs_d_perf"] = cur["d_perf"].abs()

# (snapshot tables are written after the decomposition section, once the verified
# production 2025 finals are available)

# ---------- 4. preseason-information decomposition (exact, production methodology) ----------
# Re-run production run_elo on 2018->2026w3, tracking 2026 per-team deltas.
sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
s26u = s26[s26["home_score"].notna()].copy()
sched = sched[sched["season"] != 2026]
cols = [c for c in sched.columns if c in s26u.columns]
games = pd.concat([sched[cols], s26u[cols]], ignore_index=True)
games = games[games["home_score"].notna()].copy()
games = games.sort_values(["season", "week"]).reset_index(drop=True)
games["home_margin"] = games["home_score"] - games["away_score"]

K, HFA, REGRESS = r03.K, r03.HFA_ELO, r03.REGRESS
elos = {}
rows2026 = []
final2025, pre2026 = {}, {}
delta2026 = {}
for (season, week), grp in games.groupby(["season", "week"], sort=True):
    if season > 2026 or (season == 2026 and week > 3):
        break
    if week == 1:
        if season == 2026:
            pre2026 = {t: 1500.0 + (e - 1500.0) * (1 - REGRESS) for t, e in elos.items()}
        for t in list(elos.keys()):
            elos[t] = 1500.0 + (elos[t] - 1500.0) * (1 - REGRESS)
    if season == 2025 and week == games[games["season"] == 2025]["week"].max():
        pass
    updates = {}
    for _, g in grp.iterrows():
        h, a = g["home_team"], g["away_team"]
        he = elos.get(h, 1500.0); ae = elos.get(a, 1500.0)
        diff = he - ae + HFA
        exp_h = 1.0 / (1.0 + 10 ** (-diff / 400.0))
        actual = 1.0 if g["home_margin"] > 0 else (0.5 if g["home_margin"] == 0 else 0.0)
        mm = r03.mov_multiplier(g["home_margin"], diff)
        delta = K * mm * (actual - exp_h)
        updates[h] = updates.get(h, 0.0) + delta
        updates[a] = updates.get(a, 0.0) - delta
        if season == 2026:
            rows2026.append({"team": h, "delta": delta, "opp": a})
            rows2026.append({"team": a, "delta": -delta, "opp": h})
    for t, d in updates.items():
        elos[t] = elos.get(t, 1500.0) + d
        if season == 2026:
            delta2026[t] = delta2026.get(t, 0.0) + d
    if season == 2025:
        # capture final 2025 state after last 2025 week is applied
        if week == games[games["season"] == 2025]["week"].max():
            final2025 = dict(elos)

recomp = pd.DataFrame({"team": list(elos.keys()), "elo_recomputed": list(elos.values())})
chk = cur.merge(recomp, on="team")
maxdiff = (chk["elo"] - chk["elo_recomputed"]).abs().max()
print(f"recompute-vs-production-snapshot max abs diff: {maxdiff:.6f}")
assert maxdiff < 1e-6, "recompute does not match production snapshot!"

chk25 = pd.DataFrame({"team": list(final2025.keys()), "elo_2025_recomp": list(final2025.values())})
pkl_elos = pickle.load(open(f"{DATA}/final_2025_state.pkl", "rb"))["elos"]
chk25["elo_2025_pkl"] = chk25["team"].map(pkl_elos)
print(f"2025-final recomputed vs STALE final_2025_state.pkl max abs diff: "
      f"{(chk25['elo_2025_pkl']-chk25['elo_2025_recomp']).abs().max():.6f} "
      f"(pkl not used by production; recomputed values are authoritative)")

decomp = cur[["team", "elo", "elo_rank"]].copy()
decomp["elo_2025_final"] = decomp["team"].map(final2025)
# overwrite the stale-pkl column with the verified production 2025 finals
cur["elo_2025_final"] = cur["team"].map(final2025)
cur["elo_preseason_2026"] = 1500.0 + (cur["elo_2025_final"] - 1500.0) * (2.0 / 3.0)
cur["elo_change_from_preseason"] = cur["elo"] - cur["elo_preseason_2026"]
# refresh snapshot table with corrected 2025 finals (recompute ranks unchanged)
snap = cur[["team", "elo", "elo_rank", "elo_2025_final", "elo_preseason_2026",
            "elo_change_from_preseason", "wl", "gp", "pt_diff",
            "off_epa", "off_epa_rank", "def_epa", "def_epa_rank",
            "net_sr", "net_sr_rank", "perf_rank",
            "d_off", "d_def", "d_sr", "d_wl", "d_perf"]].copy()
snap["abs_d_perf"] = cur["abs_d_perf"].values
snap.to_csv(f"{OUT}/table_32team_diagnostic.csv", index=False)
snap.sort_values("abs_d_perf", ascending=False).to_csv(
    f"{OUT}/table_32team_sorted_by_disagreement.csv", index=False)
decomp["preseason_2026"] = decomp["team"].map(pre2026)
decomp["delta_2026_games"] = decomp["team"].map(delta2026).fillna(0.0)
# exact additive identity: elo - 1500 = (preseason - 1500) + sum(deltas)
decomp["check"] = (decomp["preseason_2026"] - 1500.0) + decomp["delta_2026_games"] - (decomp["elo"] - 1500.0)
print("decomposition identity max err:", decomp["check"].abs().max())
decomp["preseason_component"] = decomp["preseason_2026"] - 1500.0
decomp["games_component"] = decomp["delta_2026_games"]
decomp["total_dev"] = decomp["elo"] - 1500.0
decomp["preseason_share"] = decomp["preseason_component"] / decomp["total_dev"].replace(0, np.nan)
decomp["games_share"] = decomp["games_component"] / decomp["total_dev"].replace(0, np.nan)
# alternative preseason starting points for context
for name, r in (("half", 0.5), ("two_thirds", 2/3), ("full", 1.0)):
    decomp[f"preseason_alt_{name}"] = 1500.0 + (decomp["elo_2025_final"] - 1500.0) * (1 - r)
decomp.to_csv(f"{OUT}/table_preseason_decomposition.csv", index=False)
print("decomposition table written")
n_pre_dom = ((decomp["preseason_component"].abs() > decomp["games_component"].abs())).sum()
print(f"teams where |preseason component| > |2026-games component|: {n_pre_dom}/32")

# ---------- 3. Patriots case study ----------
ne = snap[snap["team"] == "NE"].iloc[0]
print("\n=== PATRIOTS ===")
print(ne.to_string())
print("\nLeague disagreement distribution (d_perf):")
print(snap["d_perf"].describe().to_string())
print("\nTop 10 by |d_perf|:")
print(snap.sort_values("abs_d_perf", ascending=False)[["team","elo_rank","perf_rank","d_perf","wl"]].head(10).to_string(index=False))
