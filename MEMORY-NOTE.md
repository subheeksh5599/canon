# CANON — Memory Implementation Note

**What CANON is:** a venue where autonomous agents transact under executable terms generated from the venue's collective institutional memory (Sibyl).

## What CANON remembers

- **Cases** (WARM entities, `category="case"`): every resolved dispute — buyer, provider, job type, value, contract terms, evidence, outcome, loss, confidence, precedent linkage.
- **Counterparty files** (WARM, `category="counterparty"`): completed/failed/partial jobs, claim count, clean-jobs-since-failure, resolution history — facts, never scores.
- **Admissions** (WARM, `category="agent"`): who accepted venue rules (jurisdiction is contractual) and whether they are active or suspended.
- **The doctrine** (REFERENCE references `doctrine:v{n}` + `doctrine:current`): versioned rules with trigger conditions, term modifiers, supporting-case evidence, provenance (`created_by_case`, `supersedes`, `amended_by_appeal`), and a SHA-256 sidecar checksum per version.
- **Appeals** (WARM, `category="appeal"`): open challenges, bonds, adjudications.
- **The journal** (COLD events): every meaningful decision — admission, evaluation, funding, completion, failure, claim resolution, doctrine activation, appeal outcome — append-only with per-event chain hashes.

## What CANON recalls and when

- **At every evaluation** (`canon/engine.py::evaluate`): the venue recalls the current doctrine version from `doctrine:current`, loads the full rule set, and checks which rules are frozen by open appeals. Term generation is impossible without this read.
- **At every claim** (`canon/doctrine.py::pattern_stats`): the engine recalls *all resolved cases matching the job-class pattern* — including cases involving entirely unrelated participants. This is the stranger effect: Provider B's terms change because of Provider A's failures.
- **At every fresh session**: a new `Canon` object over the same Sibyl file starts with zero Python state and reconstructs admission, doctrine, and case history purely from memory. `scripts/fresh_session.py` proves it.

## Why CANON persists

Without persistence, every session is the first session: the same bad actor gets the same naive 100%-upfront terms forever, and no rule ever forms from experience. Persistence is what turns isolated transactions into an institution.

## How recall changes decisions

The money path is: `Sibyl recall → doctrine evaluator → deterministic term generator → transaction terms → Base execution`. Recall directly changes the numbers on the deal. Delete memory and the only possible output is the naive default (100% upfront, no bond) — and in practice evaluation refuses entirely because admission records and doctrine are gone (`scripts/deletion_test.py`).

## How doctrine becomes transaction terms

1. A case resolves with HIGH/MEDIUM-confidence evidence (`canon/cases.py::resolve_case`).
2. The engine counts confirmed failures per normalized job pattern (`pattern_stats`).
3. At the 5-case threshold the doctrine engine activates vN+1 (`activate_doctrine_update`) — a new rule whose triggers and modifiers are derived from the evidence, stored in Sibyl's REFERENCE tier with full provenance.
4. The next evaluation matches the transaction facts against the stored doctrine (`_match`) and returns terms: upfront cap, milestone count, bond ratio, coverage.
5. A winning appeal writes vN+2 with a relaxed rule; a rejected appeal leaves the doctrine byte-identical (archived versions stay readable for audit).

## Why deletion breaks the product

The litmus test applied by the rules: *delete the Sibyl Memory layer — does the project still do what it claims?* No. Without Sibyl there is:

- no admission record → agents cannot enter the venue (`UnauthorizedVenueError`);
- no doctrine → no rule to derive terms from;
- no case history → no precedent, no stranger effect;
- no journal → no audit trail, and the chain-verification fails.

The product *is* the memory. Removing it removes the institution. That is asserted three ways: `tests/test_cases_gate.py::test_g003/test_g004/test_g020`, `tests/test_doctrine.py::test_m013`, and the standalone `scripts/deletion_test.py` which exits non-zero if CANON still evaluates after deletion.

## Cold-start proof

`scripts/fresh_session.py` runs two genuinely separate processes over one Sibyl file. Session A seeds five resolved failures (doctrine v1 written). Session B — fresh object, empty context — evaluates the same request and returns different terms (bond $0 → $80) purely from what session A left in memory. Output includes a timestamp for the unedited demo cut.
