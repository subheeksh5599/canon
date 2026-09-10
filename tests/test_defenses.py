"""Defense suite — the three hardening layers added after the hostile review.

1. Anti-Sybil: a doctrine built by one counterparty cannot become law when the
   venue requires distinct counterparties.
2. Appeal quorum: a resolution can require several distinct approvals.
3. Attestation replay: an attestation id is single-use.
"""
import pytest

from canon.errors import ConflictError, ValidationError
from tests.conftest import make_facts, prime_doctrine

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"


# ------------------------------------------------------- 1. anti-Sybil
def test_single_counterparty_history_cannot_make_law(monkeypatch, canon):
    monkeypatch.setenv("CANON_MIN_DISTINCT_COUNTERPARTIES", "3")
    canon.admit(B); canon.admit(P)
    prime_doctrine(canon, n=5, provider=P)     # five failures, ONE provider
    assert canon.doctrine_now().version == 0   # activation refused


def test_sybil_guard_off_by_default_keeps_fixtures_working(canon):
    canon.admit(B); canon.admit(P)
    prime_doctrine(canon, n=5, provider=P)
    assert canon.doctrine_now().version >= 1


# ------------------------------------------------------- 2. appeal quorum
def test_appeal_quorum_requires_distinct_approvals(monkeypatch, canon):
    monkeypatch.setenv("CANON_APPEAL_QUORUM", "2")
    canon.admit(B); canon.admit(P); canon.admit(P2)
    prime_doctrine(canon)
    rule_id = canon.doctrine_now().rules[0].rule_id
    app = canon.open_appeal(challenger=P2, target_rule_id=rule_id, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    with pytest.raises(ValidationError):
        canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=B,
                             approvals=[B])          # one approval, quorum is two
    ok = canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=B,
                              approvals=[B, "0xjudg0000000000000000000000000000"])
    assert ok.decision == "ACCEPTED"


def test_appeal_quorum_of_one_is_the_deployment_default(canon):
    canon.admit(B); canon.admit(P); canon.admit(P2)
    prime_doctrine(canon)
    rule_id = canon.doctrine_now().rules[0].rule_id
    app = canon.open_appeal(challenger=P2, target_rule_id=rule_id, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    assert canon.resolve_appeal(app.appeal_id, decision="REJECTED", adjudicator=B).decision == "REJECTED"


# ------------------------------------------------------- 3. replay
def test_attestation_id_is_single_use(canon):
    canon.admit(B); canon.admit(P)
    for i in (1, 2):
        f = make_facts(value=100.0)
        t = canon.evaluate(buyer=B, provider=P, job_type=f.job_type, job_value_usd=100.0)
        tx = canon.create_tx(buyer=B, provider=P, job_type=f.job_type,
                             job_value_usd=100.0, terms=t)
        canon.execute(tx.tx_id, chain_ref=f"0xdead{i}")
        canon.fail(tx.tx_id, provider=P)
        ev = [{"source": "ATTESTATION", "note": "same attestation", "attestation_id": "att-777"}]
        if i == 1:
            canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier="0xjudge", evidence=ev)
        else:
            with pytest.raises(ConflictError):
                canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier="0xjudge", evidence=ev)
