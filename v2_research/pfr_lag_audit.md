# Blocker 3 — PFR Tuesday-Lag Audit

**Owner:** research lead (blocker 3 of 5)
**Date:** 2026-09-29
**Scope:** all 17 `pressure_pfr` features in `v2_research/feature_inventory.json`
**Boundaries honored:** no training, no fitted weights, no validation metrics, no vault
(2023–2025), no Experiment 006 observations, no V2-A:E, V1 read-only. All
computation/description below uses 2018–2022 only and is architectural, not
evaluative.

---

## 1. Headline verdict

**All 17 `pressure_pfr` features → LAG ONE WEEK. Zero KEEP. Zero DROP.**

Pro Football Reference's own published guidance says its advanced statistics
"don't fully update until the Wednesday morning following the weekend's games."
The V2 Tuesday information set is cut at **Tuesday 08:00 CT** of the game week
(the standing Tuesday snapshot convention: `scripts/22_tuesday_snapshot.py` /
`nfl-timing-tuesday-snapshot` cron, ~8am CT). Week W−1's PFR advanced stats are
therefore *not yet published* when the Tuesday snapshot for prediction week W
is taken — even though the underlying games occurred Sunday/Monday. For
prediction week W, only PFR data from games through **week W−2** may enter the
Tuesday set.

