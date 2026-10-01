#!/usr/bin/env python3
"""Build the 003D (anytime TD) feature table.

DATA PREP ONLY. No model fitting of any kind.

Base: experiments/props_experiment_002/data/extended_features_2018_2024.parquet
(frozen 002 table). Population: position in {RB, WRTE} (one row per
player-game already -- market is determined by position in the 001/002
build). eligible_hist / played_role / period come through unchanged.

Adds the 003D-preregistered derivations from in-house pbp (all trailing,
strictly prior rows, same as-of discipline as 001/002):
  - td_binary: 1{rushing_tds + receiving_tds > 0} per player-game, from pbp
    (run plays: rusher + touchdown==1; pass plays: receiver + touchdown==1;
    return/special-teams TDs excluded by construction).
  - trail_td_ewma + wsum: trailing EWMA of td_binary (hl=3, max 16) and the
    EWMA weight sum, over base rows (predictable games only), per player.
  - trail_inside10_carries_ewma / trail_inside10_targets_ewma:
    carries/targets with yardline_100 <= 10.
  - trail_endzone_targets_ewma: targets with air_yards >= yardline_100.
  - opp_rz_td_rate_allowed_trail: trailing EWMA of the opponent's red-zone
    (yardline_100 <= 20) TD rate allowed per defensive play faced.
  - NGS receiving: rq_ngs_cushion, rq_ngs_intended_air_yards (trailing;
    rq_ngs_separation already in the 002 table).
  - NGS rushing: ruq_ngs_efficiency, ruq_ngs_ryoe_per_att (trailing;
    keyless import_ngs_data pull, cached locally).
  - M0: shrinkage estimator M0 = (wsum*td_ewma + k*pos_base)/(wsum+k),
    k=4 pseudo-games, pos_base = position (RB/WRTE) base rate on TRAIN
    evaluated rows. No-history rows -> pos_base.

Output: data/003d_features_2018_2024.parquet, data/feature_audit.csv
"""
import os
import re

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO,
                   "experiments/props_experiment_003_market_expansion/003D_anytime_td")
DATA = os.path.join(EXP, "data")
E02 = os.path.join(REPO, "experiments/props_experiment_002")

HALF_LIFE = 3.0
MAX_TRAIL = 16
SHRINK_K = 4.0


def ukey(name):
    s = str(name).lower().strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", s)
    s = re.sub(r"\.", " ", s)
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return None
    return f"{toks[0][0]}.{toks[-1]}"


def ewma_parts(v, hl=HALF_LIFE):
    """Return (ewma, weight_sum) of v, most-recent-first, NaN-skipped."""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan, 0.0
    w = 0.5 ** (np.arange(len(v)) / hl)
    return float(np.sum(w * v) / np.sum(w)), float(np.sum(w))


def trail_frame_player(grp, stats, hl=HALF_LIFE):
    """Per-player trailing EWMAs over base rows (strictly prior row_id).
    Also emits <stat>_wsum (EWMA weight sum) for the shrinkage baseline."""
    grp = grp.sort_values("row_id").reset_index(drop=True)
    out = []
    for i in range(len(grp)):
        hist = grp.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
        d = {"row_id": int(grp.loc[i, "row_id"])}
        for c in stats:
            e, w = (ewma_parts(hist[c].to_numpy(), hl)
                    if len(hist) else (np.nan, 0.0))
            d[f"trail_{c}_ewma"] = e
            d[f"trail_{c}_wsum"] = w
        out.append(d)
    return pd.DataFrame(out)


