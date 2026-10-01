#!/usr/bin/env python3
"""Step 37: V2 historical QB value (BLOCKER 1 resolution).

Builds a historically valid QB value generated ONLY from games completed
strictly before the prediction week. QB identity at prediction time is the
scheduled starter (schedules home/away_qb_name, repo pregame convention);
the value is computed from THAT QB's own prior-game history, which travels
with him across mid-season team changes.

Inputs (deterministic composites / recency-weighted expanding means only;
NO fitted coefficients anywhere):
  - PBP 2018-2022: qb_epa per dropback, pass-play qb_epa, cpoe (completions
    only), air_yards, sack rate, qb_hit plays + qb_epa under hits (pressure
    response proxy), QB rushing EPA (scrambles + designed runs via
    rusher_player_name attribution)
  - PFR advstats_week_pass 2018-2022: times_pressured_pct (100% coverage)

Design:
  - Canonical QB key: last-token-lower + "_" + first-initial-lower, suffixes
    (jr/sr/ii/iii/iv/v) stripped. Schedule data quirks handled via explicit
    ALIASES (documented, deterministic data cleaning, not fitting):
    "herbery_j" (schedule typo) -> "herbert_j". "murray_t"
    ("Taysom Kyler Murray", ambiguous) is left unmatched -> NaN (logged).
  - History for pred row (team, season S, pred_week W): all QB games with
    (season < S) OR (season == S AND week < W), ANY team. Strictly before.
  - Recency weighting: games ordered most-recent-first, g = 1..G,
    w_g = 0.5 ** ((g - 1) / HALF_LIFE), HALF_LIFE = 8 games.
    HALF_LIFE is a stated parameter, NOT fitted. Volume enters via the
    per-dropback denominators (weighting by dropbacks too would
    square-count volume since epa_sum is already a game total).
  - Cold start: value exists iff >= MIN_QB_GAMES (4) prior games AND
    >= MIN_QB_DROPBACKS (40) prior dropbacks; else NaN + qb_cold_start = 1.
    Backups degrade the same way: small-sample expanding mean, NaN below
    minimum. No fitted imputation (documented as modeling-stage concern).
  - Composite: qb_value_historical = recency-weighted qb_epa per dropback
    (single, unfitted, transparent). A multi-component composite with honest
    weights is UNRESOLVED -- needs fitted coefficients (equal weighting is
    arbitrary and double-counts: CPOE/pressure/sack outcomes already flow
    into qb_epa). The components are emitted so a future authorized
    experiment can fit weights on a proper validation window.

qb_value_poll (2026-anchored oddsmaker poll) is QUARANTINED: not read here,
kept as placeholder only; see v2_research/qb_value_design.md.

Output: data/v2/qb_value_pred.parquet -- team x season x pred_week,
2018-2022 ONLY (vault 2023-2025 and 2026 never touched).

NO model fitting. NO validation evaluation. Architecture only.
"""
import os
import re

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
V2 = f"{DATA}/v2"
OUT = f"{V2}/qb_value_pred.parquet"

SEASONS = (2018, 2022)  # vault 2023-2025 excluded, 2026 excluded
MAX_WEEK = 22
MIN_QB_GAMES = 4
MIN_QB_DROPBACKS = 40
HALF_LIFE = 8  # games; stated parameter, not fitted

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
# Deterministic data-cleaning aliases (schedule entry quirks found 2026-09-29)
ALIASES = {"herbery_j": "herbert_j"}  # "Justin Herbery" typo in schedules
UNMATCHABLE = {"murray_t"}  # "Taysom Kyler Murray" -- ambiguous, stays NaN


def canon_key(x):
    """Canonical QB key from any name format ('K.Murray', 'C.J. Beathard',
    'Patrick Mahomes', 'Gardner Minshew II'): last alpha token + '_' +
    first char of first token, suffixes stripped."""
    if pd.isna(x):
        return None
    toks = re.findall(r"[a-z]+", str(x).lower())
    toks = [w for w in toks if w not in SUFFIXES]
    if not toks:
        return None
    return f"{toks[-1]}_{toks[0][0]}"


