"""Seed a CANON demo market with real historical case records in Sibyl.

Deterministic: the same scenario list always produces the same market state
(no clock reads, no randomness). Used by the demo and judge flows.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from canon.types import Outcome

BUYER = "0xbuyer000000000000000000000000000001"
PROVIDER = "0xprov000000000000000000000000000002"
PROVIDER2 = "0xprov000000000000000000000000000003"
JUDGE = "0xjudg0000000000000000000000000000"


def seed(canon: Canon, failures: int = 5) -> None:
    canon.admit(BUYER)
    canon.admit(PROVIDER)
    for i in range(failures):
        t = canon.evaluate(buyer=BUYER, provider=PROVIDER,
                           job_type="research agent", job_value_usd=400.0)
        tx = canon.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                             job_value_usd=400.0, terms=t)
        canon.execute(tx.tx_id, chain_ref=f"0xseeddead{i:02x}")
        canon.fail(tx.tx_id, provider=PROVIDER)
        res = canon.file_and_resolve_claim(
            tx_id=tx.tx_id, buyer=BUYER, verifier=JUDGE,
            evidence=[{"source": "TX_VERIFIED", "note": "no delivery"}])
        assert res["case"]["status"] == "RESOLVED"
    canon.admit(PROVIDER2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/tmp/canon-market.db")
    ap.add_argument("--failures", type=int, default=5)
    args = ap.parse_args()
    canon = Canon(args.db)
    seed(canon, failures=args.failures)
    d = canon.doctrine_now()
    print(f"seeded {args.failures} resolved research failures at {args.db}")
    print(f"doctrine v{d.version} · cases {len(canon.cases.list_cases())} · journal ok {canon.journal_ok()[0]}")


if __name__ == "__main__":
    main()
