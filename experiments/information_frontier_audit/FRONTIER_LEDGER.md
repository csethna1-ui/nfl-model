# Information-Frontier Ledger — Demonstrated vs Hypothesized

**Date:** 2026-09-29 (framework preregistered; PFT verdict lands 2026-10-01)
**Binding rule:** An information class counts as a *demonstrated* advantage only
if a preregistered diagnostic shows it. Everything else is *hypothesized* —
a plausible explanation for the residual market gap, never evidence.

**Key question (Cale):** "What information does the market have, when does it
receive it, and how much of that information can we historically reconstruct
without leakage?"

NOT the question: "Can PFT explain the market gap?" PFT is the first test of
one channel, not the whole hypothesis.

## Status key

- **DEMONSTRATED**: preregistered diagnostic passed; effect shown on clean data.
- **PENDING**: diagnostic preregistered and running.
- **HYPOTHESIZED/RECONSTRUCTABLE**: audit judged it historically rebuildable
  with valid timestamps; no diagnostic run yet.
- **HYPOTHESIZED/INACCESSIBLE**: cannot be rebuilt under the free/keyless
  constraint; may only ever be documented as a *potential* explanation.
- **DEAD**: audit verified it cannot be reconstructed; do not re-spend effort.

## The ledger

| # | Information class | Status | Reconstructable? | Timestamp-valid? | Notes |
|---|---|---|---|---|---|
| 1 | PFT news-arrival timing (2018–2022) | **PENDING** (verdict Thu 2026-10-01) | Yes — crawl in progress | Minute-res `datePublished`, cross-checked | Preregistered: ≥40% of sampled Out/Doubtful preceded by corpus news ≥24h before nflverse `date_modified` = timing layer; else ARCHIVE |
| 2 | Roster/transaction changes (PFR wire) | HYPOTHESIZED/RECONSTRUCTABLE | Yes — day-level body dates (sitemap `lastmod` contaminated, use body) | Day-level | Thu–Sat moves V1 never sees; not yet built |
| 3 | Confirmed inactives (nflverse INA token) | HYPOTHESIZED/RECONSTRUCTABLE | Yes | Pre-kickoff only (~90 min) | ~1 day effort; not yet built |
| 4 | Sunday-morning QB news | HYPOTHESIZED/RECONSTRUCTABLE | Yes — subset of PFT corpus | Minute-res via PFT | Highest per-event leverage, rare |
| 5 | Weather forecast vintages (IEM MOS) | HYPOTHESIZED/RECONSTRUCTABLE | Yes — as-issued archives | As-issued timestamps | Weak margin mechanism (wind is a totals story; totals never bet) |
| 6a | Public betting splits (% tickets) | HYPOTHESIZED/INACCESSIBLE | No — no free historical archive found; SBR mirror died Sept 2026 | — | Tells what the crowd is doing; weakest of the three signals. Needs timestamped snapshots (Mon→Sun AM→pre-kickoff); post-kickoff numbers are leakage, useless |
| 6b | Money splits (% handle) — PROXY, not true sharp | HYPOTHESIZED/INACCESSIBLE | No — Action Network PRO paywall (~$100/yr) | — | Ticket-vs-money divergence (e.g. 72% tickets / 44% money) is a proxy for where larger bets land. Publicly reported money% does NOT identify bettors. Never call it sharp money |
| 6c | True sharp money (identified bettors) | HYPOTHESIZED/INACCESSIBLE | No — books do not publish identified flow | — | May only ever be documented as a potential explanation, never measured |
| 6d | Line movement / open-to-close trajectory | HYPOTHESIZED/INACCESSIBLE | No — SBR free mirror died Sept 2026; DonBest/Sportradar paywalled | — | The market's continuously updated consensus price; arguably the most interesting of the three. Treat free odds archives as perishable |
| 7 | ~~Sharp-book / money% (Action Network PRO)~~ | — | — | — | Split into 6a–6d above for precision |
| 8 | X/Twitter full archive (the wire the market trades on) | HYPOTHESIZED/INACCESSIBLE | No — $5k–$42k/mo | — | Named likely reason if the gap never closes |
| 9 | Day-level practice participation | DEAD | No — verified in audit | — | Do not revisit without new evidence |
| 10 | Structured beat-reporter reconstruction | DEAD | No — verified in audit | — | Do not revisit without new evidence |
| 11 | ESPN/Sleeper/FantasyPros historical APIs | DEAD | No — verified in audit | — | Do not revisit without new evidence |
| 12 | Officiating assignments | NOT ASSESSED | Unknown — feasibility check not yet run | — | Crews are announced weekly in principle; no audit verdict exists. Do not assume reconstructable. |
| 13 | Travel/rest/context | PARTIALLY ASSESSED | Schedule-derived rest is computable from nflverse; true travel burden is not | Game-level | No audit verdict on marginal value |
| 14 | Premium player/team evaluation (PFF grades etc.) | HYPOTHESIZED/INACCESSIBLE | No — paywalled | — | Free-tier PFR advanced stats were used in V2 (Tuesday publication lag) |

## Thursday's deliverable (2026-10-01 ~1:20 PM CDT)

The PFT pilot report must contain exactly these four sections, in Cale's words:

1. **What PFT proves or disproves about news timing** — the five preregistered
   criteria, PASS/FAIL each, no spin.
2. **What other information classes remain plausible after the audit** — rows
   2–8, 12–14 above; nothing promoted, nothing buried.
3. **Which of those are historically reconstructable and timestamp-valid** —
   rows 2–5 (and 12–13 only after a feasibility check, not before).
4. **Which are inaccessible and can only be documented as potential
   explanations** — rows 6–8, 14. If the ~0.44 MAE market gap never closes,
   these are the named likely reasons — stated as hypothesis, never as finding.

## Standing constraints (unchanged)

- PFT pilot scope frozen as preregistered. No expansion.
- V1 untouched. Vault unspent for selection. Experiment 006 untouched.
- No new model/algorithm work on existing information (freeze holds).
- Building rows 2–5 requires Cale's explicit go-ahead after Thursday.
