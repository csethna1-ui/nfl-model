# QUEUED — Betting-Splits & Line-Movement Feasibility Audit

**Status:** QUEUED. DO NOT START until (a) the PFT pilot verdict is delivered
(Thu 2026-10-01) AND (b) Cale explicitly authorizes this audit.
**Scope:** information-feasibility audit ONLY. No modeling. V1 untouched.
Vault unspent for selection.

## Objective

Determine whether historically timestamped public betting splits (% tickets),
money splits (% handle), and line movement can be reconstructed for 2018+
without leakage. The goal is NOT to assume these signals are predictive — it
is to determine whether they represent a historically available information
channel absent from V1.

## The three signals (distinct — do not conflate)

1. **Public behavior — % of tickets.** What the crowd is doing. Potentially
   useful, probably weakest of the three.
2. **Money distribution — % of handle.** More interesting (ticket size varies
   dramatically). Ticket-vs-money divergence (e.g. 72% tickets / 44% money)
   is a commonly used proxy for where larger bets land. It is ONLY a proxy:
   publicly reported money percentages do not identify the bettors. NEVER
   call it "sharp money."
3. **Market reaction — line movement.** The line is the market's continuously
   updated consensus price. Open → intraday → close trajectory, timestamped.
   Arguably the most interesting of the three: it reprices as new information
   and betting flows arrive.

The combination — public bets + money distribution + line movement +
timestamps — could reconstruct a portion of the market's information-processing
mechanism that V1 does not see. Example of an informative pattern: V1 says
Cowboys -2.1, market opens -1.5, drifts to -3 through the week while 80% of
tickets are on Dallas but only 45% of money is — the movement may encode
information V1 never observes.

## The leakage problem (central to this audit)

V1 needs information that existed BEFORE the prediction timestamp. A split
like "72% of bets were on Dallas" is useless if it was only published after
kickoff. Using final closing splits to predict the game leaks the future.

Required granularity — timestamped snapshots at each of:
Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday AM, pre-kickoff
— for BOTH splits and line. For each candidate source, document: what
timestamp the number carries, when it was actually published/available, and
whether it precedes our prediction cutoff.

## Audit questions

1. Does any free/keyless source archive timestamped % tickets, % handle, or
   line movement for 2018+ NFL games? (Prior audit: SBR free mirror died
   Sept 2026 — treat free odds archives as perishable; verify, don't assume.)
2. For each candidate source: exact timestamp semantics (as-published vs
   as-of), publication lag, coverage by season/week.
3. Can a leakage-free historical panel be built at the required granularity?
   If only closing numbers exist, say so — that answers the question.
4. True sharp (identified) flow: confirm inaccessible; document as
   hypothesized-only.

## Out of scope

- No predictive modeling, no backtests, no V1 changes.
- No paid sources (Action Network PRO ~$100/yr noted as paywalled; do not
  subscribe or ask Cale to).
- No scope creep into the PFT pilot — Thursday stays clean.

## Deliverable

A feasibility verdict per signal: RECONSTRUCTABLE (with timestamp spec) /
PARTIAL (state exactly what's missing) / INACCESSIBLE. If reconstructable,
the panel spec becomes a preregistered build proposal — not a build.
