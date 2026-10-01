# Information Frontier Audit — Executive Report

**Date:** 2026-09-29 | **Type:** read-only research inventory. No training, no fitting, no evaluation. Vault 2023–2025 untouched. V1 untouched. Experiment 006 untouched.

## The question

After three closed-null research branches (features 001–007, component architecture V2-A–D, distributional target 008), the standing conclusion is: **V1 is the ceiling given this information set.** The market holds ~0.33 MAE over V1 on the historical sample (9.73 vs 10.06). This audit asks: *what information does the market have that our free/keyless system cannot reproduce?* Governing question per source: **historically reconstructable (2018+) AND genuinely available before the prediction timestamp?**

## Method

13 information classes audited across two independent research tracks (personnel/availability; market/weather/officiating), using web search and direct verification. Every source tagged VERIFIED / REPORTED / INFERRED. Full dossiers in `source_inventory.md`.

## Headline findings

**There IS a free/keyless news-timing layer we don't have.** ProFootballTalk's article archive (NBC sitemap, 2009+, per-article timestamps verified to the minute) records *when injury news broke* — the process nflverse's weekly designations only record the outcome of. A second verified corpus, Pro Football Rumors' transaction wire (2014+, day-level timestamps), captures Thu–Sat roster moves V1 never sees. Both pass the governing question.

**Confirmed inactives are already free** in nflverse `weekly_rosters` (`INA` token) — lowest-effort source in the audit, though pre-kickoff-only.

**Several requested classes are dead ends, verified:** day-level practice participation is systematically un-reconstructable (nflverse is weekly-only); beat-reporter information is fundamentally un-reconstructable in structured form (every free route checked and dead); the free opener-vs-close odds mirror died in September 2026 (treat all free odds archives as perishable).

**The honest weak spots:** as-issued weather forecasts (IEM MOS) are fully reconstructable but the margin mechanism is weak (forecast ≈ observed + noise; wind is a totals story); referee assignments are reconstructable but totals-heavy with no credible margin effect and a Tuesday-AM leakage trap.

## Ranked shortlist (value × feasibility)

1. **PFT news-timing corpus** — HIGH feasibility (verified bulk path). Case against: entity resolution unproven; coverage skews to notable players; official reports may already capture the outcome.
2. **PFRumors transaction wire** — HIGH feasibility (verified). Case against: low-frequency events, mostly practice-squad churn; Friday/pre-kickoff only.
3. **INA-row inactive ground truth** — HIGH feasibility, ~1 day. Case against: pre-kickoff only; overlaps Out designations; value concentrated in the Questionable bucket.
4. **Sunday-morning QB news** (PFT subset) — MEDIUM feasibility. Case against: rare events; no standalone value outside rank 1.
5. **IEM MOS as-issued forecasts** — HIGH feasibility. Case against: weak margin mechanism; mostly overlaps observed weather.

## The inaccessible gap (what the 0.33 may cost)

1. **X/Twitter full-archive search** — the actual wire the market trades on (Schefter/Rapoport, exact timestamps). Pro $5k/mo closed to new signups. *The single most painful loss.*
2. **Timestamped historical line-movement feeds** (DonBest/Sportradar) — *when* the market moved.
3. **Action Network PRO money%** (~$100/yr) — the sharp half of betting splits.
4. **Pinnacle historical odds** — the sharp-book reference.
5. Plus: PFF grades, NGS premium, FantasyPros historical news API, Visual Crossing (key signup), Stathead, ESPN+/Athletic.

Our best free substitutes (PFT corpus, PFRumors) are slower, coarser, editorially filtered versions of the market's true channels. If the gap never closes, these two inaccessibles should be named explicitly as the likely reason.

## Pilot recommendation

**Build the PFT news-timing corpus (2018–2022) as a data-collection pilot — recommendation only, not started.** Success is judged on data-quality criteria only: ≥80% weekly coverage, timestamp validity ≥48/50 on manual audit, entity-resolution precision ≥90%, and the key diagnostic — ≥40% of sampled Out/Doubtful designations preceded by corpus news ≥24h before nflverse `date_modified`. If the news-lead criterion fails, the corpus is an archive, not a timing layer — report that plainly. Full proposal in `pilot_proposal.md`, including timestamp discipline per 006 cutoff (Tuesday-AM / Friday / pre-kickoff).

## Standing notes

- No pilot build begins without Cale's approval.
- Any future modeling use of a new source requires a frozen preregistered protocol, 2021–2022 validation, and the vault stays locked until gates pass.
- Failed-source documentation is preserved: the dead ends (ESPN/Sleeper/FantasyPros APIs, SBR mirror, structured beat reporters) are recorded in `source_inventory.md` §15 so no effort is re-spent.
- The snap-weighted availability construction (all owned nflverse data) is documented as sitting at the research-freeze boundary — better aggregation of the same data — and is NOT recommended under the freeze.

## Files

- `source_inventory.md` — 13 per-class dossiers + inaccessible list + verified dead ends
- `feasibility_ranking.md` — top 5 with case-against each + honorable mentions + priced gap
- `pilot_proposal.md` — the one pilot, data-quality success criteria, timestamp discipline
- `REPORT.md` — this file
- `scratch_personnel.md`, `scratch_market_env.md` — raw working dossiers from the two tracks
