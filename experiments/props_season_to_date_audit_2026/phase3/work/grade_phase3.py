#!/usr/bin/env python3
"""Phase 3 grading: join frozen-head projections (W1-W3) to actuals and
produce the per-row error table, aggregates, and cut analyses.

Inputs (read-only):
  phase3/projections/prop_v2_2026_w{W}_{rush_attempts,receptions}.json
  phase3/work/actuals_2026_pbp_derived.parquet  (nflverse-2026-pbp-derived
      actuals; rush_att validated 100% exact vs player_games after kneel
      exclusion; receptions via the standard complete_pass-sum recipe)
  data/player_games.parquet  (position spine, rookie detection)
Outputs (phase3/ only):
  phase3/error_table_2026_w1w3.parquet
  phase3/aggregates_2026_w1w3.json
  phase3/PHASE3.md, phase3/PHASE3_NOTES.md (written by hand after review)

MONITORING ONLY: no refit, no tuning. W1-W3 outcomes never enter features;
they are joined here solely for grading.

Cuts (documented, analysis-only):
  - NGS availability: ngs_trail_weeks >= 8 -> full; 1-7 -> partial;
    0 -> fallback-or-zero (0-filled per the trained convention).
  - Opportunity volume: trailing EWMA (hl=3, max 16, strictly prior weeks)
    of targets (003A) / rush attempts (003B) from player_games, terciled
    within market x week.
  - Projection size: terciles of projection within market x week.
  - Uncertainty: model-stated bucket (both heads ship "Medium Uncertainty"
    placeholder); 003A additionally cut by P75-P25 interval-width tercile
    within week (analysis only).
  - Position: WR vs TE for 003A (player_games 2026 latest); RB for 003B.
  - Rookie: first season in player_games history == 2026.
"""
import json
import os

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
PH3 = os.path.join(REPO, "experiments/props_season_to_date_audit_2026/phase3")
WORK = os.path.join(PH3, "work")
PROJDIR = os.path.join(PH3, "projections")

LOCKED_MAE = {"receptions": 1.3496, "rush_attempts": 2.981}


def ewma(v, hl=3.0):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    w = 0.5 ** (np.arange(len(v)) / hl)
    return float(np.sum(w * v) / np.sum(w))


def ngs_status(n):
    if n >= 8:
        return "full"
    if n >= 1:
        return "partial"
    return "fallback-or-zero"


# ---------------- load projections ----------------
rows = []
for market, mfile in [("rush_attempts", "rush_attempts"),
                      ("receptions", "receptions")]:
    for W in (1, 2, 3):
        p = os.path.join(PROJDIR, f"prop_v2_2026_w{W}_{mfile}.json")
        obj = json.load(open(p))
        assert obj["week"] == W and obj["market"] == market
        for pr in obj["projections"]:
            ml = pr["market_line"]
            rows.append({
                "player": pr["player"], "team": pr["team"], "opp": pr["opp"],
                "week": W, "market": market,
                "projection": float(pr["projection"]),
                "interval_p25": pr.get("interval_p25"),
                "interval_p75": pr.get("interval_p75"),
                "uncertainty_bucket": pr["uncertainty"],
                "market_line": None if ml is None else float(ml["line"]),
                "market_source": None if ml is None else ml["source"],
                "market_captured_at": None if ml is None else ml["captured_at"],
                "model_minus_market": (None if ml is None
                                       else round(float(pr["projection"]) - float(ml["line"]), 2)),
                "over_under_vs_line": (None if ml is None
                                       else ("over" if float(pr["projection"]) > float(ml["line"]) else "under")),
                "model_version": pr["model_version"],
                "stale_ngs_used": bool(pr["stale_ngs_used"]),
                "fallback_to_M1": bool(pr["fallback_to_M1"]),
                "trailing_games": int(pr["trailing_games"]),
                "ngs_trail_weeks": int(pr["ngs_trail_weeks"]),
                "ngs_status": ngs_status(int(pr["ngs_trail_weeks"])),
                "prediction_timestamp": pr["prediction_timestamp"],
                "latest_game_included": pr["latest_game_included"],
            })
