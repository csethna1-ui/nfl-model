# PREREGISTRATION — Experiment 011: Historical Roster Transactions (Information-Channel Delineation)

**Status: SHELVED — DESIGNED, RECONSTRUCTABLE, UNDERPOWERED. Decided by Cale
2026-10-01.** The protocol below is preserved intact as a research artifact.
It was NOT frozen and the 2023–2025 vault was NOT touched for this
hypothesis. Reason (methodological, not substantive): the reconstructability
probe confirmed the experiment is viable — PFR trade trackers as
identification source, nflverse roster diffs as cross-check, ~55–65
non-QB in-season trades 2021–2025 — but ~23 dev trades imply a paired CI
around ±0.3 or wider against the 0.15 MAE bar. "We couldn't detect a 0.15
effect because the experiment was underpowered" is not the same information
as "the trade channel doesn't matter," so the vault was not spent on a
predictable inconclusive. Program direction shifts to prospective 2026
observation (see §9).

## 1. Research question (binding, narrow)

> Do week-W roster transactions that change team talent contain incremental
> predictive information vs V1's freeze, in the window before V1's ELO
> component absorbs them through game outcomes?

NOT: "does transaction information exist." NOT: "can transactions improve V1"
(a modeling question). This is a channel-delineation experiment: it tests
whether roster transactions are a *new* information channel or the same
player-availability information measured a fifth time.

## 2. The channel-delineation argument (the load-bearing section)

Everything tested to date measures **availability** — who plays on Sunday:

| Tested channel | What it measures | Content type |
|---|---|---|
| PFT timing (PASS) | Injury *news* precedes official reports ~74.5% of the time | Availability, via reporting |
| Phase 2 (NULL) | Official Wed–Fri injury report (Out/Doubtful/Questionable) | Availability, official |
| QB plumbing (production) | Expected starting QB per team-week | Availability, one position |
| Exp 010 (NULL) | T-90 gameday inactive list | Availability, final |

Roster transactions change **who is on the roster**, not who is available from
it. But the category splits into two subtypes with entirely different
information content, and the split is the whole experiment:

- **Type A — availability bookkeeping.** IR placements/activations, PUP/NFI
  moves, gameday practice-squad elevations, injury settlements. These are the
  *administrative shadow of injuries*: the same underlying event (player hurt)
  already measured three ways (Friday report, PFT news, T-90 inactives).
  Testing Type A would be the fourth measurement of the same thing. **Excluded
  from primary scope.** Included only as a secondary redundancy check with a
  *predicted null* — if Type A shows signal beyond inactives, our
  channel-delineation is wrong, and that itself is informative.
- **Type T — talent shocks.** Trades, veteran free-agent signings,
  releases/waivers of vested veterans. These change *how good the roster is*,
  independent of who is hurt. This is the candidate new channel, and its
  mechanism is specific: V1's ELO component absorbs talent changes only
  gradually, through game outcomes (K-factor smoothing over several games). A
  trade's talent impact is knowable at announcement — games before ELO fully
  prices it. The timing gap here is **discrete event vs smoothed ratings**,
  a different dimension from the news-vs-official gap the PFT work measured.

**The new information, stated plainly:** discrete changes in roster talent
that postdate V1's prior-week feature freeze and that V1's ELO has not yet
absorbed through observed game outcomes. Nothing in PFT timing (injury news),
the Friday report (availability of the current roster), QB plumbing (expected
starter), or Exp 010 (final availability from a fixed roster) measures roster
*composition change*.

## 3. What constitutes a transaction (definitional)

**Exclusion hierarchy (applied up front, prevents double-counting across
experiments):**

1. **QB transaction → QB channel.** Excluded from this experiment entirely
   (the QB-plumbing layer already captures expected-starter changes).
2. **IR / injury / elevation / settlement → availability channel.** Type A —
   excluded from primary scope (§2).
3. **Trade (non-QB) → primary Type-T roster-talent channel.**
4. **Non-QB veteran signing / release → secondary Type-T** (descriptive
   only; does not determine the primary coefficient).

**Binding sentence:** the primary treatment must measure roster change that
is knowable before the team's next game but not already represented by the
existing QB/injury/inactive information channels.

A transaction is a change to a team's 53-man roster (or practice squad with
gameday elevation) between week W−1's games and week W's games, classified:

- **TRADE:** player moved team-for-team or team-for-picks. Always Type T.
  Timestamp: announcement (team/league), effective immediately.