This supersedes the note in `v2_research/leakage_audit.md` ("Consume in the
Tuesday batch, not Monday", "timestampable to the Tuesday batch", "~1 day lag"),
which was written on the assumption that a ~1-day post-game lag is the whole
story. PFR's official Wednesday-morning statement is a *not-before* bound: the
weekend's advanced stats are not complete until Wednesday AM, i.e. **after**
the Tuesday 08:00 CT snapshot.

## 2. The Tuesday information-set boundary

- **Cutoff:** Tuesday 08:00 CT of game week W, prior to any week-W kickoff.
- **Rule:** any PFR advstats row with `week = W−1` must not be consumed at that
  cutoff. Only rows with `week <= W−2` are admissible.
- **Applies uniformly** to every feature derived from the PFR advstats scrape
  (pass and def files). Partial week-W−1 publication (some teams/games posted
  earlier) does not qualify: a partially-updated weekly file would corrupt the
  team-week aggregates in `team_week_pfr.parquet` (missing players/teams
  silently bias sums and means), so only complete weeks are admissible.

## 3. Feature inventory: which raw file each feature derives from

Source of truth: `scripts/32_v2_features_pfr.py` (player-grain →
team × season × played-week aggregates). Raw inputs:
`data/v2/raw/advstats_week_{pass,def}_{YYYY}.parquet` (2018–2022 asserted).

### 3a. From `advstats_week_pass_*.parquet` (offense / pass protection)

| # | feature | raw PFR column(s) | aggregation | verdict |
|---|---------|-------------------|-------------|---------|
| 1 | `pressure_allowed_pct` | `times_pressured_pct` of primary passer (max `times_pressured`) | primary-passer take | LAG ONE WEEK |
| 2 | `sacks_allowed` | `times_sacked` | team sum | LAG ONE WEEK |
| 3 | `hits_taken` | `times_hit` | team sum | LAG ONE WEEK |
| 4 | `hurries_taken` | `times_hurried` | team sum | LAG ONE WEEK |
| 5 | `blitzed_taken` | `times_blitzed` | team sum | LAG ONE WEEK |
| 6 | `pressures_taken` | `times_pressured` | team sum | LAG ONE WEEK |
| 7 | `drops` | `passing_drops` | team sum | LAG ONE WEEK |
| 8 | `bad_throw_pct` | `passing_bad_throw_pct` of primary passer | primary-passer take | LAG ONE WEEK |

### 3b. From `advstats_week_def_*.parquet` (defense / pass rush + coverage)

| # | feature | raw PFR column(s) | aggregation | verdict |
|---|---------|-------------------|-------------|---------|
| 9 | `def_blitzes` | `def_times_blitzed` | team sum | LAG ONE WEEK |
| 10 | `def_hurries` | `def_times_hurried` | team sum | LAG ONE WEEK |
| 11 | `def_qb_hits` | `def_times_hitqb` | team sum | LAG ONE WEEK |
| 12 | `def_sacks` | `def_sacks` | team sum | LAG ONE WEEK |
| 13 | `def_pressures` | `def_pressures` | team sum | LAG ONE WEEK |
| 14 | `def_missed_tackles` | `def_missed_tackles` | team sum | LAG ONE WEEK |
| 15 | `def_adot_allowed` | `def_adot` | mean across defenders (documented approximation) | LAG ONE WEEK |
| 16 | `def_ypt_allowed` | `def_yards_allowed_per_tgt` | mean across defenders (documented approximation) | LAG ONE WEEK |
| 17 | `def_prating_allowed` | `def_passer_rating_allowed` | mean across defenders (documented approximation) | LAG ONE WEEK |

No per-field differentiation is possible: PFR's statement covers "advanced
statistics across the site" as a whole, and the pipeline consumes only these
two scraped files. No field is demonstrably published by Tuesday AM, so no
feature earns KEEP. No feature needs DROP: a uniform one-week lag fully
resolves the timing violation.

## 4. Publication-timing research (what was verified, what was assumed)

### 4a. PFR publication timing — VERIFIED (primary-source statement)

Sports-Reference's official PFR blog announcement, "Advanced Team Statistics
Tables Now on PFR" (October 11, 2019):

> "A reminder that **advanced statistics across the site don't fully update
> until the Wednesday morning following the weekend's games.**"

Source: https://www.sports-reference.com/blog/category/pro-football-reference-com/page/7/

Corroborated by the boilerplate on live PFR player pages ("[Advanced stats]
are updated the Wednesday following the week's games"), rendered here via a
page mirror of a real PFR player page:
https://www.dejavu.org/cgi-bin/get.cgi?ver=95&url=https%3A%2F%2Fwww.pro-football-reference.com%2Fplayers%2FR%2FRivePh00.htm

Interpretation for the Tuesday set: "don't fully update until Wednesday
morning" is a not-before bound, not a promise they land exactly then. At the
Tuesday 08:00 CT snapshot, week W−1 advanced stats are incomplete (and may be
partially posted — which is worse, because partial weeks would silently
corrupt team-week sums/means). Either way they are inadmissible.

### 4b. nflverse refresh cadence — VERIFIED (schedule), binding constraint identified

The nflverse PFR pipeline lives in the `nflverse/nflverse-pfr` repo ("stores
code and workflows for updating nflverse snap counts and PFR advanced stat
summaries… pushed to GitHub releases at nflverse-data/releases"):
https://github.com/nflverse/nflverse-pfr/blob/HEAD/README.md

Its `update_advanced_stats.yaml` workflow is scheduled **every 6 hours**
(0/6/12/18 UTC) during Sep–Jan, per the nflverse-data workflow schedule doc:
https://github.com/nflverse/nflverse-data/blob/HEAD/workflows.md

Finding: **the nflverse scraper cadence is not the binding constraint — PFR's
own publication timing is.** Even a Tuesday-08:00-CT (13:00 UTC) scrape,
minutes after the 12:00 UTC run, can only fetch what PFR has published, and
PFR says the week-W−1 advanced stats are not fully updated until Wednesday
morning. So the lag requirement stands regardless of how often nflverse
scrapes.

### 4c. What was NOT verified (assumed conservative)

- PFR's "Wednesday morning" is stated without a timezone; treated as Wednesday
  AM US time (~24h after the Tuesday 08:00 CT snapshot). The exact hour does
  not change the verdict.
- No per-field or per-week publication order was found or assumed. The uniform
  one-week lag covers the worst case.
- No field-level revision history exists to audit retroactively (see §6).

## 5. Default-conservative rule (standing rule going forward)

> **Where publication timing cannot be verified for a PFR-derived feature, the
> feature is lagged one week — never assumed timely.**

The burden of proof runs one way: KEEP requires affirmative evidence the
statistic is published by Tuesday 08:00 CT. Absent that evidence, LAG ONE WEEK.
This is the same information-time discipline Experiment 006 applies
prospectively; the historical pipeline must honor it too.

## 6. Timestamp / revision markers in the raw files

**Checked and absent.** Inspected the column sets of
`advstats_week_pass_2018.parquet` and `advstats_week_def_2018.parquet` (24 and
29 columns respectively): they carry `season`, `week`, `game_id`,
`pfr_game_id`, `pfr_player_id`, `pfr_player_name`, `team`, `opponent`,
`game_type`, and the stat columns — **no publication timestamp, no
`date_modified`, no revision/version/snapshot marker of any kind.** (Columns
containing "times_" e.g. `times_sacked` are stat names, not timestamps.)

Consequence: there is no in-file way to reconstruct what PFR had published at
any historical Tuesday snapshot. This audit therefore rests entirely on the
publication-schedule research in §4 plus the conservative default in §5.

## 7. What survives in the Tuesday set (degradation accounting)

Features themselves survive — the family stays, at one-week-lagged history.
The degradation is in **effective sample**, not feature count:

- Feature grain is expanding history over played weeks with `min_sample = 4
  prior games` (per inventory). With the lag, prediction week W may use only
  weeks ≤ W−2.
- Weeks 1–4 of a season: below `min_sample` with or without the lag → NaN
  (already handled by the 4-game minimum; blocker 4's prior-games bucketing
  governs this region).
- **Prediction week 5 is the casualty of the lag:** without lag it would use
  weeks 1–4 (exactly 4 games, meeting the minimum); with the lag it uses
  weeks 1–3 (3 games → below minimum → NaN).
- **Week 6+:** full expanding history, but every week's aggregate is computed
  without the most recent week's data — the single most form-relevant week is
  systematically excluded.
- **Train/serve consistency requirement (critical):** the historical table
  `data/v2/team_week_pfr.parquet` was built from complete historical files, so
  its rows are *not* Tuesday-timely as stored. Any future walk-forward use
  must apply the one-week shift (predict week W from rows with week ≤ W−2),
  not consume the raw table as if it were available at the Tuesday snapshot.
  Failure to shift = information-time leakage of exactly the class
  Experiment 006 studies.

## 8. Refined-filter note

The refined filter makes low correlation with the latent team-strength signal
a priority, not a hard exclusion. Per the inventory, all 17 `pressure_pfr`
features are already tagged `overlaps_v1: LOW` and `genuinely_new: LIKELY`
(pressure is a trench-process signal V1 does not model). This audit changes
nothing about that priority assessment — it changes only *when* the data may
be consumed, not whether the family belongs. No feature is dropped merely for
being correlated with ELO/EPA; none are, per the current tags.

## 9. Tag changes proposed

Patch file: `v2_research/tag_updates_pfr.json` (patch only — do not edit
`feature_inventory.json` directly). For each of the 17 features:

- `timestamp_availability` → "PFR publishes advanced stats Wednesday AM after
  the week's games (PFR's own statement); nflverse scrapes 6-hourly so PFR
  publication is the binding constraint. Tuesday 08:00 CT snapshot uses games
  through week W−2 only (LAG ONE WEEK)."
- `leakage_status` → "LAG ONE WEEK — week W−1 advstats not published by Tuesday
  AM; consuming them is information-time leakage. Live pipeline must use weeks
  ≤ W−2; historical team_week_pfr.parquet must be shifted the same way. See
  v2_research/pfr_lag_audit.md."

## 10. What remains unresolved

1. **Per-week reality checks:** PFR's Wednesday-morning statement is a standing
   policy, not a per-week guarantee; some weeks may finalize earlier or later.
   The lag rule handles this by design, but the true weekly distribution of
   PFR publication times is unverified and cannot be reconstructed from the
   raw files (no timestamps, §6).
2. **nflverse scraper observed behavior:** the 6-hourly cron is documented, not
   observed; transient delays (rate limits, PFR HTML changes, seasonal manual
   re-enabling noted by third-party consumers) are possible but irrelevant to
   the verdict, since PFR publication is binding.
3. **Historical train/serve shift implementation:** the required one-week shift
   of `team_week_pfr.parquet` for any future walk-forward use is specified
   here (§7) but not implemented — implementation belongs to the modeling stage
   (V2-A:E, not authorized), not to this audit.
4. **Interaction with blocker 4 (Weeks 1–4 bucketing):** the lag pushes week 5
   below the 4-game minimum; the prior-games bucketing resolution owns how
   early-season weeks are handled.
5. **Experiment 006 alignment:** the prospective timing study's live stream
   (from Week 5) should independently confirm when PFR advanced stats are
   actually complete each week; its findings may refine or confirm this audit's
   conservative stance. 006 observations remain untouched per protocol.
