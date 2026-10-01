# Injury Cutoff Policy — Blocker 2 (Injury Timestamps)

**Status:** RESOLVED (policy defined; implementation pending in build scripts).
**Scope:** all historical seasons 2018–2022. 2023–2025 vault untouched; no 2026 live data used.
**Owner:** research lead (2026-09-29).

## 1. What this policy governs

The `player_availability` features (`avail_value_out`, `avail_n_out`) are built from
nflverse weekly injury reports (`data/v2/raw/injuries_{YYYY}.csv`) joined to a
snap-count value proxy. Cale's hard rule: **`date_modified < prediction_cutoff`,
with the cutoff explicitly defined per experiment type.** "Eventually known
before kickoff" ≠ "knowable at prediction time" — a player ruled Out on Friday
was eventually known before a Sunday kickoff, but was NOT knowable at a
Tuesday-AM prediction cutoff.

## 2. Timestamp semantics (2018–2022 injury files)

Inspection of `injuries_2018.csv` … `injuries_2022.csv` (REG rows; 26,375 total):

- **One row per (season, week, team, player)** — `date_modified` is the row's
  **last-update timestamp**, not a history. A player listed Questionable
  Wednesday then ruled Out Friday appears once, with the Friday timestamp and
  final status `Out`. **Intra-week interim states are unrecoverable.**
- `date_modified` parses cleanly as UTC ISO-8601 (`...Z`) for all rows; **zero
  nulls** in 2018–2022 REG.
- Distribution (ET) clusters in real reporting windows: 99% of rows are
  modified Wednesday–Friday, peaking ~15:00 ET Friday (final designations).
  This is a genuine last-update timestamp, not a scrape artifact.
- **Weekly report cycle starts Wednesday.** In 2021–2022, zero Out/Doubtful
  rows carry a Monday or Tuesday timestamp — the nflverse rows follow the
  weekly report cycle, not the news date (e.g., a player placed on IR Monday
  first appears in the Wednesday practice report).
- **No cross-week staleness:** no row has `date_modified` more than 7 days
  before its game kickoff — every row was last touched inside its own game
  week (no carryover contamination).
- 23 rows (2018–2022 REG) have `date_modified` **after** their team's kickoff.
  All are non-Sunday-game teams with next-day postgame edits (e.g., ATL 2019
  W13: Thanksgiving game Thu 2019-11-28; rows re-touched Fri 2019-11-29
  13:25–13:28 UTC). These rows are why a bare "week-grain" rule leaks:
  week grain would include a postgame Friday edit as "known before kickoff."
- 17 rows in 2021–2022 belong to bye weeks (team has no game that week) and
  cannot be anchored to a kickoff; they are excluded from survival statistics
  and contribute nothing to any prediction (bye teams have no game to predict).

## 3. Kickoff-time source

`data/games.csv` (nflverse schedule): `gameday` (date) + `gametime` (HH:MM,
stadium-local America/New_York) + `weekday`. **Minute precision**, 0% missing
for 2018–2022 REG. Compare to `date_modified` by converting ET → UTC.
Alternative `data/schedules_2018_2025.parquet` carries the same fields; this
policy standardizes on `data/games.csv`.

## 4. Cutoff definitions

All cutoffs are in **America/New_York**, converted to UTC for comparison.
The cutoff is a property of the *experiment's information set*, not of the
game — parameterized as `cutoff_type ∈ {tuesday_am, friday}`.

### (a) Tuesday-AM information set (V2's intended set)

> **Rule:** `cutoff = 08:00 ET on the most recent Tuesday strictly before the
> team's kickoff.`

- Sunday game → Tuesday 5 days prior; Thursday game → Tuesday 2 days prior;
  Monday game → Tuesday 6 days prior.
- 08:00 ET aligns with the live Tuesday snapshot convention
  (`scripts/22_tuesday_snapshot.py` runs Tue ~8am CT ≈ 07:00 ET; 08:00 ET is
  the conservative bound).
- **Implication:** because the weekly injury-report cycle starts Wednesday
  (§2), the Tuesday-AM info set contains **no current-week Out/Doubtful
  designations** (empirically 0.0% in 2021–2022, §5). A player injured in
  Sunday's game and ruled Out Friday was eventually known before the *next*
  Sunday kickoff but was not knowable Tuesday — correctly excluded.

### (b) Friday snapshot

> **Rule:** `cutoff = 23:59:59 ET on the most recent Friday strictly before the
> team's kickoff`, **applicable only to games not yet played Friday evening**
> (Sunday/Monday/Saturday games).