proj = pd.DataFrame(rows)
m = proj  # working frame for the rest of the script
print(f"projection rows: {len(proj)}")
print(proj.groupby(["market", "week"]).size().to_string())

# ---------------- join actuals ----------------
# Exact (player, team, week) first. Unmatched projections are resolved by a
# fallback: the spine assigns a player's team from their last *predictable*
# game (19 script: cur_team from pg, fallback f["team"]), so early-2026
# team-changers are projected under their 2025 team while the actual row
# sits under the new team. Fallback order per projection row:
#   1. exact (player, team, week) -> "exact"
#   2. single actuals row for (player, week) on another team -> use it,
#      note "team_changed:<actual_team>"
#   3. no actuals row that week -> DNP -> actual = 0, note "dnp_no_actual_row"
#   4. multiple teams for (player, week) (true name collision, e.g. D.Moore
#      on BUF and CAR) -> ambiguous, excluded from aggregates, kept in the
#      error table with actual=null and note "ambiguous_name_collision:..."
act = pd.read_parquet(os.path.join(WORK, "actuals_2026_pbp_derived.parquet"))
act["actual_rec"] = act["receptions"].fillna(0)
act["actual_rush"] = act["rush_att_pbp"].fillna(0)
act_idx = act.set_index(["player_name", "team", "week"])
act_teams_pw = (act.groupby(["player_name", "week"])["team"]
                   .agg(lambda s: sorted(set(s))).to_dict())

match_rows = []
for _, r in m.iterrows():
    key = (r["player"], r["team"], r["week"])
    if key in act_idx.index:
        arow = act_idx.loc[key]
        if isinstance(arow, pd.DataFrame):
            arow = arow.iloc[0]
        match_rows.append((float(arow["actual_rec"]), float(arow["actual_rush"]),
                           "exact"))
        continue
    cands = act_teams_pw.get((r["player"], r["week"]), [])
    if len(cands) == 0:
        match_rows.append((0.0, 0.0, "dnp_no_actual_row"))
    elif len(cands) == 1:
        arow = act_idx.loc[(r["player"], cands[0], r["week"])]
        if isinstance(arow, pd.DataFrame):
            arow = arow.iloc[0]
        match_rows.append((float(arow["actual_rec"]), float(arow["actual_rush"]),
                           f"team_changed:{cands[0]}"))
    else:
        match_rows.append((float("nan"), float("nan"),
                           "ambiguous_name_collision:" + "+".join(cands)))
m["actual_rec"], m["actual_rush"], m["match_note"] = zip(*match_rows)
print("match notes:", pd.Series(m["match_note"]).value_counts().to_dict())
m["actual"] = np.where(m["market"] == "receptions", m["actual_rec"], m["actual_rush"])
m["excluded_ambiguous"] = m["actual"].isna()
print(f"excluded (ambiguous name collisions): {int(m['excluded_ambiguous'].sum())}")
m["abs_err"] = (m["projection"] - m["actual"]).abs()
m["signed_err"] = m["projection"] - m["actual"]

# ---------------- position + rookie ----------------
pg = pd.read_parquet(os.path.join(REPO, "data/player_games.parquet"))
pg26 = pg[pg["season"] == 2026].sort_values(["player_name", "week"])
pos = pg26.drop_duplicates("player_name", keep="last").set_index("player_name")["position"]
first_season = pg.groupby("player_name")["season"].min()
m["position"] = m["player"].map(pos).fillna("UNK")
m["is_rookie"] = m["player"].map(first_season).eq(2026).fillna(False)

# ---------------- opportunity volume (trailing EWMA, strictly prior) ----------------
pgp = pg[["player_name", "season", "week", "targets", "rush_att"]].copy()
pgp = pgp.sort_values(["player_name", "season", "week"])
opp_rows = []
for pn, g in pgp.groupby("player_name", sort=False):
    sw = list(zip(g["season"].astype(int), g["week"].astype(int)))
    tg = g["targets"].fillna(0).to_numpy()
    ra = g["rush_att"].fillna(0).to_numpy()
    for W in (1, 2, 3):
        mask = np.array([(s < 2026) or (s == 2026 and w < W) for s, w in sw])
        idx = np.where(mask)[0][::-1][:16]  # recent-first, max 16
        opp_rows.append({"player": pn, "week": W,
                         "trail_targets_ewma": ewma(tg[idx]) if len(idx) else np.nan,
                         "trail_rushatt_ewma": ewma(ra[idx]) if len(idx) else np.nan})