def load_qb_games():
    """Per-QB per-game aggregates from PBP 2018-2022 + PFR pressure."""
    cols = ["game_id", "season", "week", "posteam", "passer_player_name",
            "rusher_player_name", "pass", "qb_dropback", "qb_epa",
            "complete_pass", "cpoe", "air_yards", "sack", "qb_hit",
            "qb_scramble", "rush"]
    frames = []
    for y in range(SEASONS[0], SEASONS[1] + 1):
        d = pd.read_parquet(f"{DATA}/pbp_{y}.parquet", columns=cols)
        frames.append(d[d["week"] <= MAX_WEEK])
    pbp = pd.concat(frames, ignore_index=True)

    # ---- dropback frame: attribute to passer ----
    db = pbp[(pbp["qb_dropback"] == 1)
             & pbp["passer_player_name"].notna()].copy()
    db["qb_key"] = db["passer_player_name"].map(canon_key)
    db = db[db["qb_key"].notna()]
    db["is_pass"] = (db["pass"] == 1).astype(int)
    db["is_comp"] = (db["complete_pass"] == 1).astype(int)
    db["is_sack"] = (db["sack"] == 1).astype(int)
    db["is_hit"] = (db["qb_hit"] == 1).astype(int)
    db["pass_epa"] = db["qb_epa"] * db["is_pass"]
    db["hit_epa"] = db["qb_epa"] * db["is_hit"]
    db["cpoe_nn"] = db["cpoe"].notna().astype(int)
    db["air_nn"] = db["air_yards"].notna().astype(int)
    g = db.groupby(["qb_key", "season", "week", "posteam"], observed=True)
    agg = g.agg(
        n_db=("qb_dropback", "sum"),
        epa_sum=("qb_epa", "sum"),
        n_pass=("is_pass", "sum"),
        pass_epa_sum=("pass_epa", "sum"),
        n_comp=("is_comp", "sum"),
        cpoe_sum=("cpoe", "sum"),
        n_cpoe=("cpoe_nn", "sum"),
        air_sum=("air_yards", "sum"),
        n_air=("air_nn", "sum"),
        n_sack=("is_sack", "sum"),
        n_hit=("is_hit", "sum"),
        hit_epa_sum=("hit_epa", "sum"),
    ).reset_index().rename(columns={"posteam": "qb_team"})

    # ---- rush frame: QB rushing EPA via rusher attribution ----
    ru = pbp[(pbp["rush"] == 1)
             & pbp["rusher_player_name"].notna()].copy()
    ru["qb_key"] = ru["rusher_player_name"].map(canon_key)
    ru = ru[ru["qb_key"].notna()]
    rg = ru.groupby(["qb_key", "season", "week"], observed=True)
    rush = rg.agg(rush_epa_sum=("qb_epa", "sum"),
                  n_rush=("rush", "sum")).reset_index()
    agg = agg.merge(rush, on=["qb_key", "season", "week"], how="left")
    agg[["rush_epa_sum", "n_rush"]] = agg[["rush_epa_sum",
                                           "n_rush"]].fillna(0)

    # ---- PFR pressure (weekly advstats, 2018-2022 full coverage) ----
    pfr_frames = []
    for y in range(SEASONS[0], SEASONS[1] + 1):
        a = pd.read_parquet(f"{DATA}/v2/raw/advstats_week_pass_{y}.parquet")
        pfr_frames.append(a)
    pfr = pd.concat(pfr_frames, ignore_index=True)
    pfr = pfr[pfr["week"] <= MAX_WEEK]
    pfr["qb_key"] = pfr["pfr_player_name"].map(canon_key)
    pfr = pfr[pfr["qb_key"].notna()]
    pm = pfr.groupby(["qb_key", "season", "week"], observed=True).agg(
        pressured_pct=("times_pressured_pct", "first"),
        pfr_team=("team", "first"),
    ).reset_index()
    agg = agg.merge(pm, on=["qb_key", "season", "week"], how="left")
    # timing-sanity: PFR team vs PBP team agreement on matched rows
    matched = agg[agg["pressured_pct"].notna()]
    if len(matched):
        agree = (matched["qb_team"] == matched["pfr_team"]).mean()
        print(f"PFR-PBP team agreement on pressure rows: {agree:.4f} "
              f"(n={len(matched)})")
    agg = agg.drop(columns=["pfr_team"])
    return agg.sort_values(["qb_key", "season", "week"]).reset_index(drop=True)


def recency_weights(n):
    """Deterministic decay weights, most-recent-first: w_g = 0.5 ** ((g-1) /
    HALF_LIFE). Volume enters through the per-dropback denominators in the
    weighted means (weighting by dropbacks as well would square-count volume:
    epa_sum is already a game total)."""
    g = np.arange(1, n + 1)
    return 0.5 ** ((g - 1) / HALF_LIFE)


