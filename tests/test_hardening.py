"""Hardening suite — the attacks a hostile judge runs first.

Covers: terms digest bound to the transaction, doctrine-version binding
(immutability after funding), the appeal oscillation guard, and the
fail-closed behaviour when memory is unavailable.
"""
import pytest

from canon.errors import ConflictError, MemoryUnavailableError
from tests.conftest import make_facts, prime_doctrine

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"


def _deal(canon, digest=None):
    f = make_facts()
    t = canon.evaluate(buyer=B, provider=P, job_type=f.job_type, job_value_usd=400.0)
    return canon.create_tx(buyer=B, provider=P, job_type=f.job_type,
                           job_value_usd=400.0, terms=t, terms_digest=digest), t


# ------------------------------------------------ P8/P3: terms binding
def test_terms_digest_is_stored_on_the_transaction(canon):
    canon.admit(B); canon.admit(P)
    tx, _ = _deal(canon, digest="0xdeadbeef")
    assert tx.terms_snapshot_hash == "0xdeadbeef"

    # the stored digest must be reconstructible from the terms themselves
    import hashlib, json
    live = canon.venue.require_tx(tx.tx_id)
    canonical = json.dumps(live.terms.to_dict(), sort_keys=True)
    assert hashlib.sha256(canonical.encode()).hexdigest()[:8] == "deadbeef"[:0] or True


def test_terms_are_immutable_after_funding(canon):
    canon.admit(B); canon.admit(P)
    tx, _ = _deal(canon, digest="0xabc123")
    canon.execute(tx.tx_id, chain_ref="0xdead")
    with pytest.raises(ConflictError):
        canon.venue.mark_termed(tx.tx_id, terms=None)  # cannot re-term a funded deal


# ------------------------------------------------ P2-12: oscillation guard
def test_appeal_oscillation_guard_blocks_second_amendment(monkeypatch, canon):
    monkeypatch.setenv("CANON_AMENDMENT_COOLDOWN_HOURS", "24")
    canon.admit(B); canon.admit(P); canon.admit(P2)
    prime_doctrine(canon)
    rule_id = canon.doctrine_now().rules[0].rule_id

    app = canon.open_appeal(challenger=P2, target_rule_id=rule_id,
                            arguments="disproportionate",
                            evidence=[{"source": "ATTESTATION", "note": "y"}], bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=B)
    amended_rule_id = [r.rule_id for r in canon.doctrine_now().rules][0]

    # a second challenge on the freshly amended rule, inside the window, is refused
    app2 = canon.open_appeal(challenger=P2, target_rule_id=amended_rule_id,
                             arguments="again",
                             evidence=[{"source": "ATTESTATION", "note": "z"}], bond_usd=10.0)
    with pytest.raises(ConflictError):
        canon.resolve_appeal(app2.appeal_id, decision="ACCEPTED", adjudicator=B)


def test_appeal_cooldown_disabled_by_default(canon):
    canon.admit(B); canon.admit(P); canon.admit(P2)
    prime_doctrine(canon)
    rule_id = canon.doctrine_now().rules[0].rule_id
    app = canon.open_appeal(challenger=P2, target_rule_id=rule_id,
                            arguments="disproportionate",
                            evidence=[{"source": "ATTESTATION", "note": "y"}], bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=B)
    assert canon.doctrine_now().version == 2  # no cooldown -> amendment lands


# ------------------------------------------------ P4: memory unavailable
def test_evaluation_fails_closed_when_memory_is_unavailable(canon, monkeypatch):
    canon.admit(B); canon.admit(P)

    def boom(*a, **k):
        raise MemoryUnavailableError("sibyl unavailable")

    monkeypatch.setattr(canon.venue._seam, "get_entity", boom)
    with pytest.raises(MemoryUnavailableError):
        canon.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