opp = pd.DataFrame(opp_rows)
m = m.merge(opp, on=["player", "week"], how="left")
m["opp_volume"] = np.where(m["market"] == "receptions",
                           m["trail_targets_ewma"], m["trail_rushatt_ewma"])


def tercile(s):
    try:
        return pd.qcut(s, 3, labels=["low", "mid", "high"], duplicates="drop")
    except ValueError:
        return pd.Series(["mid"] * len(s), index=s.index)


m["opp_volume_tercile"] = (m.groupby(["market", "week"])["opp_volume"]
                           .transform(lambda s: tercile(s))).astype(str)
m["proj_size_tercile"] = (m.groupby(["market", "week"])["projection"]
                          .transform(lambda s: tercile(s))).astype(str)
m["interval_width"] = m["interval_p75"] - m["interval_p25"]
m["interval_width_tercile"] = (m[m["market"] == "receptions"]
                               .groupby("week")["interval_width"]
                               .transform(lambda s: tercile(s))).astype(object)
m["interval_width_tercile"] = m["interval_width_tercile"].fillna("n/a")

m.to_parquet(os.path.join(PH3, "error_table_2026_w1w3.parquet"), index=False)
print(f"error table: {len(m)} rows -> phase3/error_table_2026_w1w3.parquet")
mg = m[~m["excluded_ambiguous"]].copy()
print(f"graded rows (ambiguous excluded): {len(mg)} / {len(m)}")


# ---------------- aggregates ----------------
def agg(df):
    n = len(df)
    if n == 0:
        return {"n": 0}
    ae = df["abs_err"].to_numpy()
    se = df["signed_err"].to_numpy()
    return {"n": int(n), "mae": round(float(ae.mean()), 4),
            "rmse": round(float(np.sqrt((se ** 2).mean())), 4),
            "bias": round(float(se.mean()), 4),
            "mean_projection": round(float(df["projection"].mean()), 3),
            "mean_actual": round(float(df["actual"].mean()), 3)}


out = {"locked_test_mae": LOCKED_MAE,
       "note": ("MONITORING ONLY. Descriptive comparison vs locked-test MAE; "
                "small samples, no inference. No betting-edge language."),
       "markets": {}}
for market in ("receptions", "rush_attempts"):
    d = mg[mg["market"] == market]
    md = {"n_total": int(len(d)),
          "n_ambiguous_excluded": int(((m["market"] == market) & m["excluded_ambiguous"]).sum()),
          "by_week": {f"W{W}": agg(d[d["week"] == W]) for W in (1, 2, 3)},
          "pooled": agg(d)}
    md["pooled"]["vs_locked_mae"] = round(md["pooled"]["mae"] - LOCKED_MAE[market], 4)
    cuts = {}
    cuts["ngs_status"] = {k: agg(g) for k, g in d.groupby("ngs_status")}
    cuts["opportunity_volume_tercile"] = {k: agg(g) for k, g in d.groupby("opp_volume_tercile")}
    cuts["projection_size_tercile"] = {k: agg(g) for k, g in d.groupby("proj_size_tercile")}
    cuts["position"] = {k: agg(g) for k, g in d.groupby("position")}
    cuts["week"] = {f"W{W}": agg(d[d["week"] == W]) for W in (1, 2, 3)}
    cuts["rookie_vs_established"] = {
        "rookie": agg(d[d["is_rookie"]]),
        "established": agg(d[~d["is_rookie"]])}
    if market == "receptions":
        cuts["interval_width_tercile"] = {k: agg(g) for k, g in d.groupby("interval_width_tercile")}
    else:
        cuts["uncertainty_bucket"] = {k: agg(g) for k, g in d.groupby("uncertainty_bucket")}
    # ngs_status x week (does the edge persist when NGS is missing, per week)
    cuts["ngs_status_by_week"] = {
        f"W{W}": {k: agg(g) for k, g in d[d["week"] == W].groupby("ngs_status")}
        for W in (1, 2, 3)}
    # DNP sensitivity: pooled with DNP rows (actual=0) vs without
    cuts["dnp_sensitivity"] = {
        "with_dnp": agg(d),
        "without_dnp": agg(d[d["match_note"] != "dnp_no_actual_row"]),
        "n_dnp": int((d["match_note"] == "dnp_no_actual_row").sum()),
        "n_team_changed": int(d["match_note"].str.startswith("team_changed").sum())}
    md["cuts"] = cuts
    md["stale_ngs_rows"] = int(d["stale_ngs_used"].sum())
    md["fallback_M1_rows"] = int(d["fallback_to_M1"].sum())
    md["market_lines_present"] = int(d["market_line"].notna().sum())
    out["markets"][market] = md

