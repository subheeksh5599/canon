"""CANON canonical demo — the full 16-step judge sequence, no improv.

request -> naive terms -> failure -> 5 claims -> doctrine v1 -> fresh session
-> new terms -> appeal -> bond -> accepted -> doctrine v2 -> fresh session ->
different terms again -> deletion proof.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from scripts.seed_history import BUYER, PROVIDER, PROVIDER2, JUDGE, seed


def main(db: str) -> int:
    import tempfile
    demo_db = db or tempfile.mktemp(suffix=".db")
    canon = Canon(demo_db)
    step = 0

    def say(msg: str) -> None:
        nonlocal step
        step += 1
        print(f"{step:>2}. {msg}")

    # 1-2: venue admission
    canon.admit(BUYER)
    canon.admit(PROVIDER)
    say("buyer + provider enter the CANON venue (rules accepted, recorded)")

    # 3-4: first transaction, no history -> naive terms
    t1 = canon.evaluate(buyer=BUYER, provider=PROVIDER,
                        job_type="research agent", job_value_usd=400.0)
    say(f"no precedent found -> terms {t1.to_dict()}")
    tx1 = canon.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                          job_value_usd=400.0, terms=t1)
    canon.execute(tx1.tx_id, chain_ref="0xdemo1")
    canon.complete(tx1.tx_id, provider=PROVIDER)
    say("job 1 delivered — outcome written to memory")

    # 5-8: five failures cross the evidence threshold
    for i in range(5):
        t = canon.evaluate(buyer=BUYER, provider=PROVIDER,
                           job_type="research agent", job_value_usd=400.0)
        tx = canon.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                             job_value_usd=400.0, terms=t)
        canon.execute(tx.tx_id, chain_ref=f"0xdemo-dead{i}")
        canon.fail(tx.tx_id, provider=PROVIDER)
        res = canon.file_and_resolve_claim(
            tx_id=tx.tx_id, buyer=BUYER, verifier=JUDGE,
            evidence=[{"source": "TX_VERIFIED", "note": "no delivery"}])
    say(f"5 confirmed failures -> signal {res['signal']}, doctrine v{res['doctrine_version_after']}")

    # 9-10: fresh provider, same job -> doctrine-generated terms
    canon.admit(PROVIDER2)
    t2 = canon.evaluate(buyer=BUYER, provider=PROVIDER2,
                        job_type="research agent", job_value_usd=400.0)
    say(f"fresh session, unrelated provider -> {t2.to_dict()}")

    # 11-13: appeal with bond -> accepted -> doctrine v2
    rid = t2.rule_ids[0]
    app = canon.open_appeal(challenger=PROVIDER2, target_rule_id=rid,
                            arguments="20% bond on a clean provider is disproportionate",
                            evidence=[{"source": "ATTESTATION", "note": "100 clean jobs"}],
                            bond_usd=20.0)
    resolved = canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=JUDGE)
    say(f"appeal {resolved.decision} (bond posted on Base) -> doctrine v{canon.doctrine_now().version}")

    # 14-15: fresh session under v2 -> terms changed again
    canon2 = Canon(demo_db)
    canon2.admit(BUYER)
    canon2.admit(PROVIDER2)
    t3 = canon2.evaluate(buyer=BUYER, provider=PROVIDER2,
                         job_type="research agent", job_value_usd=400.0)
    say(f"fresh session after appeal -> {t3.to_dict()}")

    # 16: deletion proof
    canon2.seam.delete_all()
    say("DELETE SIBYL -> no admission, no doctrine -> CANON cannot construct terms")
    assert t1.bond_usd == 0.0 and t2.bond_usd > 0.0 and t3.bond_usd < t2.bond_usd
    print(f"\nDEMO PASS — terms: naive {t1.bond_usd}% bond -> v1 {t2.bond_usd} -> v2 {t3.bond_usd}")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    sys.exit(main(ap.parse_args().db))
