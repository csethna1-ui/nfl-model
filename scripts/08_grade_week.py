#!/usr/bin/env python3
"""Step 8: Grade a week's model spread picks against final scores.

Usage:
    ./venv/bin/python scripts/08_grade_week.py --predictions-csv data/predictions_2026_w1.csv \
        --season 2026 --week 1

Joins final scores from the cached schedule, grades each spread_pick against
its market spread (pushes excluded from W-L, counted separately), prints a
per-game table, and appends the week to data/record.csv (replaces the row if
the week was already graded, so re-running after MNF is safe).
"""
import argparse
import re
import sys

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")


def parse_pick(pick):
    """'ARI +9.5' -> ('ARI', 9.5); 'LAC -3.5' -> ('LAC', -3.5); 'DAL PK' -> ('DAL', 0.0)."""
    m = re.match(r"^([A-Z]{2,3}) ([+-]?)(\d+(?:\.\d+)?|PK)$", pick.strip())
    if not m:
        return None, None
    team, sign, num = m.groups()
    if num == "PK":
        return team, 0.0
    val = float(num)
    return team, -val if sign == "-" else val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions-csv", required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()

    preds = pd.read_csv(args.predictions_csv)
    # Grade the pick that actually went in the sheet: the injury-filtered
    # `spread_pick_final` when present, else the raw `spread_pick`.
    pick_col = "spread_pick_final" if "spread_pick_final" in preds.columns else "spread_pick"
    edge_col = "edge_adj" if "edge_adj" in preds.columns else "edge"
    has_void = "void_reason" in preds.columns
    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    played = sched[(sched["season"] == args.season) & (sched["week"] == args.week)
                   & sched["home_score"].notna()].copy()
    if played.empty:
        print(f"no completed games yet for {args.season} week {args.week}")
        sys.exit(1)

    results = []
    for _, p in preds.iterrows():
        edge_v = round(float(p[edge_col]), 1) if pd.notna(p[edge_col]) else None
        mkt_v = round(float(p["market_spread"]), 1) if pd.notna(p["market_spread"]) else None
        void_reason = str(p["void_reason"]).strip() if has_void and pd.notna(p["void_reason"]) and str(p["void_reason"]).strip() else ""
        if p[pick_col] == "no play":
            # A "no play" with a void_reason was a paper pick killed by the
            # injury void layer — record it as void (never as a loss).
            # A plain "no play" (below threshold) was never a pick: skip.
            if void_reason:
                pre_pick = p["spread_pick"] if "spread_pick" in preds.columns else "no play"
                results.append({"game": p["game"], "pick": pre_pick,
                                "market_spread": mkt_v, "edge": edge_v,
                                "final": "", "result": "void", "void": True,
                                "void_reason": void_reason, "clv_pts": None})
            continue
        away, home = p["game"].split(" @ ")
        g = played[(played["away_team"] == away) & (played["home_team"] == home)]
        if g.empty:
            results.append({"game": p["game"], "pick": p[pick_col],
                            "market_spread": mkt_v, "edge": edge_v,
                            "final": "", "result": "pending", "void": False,
                            "void_reason": "", "clv_pts": None})
            continue
        g = g.iloc[0]
        hm = g["home_score"] - g["away_score"]
        team, spread = parse_pick(p[pick_col])
        team_margin = hm if team == home else -hm
        diff = team_margin + spread
        outcome = "win" if diff > 0 else ("loss" if diff < 0 else "push")
        # CLV: points better than the closing number our pick got.
        # nflverse spread_line is a close proxy (home perspective, + = home favored).
        clv = None
        if pd.notna(g.get("spread_line")) and spread != 0:
            # nflverse spread_line: + = home favored, so the home team's own
            # number is -spread_line and the away team's is +spread_line.
            close_team = -g["spread_line"] if team == home else g["spread_line"]
            # CLV = picked team's spread - closing spread (same sign convention).
            # Underdog: more points is better, e.g. +8.5 vs +7.5 -> +1.0.
            # Favorite: less negative is better, e.g. -7 vs -7.5 -> +0.5.
            clv = round(spread - close_team, 1)
        results.append({"game": p["game"], "pick": p[pick_col],
                        "final": f"{int(g['away_score'])}-{int(g['home_score'])}",
                        "market_spread": mkt_v, "edge": edge_v,
                        "result": outcome, "void": False,
                        "void_reason": "", "clv_pts": clv})

    res = pd.DataFrame(results)
    print(res.to_string(index=False))
    done = res[res["result"] != "pending"]
    w = int((done["result"] == "win").sum())
    l = int((done["result"] == "loss").sum())
    pu = int((done["result"] == "push").sum())
    pend = int((res["result"] == "pending").sum())
    clv_vals = done["clv_pts"].dropna()
    clv_avg = round(float(clv_vals.mean()), 2) if len(clv_vals) else None
    clv_hit = round(float((clv_vals > 0).mean()), 3) if len(clv_vals) else None
    print(f"\nWeek {args.week}: {w}-{l}" + (f"-{pu} pushes" if pu else "")
          + (f" ({pend} pending)" if pend else "")
          + (f" | avg CLV {clv_avg:+.2f} pts" if clv_avg is not None else "")
          + (f" | CLV hit rate {clv_hit:.0%}" if clv_hit is not None else ""))

    import os
    rec_path = f"{DATA}/record.csv"
    rec = pd.read_csv(rec_path) if os.path.exists(rec_path) else pd.DataFrame(
        columns=["season", "week", "w", "l", "push", "pending", "clv_n", "clv_avg_pts",
                 "clv_hit_rate"])
    for col in ["clv_n", "clv_avg_pts", "clv_hit_rate"]:
        if col not in rec.columns:
            rec[col] = None
    rec = rec[~((rec["season"] == args.season) & (rec["week"] == args.week))]
    rec = pd.concat([rec, pd.DataFrame([{
        "season": args.season, "week": args.week, "w": w, "l": l,
        "push": pu, "pending": pend,
        "clv_n": int(len(clv_vals)), "clv_avg_pts": clv_avg,
        "clv_hit_rate": clv_hit}])], ignore_index=True)
    rec = rec.sort_values(["season", "week"]).reset_index(drop=True)
    rec.to_csv(rec_path, index=False)

    # Per-pick CLV log (powers the line-movement independence diagnostic).
    # Re-runnable: this week's rows are replaced.
    log_path = f"{DATA}/clv_picks.csv"
    log_cols = ["season", "week", "game", "pick", "result", "clv_pts"]
    log = pd.read_csv(log_path) if os.path.exists(log_path) else pd.DataFrame(columns=log_cols)
    log = log[~((log["season"] == args.season) & (log["week"] == args.week))]
    new_rows = [{"season": args.season, "week": args.week, "game": g_, "pick": p_,
                 "result": r_, "clv_pts": c_}
                for g_, p_, r_, c_ in zip(res["game"], res["pick"],
                                         res["result"], res["clv_pts"])
                if r_ in ("win", "loss", "push") and pd.notna(c_)]
    if new_rows:
        log = pd.concat([log, pd.DataFrame(new_rows)], ignore_index=True)
    log.to_csv(log_path, index=False)

    # Per-pick results ledger (powers the dashboard Performance page).
    # Every paper pick graded above, plus voided picks; idempotent per week.
    pr_cols = ["season", "week", "game", "pick", "market_spread", "edge",
               "final", "result", "void", "void_reason", "clv_pts"]
    pr_path = f"{DATA}/pick_results.csv"
    pr = pd.read_csv(pr_path) if os.path.exists(pr_path) else pd.DataFrame(columns=pr_cols)
    pr = pr[~((pr["season"] == args.season) & (pr["week"] == args.week))]
    if len(res):
        new_pr = res.copy()
        new_pr["season"] = args.season
        new_pr["week"] = args.week
        new_pr["void"] = new_pr["void"].astype(bool)
        new_pr = new_pr[pr_cols]
        pr = pd.concat([pr, new_pr], ignore_index=True)
    pr.to_csv(pr_path, index=False)
    print(f"saved {pr_path} ({int(((pr['season'] == args.season) & (pr['week'] == args.week)).sum())} rows for week {args.week})")
    tw, tl = int(rec["w"].sum()), int(rec["l"].sum())
    print(f"Season record: {tw}-{tl} ({tw/(tw+tl)*100:.1f}% ATS)" if tw + tl else "Season record: no graded games yet")
    clv_rows = rec.dropna(subset=["clv_avg_pts"])
    if len(clv_rows):
        # Pick-weighted average: sum(clv_n * clv_avg) / sum(clv_n).
        wsum = float((clv_rows["clv_n"] * clv_rows["clv_avg_pts"]).sum())
        nsum = float(clv_rows["clv_n"].sum())
        print(f"Season avg CLV: {wsum/nsum:+.2f} pts/pick (pick-weighted, "
              f"{int(nsum)} picks; vs nflverse close proxy; + means beating the close)")
    print(f"saved {rec_path}")


if __name__ == "__main__":
    main()