with open(os.path.join(PH3, "aggregates_2026_w1w3.json"), "w") as f:
    json.dump(out, f, indent=1)
print("aggregates -> phase3/aggregates_2026_w1w3.json")
for market in ("receptions", "rush_attempts"):
    md = out["markets"][market]
    delta = md['pooled']['vs_locked_mae']
    dstr = "%+.4f" % delta
    print(f"\n{market}: pooled MAE {md['pooled']['mae']} (locked {LOCKED_MAE[market]}, "
          f"delta {dstr}), n={md['pooled']['n']}")
    for wk, a in md["by_week"].items():
        print(f"  {wk}: MAE {a['mae']} RMSE {a['rmse']} bias {a['bias']} n={a['n']}")
    print("  NGS cut:", {k: (v["mae"], v["n"]) for k, v in md["cuts"]["ngs_status"].items()})

# ---------------- NGS-availability diagnostic (Cale's key question) ----------------
# Raw MAE by ngs_status is confounded: NGS-missing rows are overwhelmingly
# low-volume fringe players (lower absolute error mechanically). Volume-
# controlled diagnostic on the no-DNP set: OLS abs_err ~ projection +
# I(ngs_status==full), plus relative MAE (|err|/projection) by status.
# Observational only: NGS availability correlates with veteran stability,
# so this does NOT isolate a causal NGS contribution. The controlled
# M2-vs-M1 evidence remains the locked-test result.
diag = {}
gd = mg[mg["match_note"] != "dnp_no_actual_row"].copy()
for market in ("receptions", "rush_attempts"):
    d = gd[gd["market"] == market].copy()
    d["ngs_full"] = (d["ngs_status"] == "full").astype(int)
    X = np.column_stack([np.ones(len(d)), d["projection"].to_numpy(),
                         d["ngs_full"].to_numpy()])
    y = d["abs_err"].to_numpy()
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    dof = len(d) - 3
    s2 = float((resid ** 2).sum() / dof)
    cov = s2 * np.linalg.inv(X.T @ X)
    se = float(np.sqrt(cov[2, 2]))
    rel = d.groupby("ngs_status").apply(
        lambda s: float((s["abs_err"] / s["projection"]).mean()),
        include_groups=False).to_dict()
    diag[market] = {
        "n_no_dnp": int(len(d)),
        "ols_abs_err_on_projection_plus_ngs_full": {
            "intercept": round(float(b[0]), 4),
            "projection_coef": round(float(b[1]), 4),
            "ngs_full_coef": round(float(b[2]), 4),
            "ngs_full_se": round(se, 4),
            "ngs_full_t": round(float(b[2] / se), 3) if se > 0 else None},
        "relative_mae_by_ngs_status": {k: round(v, 4) for k, v in rel.items()},
        "raw_corr_ngs_weeks_abs_err": round(float(d["ngs_trail_weeks"].corr(d["abs_err"])), 4),
        "caveat": ("observational; NGS availability correlates with veteran "
                   "role stability; small samples; descriptive only")}
out["ngs_availability_diagnostic"] = diag
with open(os.path.join(PH3, "aggregates_2026_w1w3.json"), "w") as f:
    json.dump(out, f, indent=1)
print("ngs diagnostic appended to aggregates_2026_w1w3.json")
print(json.dumps(diag, indent=1))
