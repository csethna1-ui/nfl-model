# Experiment 011 — Reconstructability Probe: Historical Roster Transactions (2026-10-01)

Data-source investigation only. No modeling, no fitting, no outcome/margin
computation. The 2023–2025 locked test outcomes were not touched.

## Verdict: VIABLE (dated source available) — with an explicit small-n flag

In-season non-QB trades for 2021–2025 are identifiable, dated, and
game-mappable from a keyless source, cross-validated against nflverse roster
structure. **But the usable sample is small (~55–65 trades / ~110–130 treated
team-weeks over five seasons), and the 2021–2022 dev window holds only ~23
trades.** Under the frozen protocol's own terms, "underpowered/inconclusive"
is the likely-correct verdict category if the CI spans both zero and the
0.15 bar — not a forced null. Do not expect this experiment to have power for
the 0.15 MAE bar unless the true effect is large.

## Recommended source combination

1. **Primary identification: Pro Football Rumors yearly "NFL Trades" trackers**
   (e.g. `https://www.profootballrumors.com/2026/08/2026-nfl-trades` —
   fetched and parsed successfully 2026-10-01). Dated entries, explicitly
   typed as trades (player-for-player or player-for-picks), pick-for-pick
   trades excluded by the editors. Keyless HTML, fetchable, no login.
   Annual series; 2024/2025/2026 confirmed, same format all years.
2. **Structural cross-validation: nflverse weekly rosters**
   (`import_weekly_rosters`), week-to-week team-switch diffs. Confirms each
   traded player actually appears on the acquiring team's roster and pins the
   week-granular assignment the protocol accepts as primary.

Rejected / unavailable via this path: Spotrac transactions (HTTP 403 on
fetch), ESPN transactions (domain policy-blocked), NFL.com transaction wire
(domain policy-blocked).

## The five questions

### 1. Can we identify qualifying trades? — YES
PFR's yearly trade tracker lists each trade with both teams, players, and
compensation. Non-QB filter is trivial (position listed per entry). In-season
filter = entries dated Sept 1 through the trade deadline (deadlines: Nov 2
2021, Nov 1 2022, Oct 31 2023, Nov 5 2024, ~Nov 4 2025). Offseason
(Feb–Aug) entries are present but excludable by date. nflverse diffs found
25/25 known trades from independent lists (11/11 for 2021 via Sporting News
deadline tracker; 14/14 for the 2024 deadline window via PFR), each with the
correct teams.

### 2. Can we determine when each trade became publicly knowable? — YES,
day-level
PFR entries are grouped under announcement-date headings (e.g.
"### October 23" → DeAndre Hopkins, Titans→Chiefs). This is strictly finer
than the week-granular minimum the protocol accepts. The date shown is the
report/agreement date, which is the publicly-knowable timestamp.

### 3. Can we reliably assign each trade to the team's NEXT game? — YES,
with one noted caveat
In all 25 validated cases, the nflverse diff's `first_wk_new` (first roster
week on the new team) equals the game week immediately following the trade
date — exactly the protocol's timing rule ("completed/announced before the
team's next game"). **Caveat:** if the acquiring team is on bye in
`first_wk_new`, its next game is a week later; the build needs a schedule
join (nflverse schedules, read-only, no outcomes) to map roster-week →
next-game-week. One edge case observed: Stephen Weatherly (MIN→DEN, traded
Sat Oct 23 2021) shows a 1-week gap in the diffs — the trade fell between
the weekly roster snapshots. Week-granular assignment absorbs this; day-level
refinement would use the PFR date.

### 4. Can we distinguish trades from injury/availability transactions? — YES,
two independent mechanisms
- PFR separates by construction: the trade tracker lists *only* trades;
  IR placements, activations, elevations, and settlements appear in separate
  "Minor NFL Transactions" posts. The exclusion hierarchy's Type A never
  enters the trade list.
