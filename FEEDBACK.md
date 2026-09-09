# Feedback

Real entries from people who used the CANON venue, dated and attributed.
Independent tester entries are the PMF evidence; builder-side entries are
labeled as such and never passed off as independent.

---

## Entry 1 — builder-side self-review (Sep 09)

Tester: development agent acting as reviewer (same account as the build —
NOT an independent tester; recorded for the record, not PMF evidence).
Full detail: docs/REVIEW.md.

Verified against the live deployment (canon-venue.vercel.app, Base Sepolia 84532):
- Full deal lifecycle through the console with real USDC: register, escrow
  lock, complete, payout (tx-92038e982952, escrow 0x7ad5b567…).
- Integrity panel deletion gate run against a copy of the live market:
  "PASS — venue refused to rule · doctrine before wipe: v2".
- Every ledger row links escrow and payout hashes to Basescan; open deals
  resume across tab switches; Overview state matches the API.

Findings:
- A: Overview caption contradicted charter founding ("5 seed the demo
  market") — fixed same day, now "real executed deals · TX_VERIFIED evidence".
- A: explorer links missing on newer deals (0x-prefix bug) — fixed, all rows
  link now.
- B: unfunded TERMED rows clutter the ledger (real registrations, zero money
  moved); a cancel-unfunded-deal action would help.
- B: venue balance (~$3.6) too low for a fresh $16 demo deal without a drip.

## Entry 2 — builder self-review: subheeksh5599 (Sep 09)

The builder's own testing across the week — real sessions, labeled honestly as
builder-side (not independent PMF evidence).

What I tested hands-on:
- Funded the venue wallet with USDC on Base Sepolia (faucet + drips) and
  watched escrow lock against the real contract address.
- Ran the first real $16 deal end-to-end: charter terms → escrow lock →
  provider failed → claim resolved, $15.20 paid to the buyer, adjudicator-
  signed. Then posted a real $5 appeal bond against the charter rule and it
  was accepted — doctrine moved v1 → v2, bond ratio 0.20 → 0.10.
- Ran a deal where the counterparty was the Virtuals-registered agent
  ("Canon Venue Provider", 0x1776e…): the agent delivered and received the
  $9.60 escrow payout in its own wallet — verified the payout hash on
  Basescan myself.
- Caught the 0x-prefix bug while screen-recording (newer deals showed in the
  ledger but their explorer links didn't render) — reported, fixed the same
  hour, re-verified all rows link.
- Tested the cancel flow on leftover unfunded deals — ledger went from
  cluttered TERMED rows to clean CANCELLED/COMPLETED/CLAIMED.

What I'd tell a builder friend: the deletion gate from the console Integrity
panel is the demo moment — it's the only place where "memory is load-bearing"
stops being a claim and becomes something you watch happen.

---

## Entry 3 — (independent tester — pending)
Name: —
Date: —
What they tried / what broke / whether they'd use it for their own agent deals.
