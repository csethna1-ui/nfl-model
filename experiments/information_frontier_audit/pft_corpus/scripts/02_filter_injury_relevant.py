#!/usr/bin/env python3
"""
02_filter_injury_relevant.py — Flag injury/availability-relevant PFT URLs by slug tokens.

Token-level matching on dash-separated slug tokens (avoids 'out' inside 'shout').
Adds `relevant` (0/1) + `relevant_reason` to the urls table.

Target: ~250/mo (~13% of PFT output), i.e. ~15k over 2018-2022.
"""
import re, sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "data" / "pft_sitemap.db"

# Exact-token matches (dash-split slug tokens). HIGH-PRECISION ONLY:
# bare "out"/"back"/"return" removed — too noisy in slugs ("out there", "bring back").
INJURY_TOKENS = {
    "injury", "injuries", "injured", "hurt", "hurts", "hobbled",
    "doubtful", "questionable",
    "surgery", "concussion", "concussions",
    "acl", "mcl", "pcl", "lcl", "achilles", "meniscus", "lisfranc", "labrum",
    "hamstring", "quad", "quadriceps", "groin", "hip", "calf", "ankle", "knee",
    "shoulder", "elbow", "wrist", "hand", "finger", "thumb", "rib", "ribs",
    "neck", "toe", "foot", "oblique", "biceps", "triceps", "pectoral",
    "hernia", "appendectomy", "appendix",
    "sprain", "sprained", "strain", "strained", "tear", "torn", "fracture",
    "fractured", "dislocated", "dislocation", "bruise", "bruised", "sore",
    "soreness", "tightness", "stinger", "lacerated", "laceration",
    "illness", "sick", "covid", "flu",
    "limited", "dnp",
    "sidelined", "scratched", "inactive", "inactives",
    "cleared", "pup", "ir",
    "miss", "misses", "missing", "sit", "sits",
    "reserve",
}
# Compound phrases matched as substrings of the slug (high precision)
PHRASES = [
    "ruled-out", "out-for", "out-this-week", "out-sunday", "out-vs",
    "game-time", "game-time-decision", "expected-to-play",
    "full-participant", "full-go",
    "did-not-practice", "not-practicing", "miss-practice", "missed-practice",
    "on-ir", "off-ir", "to-ir", "opt-out",
    "injury-report", "practice-report", "final-injury", "injury-update",
    "to-miss", "will-miss", "to-sit", "sit-out",
    "designated-to-return", "return-to-practice", "rest-starters",
]

def is_relevant(slug):
    tokens = set(slug.split("-"))
    hits = tokens & INJURY_TOKENS
    if hits:
        return True, "token:" + ",".join(sorted(hits)[:4])
    for ph in PHRASES:
        if ph in slug:
            return True, "phrase:" + ph
    # practice + availability context
    if "practice" in tokens and tokens & {"limited", "full", "miss", "return", "cleared", "out", "sit", "dnp"}:
        return True, "practice-context"
    return False, None

def main():
    con = sqlite3.connect(DB)
    cols = [r[1] for r in con.execute("PRAGMA table_info(urls)")]
    if "relevant" not in cols:
        con.execute("ALTER TABLE urls ADD COLUMN relevant INTEGER DEFAULT 0")
        con.execute("ALTER TABLE urls ADD COLUMN relevant_reason TEXT")
    if "in_scope" not in cols:
        con.execute("ALTER TABLE urls ADD COLUMN in_scope INTEGER DEFAULT 0")
    # In-season scope: Aug..Jan per season (preseason cuts through playoffs);
    # the pilot's criteria (weekly coverage, news-lead, Sunday density) are
    # all regular-season. Documented scoping decision.
    scope_months = set()
    for y in range(2018, 2023):
        for m in (8, 9, 10, 11, 12):
            scope_months.add(f"{y}{m:02d}")
        scope_months.add(f"{y+1}01")
    rows = con.execute("SELECT url, slug, month FROM urls").fetchall()
    n_rel = n_scope = 0
    for url, slug, month in rows:
        rel, reason = is_relevant(slug)
        scope = 1 if month in scope_months else 0
        con.execute("UPDATE urls SET relevant=?, relevant_reason=?, in_scope=? WHERE url=?",
                    (1 if rel else 0, reason, scope, url))
        n_rel += rel
        n_scope += (rel and scope)
    con.commit()
    tot = len(rows)
    print(f"total={tot} relevant={n_rel} ({n_rel/tot:.1%}) in_scope_relevant={n_scope}")
    print("per-month in-scope relevant:")
    for m, c in con.execute(
        "SELECT month, COUNT(*) FROM urls WHERE relevant=1 AND in_scope=1 GROUP BY month ORDER BY month"):
        print(f"  {m}: {c}")
    con.close()

if __name__ == "__main__":
    main()
