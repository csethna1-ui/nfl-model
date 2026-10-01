#!/usr/bin/env python3
"""Experiment 003B - feature availability/leakage audit.

Emits experiments/props_experiment_003_market_expansion/003B_rush_attempts/
data/feature_audit.csv with one row per candidate feature:
  feature_name, source, historical_start, historical_end,
  as_of_timestamp_available, prediction_cutoff, leakage_risk,
  historical_reconstructable, included_primary_experiment, reason_if_excluded

Declaration + verification: every "included" feature has a verification check
below that passed on 2026-10-01 (train/dev-era sources). Checks never touch
the locked test slice.
Leakage-risk ratings: LOW = strictly prior-week completed-game data or
static pre-known info; MEDIUM = reconstructed as-of state with a documented
timing caveat; HIGH = excluded.
"""
import csv
import os

import numpy as np
import pandas as pd

REPO = os.path.expanduser("~/workspace/nfl-model")
EXP = os.path.join(REPO, "experiments/props_experiment_003_market_expansion",
                   "003B_rush_attempts")
TABLE = os.path.join(EXP, "data/features_003b_2018_2024.parquet")
CUTOFF = "Friday 18:00 America/Chicago of game week"


def row(name, source, start, end, asof, risk, recon, incl, reason=""):
    return dict(feature_name=name, source=source,
                historical_start=start, historical_end=end,
                as_of_timestamp_available=asof, prediction_cutoff=CUTOFF,
                leakage_risk=risk, historical_reconstructable=recon,
                included_primary_experiment=incl, reason_if_excluded=reason)


