"""Gate artifact 2 — the deletion test.

WITH Sibyl:  recall precedent -> doctrine -> authoritative terms.
WITHOUT Sibyl: no admission, no doctrine, no authoritative terms — CANON
cannot construct the transaction. That is the load-bearing proof.

Exit code: 0 = gate proof passes, 1 = CANON still worked without memory (fail).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from canon.errors import CanonError

BUYER = "0xbuyer000000000000000000000000000001"
PROVIDER = "0xprov000000000000000000000000000002"
PROVIDER2 = "0xprov000000000000000000000000000003"


def main(db: str) -> int:
    from scripts.seed_history import seed

    canon = Canon(db)
    seed(canon)

    # WITH memory ------------------------------------------------------------
    canon.admit(PROVIDER2)
    t = canon.evaluate(buyer=BUYER, provider=PROVIDER2,
                       job_type="research agent", job_value_usd=400.0)
    with_memory = t.to_dict()
    print(f"WITH SIBYL     : doctrine v{t.doctrine_version} -> {with_memory}")

    # DELETE memory ----------------------------------------------------------
    canon.seam.delete_all()

    # WITHOUT memory ---------------------------------------------------------
    fresh = Canon(db)
    failed = False
    try:
        fresh.admit(BUYER)
        fresh.evaluate(buyer=BUYER, provider=PROVIDER,
                       job_type="research agent", job_value_usd=400.0)
        failed = True  # evaluation succeeded without memory — bad
    except CanonError as exc:
        print(f"WITHOUT SIBYL  : refused -> {type(exc).__name__}: {str(exc)[:90]}")
    if failed:
        print("DELETION TEST FAIL — CANON still evaluated without Sibyl")
        return 1
    print("DELETION TEST PASS — removing Sibyl removes CANON's ability to rule")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/tmp/canon-deletion.db")
    sys.exit(main(ap.parse_args().db))
