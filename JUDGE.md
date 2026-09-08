# JUDGE.md — understand CANON in under two minutes

CANON is the exchange where agents transact under terms the economy itself writes.

## Fast path

1. Read the deletion-test output at the top of `README.md` — that is the gate argument.
2. Find the memory call sites:
   - Doctrine read at evaluation: `canon/doctrine.py` → `current_doctrine()` / `evaluate()`
   - Doctrine write on activation: `canon/doctrine.py` → `activate_doctrine_update()` / `persist()`
   - Case evidence write: `canon/cases.py` → `resolve_case()`
   - The only Sibyl import in the repo: `canon/memory.py`
3. Run the three gate artifacts:
   ```bash
   python scripts/fresh_session.py     # ~10s — cold-start proof
   python scripts/deletion_test.py     # ~5s  — deletion test
   python scripts/ablation.py          # ~5s  — history vs memoryless
   python scripts/demo.py              # ~10s — full 16-step story
   ```
4. Run the tests: `python -m pytest tests/ -q` (165) and `cd contracts && forge test` (19).

## The one question CANON answers

> A stranger's past failure changes the exact contract I receive today.
> Not a score. Not a warning. Not a denial. A different deal.

## The claim, made checkable

| Claim | Where it's proven |
|---|---|
| Memory is load-bearing (gate) | `scripts/deletion_test.py`; `tests/test_cases_gate.py` (G-003/G-004/G-020) |
| Fresh-session recall changes decisions | `scripts/fresh_session.py`; `tests/test_cases_gate.py` (G-010/G-018) |
| Doctrine self-amends from evidence | `canon/doctrine.py::activate_doctrine_update`; tests D-012..D-018 |
| Rules are contestable | `canon/appeals.py`; `scripts/demo.py` steps 6-7; tests A-001..A-020 |
| Terms are deterministic, not LLM-chosen | `canon/doctrine.py::_match/_build_terms`; test D-001/D-002 |
| Only resolved, verifiable evidence seeds rules | `canon/cases.py::resolve_case` + `pattern_stats`; tests D-025/S-001 |
| Base executes the terms | `contracts/CanonMarket.sol` + 19-test battery |

## Architecture in one diagram

```
agents (Virtuals) -> CANON venue -> Sibyl recall (cases + doctrine)
   -> deterministic terms -> Base escrow/bond -> outcome -> memory -> doctrine evolves
   -> any agent can appeal a rule with a bond -> accepted appeal amends doctrine for everyone
```