- Captures the final Friday designations (~16:00 ET) plus Friday-evening
  breaking news — the same information state the live Friday pipeline
  (`07_update_weekly` + `11_injury_adjust`, consolidated by
  `scripts/23_friday_snapshot.py`) observes.
- Saturday/Sunday-morning news (e.g., game-day inactives) is **not** knowable
  Friday — correctly excluded.
- **Thursday games are out of scope** for the Friday info set (already played
  when the live Friday pipeline runs; their report finalizes Wednesday).
- **Monday games:** MNF final designations land Saturday, which is genuinely
  *not* knowable Friday evening. The single-`date_modified` granularity also
  destroys the interim Friday practice-report states (§2), so as
  *reconstructible from these files* the Friday info set for MNF teams is
  nearly empty (3.8% of Out/Doubtful rows). This is faithful to a real Friday
  prediction, not a data bug — but the intra-week history loss is a known
  limitation (§9).

## 5. Survival fractions (2021–2022, REG, teams with a game that week)

Denominators exclude the 17 bye-week rows. `pre_ko` = `date_modified` <
team's own kickoff. Cutoffs per §4.

| report_status | n | date_modified < kickoff | knowable Tuesday-AM | knowable Friday |
|---|---|---|---|---|
| Out | 1,937 | 100.0% | **0.0%** | 83.3% |
| Doubtful | 311 | 100.0% | **0.0%** | 87.8% |
| Questionable | 2,917 | 100.0% | **0.0%** | 86.5% |
| (practice-only, no designation) | 5,616 | 99.95% | 1.4% | 88.8% |
| **Out + Doubtful** | **2,248** | **100.0%** | **0.0%** | **83.9%** |

