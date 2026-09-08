import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from canon.clock import Clock
from canon.types import TxFacts


@pytest.fixture()
def clock():
    from datetime import datetime, timezone
    c = Clock()
    c.freeze(datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc))
    return c


@pytest.fixture()
def canon(tmp_path, clock):
    return Canon(tmp_path / "canon.db", clock=clock)


@pytest.fixture()
def market(canon):
    """Standard venue: buyer + one provider admitted; naive doctrine (v0)."""
    canon.admit("0xbuyer000000000000000000000000000001")
    canon.admit("0xprov000000000000000000000000000002")
    return canon


def make_facts(buyer="0xbuyer000000000000000000000000000001",
               provider="0xprov000000000000000000000000000002",
               job_type="research agent", value=400.0) -> TxFacts:
    return TxFacts(buyer=buyer, provider=provider, job_type=job_type, job_value_usd=value)


def run_failed_job(canon, buyer="0xbuyer000000000000000000000000000001",
                   provider="0xprov000000000000000000000000000002",
                   job_type="research agent", value=400.0, chain="0xdead"):
    t = canon.evaluate(buyer=buyer, provider=provider, job_type=job_type, job_value_usd=value)
    tx = canon.create_tx(buyer=buyer, provider=provider, job_type=job_type,
                         job_value_usd=value, terms=t)
    canon.execute(tx.tx_id, chain_ref=chain)
    canon.fail(tx.tx_id, provider=provider)
    return tx


def resolve_failure(canon, tx, verifier="0xjudg0000000000000000000000000000"):
    return canon.file_and_resolve_claim(
        tx_id=tx.tx_id, buyer=tx.buyer, verifier=verifier,
        evidence=[{"source": "TX_VERIFIED", "note": "no delivery"}])


def prime_doctrine(canon, n=5, provider="0xprov000000000000000000000000000002"):
    """n confirmed failures in the research class -> doctrine activated."""
    last = None
    for i in range(n):
        tx = run_failed_job(canon, provider=provider, chain=f"0xdead{i}")
        last = resolve_failure(canon, tx)
    return last
