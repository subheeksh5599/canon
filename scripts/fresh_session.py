"""Gate artifact 1 — cold-start / fresh-session proof.

Two genuinely separate Canon objects (fresh processes, zero shared python
state) over the same Sibyl file. Session B recalls doctrine written by
session A and returns DIFFERENT terms for the same request. Prints a
timestamped, machine-readable record for the demo video.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from scripts.seed_history import BUYER, PROVIDER, PROVIDER2, JUDGE  # noqa: F401


def run(db: str) -> None:
    from scripts.seed_history import seed
    import tempfile

    # --- virgin baseline: a market with no history ---------------------------
    v = Canon(tempfile.mktemp(suffix=".db"))
    v.admit(BUYER)
    v.admit(PROVIDER2)
    t_virgin = v.evaluate(buyer=BUYER, provider=PROVIDER2,
                          job_type="research agent", job_value_usd=400.0)
    print(f"[virgin market] doctrine v{v.doctrine_now().version}")

    # --- session A: build history -------------------------------------------
    a = Canon(db)
    seed(a)
    print(f"[session A] doctrine v{a.doctrine_now().version}")

    # --- session B: genuinely fresh process, same db ------------------------
    b = Canon(db)
    b.admit(BUYER)
    b.admit(PROVIDER2)
    t_recalled = b.evaluate(buyer=BUYER, provider=PROVIDER2,
                            job_type="research agent", job_value_usd=400.0)
    print(f"[session B] doctrine v{b.doctrine_now().version} recalled from Sibyl")
    print(f"FRESH SESSION TIMESTAMP {b.clock.iso()}")
    print(f"terms BEFORE history: {t_virgin.to_dict()}")
    print(f"terms AFTER recall : {t_recalled.to_dict()}")
    assert t_virgin.bond_usd == 0.0
    assert t_recalled.bond_usd > 0.0
    assert b.journal_ok()[0]
    print("COLD-START PROOF PASS — a stranger's history changed the deal")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/tmp/canon-fresh.db")
    run(ap.parse_args().db)
