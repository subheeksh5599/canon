# Prior Work Declaration

Built for the Sibyl Labs Hackathon 2026 (build window Sep 1–10). This document is brutally transparent about what predates the window and what was built during it.

## What existed before Sep 1, 2026

- **The concept only.** CANON (a venue where agent transactions get terms generated from collective precedent) existed as an idea and a design conversation before the build window. No application code, no schemas, no contracts, no repository.

## What was built during the hackathon window

All of the following was written during the build window, in this repository:

- The complete Python engine (`canon/`): venue admission, transaction state machine, case lifecycle, deterministic doctrine engine, appeals, ledger, the Sibyl memory seam, typed domain errors, canonical schemas.
- The test battery: 165 tests across 7 suites.
- The gate scripts (`scripts/`): seed history, fresh-session proof, deletion test, ablation, canonical demo.
- The Base contract (`contracts/CanonMarket.sol`) and its 19-test Foundry battery.
- All documentation in this repository (README, MEMORY-NOTE, JUDGE, docs/).

## Open-source dependencies

- `sibyl-memory-client` (PyPI) — the mandatory memory layer; installed, not vendored.
- `forge-std` (Foundry) — test utilities for the contract battery.
- `pytest` / `pytest-timeout` — test runner.
- Solidity compiler 0.8.24, Python 3.10+.

## What was substantially modified from external code

- Nothing. No pre-existing open-source project code was adapted into CANON. All domain logic is original to this repository.

## Boundaries

- No external data was used; the demo market is a deterministic synthetic seed (five resolved, TX-verified failures) clearly labeled as synthetic in `scripts/seed_history.py`.
- No mainnet funds moved; contract tests run on the local EVM; any Base Sepolia deployment is env-key-driven and none is committed.
