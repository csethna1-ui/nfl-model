#!/usr/bin/env python3
"""
05_news_lead.py — Criterion 4: the news-lead diagnostic (THE KEY ONE).

For a seeded random sample of 200 (player, week) cases with nflverse
report_status in (Out, Doubtful) in 2021-2022 REG:
  what fraction have >=1 corpus article mentioning that player's injury
  with date_published >= 24h BEFORE the nflverse date_modified, AND within
  the 14 days before that cutoff? (14-day window added 2026-10-01: the
  preregistered script counted ANY prior article, so a 2019 mention could
  'lead' a 2022 injury — a spec flaw caught in the partial-verdict run.)

Definitions:
- Sampling frame: injuries_2021/2022.csv, game_type=REG, report_status in
  (Out, Doubtful), date_modified present. Group by (full_name, season, week,
  team); use MIN(date_modified) = first filing of the designation that week.
- "Mentioning their injury": article has an entity row for the player
  (resolution_method != 'ambiguous') AND event_class in
  (ruled_out, injury_report, practice_participation, expected_to_play)
  AND article date_published in [date_modified - 24h - 14d, date_modified - 24h).
  Articles with missing date_published cannot count (conservative).
- Player matching: injuries.full_name normalized the same way as 04;
  must match an entity player_name exactly.

Output: data/news_lead_results.csv (per-case evidence) + printed summary.
Success bar: >= 40%.
"""
import re, sqlite3, unicodedata
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
SEED = 20260929
N_SAMPLE = 200
LEAD_HOURS = 24
LEAD_WINDOW_DAYS = 14  # added 2026-10-01: upper bound on the lead window (spec flaw fix)

def normalize(name):
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    n = n.lower().strip()
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", n)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", "", n)).strip()

def main():
    inj = pd.concat([
        pd.read_csv(f"~/workspace/nfl-model/data/v2/raw/injuries_{s}.csv".replace("~", str(Path.home())))
        for s in (2021, 2022)
    ], ignore_index=True)
    inj = inj[(inj.game_type == "REG") & (inj.report_status.isin(["Out", "Doubtful"]))
              & (inj.date_modified.notna())]
    inj["norm_name"] = inj.full_name.map(normalize)
    grp = (inj.groupby(["norm_name", "season", "week", "team"], as_index=False)
              .agg(date_modified=("date_modified", "min"),
                   full_name=("full_name", "first"),
                   report_status=("report_status", "first"),
                   position=("position", "first")))
    grp = grp[grp.norm_name != ""]
    print(f"sampling frame: {len(grp)} player-weeks Out/Doubtful 2021-2022")
    samp = grp.sample(n=min(N_SAMPLE, len(grp)), random_state=SEED).reset_index(drop=True)

    con = sqlite3.connect(DB)
    ent = pd.read_sql("SELECT article_url, player_name, team FROM entities", con)
    art = pd.read_sql(
        "SELECT url, date_published, human_date_raw, headline, event_class FROM articles "
        "WHERE http_status=200", con)
    con.close()
    # TWO-PASS timestamp parse (fix 2026-10-01): a single pd.to_datetime() over the
    # mixed ISO + date-only series coerces all date-only values to NaT (pandas locks
    # the ISO format), silently dropping 41% of the corpus. Pass 1: ISO; pass 2:
    # human byline "%B %d, %Y, %I:%M %p EST/EDT" -> UTC.
    iso_mask = art.date_published.str.startswith("20", na=False)
    art["dp"] = pd.to_datetime(art.date_published.where(iso_mask), utc=True, errors="coerce")
    need = art.dp.isna()
    h = art.loc[need, "human_date_raw"]
    dt = pd.to_datetime(h.str.replace(r"\s+(EST|EDT)$", "", regex=True),
                        format="%B %d, %Y, %I:%M %p", errors="coerce")
    tzname = h.str.extract(r"(EST|EDT)$")[0]
    off = tzname.map({"EST": -5, "EDT": -4})
    art.loc[need, "dp"] = (dt - pd.to_timedelta(off, unit="h")).dt.tz_localize("UTC")
    art["dp"] = pd.to_datetime(art["dp"], utc=True, errors="coerce")
    print(f"article timestamps usable: {art.dp.notna().sum()}/{len(art)}")
    ent = ent.merge(art[["url", "dp", "headline", "event_class"]],
                    left_on="article_url", right_on="url", how="left")
    good_events = {"ruled_out", "injury_report", "practice_participation", "expected_to_play"}
    ent = ent[ent.event_class.isin(good_events)]
    ent = ent[ent.team.notna()]  # exclude ambiguous team resolution (conservative)

    results = []
    for _, r in samp.iterrows():
        dm = pd.to_datetime(r.date_modified, utc=True)
        cutoff = dm - pd.Timedelta(hours=LEAD_HOURS)
        window_start = cutoff - pd.Timedelta(days=LEAD_WINDOW_DAYS)
        hits = ent[(ent.player_name == r.norm_name) & (ent.dp.notna())
                   & (ent.dp < cutoff) & (ent.dp >= window_start)]
        # team consistency: prefer same-team hits but count any (record both)
        same_team = hits[hits.team == r.team]
        results.append({
            "full_name": r.full_name, "norm_name": r.norm_name, "season": r.season,
            "week": r.week, "team": r.team, "position": r.position,
            "report_status": r.report_status, "date_modified": r.date_modified,
            "n_lead_articles": len(hits), "n_lead_same_team": len(same_team),
            "lead_urls": " | ".join(hits.article_url.head(5)),
            "lead_headlines": " | ".join(hits.headline.head(3).fillna("")),
            "earliest_lead": str(hits.dp.min()) if len(hits) else "",
        })
    res = pd.DataFrame(results)
    res["has_lead"] = res.n_lead_articles > 0
    res["has_lead_same_team"] = res.n_lead_same_team > 0
    res.to_csv(DATA / "news_lead_results.csv", index=False)
    n = len(res)
    print(f"\nsampled cases: {n}")
    print(f"with >=1 injury article >=24h before date_modified: {res.has_lead.sum()} ({res.has_lead.mean():.1%})")
    print(f"  (same-team entity match): {res.has_lead_same_team.sum()} ({res.has_lead_same_team.mean():.1%})")
    print(f"SUCCESS BAR: >=40% -> {'PASS' if res.has_lead.mean() >= 0.40 else 'FAIL'}")
    # distribution of lead times for hits
    print("\nlead-time distribution (hours before date_modified) for cases with hits:")
    leads = []
    for _, r in res[res.has_lead].iterrows():
        dm = pd.to_datetime(r.date_modified, utc=True)
        for u in r.lead_urls.split(" | "):
            dp = ent.loc[ent.article_url == u, "dp"]
            if len(dp) and pd.notna(dp.iloc[0]):
                leads.append((dm - dp.iloc[0]).total_seconds() / 3600)
    if leads:
        s = pd.Series(leads)
        print(s.describe(percentiles=[.25, .5, .75, .9]).to_string())

if __name__ == "__main__":
    main()
