#!/usr/bin/env python3
"""Build the 003A (receptions) feature table. DATA PREP ONLY. No fitting.

Base: experiments/props_experiment_002/data/extended_features_2018_2024.parquet
(002 table, carries families B,C,D1,D2,E,F,J,L,O,P,Q, qb_ctx, ctx, oppd,
envs, envf, pace, inj, exp, snap, rq/rq_ngs, rec2). This script ADDS the
003A-specific columns per PREREGISTRATION.md section 3:

  - g_targets, g_receptions : actual game targets/receptions from pbp
    (complete_pass sum per receiver_player_name = receptions)
  - trail_receptions_ewma   : M0 baseline, EWMA hl=3, max 16, most-recent-first,
    strictly prior (season, week) over the player's receiving-market base rows
  - ngs_*_trail             : trailing EWMAs of the six NGS receiving fields
    (avg_separation, avg_cushion, avg_intended_air_yards,
    percent_share_of_intended_air_yards, avg_expected_yac,
    avg_yac_above_expectation), per player (ukey), strictly prior NGS weeks,
    hl=3, max 16. TRAILING ONLY per the as-of discipline.

Conventions: NaN -> 0 for undefined rates/shares; trail_games preserved.
Output: experiments/props_experiment_003_market_expansion/003A_receptions/
        data/features_003A_2018_2024.parquet

Validation checks run on TRAIN+DEV ONLY. Test slice built blind.
"""
import os
import re

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
E02 = os.path.join(REPO, "experiments/props_experiment_002")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion/003A_receptions")
DATA = os.path.join(EXP, "data")
os.makedirs(DATA, exist_ok=True)

HALF_LIFE = 3.0
MAX_TRAIL = 16


def ukey(name):
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


def ewma(v, hl=HALF_LIFE):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / hl)  # v most-recent-first
    return float(np.sum(w * v) / np.sum(w))


