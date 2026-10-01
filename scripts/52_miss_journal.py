#!/usr/bin/env python3
"""Step 52: Weekly miss journal — structured, append-only learning log.

Usage:
    ./venv/bin/python scripts/52_miss_journal.py --season 2026 --week 1

For every game with a pre-game prediction row, records: predicted vs actual
margin, error, edge vs the sheet's market line, SU/ATS results, each team's
2025 win% (prior context), and any QB/injury flag from the prediction file.
All games are logged (wins included) so base rates stay honest; the printed
summary spotlights the misses.

This is MEASUREMENT ONLY. Per the challenger charter, nothing here tunes,
refits, or otherwise changes the model mid-season. If a pattern replicates
across weeks, it becomes a candidate CHALLENGER — which must prove itself
prospectively under the promotion bar, never a quiet tweak.

Re-runnable per week: that week's rows are replaced.
"""
import argparse
import os

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "data")
JOURNAL = f"{DATA}/miss_journal.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()

    sched = pd.read_parquet(f"{DATA}/schedules_2018_2025.parquet")
    finals = sched[(sched["season"] == args.season) & (sched["week"] == args.week)
                   & sched["home_score"].notna()].copy()
    if finals.empty:
        print(f"no completed games yet for {args.season} week {args.week}")
        return

    # 2025 win% per team = the "prior" each early-season prediction leans on.
    s25 = sched[(sched["season"] == 2025) & sched["home_score"].notna()]
    rec = {}
    for _, g in s25.iterrows():
        for t, pf, pa in ((g["home_team"], g["home_score"], g["away_score"]),
                          (g["away_team"], g["away_score"], g["home_score"])):
            w, l = rec.get(t, (0, 0))
            rec[t] = (w + (pf > pa), l + (pf < pa))
    wp = {t: w / (w + l) for t, (w, l) in rec.items()}

    preds = pd.read_csv(f"{DATA}/predictions_2026_w{args.week}.csv")
    rows = []
    for _, p in preds.iterrows():
        away, home = p["game"].split(" @ ")
        g = finals[(finals["away_team"] == away) & (finals["home_team"] == home)]
        if g.empty:
            continue
        g = g.iloc[0]
        am = float(g["away_score"]) - float(g["home_score"])
        m = float(p["model_spread"])
        pred_margin = -m  # model's predicted away margin
        err = pred_margin - am
        picked = home if m > 0 else away
        actual = away if am > 0 else home
        su = "W" if picked == actual else "L"
        ats, side = "", ""
        edge = None
        if pd.notna(p["market_spread"]):
            L = float(p["market_spread"])
            s = am + L
            edge = round(m - L, 1)
            if edge < 0:
                side = f"{away} {L:+g}"
                ats = "W" if s > 0 else ("L" if s < 0 else "push")
            elif edge > 0:
                side = f"{home} {-L:+g}"
                ats = "W" if s < 0 else ("L" if s > 0 else "push")
            else:
                ats = "push"
        opp = away if picked == home else home
        rows.append({
            "season": args.season, "week": args.week, "game": p["game"],
            "picked": picked, "opponent": opp,
            "pred_margin": round(pred_margin, 1), "actual_margin": am,
            "error": round(err, 1), "abs_error": round(abs(err), 1),
            "market_spread": (round(float(p["market_spread"]), 1)
                              if pd.notna(p["market_spread"]) else None),
            "edge": edge, "ats_side": side,
            "su": su, "ats": ats,
            "final": f"{int(g['away_score'])}-{int(g['home_score'])}",
            "picked_2025_wp": round(wp.get(picked, float("nan")), 3),
            "opp_2025_wp": round(wp.get(opp, float("nan")), 3),
            "picked_better_2025": bool(wp.get(picked, 0) > wp.get(opp, 0)),
            "qb_news": (str(p["qb_news"]).strip()
                        if "qb_news" in preds.columns and pd.notna(p["qb_news"])
                        and str(p["qb_news"]).strip() else ""),
            "notes": "",
        })

    df = pd.DataFrame(rows)
    journal = pd.read_csv(JOURNAL) if os.path.exists(JOURNAL) else pd.DataFrame()
    journal = journal[~((journal["season"] == args.season) & (journal["week"] == args.week))] \
        if len(journal) else journal
    journal = pd.concat([journal, df], ignore_index=True)
    journal.to_csv(JOURNAL, index=False)

    # Weekly autopsy summary (scoreboard for the misses).
    su_l = df[df["su"] == "L"].sort_values("abs_error", ascending=False)
    ats_l = df[df["ats"] == "L"].sort_values("abs_error", ascending=False)
    print(f"Week {args.week} miss journal: {len(df)} games, "
          f"SU {int((df['su'] == 'W').sum())}-{len(su_l)}, "
          f"ATS {int((df['ats'] == 'W').sum())}-{len(ats_l)} "
          f"({int((df['ats'] == 'push').sum())} pushes)")
    if len(su_l):
        print("\nSU misses, worst first:")
        print(su_l[["game", "picked", "pred_margin", "actual_margin", "error",
                    "picked_better_2025"]].to_string(index=False))
        pb = su_l["picked_better_2025"]
        print(f"\nof SU misses, model picked the better-2025 team in "
              f"{int(pb.sum())}/{len(pb)}")
    if len(ats_l):
        conf = ats_l[ats_l["edge"].abs() >= 3]
        print(f"\nATS misses: {len(ats_l)} (mean|edge| "
              f"{ats_l['edge'].abs().mean():.2f} vs "
              f"{df[df['ats'] == 'W']['edge'].abs().mean():.2f} on ATS wins)")
        if len(conf):
            print("confidently wrong (|edge|>=3):")
            print(conf[["game", "ats_side", "edge", "error"]].to_string(index=False))
    print(f"\nsaved {JOURNAL} ({len(journal)} rows total)")


if __name__ == "__main__":
    main()
