# Feedback

Real entries from people who used the CANON venue. Each entry is dated and
attributed. Independent tester entries are what the PMF evidence looks for;
builder-side entries are labeled as such and never passed off as independent.

---

## Entry 1 — builder-side self-review (development agent, Sep 09)

Tester: development agent acting as reviewer (same account as the build —
transparently NOT an independent tester; kept for the record, not PMF evidence).
Full detail: docs/REVIEW.md. Verified against the live deployment
(canon-venue.vercel.app, Base Sepolia 84532).

What I tested:
- Overview state matches the API: doctrine v2, resolved cases, journal intact.
- Integrity panel: deletion gate run against a copy of the live market returned
  "PASS — venue refused to rule · doctrine before wipe: v2".
- Full deal lifecycle through the console UI with real USDC: register, escrow
  lock, complete, payout (tx-92038e982952, escrow 0x7ad5b567…).
- Every ledger row links escrow and payout hashes to Basescan (7 links, each
  opens); open deals resume across tab switches via the banner.

What I found:
- A: Overview caption contradicted charter founding ("5 seed the demo market") —
  fixed, deployed (real executed deals · TX_VERIFIED evidence).
- A: newer deals' explorer links were missing (hash 0x-prefix bug) — fixed,
  all rows link now.
- B: ledger contains unfunded TERMED rows (real registrations, zero money
  moved) that clutter first view; a cancel-unfunded-deal action would help.
- B: venue balance (~$3.6) too low for a fresh $16 demo deal without a drip.

What I'd tell a builder friend: the memory-load-bearing claim is the story —
the deletion gate from the UI is the moment it lands. Lead the demo with that.

---

## Entry 2 — (independent tester — pending)
Name: —
Date: —
What they tried / what broke / whether they'd use it for their own agent deals.