def main():
    base = pd.read_parquet(f"{E02}/data/extended_features_2018_2024.parquet")
    print(f"base 002 table: {base.shape}", flush=True)
    rec = base[base["market"] == "receiving_yards"].copy()
    rec = rec.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    print(f"receiving rows: {len(rec)}", flush=True)
    rec["row_id"] = np.arange(len(rec))
    rec["pukey"] = rec["player_name"].map(ukey) + "|" + rec["team"]
    rec["nukey"] = rec["player_name"].map(ukey)

    # ===== pbp 2018-2024 REG: per-player-game targets & receptions =====
    pbp = pd.concat([pd.read_parquet(f"{REPO}/data/pbp_{s}.parquet")
                     for s in range(2018, 2025)], ignore_index=True)
    pbp = pbp[pbp["season_type"] == "REG"].copy()
    recv = pbp[pbp["receiver_player_name"].notna()].copy()
    g = recv.groupby(["receiver_player_name", "posteam", "season", "week"],
                     dropna=False)
    pg = g.agg(tg_targets=("receiver_player_name", "size"),
               g_receptions=("complete_pass", "sum")).reset_index()
    pg["pukey"] = pg["receiver_player_name"].map(ukey) + "|" + pg["posteam"]
    pg = pg.drop_duplicates(["pukey", "season", "week"])
    n0 = len(rec)
    rec = rec.merge(pg[["pukey", "season", "week", "tg_targets", "g_receptions"]],
                    on=["pukey", "season", "week"], how="left")
    print(f"pbp target/rec merge: {rec['g_receptions'].notna().mean():.4f} "
          f"({n0} rows)", flush=True)

    # ===== trail_receptions_ewma (M0): strictly prior (season, week) =====
    # Note: grouping by player_name mirrors the 001/002 convention
    # (trail_frame_player groups by player_name), so first-initial.last
    # name collisions (e.g. A.Brown = Antonio + A.J. Brown) mix in the
    # trail exactly as they do in 001's trail_targets_ewma. Documented,
    # not changed: 002 has the same inherited property.
    dup = rec.duplicated(["player_name", "season", "week"]).sum()
    print(f"dup player-games (name collisions, same-week rows share trail): "
          f"{dup}")
    trails = []
    for _pn, grp in rec.groupby("player_name", sort=False):
        grp = grp.sort_values(["season", "week"]).reset_index(drop=True)
        out = []
        for i in range(len(grp)):
            prior = grp.iloc[:i]
            prior = prior[prior["season"] * 100 + prior["week"]
                          < grp.loc[i, "season"] * 100 + grp.loc[i, "week"]]
            hist = prior.tail(MAX_TRAIL)["g_receptions"].to_numpy()[::-1]
            out.append({"row_id": int(grp.loc[i, "row_id"]),
                        "trail_receptions_ewma": ewma(hist),
                        "trail_rec_games": int((~np.isnan(
                            prior.tail(MAX_TRAIL)["g_receptions"]
                            .to_numpy())).sum())})
        trails.append(pd.DataFrame(out))
    rec = rec.merge(pd.concat(trails, ignore_index=True), on="row_id",
                    how="left", validate="one_to_one")

    # ===== NGS trailing (strictly prior NGS weeks, per player ukey) =====
    NGS_COLS = ["avg_separation", "avg_cushion", "avg_intended_air_yards",
                "percent_share_of_intended_air_yards", "avg_expected_yac",
                "avg_yac_above_expectation"]
    ngs = pd.read_parquet(f"{E02}/data/ngs_receiving_2018_2024.parquet")
    ngs = ngs[ngs["season_type"] == "REG"].copy()
    ngs["nukey"] = ngs["player_display_name"].map(ukey)
    ngs = ngs.sort_values(["nukey", "season", "week"])
    REN = {"avg_separation": "ngs_avg_separation_trail",
           "avg_cushion": "ngs_avg_cushion_trail",
           "avg_intended_air_yards": "ngs_avg_intended_air_yards_trail",
           "percent_share_of_intended_air_yards":
               "ngs_pct_share_intended_air_yards_trail",
           "avg_expected_yac": "ngs_avg_expected_yac_trail",
           "avg_yac_above_expectation": "ngs_avg_yac_above_expectation_trail"}
    nparts = []
    for _nk, grp in ngs.groupby("nukey", sort=False):
        grp = grp.sort_values(["season", "week"]).reset_index(drop=True)
        rows = []
        for i in range(len(grp)):
            prior = grp.iloc[:i]
            prior = prior[prior["season"] * 100 + prior["week"]
                          < grp.loc[i, "season"] * 100 + grp.loc[i, "week"]]
            hist = prior.tail(MAX_TRAIL)
            d = {"nukey": grp.loc[i, "nukey"],
                 "season": int(grp.loc[i, "season"]),
                 "week": int(grp.loc[i, "week"])}
            for c in NGS_COLS:
                d[REN[c]] = ewma(hist[c].to_numpy()[::-1])
            rows.append(d)
        nparts.append(pd.DataFrame(rows))
    ntrail = pd.concat(nparts, ignore_index=True)
    ntrail = (ntrail.sort_values(["season", "week"])
              .drop_duplicates(["nukey", "season", "week"], keep="last"))
    n0 = len(rec)
    rec = rec.merge(ntrail, on=["nukey", "season", "week"], how="left")
    cov = {c: float(rec[REN[c]].notna().mean()) for c in NGS_COLS}
    print("NGS trailing coverage (all rows): " +
          " ".join(f"{k}={v:.3f}" for k, v in cov.items()), flush=True)

    NEW = (["tg_targets", "g_receptions", "trail_receptions_ewma",
            "trail_rec_games"] + list(REN.values()))
    missing = [c for c in NEW if c not in rec.columns]
    assert not missing, f"missing new cols: {missing}"
    rec[NEW] = rec[NEW].fillna(0)
    rec = rec.drop(columns=["pukey", "nukey", "row_id"])

    out = f"{DATA}/features_003A_2018_2024.parquet"
    rec.to_parquet(out, index=False)
    print(f"wrote {out}: {rec.shape}", flush=True)

    # ---- validation on TRAIN+DEV ONLY ----
    chk = rec[rec["period"].isin(["train", "dev"])]
    print("--- validation (train+dev only) ---")
    print("rows:", len(chk))
    print("nulls in NEW cols:", int(chk[NEW].isna().sum().sum()))
    print("eval population (eligible_hist & played_role):",
          int((chk["eligible_hist"] & chk["played_role"]).sum()))
    ev = chk[(chk["eligible_hist"] == 1) & (chk["played_role"] == 1)]
    print("eval rows with trail_targets_ewma>0:",
          int((ev["trail_targets_ewma"] > 0).sum()), "/", len(ev))
    print("eval rows with g_receptions merged:",
          int(ev["g_receptions"].notna().sum()), "/", len(ev))
    print("M0 baseline MAE (train+dev eval):",
          float(np.mean(np.abs(ev["g_receptions"] -
                               ev["trail_receptions_ewma"]))))
    print("period counts:", rec["period"].value_counts().to_dict())
    print("eval by period:")
    print(rec[(rec["eligible_hist"] == 1) & (rec["played_role"] == 1)]
          .groupby("period").size().to_string())


if __name__ == "__main__":
    main()
