# Challenger-vs-Champion Charter

Ratified: 2026-10-01 by Cale. The promotion bar below is binding.

Standing: the 2026-09-29 research freeze was LIFTED by Cale on 2026-10-01
("I don't care about the freeze as long as the model is getting smarter and
making more accurate picks"). Its core protection survives in a new form:
V1 is never modified except by losing the title under the promotion bar.
The Tuesday grading script REPORTS when the bar is cleared; the title change
itself is never automatic — Cale taps to crown.

## The deal

Cale's directive: _"keep the model continually learning and looking for new
ways to be accurate but v1 stays untouched until evidence proves it can be
beat."_ This charter is how "evidence" gets demonstrated instead of assumed.

## Champion

- **V1** (ELO K=20 + EPA + GBM, weights 40/50/10, frozen 2026-09-11).
- Makes the official weekly sheet. Never changes except by losing the title
  under the promotion bar below.
- The champion's standing protections (paper-track only, no edge/ROI claims,
  totals never played) survive any title change.

## Challengers

- Each challenger is **one controlled change** to the v1 pipeline, declared
  in `challengers/registry.json` (hypothesis, exact changes, frozen list).
- Challengers predict the same upcoming games as the champion, from the same
  Friday information set. No QB/injury overlay on challengers — the overlay
  is a separate approved layer, applied to the champion's sheet only (and to
  a challenger only if it ever promotes).
- **No backtest selection.** A challenger's record starts 0-0 and it proves
  itself prospectively. (This is the lesson of Experiment 002: dev-selected
  challengers overfit.)
- Failed challengers are preserved, never deleted. Status flips to
  `retired` with the verdict.

## The ledger

- `scripts/53_run_challenger.py` — runs a live challenger for an upcoming
  week (Friday, alongside the champion's run).
- `scripts/54_grade_challengers.py` — grades champion + challengers on
  identical rules after the week completes (Tuesday, alongside the
  champion's grading): SU winner, ATS vs the same market lines, margin MAE.
- `data/challenger_ledger.csv` — one row per model per week. Append-only.

## Promotion bar (RATIFIED 2026-10-01 — binding)

A challenger takes the title only when ALL of these hold, checked weekly
after Tuesday grading:

1. **Sample:** ≥100 head-to-head graded games (both models predicted).
   First eligibility check lands around Week 10–11. No hot-week promotions.
2. **Accuracy:** margin MAE lower than the champion's by **≥0.30** over
   those games.
3. **Picks:** ATS record strictly better than the champion's, and SU win%
   not worse.

On promotion: the challenger is frozen as the new champion, the old
champion retires to the ledger, and the weekly sheet switches. The new
champion then defends the title under the same bar.

Statistical honesty note: at n=100, a 0.30 MAE edge is suggestive rather
than conclusive (≈1 standard error) — which is why conditions 2 and 3 must
hold jointly. Tighten the bar any time; never loosen it mid-race.

## Non-goals

- The ledger never tunes anything. It measures.
- Mid-week or mid-season tweaks to a live challenger are forbidden — a
  changed challenger is a *new* challenger with a 0-0 record.
- The information-timing program (Experiment 006 stream, PFT verdict) is
  unaffected by this charter and continues as measurement.