def qb_value_for_history(hist):
    """hist: QB game rows strictly before pred week, most-recent-first.
    Returns dict of value components (NaN if below cold-start minimum)."""
    n_games = len(hist)
    n_db_tot = float(hist["n_db"].sum())
    base = {"qb_value_n_games": n_games,
            "qb_value_n_dropbacks": n_db_tot}
    if n_games < MIN_QB_GAMES or n_db_tot < MIN_QB_DROPBACKS:
        out = {k: np.nan for k in
               ["qb_value_historical", "qb_pass_epa_db_rw", "qb_cpoe_rw",
                "qb_sack_rate_rw", "qb_hit_epa_db_rw", "qb_rush_epa_db_rw",
                "qb_pressured_pct_rw"]}
        out.update(base)
        out["qb_cold_start"] = 1
        out["qb_prior_teams"] = int(hist["qb_team"].nunique())
        out["qb_team_changed"] = np.nan
        return out
    w = recency_weights(len(hist))
    wsum_db = float((w * hist["n_db"].to_numpy(dtype=float)).sum())

    def wmean(num, den):
        d = float((w * den).sum())
        return float((w * num).sum() / d) if d > 0 else np.nan

    ndb = hist["n_db"].to_numpy(dtype=float)
    out = {
        "qb_value_historical": float((w * hist["epa_sum"].to_numpy()).sum()
                                     / wsum_db) if wsum_db > 0 else np.nan,
        "qb_pass_epa_db_rw": wmean(hist["pass_epa_sum"].to_numpy(),
                                   hist["n_pass"].to_numpy(dtype=float)),
        "qb_cpoe_rw": wmean(hist["cpoe_sum"].to_numpy(),
                            hist["n_cpoe"].to_numpy(dtype=float)),
        "qb_sack_rate_rw": wmean(hist["n_sack"].to_numpy(dtype=float), ndb),
        "qb_hit_epa_db_rw": wmean(hist["hit_epa_sum"].to_numpy(),
                                  hist["n_hit"].to_numpy(dtype=float)),
        "qb_rush_epa_db_rw": wmean(hist["rush_epa_sum"].to_numpy(), ndb),
    }
    pmask = hist["pressured_pct"].notna().to_numpy()
    if pmask.any():
        wp = w[pmask] * ndb[pmask]
        out["qb_pressured_pct_rw"] = float(
            (wp * hist.loc[pmask, "pressured_pct"].to_numpy()).sum()
            / wp.sum())
    else:
        out["qb_pressured_pct_rw"] = np.nan
    out.update(base)
    out["qb_cold_start"] = 0
    out["qb_prior_teams"] = int(hist["qb_team"].nunique())
    out["qb_team_changed"] = np.nan  # filled by caller (needs current team)
    return out


def main():
    os.makedirs(V2, exist_ok=True)
    qb_games = load_qb_games()
    print(f"qb game rows: {qb_games.shape}, distinct QBs: "
          f"{qb_games['qb_key'].nunique()}")
    by_qb = {k: g.sort_values(["season", "week"], ascending=False)
             .reset_index(drop=True)
             for k, g in qb_games.groupby("qb_key", observed=True)}

    # ---- pred-week grain: team x season x week from schedules ----
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    sched = sched[(sched["season"] >= SEASONS[0])
                  & (sched["season"] <= SEASONS[1])
                  & (sched["week"] <= MAX_WEEK)
                  & sched["home_score"].notna()].copy()
    rows = []
    for _, g in sched.iterrows():
        rows.append({"team": g["home_team"], "season": g["season"],
                     "week": g["week"], "qb_sched": g.get("home_qb_name")})
        rows.append({"team": g["away_team"], "season": g["season"],
                     "week": g["week"], "qb_sched": g.get("away_qb_name")})
    pred = pd.DataFrame(rows).sort_values(
        ["team", "season", "week"]).reset_index(drop=True)
    pred["qb_key_raw"] = pred["qb_sched"].map(canon_key)

    n_unmatched = 0
    n_alias = 0
    unmatched_keys = {}
    out_rows = []
    for _, r in pred.iterrows():
        key = r["qb_key_raw"]
        if key in ALIASES:
            key, n_alias = ALIASES[key], n_alias + 1
        hist = None
        if key is not None and key not in UNMATCHABLE and key in by_qb:
            h = by_qb[key]
            hist = h[(h["season"] < r["season"])
                     | ((h["season"] == r["season"])
                        & (h["week"] < r["week"]))]
        if hist is None or len(hist) == 0:
            n_unmatched += 1
            unmatched_keys[key] = unmatched_keys.get(key, 0) + 1
            vals = qb_value_for_history(
                pd.DataFrame(columns=qb_games.columns))
        else:
            vals = qb_value_for_history(hist)
            if vals["qb_cold_start"] == 0:
                # most recent prior team = first row (most-recent-first)
                vals["qb_team_changed"] = int(
                    hist.iloc[0]["qb_team"] != r["team"])
        row = {"team": r["team"], "season": r["season"],
               "pred_week": r["week"], "qb_sched": r["qb_sched"],
               "qb_key": key}
        row.update(vals)
        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT}: {out.shape}")
    print(f"unmatched/empty-history pred rows: {n_unmatched} "
          f"(of {len(out)}); alias fixes: {n_alias}")
    top_unmatched = sorted(unmatched_keys.items(), key=lambda kv: -kv[1])[:10]
    print("top unmatched keys:", top_unmatched)
    valid = out["qb_value_historical"].notna()
    print(f"rows with value: {valid.sum()} "
          f"({valid.mean():.3f}); cold-start rows: "
          f"{int((out['qb_cold_start'] == 1).sum())}")
    print("seasons:", sorted(out["season"].unique()))
    # distribution sanity (descriptive only, no evaluation)
    print(out["qb_value_historical"].describe().to_string())


if __name__ == "__main__":
    main()
