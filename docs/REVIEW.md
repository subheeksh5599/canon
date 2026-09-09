# Fresh-eyes review — CANON live venue (internal QA, builder-side)
Run by the build agent acting as an outside reviewer, Sep 09.
This is NOT tester feedback and is NOT PMF evidence (self-authored); it exists to
catch defects before external testers and judges see them.

## Severity A — fixed in this pass
1. Overview stat caption read "Resolved cases · 5 seed the demo market".
   Contradicts the charter doctrine (zero fabricated cases). Root cause: leftover
   copy from the pre-charter synthetic-seed era. Fixed to "real executed deals ·
   TX_VERIFIED evidence" and deployed. Grep found no other synthetic-seed/mock
   copy in web/ (the only remaining "seed" strings are the starfield and the
   doctrine explainer line "Only RESOLVED, HIGH/MEDIUM-confidence cases may seed
   doctrine", which is accurate).
2. (earlier in the session, same class) explorer links missing on newer deals
   because hashes lacked the 0x prefix; deal state now resumable across tabs.

## Severity B — open, minor, disclosed by design
3. The ledger contains unfunded TERMED rows (tx-87ee8b3fe798 $55 from the old
   decimal-input bug, plus two duplicate registrations from proxy retries).
   Real registrations, zero money moved. They are honest history but clutter a
   first-time viewer's ledger; a cancel/abandon action for unfunded deals would
   clean this up. Consider a UI affordance: "cancel unfunded deal" (no money
   moves; on-chain cancel not yet wired in the engine).
4. Overview "Pool $0" may read oddly next to contract-held bonds (~$2.4). The
   caption says "fees + forfeited bonds", which is accurate (bonds are venue
   collateral, not pool), but a viewer could misread. Optional one-line explainer.
5. Journal top events are venue.admit entries from the last restart (15:47) —
   correct behavior (idempotent admission every boot) but looks like noise;
   fine once more tx events accumulate.

## Severity C — observations
6. No wallet popups anywhere (by design; venue signs server-side). A judge used
   to dApps may pause here — the demo narration now says this out loud.
7. Venue balance is ~3.6 USDC: a fresh $16 deal fails at escrow lock until a
   drip lands. Confirm funding before recording.
8. README still uses "judge console"/"judge sequence" phrasing in the Run-venue
   section even though the product posture pass renamed the console nav. Cosmetic
   inconsistency; decide whether to keep (submit-context) or rename.

## What held up under review
- Overview state matches the API: doctrine v2, 2 resolved cases, journal intact.
- Memory journal is real, chain-hashed, and populated with genuine events
  (admits, tx.create/fund/fail, case.open/resolve, claim.resolved).
- Integrity panel: journal check + deletion gate runnable, PASS against v2.
- Transactions rows all link to Basescan (verified 7 links, popup opens).
- Resume banner works across tab switches.
- No mock/synthetic/hardcoded strings found in the served surface after A-1.
