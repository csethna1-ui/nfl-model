#!/usr/bin/env python3
"""Step 27: diff injury snapshots and rebuild the current-availability state.

Compares the two most recent daily snapshots (or --from/--to) and surfaces:
  NEW OUT / NEW DOUBTFUL / NEW QUESTIONABLE / STATUS CHANGE
with a prominent flag whenever a starting QB's status changed.

Always rebuilds data/injuries/availability_current.json from the latest
snapshot. Appends one record to data/injuries/logs/diff_log.jsonl.

--freeze-friday --season S --week W  copies the current availability into the
Friday-frozen file for the prediction cutoff (refuses to overwrite).

Usage:
    ./venv/bin/python scripts/27_injury_diff.py
    ./venv/bin/python scripts/27_injury_diff.py --from 2026-09-25 --to 2026-09-26
    ./venv/bin/python scripts/27_injury_diff.py --freeze-friday --season 2026 --week 5
"""
import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
from injury_lib import (ensure_dirs, snapshot_path, load_snapshot,
                        latest_snapshot_day, build_availability, write_current,
                        freeze_friday, append_log, norm_status, load_qb1)

DATA = os.path.join(REPO_ROOT, "data")


def row_key(r):
    gid = str(r.get("gsis_id") or "").strip()
    if gid and gid.lower() != "nan":
        return (int(r["week"]), gid)
    return (int(r["week"]), str(r["team"]), str(r["full_name"]).lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_day", default=None)
    ap.add_argument("--to", dest="to_day", default=None)
    ap.add_argument("--freeze-friday", action="store_true")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None)
    args = ap.parse_args()
    ensure_dirs()

    if args.freeze_friday:
        if not args.week:
            raise SystemExit("--freeze-friday needs --week")
        dest = freeze_friday(args.season, args.week)
        print(f"Friday availability frozen -> {dest}")
        return

    to_day = args.to_day or latest_snapshot_day()
    if not to_day:
        raise SystemExit("no snapshots found — run 26_pull_injuries.py first")
    if args.from_day:
        from_day = args.from_day
    else:
        import glob
        days = sorted(f[len("injuries_"):-len(".parquet")]
                      for f in (os.path.basename(p) for p in
                                glob.glob(snapshot_path("*")))
                      if f < to_day)
        from_day = days[-1] if days else None

    new = load_snapshot(to_day)
    if new is None:
        raise SystemExit(f"snapshot for {to_day} not found")
    old = load_snapshot(from_day) if from_day else None

    pulled_at = str(new["pulled_at"].iloc[0]) if "pulled_at" in new.columns else ""
    avail = build_availability(new, pulled_at, season=args.season)
    write_current(avail)

    changes = {"new_out": [], "new_doubtful": [], "new_questionable": [],
               "status_change": [], "qb_flag": []}
    if old is not None:
        qb1 = load_qb1()
        old_map = {row_key(r): r for _, r in old.iterrows()}
        for _, r in new.iterrows():
            k = row_key(r)
            o = old_map.get(k)
            ns, ps = norm_status(r["report_status"]), norm_status(r["practice_status"])
            if o is None:
                rec = {"player": r["full_name"], "team": r["team"],
                       "position": r["position"], "week": int(r["week"]),
                       "report_status": str(r["report_status"]),
                       "practice_status": str(r["practice_status"])}
                if ns == "out":
                    changes["new_out"].append(rec)
                elif ns == "doubtful":
                    changes["new_doubtful"].append(rec)
                elif ns == "questionable":
                    changes["new_questionable"].append(rec)
                continue
            os_, ops = norm_status(o["report_status"]), norm_status(o["practice_status"])
            if ns != os_ or ps != ops:
                rec = {"player": r["full_name"], "team": r["team"],
                       "position": r["position"], "week": int(r["week"]),
                       "was": {"report_status": str(o["report_status"]),
                               "practice_status": str(o["practice_status"])},
                       "now": {"report_status": str(r["report_status"]),
                               "practice_status": str(r["practice_status"])}}
                if ns == "out" and os_ != "out":
                    changes["new_out"].append(rec)
                elif ns == "doubtful" and os_ != "doubtful":
                    changes["new_doubtful"].append(rec)
                elif ns == "questionable" and os_ != "questionable":
                    changes["new_questionable"].append(rec)
                else:
                    changes["status_change"].append(rec)
                if (r["position"] == "QB"
                        and str(r["full_name"]).lower() == str(qb1.get(r["team"], "")).lower()
                        and ns != os_):
                    changes["qb_flag"].append(
                        f"STARTING QB STATUS CHANGE: {r['full_name']} ({r['team']}) "
                        f"{o['report_status']} -> {r['report_status']}")

    n_total = sum(len(v) for k, v in changes.items() if k != "qb_flag")
    append_log("diff_log", {"event": "diff", "from": from_day, "to": to_day,
                            "new_out": len(changes["new_out"]),
                            "new_doubtful": len(changes["new_doubtful"]),
                            "new_questionable": len(changes["new_questionable"]),
                            "status_change": len(changes["status_change"]),
                            "qb_flags": changes["qb_flag"]})

    print("=" * 64)
    print(f"INJURY DIFF {from_day or '(none)'} -> {to_day}  ({n_total} changes)")
    print("=" * 64)
    for flag in changes["qb_flag"]:
        print("  ***", flag)
    for label in ("new_out", "new_doubtful", "new_questionable", "status_change"):
        items = changes[label]
        if not items:
            continue
        print(f"\n-- {label.upper().replace('_', ' ')} ({len(items)}) --")
        for c in items[:25]:
            if "was" in c:
                print(f"  {c['player']} ({c['team']} {c['position']} W{c['week']}): "
                      f"{c['was']['report_status']}/{c['was']['practice_status']} -> "
                      f"{c['now']['report_status']}/{c['now']['practice_status']}")
            else:
                print(f"  {c['player']} ({c['team']} {c['position']} W{c['week']}): "
                      f"{c['report_status']} / {c['practice_status']}")
        if len(items) > 25:
            print(f"  ... and {len(items) - 25} more")
    if not n_total:
        print("  no changes")
    print(f"\navailability_current.json rebuilt ({avail['snapshot_rows']} rows, "
          f"as_of {avail['as_of']})")


if __name__ == "__main__":
    main()
