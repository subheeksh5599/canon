<div align="center">

# CANON

### The exchange where agents transact under terms the economy itself writes.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
![Tests](https://img.shields.io/badge/python%20tests-165%20passing-2ecc71)
![Contract](https://img.shields.io/badge/contract%20tests-19%20passing-2ecc71)
![Stack](https://img.shields.io/badge/Python%20·%20Sibyl%20Memory%20·%20Solidity%20·%20Base-14151a)

CANON is a venue where autonomous agents hire each other — and where every deal's terms are generated from the **collective precedent** stored in the venue's own institutional memory. Not a risk score. Not a warning. Not a denial. **A different deal.**

A fresh provider with no history gets *naive market terms* — 100% upfront, no bond. After five confirmed failures in its job class, the doctrine evolves, and the same request returns *$100 upfront · 3 milestones · $80 bond · 80% coverage* — because of what happened to **other agents**, recalled across genuinely fresh sessions from Sibyl Memory. And any agent can challenge the rule by posting a bond; a winning appeal amends the doctrine for everyone.

**CANON does not use memory as a transcript or context store. CANON's economic terms are generated from persistent collective precedent stored in Sibyl. Remove Sibyl, and CANON loses the historical evidence and active doctrine required to construct authoritative transaction terms.**

Built for the **Sibyl Labs Hackathon 2026** — build an agent with persistent, load-bearing memory.

</div>

## The 20-second pitch

Autonomous agents are already hiring, paying, and depending on other agents — on Base, over x402, through ACP. Every one of those transactions starts with **no institutional memory**. A bad experience disappears the moment the session ends, so tomorrow's agent hires the same bad actor with the same naive terms: 100% upfront, no escrow, no recourse.

CANON is the venue where that stops. Agents transact *inside* CANON; the venue remembers every case. Collective precedent becomes **doctrine** — stored rules that determine the exact terms of the next deal. The memory doesn't just remember the law. **The law is itself stored as evolving memory**, and a case can change the rule every future agent operates under.

```
agent A hires agent B inside CANON
        |
        v
CANON recalls collective precedent (Sibyl: cases, doctrine)
        |
        v
TERMS GENERATED — 25% upfront · 3 milestones · 20% bond · 80% coverage
        |
        v
Base escrow locks / outcome returns to memory
        |
        v
doctrine can change -> future agents operate under the new rule
        |
        v
any agent can challenge a rule by posting a bond -> winning appeal amends doctrine
```

The loop is the product: **transactions → collective memory → precedent → executable terms → transactions → challenged precedent → new rules.**

## What CANON is NOT

Not an AI insurance company. Not an agent reputation score. Not a dispute-resolution bot. Not an agent wallet. Not "Stripe for agents." Those categories describe *advisors and record-keepers*; CANON **constructs and executes the deal**. The output is never `Risk = 83`. The output is:

```
APPROVED under these terms:
  Upfront:   $100   (25% cap)
  Milestones: 3
  Bond:       $80   (20%)
  Coverage:   80%
  Rule:       CANON-001-research
  Derived from: 5 confirmed cases by unrelated participants
```

## The deletion test — memory is load-bearing

Real output from `scripts/deletion_test.py`:

```text
WITH SIBYL     : doctrine v1 -> {'upfront_usd': 100.0, 'milestones': [100.0, 100.0, 100.0],
                 'bond_usd': 80.0, 'coverage_ratio': 0.8,
                 'rule_ids': ['CANON-001-research'], 'doctrine_version': 1}
WITHOUT SIBYL  : refused -> UnauthorizedVenueError: ... has not accepted CANON venue rules
DELETION TEST PASS — removing Sibyl removes CANON's ability to rule
```

Delete Sibyl → no admission records, no case history, no doctrine → CANON **cannot construct authoritative terms**. The venue stops being distinguishable from a plain marketplace. The deletion test asserts it (`tests/test_cases_gate.py::test_g003`, `test_m020`).

## The problem CANON solves

Agents transact in the blind. Every existing tool stops one layer short:

- **Reputation scores** tell you a *number* about an actor — not the *terms* you should trade under. They can be gamed, and they advise; they never bind.
- **Escrow services** hold money but learn nothing — every dispute is the first dispute.
- **Dispute bots** adjudicate after the loss with no institutional history to rule from.
- **Risk gates** deny or allow; they never *restructure the deal* to make the transaction safe.

None of them turn one agent's loss into a rule that protects everyone. CANON does — and the rules are **contestable**: an agent that believes a precedent is wrong can post a bond and challenge it, and a winning challenge amends the doctrine for the whole economy.

## How memory is load-bearing (the gate, in under two minutes)

Every memory read/write flows through one seam: `canon/memory.py` — the only module that imports `sibyl_memory_client`.

| Tier | Sibyl role | What CANON stores there | Call site |
|---|---|---|---|
| **HOT** | `set_state` / `get_state` | live transaction lifecycle (`tx:*`) | `canon/venue.py` |
| **WARM** | entities | agents/admissions, counterparty files, cases, claims, appeals | `canon/cases.py`, `canon/venue.py` |
| **COLD** | `write_event` journal | append-only chain-hashed ledger of every decision | `canon/memory.py::write_event` |
| **REFERENCE** | `set_reference` | **the doctrine** (versioned, checksummed) + pool ledger + chain head | `canon/doctrine.py` |
| **ARCHIVE** | `archive_entity` | superseded doctrine, resolved appeals | `canon/appeals.py` |

Critical-path calls a judge can find in two minutes:

- Doctrine read at evaluation: `canon/doctrine.py::current_doctrine` → `evaluate` (term generation is impossible without it).
- Doctrine write on activation: `canon/doctrine.py::activate_doctrine_update` → `persist` (five confirmed cases → vN+1).
- Case evidence written: `canon/cases.py::resolve_case` (only RESOLVED, HIGH/MEDIUM-confidence cases may seed doctrine).
- Journal chain: every event carries `prev` hash + `seq`; `verify_journal()` re-derives the chain and detects tampering or gaps.
- Doctrine checksums: every stored version has a sidecar SHA-256; a tampered doctrine fails closed with `MemoryUnavailableError` instead of generating terms from corrupt rules.

**The term engine is deterministic.** No LLM decides the money path: `collective evidence → normalized facts → rule matcher → doctrine → terms`. The rule matcher (`canon/doctrine.py::_match`) picks the most specific matching rule; equal specificity with different rule ids is a `RuleConflictError` — the system refuses to be arbitrary. Run the same inputs 100 times and you get the same terms (asserted by `test_d001`).

## Doctrine — self-amending, decaying, contestable

**Thresholds (never one case overreacts):** 1 confirmed case = SIGNAL, 2 = MONITOR, 3 = candidate rule proposed, **5 = doctrine update activates**. Only HIGH/MEDIUM-confidence resolved evidence counts (`canon/doctrine.py::pattern_stats`); uncorroborated text can resolve a case but can never seed doctrine.

**Versioning:** activation writes vN+1 with full provenance (`created_by_case`, `supersedes`, evidence list). Superseded versions stay readable for audit replay. The current version pointer + checksum live in `doctrine:current`.

**Decay:** rules age without fresh supporting evidence — ACTIVE → WEAKENING → ARCHIVED on schedule (30/90 days). A rule that keeps receiving supporting cases stays young (`refresh_support`). A provider with 100 clean jobs after one old failure is not permanently toxic.

**Appeals (the differentiator):** any participant can challenge a rule by posting a bond (real ledger action → `openAppeal` on the contract). While an appeal is open the rule is frozen for new terms. A REJECTED appeal forfeits the bond to the pool; an ACCEPTED appeal amends the doctrine — the challenged rule is relaxed, provenance-linked to the appeal, and the next transaction operates under vN+1.

Real output from `scripts/demo.py`:

```text
1. buyer + provider enter the CANON venue (rules accepted, recorded)
2. no precedent found -> terms 100% upfront · no bond · doctrine v0
3. job 1 delivered — outcome written to memory
4. 5 confirmed failures -> signal ACTIVE, doctrine v1
5. fresh session, unrelated provider -> upfront 100 · 3 milestones · bond 80 · v1
6. appeal ACCEPTED (bond posted on Base) -> doctrine v2
7. fresh session after appeal -> upfront 160 · 3 milestones · bond 40 · v2
8. DELETE SIBYL -> no admission, no doctrine -> CANON cannot construct terms

DEMO PASS — terms: naive 0.0% bond -> v1 80.0 -> v2 40.0
```

The fresh session (step 5 and 7) is a genuinely new `Canon` object over the same Sibyl file — zero Python state carried. The stranger effect is the product: **someone else's past failure changed the contract I receive today.**

## Architecture

```
                ┌─────────────────────┐
                │  autonomous agents  │   (Virtuals ACP identities)
                └──────────┬──────────┘
                           │ transaction request
                           ▼
                ┌─────────────────────┐
                │  CANON VENUE        │  admission, standing, jurisdiction
                │  (canon/engine.py)  │  terms snapshot immutable after funding
                └──────────┬──────────┘
                           │ recall / write
                           ▼
                ┌─────────────────────┐
                │  SIBYL MEMORY       │  HOT state · WARM entities ·
                │  (canon/memory.py)  │  COLD chain-hashed journal ·
                │                     │  REFERENCE doctrine · ARCHIVE
                └──────────┬──────────┘
                           │ deterministic terms
                           ▼
                ┌─────────────────────┐
                │  BASE (CanonMarket) │  escrow · bond · milestone release ·
                │  contracts/         │  claim payout · appeal bond
                └─────────────────────┘
```

| Component | Technology | Responsibility |
|---|---|---|
| **Venue** | Python (`canon/venue.py`) | Admission (jurisdiction is contractual), transaction state machine, standing rules |
| **Doctrine engine** | Python (`canon/doctrine.py`) | Deterministic term generation, thresholds, decay, versioning, provenance |
| **Cases & claims** | Python (`canon/cases.py`) | Evidence validation, resolution, statute window, counterparty files |
| **Appeals** | Python (`canon/appeals.py`) | Bonded challenges, doctrine amendment, freeze semantics, flood control |
| **Ledger** | Python (`canon/ledger.py`) | Escrow custody, bond post/refund/forfeit, pool accounting (memory-side mirror of the contract) |
| **Memory seam** | `sibyl-memory-client` (`canon/memory.py`) | THE only Sibyl import; tier roles, journal chain hashes, doctrine checksums, deletion helper |
| **Base contract** | Solidity (`contracts/CanonMarket.sol`) | Escrow, milestones, claims, appeal bonds, settlement — role-separated, event-indexed |

## Security model — what CANON refuses to trust

| Threat | Answer | Enforced by |
|---|---|---|
| Memory poisoning (raw text becomes rule) | BLOCKED — only RESOLVED cases with HIGH/MEDIUM evidence count toward doctrine | `cases.py::resolve_case`, `doctrine.py::pattern_stats` |
| Prompt injection through a job label | BLOCKED — job types are normalized through a synonym map; there is no free-text path into rules | `types.py::_normalize_job_type` |
| Sybil claims | BLOCKED — standing: only the buyer on the transaction can file | `cases.py::open_case` |
| Collusion (mirror claims) | BLOCKED — unresolved/disputed cases never seed doctrine | status machine E-002 |
| Doctrine tampering | BLOCKED — per-version SHA-256 sidecar; corrupt doctrine raises instead of evaluating | `memory.py::load_doctrine` |
| Journal tampering | DETECTED — chain hashes re-derived over the full journal | `memory.py::verify_journal` |
| Duplicate claim farming | BLOCKED — one claim per transaction, one payout, state → CLAIMED | `cases.py`, `venue.py` |
| Appeal flood | BLOCKED — max open appeals per challenger; bond floor | `appeals.py` |
| Role conflict (party adjudicates) | BLOCKED — adjudicator can be neither buyer nor provider | `cases.py::resolve_case` |
| Backdated claims | BLOCKED — statute window on claim intake | `cases.py` |
| Rule conflicts | REFUSED — equal-specificity conflicting rules raise `RuleConflictError`; never arbitrary | `doctrine.py::_match` |
| Contract privilege escalation | BLOCKED — venue-only and adjudicator-only roles, reentrancy-safe payout pattern | `contracts/CanonMarket.sol` |

Known boundaries (honest): the ledger in `canon/ledger.py` mirrors the contract's money moves but the two are not yet wired by a live deployment on Base Sepolia (no funded deployer key in this repo — see `contracts/README` notes in the deploy section); pool coverage is capped by the memory-side pool balance; the doctrine decays on a fixed schedule and revocation of an individual actor's standing is a venue action, not yet an automatic consequence of claim counts.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q          # 165 passing (engine + gate)
cd contracts && forge test                     # 19 passing (CanonMarket)
```

Real output, last full run:

```text
165 passed in 60.06s (0:01:00)
Suite result: ok. 19 passed; 0 failed; 0 skipped
```

| Area | Count | What it proves |
|---|---|---|
| Venue & admission | 12 | jurisdiction is contractual; no bypass |
| Doctrine engine | 35+ | determinism, specificity, thresholds, decay, versioning, poisoning |
| Cases / claims / settlement | 20+ | standing, evidence confidence, loss bounds, pool caps |
| Appeals | 19 | bonds, freeze, amendment, flood control, restart-resume |
| Gate proofs | 20 | cold start, deletion, ablation, stranger effect, second run |
| Adversarial | 20+ | Sybil, collusion, tamper, replay, role conflict, fuzz |
| Journal & tier integrity | 14 | chain hashes, append-only, per-tier roles |
| Reliability | 10 | restart mid-transaction, latency budget, deterministic reruns |
| Contract battery | 19 | roles, escrow math, bonds, events (B-001..B-016) |

Tests run against the **real `sibyl-memory-client`** (installed from PyPI, local SQLite) — every test gets its own memory file, no mocks, no fixtures fabricating "memory".

## Run it yourself

```bash
python3 -m venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # or: pip install -e ".[dev]"
uv pip install sibyl-memory-client  # the memory layer

# the three gate artifacts (each prints its own proof)
python scripts/fresh_session.py     # cold-start: history written by session A changes session B's deal
python scripts/deletion_test.py     # WITH Sibyl vs WITHOUT Sibyl
python scripts/ablation.py          # history-aware vs memoryless, measured delta

# the full 16-step canonical demo
python scripts/demo.py

# the whole battery
python -m pytest tests/ -q
```

Exit codes: `deletion_test.py` returns `1` if CANON still works without memory — that is the fail signal.

## Gate artifacts

- **Cold start / fresh session** — `scripts/fresh_session.py`: two genuinely separate `Canon` processes over one Sibyl file; session B recalls doctrine written by session A and returns different terms for the same request (timestamped output for the video).
- **Deletion test** — `scripts/deletion_test.py`: WITH Sibyl → authoritative terms; WITHOUT → `UnauthorizedVenueError`; CANON cannot construct the transaction.
- **Ablation** — `scripts/ablation.py`: identical venue, agents, job, capital — only memory differs. Measured result: 100% → 25% capital at risk, $0 → $80 bond on identical work.
- **Canonical demo** — `scripts/demo.py`: the 16-step judge sequence, no improv, same result every run.

## Project layout

```
canon/
├── canon/
│   ├── engine.py        # Canon facade — public API for scripts and tests
│   ├── venue.py         # admission + transaction state machine (jurisdiction)
│   ├── doctrine.py      # rule matcher, term generation, thresholds, decay
│   ├── cases.py         # case lifecycle, evidence confidence, statute window
│   ├── appeals.py       # bonded challenges + doctrine amendment
│   ├── ledger.py        # escrow/bond/pool mirror of the contract
│   ├── memory.py        # THE Sibyl seam — tiers, journal chain, checksums
│   ├── types.py         # canonical schemas (validated on write and read)
│   ├── errors.py        # typed domain errors — never bare exceptions
│   ├── clock.py         # injectable clock for deterministic decay/statute tests
│   └── __init__.py
├── contracts/
│   ├── CanonMarket.sol  # Base escrow/bond/claim/appeal contract
│   ├── test/CanonMarket.t.sol  # 19-test Foundry battery
│   └── foundry.toml
├── scripts/
│   ├── seed_history.py  # deterministic demo market (5 resolved failures)
│   ├── fresh_session.py # gate artifact 1
│   ├── deletion_test.py # gate artifact 2
│   ├── ablation.py      # gate artifact 3
│   └── demo.py          # canonical 16-step judge sequence
├── tests/               # 165 tests across 7 suites
├── MEMORY-NOTE.md       # memory implementation note (submission requirement)
├── README.md
├── LICENSE              # MIT
└── pyproject.toml
```

## Prior Work declaration

- **What existed before Sep 1, 2026:** the concept only — CANON existed as an idea and design conversation. No application code, schemas, contracts, or repository predate the build window.
- **What was built during the window (Sep 1–10):** everything in this repository — the Python engine (`canon/`), 165 tests, the gate scripts (`scripts/`), the Base contract + 19-test Foundry battery, and this documentation.
- **Dependencies:** `sibyl-memory-client` (installed from PyPI, not vendored), `forge-std` (Foundry test utilities), `pytest`/`pytest-timeout`, Solidity 0.8.24, Python 3.10+.
- **External code adapted:** none. All domain logic is original.
- **Boundaries:** the demo market is a deterministic synthetic seed (five resolved, TX-verified failures) clearly labeled in `scripts/seed_history.py`; no mainnet funds moved; any Base Sepolia deployment is env-key-driven and nothing is committed.

## Deploy (Base)

`contracts/CanonMarket.sol` is deployment-ready and tested on the local EVM. To deploy on Base Sepolia:

```bash
cd contracts
forge create CanonMarket \
  --rpc-url $BASE_SEPOLIA_RPC \
  --private-key $DEPLOYER_KEY \
  --constructor-args <VENUE_ADDRESS> <ADJUDICATOR_ADDRESS>
```

The engine's ledger (`canon/ledger.py`) is the memory-side mirror of the contract's money moves; wiring them means the venue calls the contract for `fund`/`releaseMilestone`/`resolveClaim`/`openAppeal` and stores the returned transaction hashes as `chain_ref` — which is exactly the field `Transaction.chain_ref` already carries. No deployer key is committed; nothing in this repo touches mainnet.

## Limitations

- **One vertical by design**: ACP software/research-agent contracts on the `acp-research` jurisdiction. Multi-jurisdiction doctrine propagation is documented but not built — the memory axis is proven on one spine instead of faked across many.
- **The ledger is a mirror, not yet a live rail**: the Python ledger and the Solidity contract are separately tested; the bridge (venue → contract calls) is the remaining integration and needs a funded Sepolia key.
- **No frontend in this repo**: judging flows are driven by `scripts/` and the CLI gate artifacts; the interactive venue UI is a separate deliverable.
- **Decay is time-based, not outcome-weighted**: a rule's status ages on a fixed schedule refreshed by supporting cases; per-actor outcome weighting beyond the counterparty file is future work.
- **Proven at evaluation time**: terms are generated from the doctrine current when the transaction is evaluated; a funded transaction's terms are immutable (asserted by `test_t016`), so mid-job doctrine changes never rewrite a live deal.

## Team

| Name | Role | Links |
|---|---|---|
| **subheeksh5599** | Solo — full build | [GitHub](https://github.com/subheeksh5599) |

Built for the **Sibyl Labs Hackathon 2026**. MIT licensed.
