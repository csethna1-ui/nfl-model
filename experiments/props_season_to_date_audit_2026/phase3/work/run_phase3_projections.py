#!/usr/bin/env python3
"""Phase 3 projection driver: apply the two FROZEN experimental heads to
2026 W1/W2/W3 with strict as-of discipline.

Method: import scripts/17_prod_rush_attempts.py and
scripts/19_prod_receptions.py as modules (read-only; the files themselves
are never modified), redirect their module-level DATA / NGS_CACHE /
NGS_CACHE_PREV to phase3/work/datamirror/ (symlinks to production data
plus as-of reconstructions: pbp_2026.parquet from a keyless 2026 pull and
ratings_current_2026_w{W}.parquet rebuilt via the byte-verified w4 code
path), then call each module's weekly_run() verbatim -- the exact
production code path, including schema validation. Outputs are moved out
of the mirror into phase3/projections/; data/ is never written.

As-of discipline (documented in PHASE3_NOTES.md):
  - All trailing features use strictly-prior (season, week) rows only
    (enforced inside the prod code).
  - NGS trailing uses rows strictly before the target week from a fresh
    keyless pull; week==0 aggregates excluded; required-release check
    per the production gate.
  - Pre-week ELO/EPA from reconstructed ratings snapshots (W1 uses the
    regressed-prior rule, mirroring 07).
  - Market join runs against data/market_props_2026_w{W}.json (read-only);
    those files contain no receptions/rush_attempts lines, so market_line
    is expected to be null for every row.
No refit, no feature changes, no tuning. W1-W3 outcomes never enter
features (actuals are joined only afterwards, in the grading step).
"""
import importlib.util
import json
import os
import shutil
import sys

REPO = os.path.expanduser("~/workspace/nfl-model")
PH3 = os.path.join(REPO, "experiments/props_season_to_date_audit_2026/phase3")
WORK = os.path.join(PH3, "work")
MIRROR = os.path.join(WORK, "datamirror")
PROJDIR = os.path.join(PH3, "projections")
os.makedirs(PROJDIR, exist_ok=True)

NGS_KIND = {"m17": "rushing", "m19": "receiving"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_head(modname, script, market):
    print(f"===== {modname}: {script} -> {market} =====", flush=True)
    mod = _load(modname, os.path.join(REPO, script))
    # Redirect all file I/O to the mirror. The scripts under test are
    # imported read-only; nothing is written to data/ or the scripts.
    mod.DATA = MIRROR
    kind = NGS_KIND[modname]
    mod.NGS_CACHE = os.path.join(MIRROR, f"prod_ngs_{kind}.parquet")
    mod.NGS_CACHE_PREV = os.path.join(MIRROR, f"prod_ngs_{kind}_prev.parquet")
    for W in (1, 2, 3):
        mkt = os.path.join(REPO, "data", f"market_props_2026_w{W}.json")
        print(f"--- week {W} ---", flush=True)
        opath = mod.weekly_run(2026, W, market_json=mkt)
        assert opath.startswith(MIRROR), f"unexpected output path {opath}"
        with open(opath) as f:
            obj = json.load(f)
        mod.validate_output(obj)  # production schema validation, verbatim
        n_mkt = sum(1 for p in obj["projections"]
                    if p["market_line"] is not None)
        print(f"  validated: {len(obj['projections'])} rows, "
              f"{n_mkt} with market line", flush=True)
        dest = os.path.join(PROJDIR, f"prop_v2_2026_w{W}_{market}.json")
        shutil.move(opath, dest)
        print(f"  moved -> {dest}", flush=True)


def main():
    run_head("m17", "scripts/17_prod_rush_attempts.py", "rush_attempts")
    run_head("m19", "scripts/19_prod_receptions.py", "receptions")
    print("ALL PROJECTION RUNS COMPLETE", flush=True)


if __name__ == "__main__":
    main()