- **SIGNING (veteran FA):** vested veteran signed to the 53-man roster.
  Type T, unless signed to replace an IR placement within the same week AND
  the signee's trailing snap share is negligible (camp-body churn) — then
  excluded as noise, not Type A.
- **RELEASE/WAIVER:** vested veteran released. Type T (roster getting worse
  or clearing space is still a talent change; direction handled by the signed
  delta, §5).
- **IR/ PUP/ NFI placement or activation:** Type A. Excluded from primary.
- **Practice-squad elevation (standard or gameday):** Type A (availability
  cover by construction). Excluded from primary.
- **Injury settlement:** Type A. Excluded.

**Edge cases prespecified:** a trade for a player who is currently injured
(e.g., acquiring an IR-bound star) is Type T by form but availability-driven
in substance — flagged, reported separately, excluded from the primary
aggregate. QB transactions are **excluded from primary** (the QB-plumbing
layer already captures expected-starter changes; including them would
double-count a channel we already own).

## 4. Effective timing

- V1's freeze: all features through the prior week; zero current-week
  information (§2 of Exp 010's probe).
- **Timing rule (Cale 2026-10-01):** week-granular timing is sufficient for
  the primary experiment. The operative question is: *was the transaction
  completed/announced before the team's next game?* If yes, it is post-freeze
  information under the same institutional logic as the T-90 list.
- **Temporal resolution, documented explicitly:** the primary treatment
  assignment is week-granular (transaction occurred between week W−1's games
  and week W's kickoffs, inferred from weekly roster diffs). We do not claim
  announcement-day precision we do not have. If dated transaction logs prove
  reconstructable (§7), day-level assignment becomes a secondary refinement —
  not a requirement, and not a reason to re-specify the primary.
- QB transactions excluded per the hierarchy (§3); a trade for a currently
  injured player is flagged and excluded from the primary aggregate
  (Type T by form, availability-driven in substance).

## 5. Measurement (decided by Cale 2026-10-01)

**Primary: trades-only.** The hypothesis is specifically that *discrete,
externally observable roster-talent changes may contain information before
smoothed ELO incorporates them*, and trades are the cleanest test of it.
Veteran signings/releases introduce too much ambiguity about whether the
player meaningfully changes team strength to carry the primary coefficient.

- Per team-week: `TRADE_DELTA = Σ snap_share(incoming via trade) −
  Σ snap_share(outgoing via trade)`, non-QB trades only, snap shares
  trailing-4-week through the prior week (frozen weighting philosophy as
  Exp 010; playing time, not an outcome). Signed away−home, home-margin
  convention.
- One coefficient, fit mechanically on 2021–2022 dev, applied frozen once to
  the 2023–2025 locked test: ΔMAE vs untouched V1, 95% paired CI,
  materiality bar ΔMAE ≥ 0.15 with CI excluding zero — the lab's standard.
- **Power, stated honestly:** in-season trades are ~20–40/year; most
  team-weeks have zero treatment. Low power is preferable to broadening the
  treatment definition to manufacture sample size. **If the sample is too
  small to support a meaningful estimate, the correct result is
  underpowered/inconclusive — not a forced null.** The protocol reports the
  effective n (nonzero team-weeks) alongside any result, and a wide CI that
  includes both zero and material effects is read as inconclusive, not as
  evidence of absence.

**Secondaries (do not determine the primary coefficient):**
- Broader Type-T (non-QB signings/releases) aggregate — descriptive only.
- Type-A redundancy check — **predicted null**; a falsification/delineation
  check that we are not re-measuring the availability channel. Its result
  does not change the Type-T specification under any outcome.
- Absorption curve (1–3 games post-trade) — mechanism check for the
  ELO-absorption story, not a tuning exercise.

**Decided — no longer open:** trades-only primary (§5), week-granular timing
sufficient (§4), Type-A kept as predicted-null secondary. Remaining gate is
the reconstructability probe (§7).

## 6. Confounders, stated honestly

- **Selection:** teams making trades are often underperforming (buyers think
  they're a piece away; sellers are giving up). Transaction occurrence
  correlates with team state V1 may already price — the coefficient measures
  the *announcement surprise*, confounded by *why* the trade happened.
- **Direction ambiguity:** both sides of a trade change talent in opposite
  directions; the signed delta handles this arithmetically but the football
  substance (picks vs players, present vs future value) is coarse.
- **PFT overlap:** PFT covers major trades as news, but the constructed PFT
  timing layer is injury-news only — no overlap in the built corpus. A future
  PFT×transactions design is the "eventually" bucket, not this experiment.
- **Small, lumpy events:** most team-weeks have zero Type-T transactions;
  inference rests on a minority of team-weeks. Power is the binding
  constraint — the draft proposes reporting the effective n (nonzero
  team-weeks) alongside any result.

## 7. Data availability and the reconstructability gate

**Probe completed 2026-10-01 — verdict: VIABLE (dated source available),
with an explicit small-n flag.** Full probe report:
`RECONSTRUCTABILITY_PROBE.md`. The five gate questions, answered:

1. **Identify qualifying trades? YES.** Pro Football Rumors yearly "NFL
   Trades" trackers (e.g. profootballrumors.com/2026-nfl-trades) — dated
   entries, explicitly typed as trades (player-for-player or player-for-picks;
   pick-for-pick excluded by the editors), keyless HTML, no login. Validated:
   25/25 known trades found in nflverse roster diffs with correct teams.
   Non-QB and in-season (Sept 1–deadline) filters are trivial on entry data.
2. **Publicly knowable date? YES, day-level** — entries grouped under
   announcement-date headings. Strictly finer than the week-granular minimum.
3. **Assign to next game? YES, with one caveat** — in all 25 validated cases
   the roster-diff week equals the game week right after the trade date
   (exactly the protocol's timing rule). Bye weeks need a schedule join;
   one snapshot-timing edge case observed, absorbed by week-granular
   assignment.
4. **Distinguish from availability transactions? YES, two independent ways.**
   PFR lists *only* trades (IR/elevations/settlements live in separate posts);
   in diffs, team-switches are structurally distinct from status-changes.
   **Critical:** diffs alone over-identify trades ~2–3x (waiver claims look
   like direct switches — e.g. Diontae Johnson BAL→HOU Dec 2024) — **PFR must
   be the identification source**, diffs the cross-validation. Also: nflverse
   status codes TRC/TRD/TRT are practice-squad elevations, *not* trades.
5. **Count? ~55–65 non-QB in-season trades, 2021–2025** → ~110–130 treated
   team-weeks. Per-season: 2021: 11 (hard) | 2022: ~12 | 2023: ~10 |
   2024: ~14–16 | 2025: ~8–10.

**The small-n flag (headline caveat for the freeze decision):** dev
(2021–2022) rests on ~23 trades (~46 treated team-weeks). The paired CI over
~110–130 treated team-games will be far wider than Exp 010's ±0.13 —
plausibly ±0.3+, wider than the 0.15 bar. The experiment likely **cannot
clear the bar unless the true effect is large**; the honest verdict in the
likely case is **inconclusive**, exactly as §5 prescribes. This is not a
reason to broaden the treatment. The freeze decision should be made with
eyes open.

- nfl_data_py has no native transactions function (checked 2026-10-01).
  Spotrac (403) and ESPN/NFL.com transaction pages (policy-blocked) were
  assessed and are not needed — PFR + nflverse suffice.

## 8. What this experiment will not claim

- It will not re-measure availability information (Type A excluded from
  primary by construction).
- It will not claim tradable edge from any result.
- It will not combine with PFT (reserved), re-litigate Exp 010's null, or
  touch QB plumbing.
- A null here closes the transaction channel as specified; it does not claim
  "front offices don't matter."

## 9. Approval gate — SHELVED

**Shelved by Cale 2026-10-01: DESIGNED, RECONSTRUCTABLE, UNDERPOWERED.**
Design decisions preserved: trades-only primary (§5), week-granular timing
(§4), Type-A predicted-null secondary, exclusion hierarchy + binding sentence
(§3), PFR-as-identification-source with diffs-as-cross-check (§7), confounder
discussion (§6), explicit power limitation (§5, §7). The reconstructability
probe (`RECONSTRUCTABILITY_PROBE.md`) is preserved alongside.

**Program implication:** with PFT PASS (timing channel exists), Exp 010 NULL
(genuine new information, 0.069 MAE), and 011 shelved (different channel,
unresolvable sample), the information-timing investigation moves to
**prospective 2026 observation** rather than further vault experiments. The
2026 Friday stream can observe the full arrival sequence with real
timestamps — Friday V1 freeze → PFT/news → roster changes → inactives →
market movement → kickoff → outcome — which no historical reconstruction can
reliably recover. That protocol is a separate design task; this experiment
is closed as an artifact.
