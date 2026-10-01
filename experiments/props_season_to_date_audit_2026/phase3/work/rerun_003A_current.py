#!/usr/bin/env python3
"""Re-run ONLY the 003A head with the current on-disk 19_prod_receptions.py
(player_games-based base, game_id predictable filter). The earlier audit run
used the parent's intermediate pbp-based version; those outputs are backed
up under work/projections_003A_pbp_version/.

Verbatim driver logic: import read-only, redirect DATA/NGS_CACHE to the
mirror, call weekly_run(), validate, move to projections/.
"""
import importlib.util
import json
import os
import shutil
import sys

REPO = os.path.expanduser("~/workspace/nfl-model")
PH3 = os.path.join(REPO, "experiments/props_season_to_date_audit_2026/phase3")
MIRROR = os.path.join(PH3, "work", "datamirror")
PROJDIR = os.path.join(PH3, "projections")

# Record the exact code version being run.
import hashlib
src = open(os.path.join(REPO, "scripts/19_prod_receptions.py"), "rb").read()
print("19 sha256:", hashlib.sha256(src).hexdigest()[:16], flush=True)

spec = importlib.util.spec_from_file_location(
    "m19_rerun", os.path.join(REPO, "scripts/19_prod_receptions.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.DATA = MIRROR
mod.NGS_CACHE = os.path.join(MIRROR, "prod_ngs_receiving.parquet")
mod.NGS_CACHE_PREV = os.path.join(MIRROR, "prod_ngs_receiving_prev.parquet")

for W in (1, 2, 3):
    mkt = os.path.join(REPO, "data", f"market_props_2026_w{W}.json")
    print(f"--- week {W} ---", flush=True)
    opath = mod.weekly_run(2026, W, market_json=mkt)
    assert opath.startswith(MIRROR), f"unexpected output path {opath}"
    with open(opath) as f:
        obj = json.load(f)
    mod.validate_output(obj)
    n_mkt = sum(1 for p in obj["projections"] if p["market_line"] is not None)
    print(f"  validated: {len(obj['projections'])} rows, {n_mkt} with market line",
          flush=True)
    dest = os.path.join(PROJDIR, f"prop_v2_2026_w{W}_receptions.json")
    shutil.move(opath, dest)
    print(f"  moved -> {dest}", flush=True)
print("003A RE-RUN COMPLETE", flush=True)