- In nflverse diffs, team-switches are structurally distinct from
  status-changes: IR/PUP/elevation events change `status` within a team, not
  `team`. Availability bookkeeping cannot masquerade as a team switch.
- **Documented residual ambiguity (diffs only):** waiver claims appear as
  direct team-switches but are NOT trades — e.g. Diontae Johnson BAL→HOU
  (Dec 2024, waived then claimed) and Emmanuel Forbes to LAR (Dec 2024,
  claimed). The PFR tracker resolves this (claims are not listed as trades);
  **diffs alone over-identify trades by ~2–3x** (28–41 veteran direct
  switches per deadline window vs ~10–16 real trades). The PFR tracker must
  be the identification source; diffs are validation only.
- nflverse roster `status` codes TRC/TRD/TRT are **practice-squad
  elevations, not trades** (single-week appearances by fringe players) —
  the status field cannot identify trades.
- Protocol edge case "trade for a currently injured player": PFR entries
  sometimes note injury context (e.g. the nixed Maxx Crosby physical);
  diffs cannot tell. Flag for manual review at build time.

### 5. How many usable observations? — ~55–65 non-QB in-season trades,
2021–2025

| Season | Non-QB in-season trades | Basis |
|---|---|---|
| 2021 | 11 | Hard count (Sporting News deadline tracker; 11/11 in diffs) |
| 2022 | ~12 | Estimated (40 deadline-window veteran switches × ~30% trade share) |
| 2023 | ~10 | Estimated (32 × ~30%) |
| 2024 | ~14–16 | Hard-ish (14 in PFR deadline window alone; 14/14 in diffs) |
| 2025 | ~8–10 | Estimated (28 × ~30%) |
| **Total** | **~55–65** | → **~110–130 treated team-weeks** (each trade touches 2 teams) |

Calibration: in 2021, 11 real trades out of 39 deadline-window veteran
direct switches (~28%); in 2024, ~14 out of 41 (~34%). 2021 deadline
examples: Von Miller→LAR, Stephon Gilmore→CAR, Zach Ertz→ARI,
Melvin Ingram→KC. 2024: DeAndre Hopkins→KC, Ernest Jones→SEA,
Diontae Johnson→BAL, Marshon Lattimore→WAS, Za'Darius Smith→DET.

**Power implication (stated without touching outcomes):** the dev fit
(2021–2022) would rest on ~23 trades (~46 treated team-weeks); the locked
test on ~35–40 more. A paired CI over ~110–130 treated team-games will be
substantially wider than Exp 010's ±0.13 on n=815 — plausibly ±0.3 or more,
i.e. wider than the 0.15 materiality bar. The experiment can only clear the
bar if the true trade effect is large (order 0.4+ MAE). Otherwise the honest
verdict is **inconclusive**, exactly as the protocol prescribes.

## Sample raw formats

PFR tracker (2026 page, fetched 2026-10-01):
```
### September 30
- **Cowboys** land CB **Joey Porter Jr.** from **Steelers** for **2028
  second-round pick, conditional 2027 sixth-rounder**
```
nflverse diff row (validated trade):
```
season=2021, player='Von Miller', pos='LB', from_team='DEN', to_team='LA',
last_wk_old=8, first_wk_new=9, gap_weeks=0   (traded Nov 1, between W8/W9)
```

## Coverage notes
- PFR trackers are annual editorial pages (third-party, not the league
  wire). 2024/2025/2026 confirmed; 2021–2023 follow the same series format —
  locate exact URLs at build time (small task).
- nflverse weekly rosters 2021–2025: complete (231,942 rows); 2025 REG
  essentially complete (542/544 team-games).
- Polite, keyless HTML scraping of ~5 PFR pages is all the external fetching
  the build needs. No API keys, no login, no Wayback required.

## What the probe did not do
No coefficient fit, no outcome/margin computation, no locked-test access.
All counts above are from transaction/trade lists and roster structure only.
