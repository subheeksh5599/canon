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

---

## Entry 2 — (independent tester — pending)
Name: —
Date: —
What they tried / what broke / whether they'd use it for their own agent deals.
