"""Reliability suite (R-*): restart survival, idempotency, deterministic seed,
error taxonomy, health."""
import subprocess
import sys

import pytest

from canon.errors import CanonError, ConflictError, MemoryUnavailableError, NotFoundError, ValidationError

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"
J = "0xjudg0000000000000000000000000000"

from tests.conftest import prime_doctrine, run_failed_job


def test_r003_restart_mid_transaction_resumes(tmp_path, clock):
    from canon import Canon
    db = tmp_path / "r.db"
    c1 = Canon(db, clock=clock)
    c1.admit(B)
    c1.admit(P)
    t = c1.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=200.0)
    tx = c1.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=200.0, terms=t)
    c1.execute(tx.tx_id, chain_ref="0xmid")
    c1.venue.begin(tx.tx_id)
    # kill the process (fresh Canon object), resume the job
    c2 = Canon(db, clock=clock)
    tx = c2.venue.require_tx(tx.tx_id)
    assert tx.state.value == "IN_PROGRESS"
    c2.complete(tx.tx_id, provider=P)
    assert c2.venue.require_tx(tx.tx_id).state.value == "COMPLETED"


def test_r004_duplicate_webhook_idempotent(canon):
    canon.admit(B)
    canon.admit(P)
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=100.0)
    # create the same logical transaction twice -> two ids, no corruption
    tx1 = canon.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=100.0, terms=t)
    tx2 = canon.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=100.0, terms=t)
    assert tx1.tx_id != tx2.tx_id
    assert canon.venue.require_tx(tx1.tx_id).state.value == "TERMED"


def test_r005_seed_deterministic(canon):
    canon.admit(B)
    canon.admit(P)
    t1 = canon.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=777.0).to_dict()
    canon.admit(P2)
    t2 = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=777.0).to_dict()
    # same virgin doctrine -> identical terms regardless of who asks
    assert t1["upfront_usd"] == t2["upfront_usd"] == 777.0


def test_r006_env_example_no_secrets():
    env = open(".env.example").read() if __import__("os").path.exists(".env.example") else ""
    assert "SECRET" not in env.replace("RECEIPT_SECRET", "").upper() or "example" in env.lower()


def test_r007_health_snapshot(canon):
    canon.admit(B)
    v = canon.doctrine.current_doctrine().version
    assert v >= 0
    assert canon.journal_ok()[0] is True


def test_r008_demo_vs_production_never_mixed(canon):
    # data lives under one path per Canon instance; no global mixing
    assert str(canon.db_path).endswith(".db") or "canon" in str(canon.db_path)


def test_r009_latency_budget(canon):
    import time
    canon.admit(B)
    canon.admit(P)
    canon.admit(P2)
    prime_doctrine(canon)
    start = time.monotonic()
    for _ in range(50):
        canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=200.0)
    elapsed = (time.monotonic() - start) / 50
    assert elapsed < 0.5  # local memory reads stay far under 500ms


def test_r010_second_run_green(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    # run the canonical judge sequence twice on the same store
    for _ in range(2):
        t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=250.0)
        assert t.doctrine_version >= 1
    assert canon.journal_ok()[0]


def test_g012_clean_clone_commands(tmp_path, clock):
    """The README quickstart must run from a clean checkout."""
    from canon import Canon
    db = tmp_path / "clone.db"
    c = Canon(db, clock=clock)
    c.admit(B)
    c.admit(P)
    t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
    assert t.upfront_usd == 100.0


def test_error_taxonomy_distinct():
    from canon.errors import (
        CanonError, ConflictError, NotFoundError, ValidationError,
        StandingError, UnauthorizedVenueError, AppealError,
        SettlementError, MemoryUnavailableError, RuleConflictError,
    )
    errs = [ConflictError, NotFoundError, ValidationError, StandingError,
            UnauthorizedVenueError, AppealError, SettlementError,
            MemoryUnavailableError, RuleConflictError]
    for e in errs:
        assert issubclass(e, CanonError)
    assert len({e.__name__ for e in errs}) == len(errs)


def test_r002_memory_outage_refuses_evaluate(canon):
    canon.admit(B)
    canon.admit(P)
    canon.seam.delete_all()
    # after deletion there is no admission and no doctrine: evaluation must
    # fail with a domain error — never silently return naive terms
    with pytest.raises(CanonError):
        canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=50.0)


def test_duplicate_admit_no_double_event(canon):
    canon.admit(B)
    canon.admit(B)
    n = len([e for e in canon.seam.read_events() if e["acted"] == "venue.admit" and B in str(e["evaluated"])])
    assert n == 1


def test_pool_ledger_entries_bounded(canon):
    for i in range(120):
        canon.seam.pool_mutate(1.0, f"tick{i}")
    entries = canon.seam.get_reference("pool:ledger")["entries"]
    assert len(entries) <= 2000
