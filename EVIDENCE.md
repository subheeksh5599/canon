# EVIDENCE — every claim in this repo, mapped to the thing that proves it

Re-verify all on-chain claims in one command:

```bash
$ .venv/bin/python scripts/verify_receipts.py
...
ALL RECEIPTS VERIFIED
```

| Claim in the README | Proof artifact | How to check |
|---|---|---|
| CanonMarket deployed on Base Sepolia | tx `0xfe5bdfd3…c346`, contract `0x802d15d159B15F91f1663D2b86e90132F6da4D06` | `verify_receipts.py`; explorer page |
| Source matches the deployed bytecode | Sourcify `exact_match` (creation + runtime), Blockscout `Pass - Verified` | links in README honesty table |
| Roles are split on-chain (venue ≠ adjudicator) | `setRoles` tx `0xa00e0418…a47d`; live `venue()`/`adjudicator()` reads | `verify_receipts.py` prints both live |
| Charter-founded doctrine, zero fabricated cases | `canon.establish_charter()`; live rule `created_by_case="charter"` | `/api/doctrine`; `tests/test_charter.py` |
| Real USDC escrow + claim payout | run 1 txs `0x80bb3cb9…`, `0x9153c66f…`, `0x26de681a…`, `0x8fad0e37…` | `verify_receipts.py` |
| Claim signed by the adjudicator wallet | claim tx `0xc2deaefd…e29` (from `0x617B…3046`) | explorer; `/api/chain` |
| Doctrine v2 exists because of a real bonded appeal | appeal tx `0xcb3f5465…3402`, resolve `0xd3e09df2…88e6`; live doctrine v2, bond 0.20→0.10 | `verify_receipts.py`; `/api/appeals` |
| A registered Virtuals EconomyOS agent transacted in the venue | agent `01a08682-7c76-73a8-b2c8-d2e6f42b05b3`, wallet `0x1776e…`; register `0x3b3020d6…`, escrow `0x28dd0366…`, **payout $9.60 `0x292c599d…`** | `verify_receipts.py` prints the agent's live USDC balance |
| Memory is load-bearing (deleting it stops the venue) | `scripts/deletion_test.py` (exits non-zero on failure); UI Integrity panel run; `tests/test_cases_gate.py` | run it; or the console |
| Cold-start recall works across processes | `scripts/fresh_session.py` — two processes, one Sibyl file | run it |
| Memory saves 75% of capital-at-risk | `scripts/ablation.py` — measured on identical work | run it |
| 179 engine tests + 20 contract tests pass | `pytest -q`, `forge test` | run them |
| Live venue + console | https://canon-venue.vercel.app , `/console` | open |

If any row fails to reproduce, that is a real bug: open an issue.
