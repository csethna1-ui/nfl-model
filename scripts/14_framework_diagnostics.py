#!/usr/bin/env python3
"""Step 14: Framework diagnostics from the SportsCommand.ai "7 frameworks" review.

Implements the *testable* parts of the article as read-only diagnostics:

Part A — Situational handicapping (framework #2). Pre-specified buckets from the
    article, evaluated on the untouched 2023-2025 test window at the operating
    threshold (|edge| >= 3.0). Buckets are fixed BEFORE looking: no cherry-picking.
    This is hypothesis-generating, not a production filter.

Part B — CLV independence check (frameworks #1 + #3). The article's test for an
    AI model: "good when the opening line barely moves (independent signal); if
    it only performs after big line movement, it's confirming what the market
    already knows." Uses data/clv_picks.csv (Friday pick number vs nflverse close
    proxy), written by 08_grade_week.py. Needs ~20+ graded picks; reports
    "insufficient data" until then.

Part C — prints the 7-framework mapping (what we have / added / skipped + why).

No production weights, thresholds, or picks are changed by this script.
"""
import os
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
THRESH = 3.0
MIN_N_B = 20  # article: meaningful CLV signal emerges around 30-50 bets; 20 is the floor for a peek


def pick_frame(df):
    """Reconstruct threshold picks: side + win/loss (pushes excluded)."""
    d = df.dropna(subset=["ens_margin", "spread_line"]).copy()
    d["edge"] = d["ens_margin"] - d["spread_line"]
    d = d[d["edge"].abs() >= THRESH].copy()
    d["bet_home"] = d["edge"] > 0
    d["win"] = np.where(d["bet_home"],
                        d["home_margin"] > d["spread_line"],
                        d["home_margin"] < d["spread_line"])
    d = d[d["home_margin"] != d["spread_line"]].copy()  # drop pushes
    d["pick_rest_edge"] = np.where(d["bet_home"],
                                   d["home_rest"] - d["away_rest"],
                                   d["away_rest"] - d["home_rest"])
    return d


def show(name, d):
    n = len(d)
    if n == 0:
        print(f"  {name:34s} n=0")
        return
    w = int(d["win"].sum())
    print(f"  {name:34s} n={n:3d}  {w}-{n - w}  {w / n:.1%}")


def part_a():
    print("== Part A: situational buckets, 2023-2025 test @ |edge|>=3.0 (pre-specified) ==")
    d = pd.read_parquet(f"{DATA}/games_with_preds.parquet")
    t = pick_frame(d[d["season"].between(2023, 2025)])
    show("baseline (all threshold picks)", t)
    show("divisional (div_game==1)", t[t["div_game"] == 1])
    show("late-season divisional (wk>=15)", t[(t["div_game"] == 1) & (t["week"] >= 15)])
    show("pick-side rest disadvantage (<=-3d)", t[t["pick_rest_edge"] <= -3])
    show("pick-side rest advantage (>=+3d)", t[t["pick_rest_edge"] >= 3])
    print("  note: small-n buckets are descriptive only; not a filter without validation.")


def part_b():
    print("\n== Part B: CLV independence check (2026 graded picks) ==")
    p = f"{DATA}/clv_picks.csv"
    if not os.path.exists(p):
        print("  no clv_picks.csv yet (08_grade_week writes it on each grade).")
        return
    d = pd.read_csv(p)
    d = d[d["result"].isin(["win", "loss"])].copy()
    n = len(d)
    if n == 0:
        print("  no graded picks with CLV yet.")
        return
    d["clv_hit"] = d["clv_pts"] > 0
    d["win_b"] = d["result"] == "win"
    print(f"  n={n}  avg CLV {d['clv_pts'].mean():+.2f} pts  hit rate {d['clv_hit'].mean():.0%}  "
          f"ATS {int(d['win_b'].sum())}-{n - int(d['win_b'].sum())}")
    if n < MIN_N_B:
        print(f"  insufficient data for the line-movement split (need >={MIN_N_B} graded picks).")
        return
    calm = d[d["clv_pts"].abs() <= 1.0]   # line barely moved Fri->close: independent-signal condition
    moved = d[d["clv_pts"].abs() > 1.0]
    for name, s in [("|line move|<=1 (line barely moved)", calm),
                    ("|line move|>1  (line moved)", moved)]:
        nn = len(s)
        if nn:
            print(f"  {name:34s} n={nn:3d}  {int(s['win_b'].sum())}-{nn - int(s['win_b'].sum())}  "
                  f"{s['win_b'].mean():.1%}")
    print("  article's read: model should hold up best when the line barely moves.")


def part_c():
    print("\n== Part C: 7-framework mapping ==")
    rows = [
        ("1. CLV analysis", "HAVE + EXTENDED",
         "avg CLV was tracked; added clv_hit_rate + per-pick clv_picks.csv log (08)."),
        ("2. Situational handicapping", "DIAGNOSTIC ONLY",
         "rest/div already GBM features; Part A tests pre-specified buckets. No filter without validation."),
        ("3. Sharp line movement", "FORWARD-LOOKING",
         "no intraday data historically; Part B runs the article's independence test once n>=20."),
        ("4. Player-availability weighting", "HAVE (QB)",
         "stale-QB-news void filter (11); 'doubtful~=out' already our trigger. O-line weighting skipped: no quantitative evidence."),
        ("5. Weather protocols", "HAVE (v2, totals)",
         "wind is real for totals (t=-4.25) but totals aren't bet; no spread signal. No direction data for crosswind splits."),
        ("6. ATS trends w/ context filters", "NOT ADDED",
         "secondary confirmation at best; high data-mining risk, no pre-specifiable edge. Skipped deliberately."),
        ("7. AI composite modeling", "HAVE",
         "the ensemble IS this; weekly refits = continuous recalibration; judged via CLV per the article."),
    ]
    for name, status, note in rows:
        print(f"  {name:32s} [{status}] {note}")


def main():
    part_a()
    part_b()
    part_c()


if __name__ == "__main__":
    main()
