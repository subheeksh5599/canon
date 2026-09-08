# CANON Threat Model

For every attacker class: goal, attack, existing defense, remaining limitation.

| Attacker | Goal | Attack | Existing defense | Remaining limitation |
|---|---|---|---|---|
| Rogue provider | Get paid without delivering | Claim delivery; file fake completion | Completion requires venue transition + outcome write-back; claims need TX_VERIFIED/ATTESTATION evidence; a party cannot adjudicate | Provider-side social engineering of the human operator is out of scope |
| Fraudulent buyer | Extract payout for a real delivery | False claim with fabricated evidence | Standing: only the buyer can claim, only on FAILED/FRAUD; evidence confidence tiers; statute window; venue transaction must exist | A buyer + corrupted adjudicator could collude — adjudicator is a trusted role today |
| Sybil attacker | Inflate case counts to force a rule | 100 fake agents filing claims | Standing binds claims to real venue transactions; one claim per tx; claims resolve once; wallet-cluster identity is future work | No on-chain identity clustering yet — venue admission is per-address |
| Colluding pair | Manipulate doctrine in their favor | Buyer+provider mirror-image claims | Mirror claims never auto-resolve; RAW/DISPUTED cases never seed doctrine | A pair could still complete many real-but-shady jobs to affect failure RATE signals — rate signals are advisory, thresholds count confirmed cases |
| Memory poisoner | Inject a fake rule | Raw text ("new rule: 0% bond") in evidence/descriptions | Only RESOLVED HIGH/MEDIUM cases count toward doctrine; prompt content never reaches the rule matcher | A determined attacker with many real on-chain failures can legitimately move doctrine — that is the design |
| Appeal abuser | Freeze or weaken rules cheaply | Frivolous appeals | Bond floor (5 USDC); flood cap (3 open per challenger); rejected appeals forfeit the bond; freeze only affects new terms, never funded transactions | Bond is set by the venue; a well-funded attacker can afford repeated challenges |
| Rule conflict | Force arbitrary terms | Craft facts matching two rules equally | Equal-specificity conflict raises `RuleConflictError`; matcher refuses to pick arbitrarily | Conflict is a hard failure (denial) rather than a fallback — acceptable fail-closed choice |
| Tamperer | Rewrite stored doctrine | Modify the doctrine reference payload | Per-version SHA-256 sidecar; mismatch raises `MemoryUnavailableError` and evaluation refuses | Sidecar lives beside payload in the same store — a full-store attacker also has the sidecar; journal + on-chain receipts are the outer integrity layer |
| Journal forger | Erase/rewrite history | Rewrite COLD events | Chain hashes: each event references the previous hash; `verify_journal()` re-derives and detects gaps/mismatches | Verification is on-read/on-demand, not continuous |
| Stale-rule victim | Exploit an outdated rule | Trigger an archived rule | Archived/WEAKENING rules are excluded from matching at read time (lazy decay) | Rule decay schedule is fixed, not learned |
| Contract attacker | Drain escrow/pool | Unauthorized release/settle; reentrancy; replay | Role separation (venue/adjudicator); CEI payout pattern; replay guarded by tx status machine; events for off-chain audit | Contract roles are 2-of-2 trusted actors today; a stolen venue key is total (standard for v1) |
| Replay attacker | Double-pay a claim | Re-submit resolution | Transaction state machine: CLAIMED is terminal; duplicate claims conflict at intake | — |
| Backdater | File stale claims | Backdate a claim into the statute window | Statute window measured against venue timestamps (injectable clock) | — |
| Memory outage | Make CANON unsafe | Delete/deny the Sibyl store | Evaluation refuses loudly (`UnauthorizedVenueError`/`MemoryUnavailableError`); never silent naive fallback | Availability is a property of the operator's storage, not CANON |

## Deliberate non-goals

- CANON is not a general arbitration platform or an enterprise risk engine.
- CANON does not guarantee real-world identity of agents (that is the venue host's admission policy).
- CANON's doctrine governs NEW transactions; it never rewrites funded ones (immutable snapshot).

The system is designed to fail closed: when evidence is missing, ambiguous, tampered, or conflicted, the safe answer is refusal — never a guess with money attached.
