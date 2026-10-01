#!/usr/bin/env python3
"""
06_report_stats.py — Criteria 1, 2, 5 + audit sample exports.

C1 coverage: >=80% of 2018-2022 REG weeks with >=20 injury-relevant articles.
    Week W window (ET): [Sunday(W)-5d, Sunday(W)+1d] (Tue..Mon).
C2 timestamp validity: export 50-article sample (10/season, seeded) with
    date_published vs human_date_raw for manual audit; also programmatic
    same-calendar-day agreement rate as a first pass.
C5 Sunday-morning QB density: QB-relevant articles with date_published on a
    Sunday 00:00 ET <= t < that team's kickoff (from schedules).
C3 sample export: 100 articles (seeded) with their entities for manual audit.

Outputs: data/audit_ts_sample.csv, data/audit_entity_sample.csv, printed stats.
"""
import json, sqlite3
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = DATA / "pft_sitemap.db"
SEED = 20260929

def main():
    con = sqlite3.connect(DB)
    art = pd.read_sql(
        "SELECT url, slug, date_published, human_date_raw, parsely_pub_date, "
        "headline, event_class, qb_relevant, n_entities FROM articles "
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
    # NFL weeks anchored on ET Sundays
    art["dp_et"] = art.dp.dt.tz_convert("US/Eastern").dt.tz_localize(None)

    sched = pd.read_parquet(DATA / "schedules_2018_2022.parquet")
    sched = sched[sched.game_type == "REG"].copy()
    sched["gameday"] = pd.to_datetime(sched.gameday)

    # ---- week windows: Sunday with most games per (season, week) ----
    week_sun = (sched[sched.weekday == "Sunday"].groupby(["season", "week"])["gameday"]
                .agg(lambda x: x.mode().iloc[0]).reset_index()
                .rename(columns={"gameday": "sunday"}))
    week_sun["win_start"] = week_sun.sunday - pd.Timedelta(days=5)
    week_sun["win_end"] = week_sun.sunday + pd.Timedelta(days=1)

    def assign_week(row):
        c = week_sun[(week_sun.season == row["season_et"]) &
                     (week_sun.win_start <= row["dp_et"]) &
                     (row["dp_et"] <= week_sun.win_end)]
        if len(c):
            return int(c.iloc[0]["week"])
        return None
    art["season_et"] = art.dp_et.dt.year
    # season year: Sep-Dec -> that year; Jan -> prior year (playoffs not in scope anyway)
    art["season_et"] = art.apply(
        lambda r: r.season_et if (pd.notna(r.dp_et) and r.dp_et.month >= 3) else
        (r.season_et - 1 if pd.notna(r.dp_et) else None), axis=1)
    art["nfl_week"] = art.apply(assign_week, axis=1)

    # ---- C1 coverage ----
    art_ok = art[art.dp.notna() & art.nfl_week.notna()]
    per_week = art_ok.groupby(["season_et", "nfl_week"]).size().reset_index(name="n")
    n_weeks = len(week_sun)
    n_covered = (per_week.n >= 20).sum()
    print(f"C1 COVERAGE: {n_covered}/{n_weeks} REG weeks with >=20 injury-relevant articles "
          f"({n_covered/n_weeks:.1%}) | bar >=80% -> {'PASS' if n_covered/n_weeks>=0.8 else 'FAIL'}")
    print(f"  articles with usable timestamps: {len(art_ok)}/{len(art)}")
    thin = per_week[per_week.n < 20].sort_values("n")
    if len(thin):
        print(f"  thinnest weeks: {thin.head(10).to_dict('records')}")
    per_week.to_csv(DATA / "coverage_per_week.csv", index=False)

    # ---- C2 timestamp sample ----
    # pandas>=2.2 groupby.apply drops grouping columns from the result; use
    # explicit per-group sampling to keep all columns (same seeds => same draws).
    ts_parts = [g.sample(n=min(10, len(g)), random_state=SEED)
                for _, g in art_ok.groupby("season_et")]
    ts_samp = pd.concat(ts_parts, ignore_index=True)
    ts_samp[["season_et", "nfl_week", "date_published", "human_date_raw",
             "parsely_pub_date", "headline", "url"]].to_csv(
        DATA / "audit_ts_sample.csv", index=False)
    # programmatic first pass: same calendar day (ET)
    def same_day(r):
        m = pd.Series([r.human_date_raw]).str.extract(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d\d)")
        if m.isna().any().any():
            return None
        import datetime
        months = {m_: i+1 for i, m_ in enumerate(
            ["January","February","March","April","May","June","July","August",
             "September","October","November","December"])}
        try:
            hd = datetime.date(int(m.iloc[0,2]), months[m.iloc[0,0]], int(m.iloc[0,1]))
        except Exception:
            return None
        return hd == r.dp_et.date()
    ts_samp["same_day_prog"] = ts_samp.apply(same_day, axis=1)
    v = ts_samp.same_day_prog.dropna()
    print(f"\nC2 TIMESTAMP (programmatic first pass, n={len(v)} parseable): "
          f"same-day agreement {v.sum()}/{len(v)} = {v.mean():.1%}")
    print("  -> manual verification of extraction on subset still required; see audit_ts_sample.csv")

    # ---- C5 Sunday-morning QB density ----
    qb = art[(art.qb_relevant == 1) & art.dp.notna()].copy()
    qb["dow"] = qb.dp_et.dt.day_name()
    qb_sun = qb[qb.dow == "Sunday"].copy()
    # kickoff per team-game: build (season, team, gameday) -> kickoff ET
    games = []
    for _, r in sched.iterrows():
        kt = pd.to_datetime(r.gameday.strftime("%Y-%m-%d") + " " + str(r.gametime))
        games.append((r.season, r.away_team, r.gameday.date(), kt))
        games.append((r.season, r.home_team, r.gameday.date(), kt))
    kg = pd.DataFrame(games, columns=["season", "team", "gameday", "kickoff"])
    con = sqlite3.connect(DB)
    ent = pd.read_sql("SELECT article_url, team FROM entities WHERE position='QB' AND team IS NOT NULL", con)
    con.close()
    qb_sun = qb_sun.merge(ent, left_on="url", right_on="article_url", how="left")
    qb_sun = qb_sun.merge(kg, left_on=["season_et", "team"],
                          right_on=["season", "team"], how="left")
    # match gameday: article ET date == game date
    qb_sun["art_date"] = qb_sun.dp_et.dt.date
    qb_sun = qb_sun[qb_sun.art_date == qb_sun.gameday]
    qb_sun["pre_kickoff"] = (qb_sun.dp_et >= qb_sun.art_date.map(
        lambda d: pd.to_datetime(d))) & (qb_sun.dp_et < qb_sun.kickoff)
    pre = qb_sun[qb_sun.pre_kickoff]
    print(f"\nC5 SUNDAY-MORNING QB DENSITY:")
    print(f"  QB-relevant Sunday articles: {qb_sun.url.nunique()} (article-team pairs: {len(qb_sun)})")
    print(f"  published 00:00 ET <= t < kickoff: {pre.url.nunique()} unique articles")
    print(f"  by season: {pre.groupby('season_et').url.nunique().to_dict()}")
    pre[["season_et","dp_et","kickoff","team","headline","url"]].to_csv(
        DATA / "sunday_qb_articles.csv", index=False)

    # ---- C3 entity sample export ----
    ent_parts = [g.sample(n=min(20, len(g)), random_state=SEED+1)
                 for _, g in art_ok.groupby("season_et")]
    ent_samp_urls = pd.concat(ent_parts, ignore_index=True).url.tolist()
    con = sqlite3.connect(DB)
    es = pd.read_sql("SELECT * FROM entities WHERE article_url IN (%s)" %
                     ",".join("?" * len(ent_samp_urls)), con, params=ent_samp_urls)
    artsub = art_ok.set_index("url").loc[[u for u in ent_samp_urls if u in art_ok.url.values]]
    con.close()
    out = es.merge(artsub[["headline","date_published"]], left_on="article_url",
                   right_index=True, how="left")
    out.to_csv(DATA / "audit_entity_sample.csv", index=False)
    print(f"\nC3 ENTITY SAMPLE: {len(ent_samp_urls)} articles, {len(out)} entity mentions exported "
          f"-> audit_entity_sample.csv (manual audit by reviewer)")

if __name__ == "__main__":
    main()