Of the 2,248 Out/Doubtful rows: **83.9% are knowable Friday but not Tuesday**;
**16.1% are modified Saturday or later** — known before kickoff but knowable
at *neither* cutoff. For Sunday games alone (the Friday info set's core),
**99.1%** of Out/Doubtful rows are knowable by the Friday cutoff; the
shortfall is MNF teams (§4b) and Thursday games (out of scope).

Reading: under a Tuesday-AM cutoff, per-team-week availability from the
current week's report is **identically zero** — the features contribute
nothing at Tuesday granularity. Under the Friday cutoff, ~84% of the
Out/Doubtful signal survives.

(2018–2022 pre-kickoff survival is 99.9%; the 23 exceptions are the
postgame-edited non-Sunday rows in §2 — the case the kickoff guard exists for.)

## 6. The knowable-vs-eventually-known distinction (concrete examples)

**Example A — knowable Friday, NOT knowable Tuesday.**
Evan Engram, TE, NYG, 2021 Week 1. Row: `report_status=Out`,
`date_modified=2021-09-10T19:14:51Z` (Fri 15:14 ET). Game: Sun 2021-09-12,
16:25 ET. Tuesday cutoff = Tue 2021-09-07 08:00 ET → **excluded**. Friday
cutoff = Fri 2021-09-10 23:59:59 ET → **included**. A Tuesday prediction must
treat Engram as available; a Friday prediction must not. (Same pattern: Eric
Fisher T IND W1, Dennis Gardeck LB ARI W1 — 1,804 of 2,248 Out/Doubtful rows
are Friday-stamped.)

**Example B — eventually known before kickoff, knowable at NEITHER cutoff.**
Minkah Fitzpatrick, S, PIT, 2022 Week 10. Row: `report_status=Out`,
`date_modified=2022-11-12T21:50:44Z` (Sat 16:50 ET). Game: Sun 2022-11-13,
13:00 ET. Known ~20h before kickoff (Saturday downgrade) — but **excluded**
under both the Tuesday and Friday cutoffs. A Friday pipeline legitimately
misses him. (Same pattern: Zach Ertz TE ARI 2021 W6, Sat 15:37 ET; Jadeveon
Clowney DE CLE 2022 W18, Sat 13:53 ET.)

**Example C — game-day morning, known before kickoff only.**
River Cracraft, WR, MIA, 2022 Week 8. `report_status=Out`,
`date_modified=2022-10-30T08:01:22Z` (Sun 04:01 ET); game Sun 13:00 ET.
Game-day inactives news — knowable to no prediction pipeline in this project.

**Example D — why the kickoff guard is mandatory (Thursday games).**
ATL 2019 Week 13: Thanksgiving game Thu 2019-11-28. Rows for Austin Hooper
(Out), Julio Jones (Questionable) carry `date_modified` Fri 2019-11-29 —
*postgame* edits. A week-grain "before the week's first kickoff" or
"eventually known" rule would leak postgame information; the per-team
`date_modified < kickoff` guard excludes them.

## 7. What the missing `date_modified` in 2025/26 files implies

The 2025 (and 2026) injury files **have no `date_modified` column at all**
(schema differs: `season_type` column present, no timestamp columns).
Implications — stated, not fixed:

1. **No pregame-cutoff discipline is possible for 2025/26 injury data.**
   Any availability feature built from those files cannot implement §8.
2. Therefore: **2025/26 injury rows are unusable for `avail_value_out` /
   `avail_n_out`** in any experiment that must respect prediction-time
   cutoffs. A week-grain fallback (all rows in the week's report count as
   known) is **not acceptable** — it is exactly the leak demonstrated in
   Example D, and it would also smuggle Saturday/Sunday news into a Friday
   cutoff (Examples B, C).
3. The only compliant use of 2025/26 injury data is **postgame descriptive**
   (e.g., "who was listed Out that week") with an explicit no-timing claim.
   Documented bias if ever used: overstates knowability at both cutoffs.
4. When a 2026 live pull regains per-row timestamps, the live pipeline must
   apply §8 at pull time (the Tuesday snapshot already runs Tuesday;
   `scripts/22/23` are the live implementation of this policy — §9).

## 8. Pipeline spec

**Row-level inclusion rule** (applies to every team-week feature row):

```
include row  ⟺  date_modified < min(prediction_cutoff, team_game_kickoff)
```

- `prediction_cutoff` ∈ { Tuesday 08:00 ET (§4a), Friday 23:59:59 ET (§4b) },
  chosen by the experiment's declared information set. Thursday games under
  the Friday info set are excluded from prediction (already played).
- The `team_game_kickoff` guard is non-negotiable: it excludes the 23
  postgame-edited rows and any future post-kickoff touches.
- Comparison in UTC; ET cutoffs converted via America/New_York.
- Rows for bye-week teams (no kickoff to anchor to) are dropped.

**Aggregation rule** (as the features are currently defined):

1. Filter rows to `report_status ∈ {Out, Doubtful}`.
2. Map each surviving row to a value weight: the player's **season snap-share**
   (offense snaps / team-season offense snaps, snap-count value proxy;
   name-match snap `player` ↔ injury `full_name`, lowercased/stripped —
   unmatched rows contribute 0, documented fuzz).
3. `avail_value_out` = Σ snap-share over surviving rows (value-weighted).
4. `avail_n_out` = count of surviving rows (comparison only; not a signal).
5. `Questionable` and practice-only rows are **excluded** from both features
   (current definition; any Questionable inclusion is future work, §9).

**Cutoff parameter:** every downstream consumer of these features must take
`cutoff_type` and apply §4 before aggregation. The grain is
team × pred_week; when the grain is an expanding mean, each week's value
must be computed under the *same* cutoff type (a Tuesday-AM expanding mean
is all zeros — that is the correct, faithful result, not a bug).

**Implementation gap (known, not fixed here):** `scripts/33_v2_features_player.py`
reads `date_modified` and claims "strictly before the week's first kickoff"
in its docstring, but **the code never applies any timestamp filter** — it
aggregates all week-grain rows, i.e., the Example-D leak is live in the
current build. When the pipeline is rebuilt, replace with the §8 rule. The
"week's first kickoff" convention also documented in `leakage_audit.md` is
superseded by this policy: it is over-conservative for Sunday teams (would
drop Friday-known injuries — Example A) and the wrong grain (cutoff, not
kickoff, is the binding constraint for Sun/Mon games).

## 9. Unresolved

1. **Intra-week history loss.** A single last-update timestamp per row means
   interim states (e.g., Friday practice report for MNF teams, later
   overwritten by the Saturday final) are unrecoverable. Fixing this needs
   timestamped intra-week report history, which the nflverse files do not
   carry. Bounded impact: primarily MNF teams under the Friday cutoff.
2. **Questionable aggregation.** Current features exclude Questionable;
   whether to include it (and at what value weight) is a design decision for
   the V2 build, not this policy.
3. **Live 2026 pulls.** When `load_injuries()` regains per-row timestamps,
   the Tuesday/Friday snapshots (scripts 22/23) are the live implementation
   of this policy — verify at that time that the pull preserves
   `date_modified` and that the Friday pull applies the §8 rule before the
   features are written. The 2025/26 CSVs must not be used as a substitute.
4. **Practice-only rows** (no `report_status`) are excluded from the current
   features; whether limited-practice participation carries orthogonal
   information is out of scope for Blocker 2.
