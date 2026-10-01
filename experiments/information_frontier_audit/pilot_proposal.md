# Pilot Proposal — PFT News-Timing Corpus

**Recommendation:** build the ProFootballTalk injury/news-timing corpus for 2018–2022 as the first (and only, for now) information-frontier pilot. **Do NOT begin the pilot — recommendation only; Cale approves first.**

## Why this one first

1. It is the highest value×feasibility source in the audit (rank 1).
2. It is general infrastructure: the same corpus subsumes the Sunday-QB-news slice (rank 4), notable-player practice trajectories, and non-injury lineup-change events — one build serves four research questions.
3. It directly tests the core frontier hypothesis: does *news arrival timing* contain information beyond official designations?
4. The bulk path is independently verified (299,739 dated PFT NFL URLs, 202/202 months, 0 failures by a third-party audit, 2026-08).

## What the pilot collects

- **Scope:** PFT NFL articles, regular seasons 2018–2022 (5 seasons × ~17 weeks), injury/availability-relevant subset only.
- **Per article:** URL, `datePublished` (JSON-LD, minute resolution; cross-checked against human-readable date), headline, body text, extracted player entities → team mapping, event class (injury report / practice participation / expected-to-play / ruled out / other).
- **Method:** NBC sitemap → monthly chunks (Sept 2009+ available; pull 2018–2022 window) → fetch injury-relevant subset (~250/mo × 60 mo ≈ 15k articles) at polite crawl rate (robots.txt `Crawl-delay: 10`) → timestamp extraction + player-name resolution.
- **Explicitly NOT collected:** article opinion content, comments, non-NFL articles, anything requiring login.

## Data-quality success criteria (NOT predictive performance)

The pilot succeeds or fails on data quality alone. No model is fit; no MAE is computed.

1. **Coverage:** ≥80% of 2018–2022 regular-season weeks contain ≥20 injury-relevant articles. (If the corpus is thin outside contenders, that is a finding, not a failure — but below this bar it cannot serve as a timing layer.)
2. **Timestamp validity:** manual audit of 50 sampled articles — `datePublished` agrees with the human-readable article date to within the same calendar day in ≥48/50. (Known caveat: treat stamps as "known no later than.")
3. **Entity resolution precision:** manual audit of 100 sampled articles — ≥90% of extracted player mentions map to the correct team for that season.
4. **News-lead measurement (the key diagnostic):** for a random sample of 200 players with nflverse Out/Doubtful designations in 2021–2022, what fraction have corpus news mentioning their injury ≥24 hours before the nflverse `date_modified`? **Success bar: ≥40%.** Below that, the corpus is mostly echoing the official report and the timing layer adds little.
5. **Sunday-morning density check:** count of QB-relevant articles published Sunday 00:00–kickoff across the 5 seasons. (Unmeasured in the audit; needed before any Sunday-QB work.)

If criteria 1–3 pass but 4 fails, the corpus is still useful as a news archive but NOT as a timing layer — report that plainly and do not proceed to modeling on timing claims.

## Timestamp discipline for downstream use

- Articles dated Mon–Tue of game week → **Tuesday-AM info set** (V1's current state).
- Articles dated Wed–Fri → **Friday info set** (006's Friday snapshot).
- Articles dated Sat / Sunday pre-kickoff → **pre-kickoff info set** (diagnostic only; not a prediction timestamp V1 uses).
- The 006 timing study distinguishes exactly these cutoffs; the corpus must store raw timestamps, never pre-bucketed.

## Cost and risks

- **Effort:** ~3–5 days (crawl + fetch + NLP-lite entity resolution + manual audits).
- **Risk 1 — robots.txt / rate limits:** `Crawl-delay: 10` respected; ~15k fetches ≈ 40+ hours wall-clock at full politeness. Mitigation: fetch only the injury-relevant subset (URL/headline pre-filter), run unattended.
- **Risk 2 — entity resolution quality:** player-name ambiguity (common names, nicknames). Mitigation: team-context from headline + roster cross-check; manual audit gates this (criterion 3).
- **Risk 3 — coverage skew:** PFT covers contenders and fantasy-relevant players disproportionately. This is inherent; document it as a corpus bias rather than trying to fix it.
- **Risk 4 — the "known no later than" timestamp caveat:** one sampled article showed an earlier human-readable date than its ISO stamp. The manual audit (criterion 2) quantifies this; if systematic, timestamps shift from "news arrival" to "news arrival upper bound" — still usable for pre-cutoff filtering, with the bound documented.

## What happens after a successful pilot

A successful pilot produces a *dataset*, not a model. The next decision (separate authorization) would be whether to test — under a frozen preregistered protocol, 2021–2022 validation, vault untouched — whether news-timing features add information conditional on V1. That is a future experiment proposal, not this pilot.

## Deliberately deferred

- **PFRumors transaction wire (rank 2):** second pilot candidate; independent corpus, same methods apply. Run only after the PFT pilot's entity-resolution pipeline exists to reuse.
- **INA-row inactive ground truth (rank 3):** ~1 day of work; can be done alongside the pilot as a join, but its value is pre-kickoff-only.
- **IEM MOS forecasts (rank 5):** honest mechanism assessment is weak for margin; defer unless a totals-adjacent question arises (and totals are never bet).