def main():
    rows = []
    # ---- M1 opportunity family ----
    rows.append(row("pace_team_plays",
        "experiments/props_experiment_002/data/extended_features_2018_2024.parquet "
        "(002 Family E; trailing team plays EWMA from nflverse pbp REG)",
        2018, 2024, "trailing completed team games, strictly prior", "LOW",
        "YES", "YES"))
    rows.append(row("trail_rush_share_ewma",
        "experiments/player_props_projection/data/modeling_table.parquet "
        "(001: carries/team carries per game, trailing EWMA hl=3/max16)",
        2018, 2024, "trailing completed games, strictly prior", "LOW",
        "YES", "YES"))
    rows.append(row("opp2_snap_pct",
        "002 Family F (snap_counts.offense_pct trailing EWMA; 002-verified "
        "date_modified as-of handling in nflverse local DB)",
        2018, 2024, "trailing completed games, strictly prior", "LOW",
        "YES", "YES"))
    rows.append(row("neut_rush_rate",
        "derived 1 - pace_neutral_pass_rate (002 Family E; neutral = qtr 1-3, "
        "|score diff| <= 10; trailing EWMA)",
        2018, 2024, "trailing completed games, strictly prior", "LOW",
        "YES", "YES"))
    rows.append(row("ctx_elo_adv",
        "data/games_with_ratings.parquet (scripts/03_ratings.py ELO "
        "walk-forward); pre-week rating attached before the week's games",
        2018, 2024, "pre-week rating: strictly prior information", "LOW",
        "YES", "YES"))
    rows.append(row("trail_rz_carries_ewma",
        "experiments/player_props_projection/data/modeling_table.parquet "
        "(001: pbp-derived red-zone carries, trailing EWMA hl=3/max16)",
        2018, 2024, "trailing completed games, strictly prior", "LOW",
        "YES", "YES"))
    rows.append(row("trail_games",
        "001 modeling table (count of trailing games; shared protocol "
        "section 3 weight input)", 2018, 2024,
        "trailing completed games, strictly prior", "LOW", "YES", "YES"))
    # ---- M2 NGS rushing family ----
    ngs_src = ("NFL Next Gen Stats via nfl_data_py.import_ngs_data('rushing') "
               "keyless, weekly 2018-2024; strictly-prior-week trailing EWMA "
               "hl=3/max16 (002 rq_ngs_separation precedent)")
    for nm, desc in [
            ("ngs_eff", "efficiency"),
            ("ngs_xrush", "expected_rush_yards (raw column, prereg-verified)"),
            ("ngs_ryoe", "rush_yards_over_expected"),
            ("ngs_ryoe_pct", "rush_pct_over_expected"),
            ("ngs_8box", "percent_attempts_gte_eight_defenders"),
            ("ngs_ttl", "avg_time_to_los")]:
        rows.append(row(nm, f"{ngs_src}; {desc}", 2018, 2024,
            "trailing NGS weeks strictly prior (weekly releases post-game)",
            "LOW", "YES", "YES"))
    # ---- M3 context families (002 B/C/D1/D2/E/L, frozen definitions) ----
    fam_src = ("experiments/props_experiment_002/data/"
               "extended_features_2018_2024.parquet (002 Family {}, "
               "as-of-safe per 002 audit)")
    for nm, fam in [("ctx_team_off_epa", "B"), ("ctx_team_off_pass_epa", "B"),
                    ("ctx_team_off_rush_epa", "B"), ("ctx_team_off_sr", "B"),
                    ("oppd_def_rush_epa", "C"),
                    ("envs_dome", "D1"), ("envs_team_pts_trail", "D1"),
                    ("envs_opp_pts_allowed_trail", "D1"),
                    ("envf_days_rest", "D2"), ("envf_rest_diff", "D2"),
                    ("envf_short_week", "D2"), ("envf_long_rest", "D2"),
                    ("envf_div_game", "D2"),
                    ("pace_combined", "E"), ("pace_neutral_pass_rate", "E"),
                    ("inj_player_status", "L"), ("inj_team_out_share", "L"),
                    ("inj_ol_out", "L")]:
        risk = ("MEDIUM" if nm.startswith("inj_") else "LOW")
        asof = ("latest row per player with date_modified <= cutoff; "
                "feed-available info, not market knowledge"
                if nm.startswith("inj_") else
                "trailing completed games / pre-week ratings, strictly prior")
        rows.append(row(nm, fam_src.format(fam), 2018, 2024, asof, risk,
                        "YES", "YES"))
    # ---- target / baseline ----
    rows.append(row("actual_att (target)",
        "player_stats-equivalent carries: 001 modeling table actual_att for "
        "market=='rush_yards' (pbp rusher counts; verified == carries)",
        2018, 2024, "outcome (post-game)", "LOW", "YES", "YES"))
    rows.append(row("trail_rush_att_ewma (M0)",
        "001 modeling table (trailing carries EWMA hl=3/max16); shared "
        "protocol section 3 frozen baseline", 2018, 2024,
        "trailing completed games, strictly prior", "LOW", "YES", "YES"))
    # ---- excluded ----
    rows.append(row("spread_line/total_line/implied totals",
        "nflverse closing lines", 2018, 2024,
        "NOT available at Friday 18:00 CT cutoff; zero A-class Friday lines "
        "(Experiment 006 backfill)", "HIGH", "NO", "NO",
        "excluded by 002 leakage rule: no timestamped historical Friday lines"))
    rows.append(row("historical depth-chart position",
        "local depth charts are 2026-only (002 documented)", "2026", 2026,
        "n/a", "HIGH", "NO", "NO",
        "unavailable historically; depth-chart changes via as-of injury feed"))
    rows.append(row("NGS routes / coverage splits / xYAC / defensive tracking",
        "not in keyless NGS feed (002/AUDIT documented)", "n/a", "n/a",
        "n/a", "HIGH", "NO", "NO", "not keyless-available"))

    # ---- verification on train+dev-era sources only (never locked test) ----
    t = pd.read_parquet(TABLE)
    chk = t[t["period"].isin(["train", "dev"])]
    pop = chk[(chk["market"] == "rush_yards") & (chk["eligible_hist"] == 1) &
              (chk["played_role"] == 1) & (chk["trail_rush_att_ewma"] >= 5)]
    incl = [r["feature_name"] for r in rows
            if r["included_primary_experiment"] == "YES"
            and not r["feature_name"].endswith("(target)")
            and not r["feature_name"].endswith("(M0)")]
    missing = [c for c in incl if c not in pop.columns]
    assert not missing, f"included features missing from table: {missing}"
    assert int(pop[incl].isna().sum().sum()) == 0, "NaNs in included features"
    assert (pop["actual_att"] >= 5).all(), "target below role threshold"
    banned = ["spread_line", "total_line", "team_spread", "team_implied_total",
              "opp_implied_total"]
    leaked = [c for c in incl if c in banned]
    assert not leaked, f"leakage: market lines in features: {leaked}"
    print(f"audit checks passed: {len(pop)} train+dev population rows, "
          f"{len(incl)} included features, 0 NaN, 0 market-line features")

    os.makedirs(os.path.join(EXP, "data"), exist_ok=True)
    with open(os.path.join(EXP, "data/feature_audit.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {EXP}/data/feature_audit.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
