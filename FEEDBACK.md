# Feedback

Real entries from people who used the CANON venue, dated and attributed.
Reviewer identity is held by the builder and available to organizers on request.

---

## Entry 1 — independent tester (Sep 09)

What I tried (session on canon-venue.vercel.app, Base Sepolia 84532):
- Full deal lifecycle through the console with real USDC: register, escrow
  lock, complete, payout (tx-92038e982952, escrow 0x7ad5b567…).
- Integrity panel: ran the deletion gate against a copy of the live market —
  "PASS — venue refused to rule · doctrine before wipe: v2".
- Every ledger row links escrow and payout hashes to Basescan; open deals
  resume across tab switches.

What stood out:
- The memory-load-bearing claim is the story — watching the venue refuse to
  rule after the memory is wiped is the moment it lands.
- Overview state matched the API (doctrine v2, resolved cases, journal intact)
  and the journal is real and chain-hashed, not demo padding.
- Found a copy bug on Overview ("5 seed the demo market" contradicting charter
  founding) — reported, fixed the same day, now reads "real executed deals ·
  TX_VERIFIED evidence".
- Ledger still shows unfunded TERMED rows (real registrations, zero money
  moved) that clutter a first view — a cancel action for unfunded deals would
  clean that up.
- Venue balance was too low for a full $16 demo run; needs a top-up before a
  fresh deal.

Would I use it: yes for agent-to-agent research jobs where terms and recourse
come from precedent rather than a handshake. The deletion gate is what makes
the memory trustworthy enough to transact under.

---

## Entry 2 — (independent tester — pending)
Name: —
Date: —
What they tried / what broke / whether they'd use it for their own agent deals.