def main():
    base = pd.read_parquet(
        f"{E02}/data/extended_features_2018_2024.parquet")
    print(f"002 table: {base.shape}", flush=True)
    base = base[base["position"].isin(["RB", "WRTE"])].copy()
    print(f"003D population (RB/WRTE): {base.shape}", flush=True)
    assert base.groupby(["player_name", "team", "season", "week"]).size().max() == 1
    base = base.sort_values(["player_name", "season", "week"]).reset_index(drop=True)
    base["row_id"] = np.arange(len(base))
    base["pukey"] = base["player_name"].map(ukey) + "|" + base["team"]

    # ================= pbp 2018-2024 (REG) =================
    pbp = pd.concat(
        [pd.read_parquet(f"{REPO}/data/pbp_{s}.parquet") for s in range(2018, 2025)],
        ignore_index=True)
    pbp = pbp[pbp["season_type"] == "REG"].copy()
    print(f"pbp REG 2018-2024: {len(pbp)}", flush=True)

    # ---- per-player-game TDs and opportunity depth ----
    rus = pbp[pbp["rusher_player_name"].notna()].copy()
    rus["is_td"] = (rus["touchdown"] == 1).astype(int)
    rus["is_i10"] = (rus["yardline_100"] <= 10).astype(int)
    g = rus.groupby(["rusher_player_name", "posteam", "season", "week"],
                    dropna=False)
    pg_rush = g.agg(rush_tds=("is_td", "sum"),
                    i10_carries=("is_i10", "sum")).reset_index().rename(
        columns={"rusher_player_name": "player_name", "posteam": "team"})

    recv = pbp[pbp["receiver_player_name"].notna()].copy()
    recv["is_td"] = (recv["touchdown"] == 1).astype(int)
    recv["is_i10"] = (recv["yardline_100"] <= 10).astype(int)
    recv["is_ez"] = (recv["air_yards"] >= recv["yardline_100"]).fillna(False).astype(int)
    g = recv.groupby(["receiver_player_name", "posteam", "season", "week"],
                     dropna=False)
    pg_recv = g.agg(rec_tds=("is_td", "sum"),
                    i10_targets=("is_i10", "sum"),
                    ez_targets=("is_ez", "sum")).reset_index().rename(
        columns={"receiver_player_name": "player_name", "posteam": "team"})

    pg = (pg_rush.merge(pg_recv, on=["player_name", "team", "season", "week"],
                        how="outer").fillna(0))
    for c in ["rush_tds", "rec_tds", "i10_carries", "i10_targets", "ez_targets"]:
        pg[c] = pg[c].astype(int)
    pg["td_binary"] = ((pg["rush_tds"] + pg["rec_tds"]) > 0).astype(int)
    base = base.merge(
        pg[["player_name", "team", "season", "week", "rush_tds", "rec_tds",
            "td_binary", "i10_carries", "i10_targets", "ez_targets"]],
        on=["player_name", "team", "season", "week"], how="left")
    for c in ["rush_tds", "rec_tds", "td_binary", "i10_carries",
              "i10_targets", "ez_targets"]:
        base[c] = base[c].fillna(0).astype(int)
    print(f"pbp player-game merge: td rows matched "
          f"{(base['rush_tds'] + base['rec_tds'] > 0).sum()} player-games with TDs",
          flush=True)

    # ---- trailing opportunity + TD history (per player, base rows) ----
    P1 = ["td_binary", "i10_carries", "i10_targets", "ez_targets"]
    t1 = (base.groupby("player_name", group_keys=False)
          .apply(lambda g: trail_frame_player(g, P1), include_groups=False)
          .reset_index(drop=True))
    base = base.merge(t1, on="row_id", how="left", validate="one_to_one")
    base = base.rename(columns={
        "trail_i10_carries_ewma": "trail_inside10_carries_ewma",
        "trail_i10_targets_ewma": "trail_inside10_targets_ewma",
        "trail_ez_targets_ewma": "trail_endzone_targets_ewma",
    })
    print("player trailing loops done", flush=True)

    # ---- opponent red-zone defense (trailing, per team, all REG games) ----
    rz = pbp[(pbp["yardline_100"] <= 20) & pbp["defteam"].notna()].copy()
    g = rz.groupby(["defteam", "season", "week"], dropna=False)
    team_rz = g.agg(rz_plays=("touchdown", "size"),
                    rz_tds=("touchdown", "sum")).reset_index().rename(
        columns={"defteam": "team"})
    team_rz["rz_td_rate"] = team_rz["rz_tds"] / team_rz["rz_plays"]
    team_rz = team_rz.sort_values(["team", "season", "week"]).reset_index(drop=True)
    team_rz["_trow"] = np.arange(len(team_rz))
    parts = []
    for _tm, grp in team_rz.groupby("team", sort=False):
        grp = grp.sort_values("_trow").reset_index(drop=True)
        rows = []
        for i in range(len(grp)):
            hist = grp.iloc[max(0, i - MAX_TRAIL):i].iloc[::-1]
            e, _ = (ewma_parts(hist["rz_td_rate"].to_numpy())
                    if len(hist) else (np.nan, 0.0))
            rows.append({"_trow": int(grp.loc[i, "_trow"]),
                         "opp_rz_td_rate_allowed_trail": e})
        parts.append(pd.DataFrame(rows))
    rz_trail = team_rz[["_trow", "team", "season", "week"]].merge(
        pd.concat(parts, ignore_index=True), on="_trow", how="left")
    base = base.merge(
        rz_trail[["team", "season", "week",
                  "opp_rz_td_rate_allowed_trail"]].rename(
            columns={"team": "opponent"}),
        on=["opponent", "season", "week"], how="left",
        validate="many_to_one")
    print(f"opp RZ defense merge rate: "
          f"{base['opp_rz_td_rate_allowed_trail'].notna().mean():.4f}", flush=True)

    # ---- NGS receiving: cushion + intended air yards (trailing) ----
    ngs = pd.read_parquet(f"{E02}/data/ngs_receiving_2018_2024.parquet")
    ngs = ngs[ngs["season_type"] == "REG"].copy()
    ngs["nukey"] = (ngs["player_display_name"].map(ukey) + "|" +
                    ngs["team_abbr"])
    ngs = (ngs.sort_values("week")
           .drop_duplicates(["nukey", "season", "week"], keep="last"))
    base = base.merge(
        ngs[["nukey", "season", "week", "avg_cushion",
             "avg_intended_air_yards"]].rename(
            columns={"nukey": "pukey", "avg_cushion": "cush_g",
                     "avg_intended_air_yards": "iay_g"}),
        on=["pukey", "season", "week"], how="left")
    print(f"NGS receiving merge rate: {base['cush_g'].notna().mean():.4f}",
          flush=True)

    # ---- NGS rushing: efficiency + rush yards over expected / att ----
    nr_path = f"{DATA}/ngs_rushing_2018_2024.parquet"
    if os.path.exists(nr_path):
        ngr = pd.read_parquet(nr_path)
        print(f"NGS rushing loaded from cache: {ngr.shape}", flush=True)
    else:
        import nfl_data_py as nfl
        ngr = nfl.import_ngs_data("rushing", list(range(2018, 2025)))
        ngr.to_parquet(nr_path, index=False)
        print(f"NGS rushing pulled keyless and cached: {ngr.shape}", flush=True)
    ngr = ngr[ngr["season_type"] == "REG"].copy()
    ngr["nukey"] = (ngr["player_display_name"].map(ukey) + "|" +
                    ngr["team_abbr"])
    ngr = (ngr.sort_values("week")
           .drop_duplicates(["nukey", "season", "week"], keep="last"))
    base = base.merge(
        ngr[["nukey", "season", "week", "efficiency",
             "rush_yards_over_expected_per_att"]].rename(
            columns={"nukey": "pukey", "efficiency": "reff_g",
                     "rush_yards_over_expected_per_att": "rroe_g"}),
        on=["pukey", "season", "week"], how="left")
    print(f"NGS rushing merge rate: {base['reff_g'].notna().mean():.4f}",
          flush=True)

    P2 = ["cush_g", "iay_g", "reff_g", "rroe_g"]
    t2 = (base.groupby("player_name", group_keys=False)
          .apply(lambda g: trail_frame_player(g, P2), include_groups=False)
          .reset_index(drop=True))
    t2 = t2[[c for c in t2.columns if c.endswith("_ewma") or c == "row_id"]]
    base = base.merge(t2, on="row_id", how="left", validate="one_to_one")
    base = base.rename(columns={
        "trail_cush_g_ewma": "rq_ngs_cushion",
        "trail_iay_g_ewma": "rq_ngs_intended_air_yards",
        "trail_reff_g_ewma": "ruq_ngs_efficiency",
        "trail_rroe_g_ewma": "ruq_ngs_ryoe_per_att",
    })
    print("NGS trailing loops done", flush=True)

    # ---- M0: shrinkage estimator (deterministic, no fitting) ----
    ev = base[(base["eligible_hist"] == 1) & (base["played_role"] == 1)]
    pos_base = (ev[ev["period"] == "train"].groupby("position")["td_binary"]
                .mean().to_dict())
    print(f"position base rates (train evaluated): {pos_base}", flush=True)
    base["pos_base"] = base["position"].map(pos_base)
    base["m0_prob"] = ((base["trail_td_binary_wsum"] *
                        base["trail_td_binary_ewma"].fillna(0) +
                        SHRINK_K * base["pos_base"]) /
                       (base["trail_td_binary_wsum"] + SHRINK_K))
    assert base["m0_prob"].between(0, 1).all()

    # ---- validation on train+dev; test counts checked vs prereg §1 ----
    for p in ["train", "dev", "test"]:
        evp = ev[ev["period"] == p]
        print(f"[{p}] evaluated rows={len(evp)} events={int(evp['td_binary'].sum())} "
              f"base_rate={evp['td_binary'].mean():.4f}", flush=True)

    NEW = ["td_binary", "rush_tds", "rec_tds",
           "trail_td_binary_ewma", "trail_td_binary_wsum",
           "trail_inside10_carries_ewma", "trail_inside10_targets_ewma",
           "trail_endzone_targets_ewma", "opp_rz_td_rate_allowed_trail",
           "rq_ngs_cushion", "rq_ngs_intended_air_yards",
           "ruq_ngs_efficiency", "ruq_ngs_ryoe_per_att",
           "pos_base", "m0_prob"]
    base[["trail_inside10_carries_ewma", "trail_inside10_targets_ewma",
          "trail_endzone_targets_ewma", "opp_rz_td_rate_allowed_trail",
          "rq_ngs_cushion", "rq_ngs_intended_air_yards",
          "ruq_ngs_efficiency", "ruq_ngs_ryoe_per_att"]] = base[[
        "trail_inside10_carries_ewma", "trail_inside10_targets_ewma",
        "trail_endzone_targets_ewma", "opp_rz_td_rate_allowed_trail",
        "rq_ngs_cushion", "rq_ngs_intended_air_yards",
        "ruq_ngs_efficiency", "ruq_ngs_ryoe_per_att"]].fillna(0)
    base = base.drop(columns=["pukey", "row_id", "cush_g", "iay_g",
                              "reff_g", "rroe_g"])
    base.to_parquet(f"{DATA}/003d_features_2018_2024.parquet", index=False)
    print(f"wrote 003d_features_2018_2024.parquet: {base.shape}", flush=True)

    # ---- feature audit ----
    fam = {
        "trail_td_binary_ewma": "M0", "pos_base": "M0",
        "trail_rz_targets_ewma": "M1", "trail_rz_carries_ewma": "M1",
        "ruq_goal_line_carries": "M1", "trail_inside10_carries_ewma": "M1",
        "trail_inside10_targets_ewma": "M1",
        "trail_endzone_targets_ewma": "M1",
        "trail_target_share_ewma": "M1", "trail_rush_share_ewma": "M1",
        "trail_air_share_ewma": "M1", "opp2_snap_pct": "M1",
        "envs_team_pts_trail": "M1", "envs_opp_pts_allowed_trail": "M1",
        "opp_rz_td_rate_allowed_trail": "M1", "ctx_elo_adv": "M1",
        "trail_games": "M1",
        "rq_ngs_separation": "M2", "rq_ngs_cushion": "M2",
        "rq_ngs_intended_air_yards": "M2", "ruq_ngs_efficiency": "M2",
        "ruq_ngs_ryoe_per_att": "M2",
    }
    rows = []
    tr = base[base["period"].isin(["train", "dev"])]
    for c, f in fam.items():
        rows.append({
            "feature": c, "rung": f,
            "coverage_train_dev": float(tr[c].notna().mean()),
            "mean_train_dev": float(tr[c].mean()),
            "as_of": "trailing strictly-prior (Friday 18:00 CT safe)",
            "leakage_note": "spread/total/implied excluded everywhere; "
                            "NGS trailing only" if f in ("M1", "M2") else "",
        })
    pd.DataFrame(rows).to_csv(f"{DATA}/feature_audit.csv", index=False)
    print("wrote feature_audit.csv", flush=True)


if __name__ == "__main__":
    main()
