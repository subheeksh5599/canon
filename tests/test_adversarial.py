"""Adversarial suite (S-*) — the system fails safely under attack."""
import pytest

from canon.errors import (
    AppealError,
    CanonError,
    ConflictError,
    NotFoundError,
    RuleConflictError,
    StandingError,
    ValidationError,
)

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"
J = "0xjudg0000000000000000000000000000"

from tests.conftest import prime_doctrine, run_failed_job


def test_s003_sybil_claims_map_to_one_tx(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    for fake in ("0xbuyer0000000000000000000000000000a1",
                 "0xbuyer0000000000000000000000000000a2"):
        canon.admit(fake)
        with pytest.raises(StandingError):
            canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=fake,
                                  evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_s004_collusion_cannot_inflate(canon):
    canon.admit(B)
    canon.admit(P)
    for i in range(6):
        tx = run_failed_job(canon, chain=f"0xcol{i}")
        canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
        # RAW cases (never adjudicated) cannot seed doctrine
    assert canon.doctrine_now().version == 0
    assert canon.doctrine.signal_level("research")[0].value == "NONE"


def test_s005_appeal_economics(ruled_market):
    canon, rid = ruled_market
    with pytest.raises(AppealError):
        canon.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                          evidence=[{"source": "ATTESTATION"}], bond_usd=0.01)


@pytest.fixture()
def ruled_market(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    return canon, canon.doctrine_now().rules[0].rule_id


def test_s006_archived_rule_never_fires(canon, clock):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    clock.advance(days=200)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=300.0)
    assert t.doctrine_version == 1      # version retained
    assert t.bond_usd == 0.0            # archived rule cannot fire


def test_s011_tampered_doctrine_blocks(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.seam.set_reference("doctrine:v1", {"rules": [], "version": 1, "evil": True})
    with pytest.raises(CanonError):
        canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=100.0)


def test_s012_duplicate_claim_farming_pays_once(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                       evidence=[{"source": "TX_VERIFIED"}])
    paid = res["settlement"]["paid"]
    assert canon.venue.require_tx(tx.tx_id).state.value == "CLAIMED"
    claims = [c for c in canon.seam.list_entities("claim")]
    assert len(claims) == 1
    assert claims[0]["amount_usd"] == paid


def test_s013_mid_flight_tamper_invalidates(canon):
    canon.admit(B)
    canon.admit(P)
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=500.0)
    tx = canon.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=500.0, terms=t)
    tx2 = canon.venue.require_tx(tx.tx_id)
    assert tx2.terms == t
    # mutating the terms snapshot is refused: only the evaluated terms may fund
    with pytest.raises((ConflictError, ValidationError)):
        canon.venue.mark_termed(tx.tx_id, None)


def test_s014_no_secrets_in_repo():
    import os
    bad = []
    for root, _, files in os.walk("canon"):
        for f in files:
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for token in ("PRIVATE KEY", "BEGIN RSA", "mnemonic"):
                if token in txt:
                    bad.append(p)
    assert bad == []


def test_s015_memory_db_not_committed():
    import subprocess
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout
    assert not any(x.endswith(".db") for x in out.split())


def test_s016_duplicate_claim_spam_blocked(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                          evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    for _ in range(10):
        with pytest.raises(ConflictError):
            canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                                  evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_s018_decay_under_adversarial_input(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    for i in range(3):
        t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=40.0)
        tx = canon.create_tx(buyer=B, provider=P2, job_type="research agent",
                             job_value_usd=40.0, terms=t)
        canon.execute(tx.tx_id, chain_ref=f"0xcl{i}")
        canon.complete(tx.tx_id, provider=P2)
    cp = canon.cases.get_counterparty(P2)
    assert cp.completed_jobs == 3


def test_s019_role_conflict_impossible(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    with pytest.raises(ValidationError):
        canon.cases.resolve_case(case.case_id, outcome="FAILED", loss_usd=1.0,
                                 ruling="x", verifier=B)


def test_s021_backdating_blocked(canon, clock):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    clock.advance(days=400)
    with pytest.raises(ValidationError):
        canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


@pytest.mark.parametrize("payload", [
    {"buyer": "", "provider": P, "job_type": "x", "job_value_usd": 1},
    {"buyer": B, "provider": "", "job_type": "x", "job_value_usd": 1},
    {"buyer": B, "provider": P, "job_type": "", "job_value_usd": 1},
    {"buyer": B, "provider": P, "job_type": "x", "job_value_usd": -1},
    {"buyer": B, "provider": B, "job_type": "x", "job_value_usd": 1},
])
def test_s022_fuzz_malformed(canon, payload):
    canon.admit(B)
    canon.admit(P)
    with pytest.raises((ValidationError, StandingError)):
        canon.create_tx(**payload)


def test_rule_conflict_detected():
    from canon.doctrine import DoctrineEngine
    from canon.types import Doctrine, TxFacts
    from tests.test_doctrine import _rule
    engine = DoctrineEngine.__new__(DoctrineEngine)
    engine.persist = lambda doctrine: None
    engine.clock = __import__("canon.clock", fromlist=["Clock"]).Clock()
    engine.decay_weakening_days = 30
    engine.decay_archive_days = 90
    engine.lookback_days = 180
    engine._seam = type("S", (), {"list_entities": lambda *a, **k: []})()
    doc = Doctrine(version=1, rules=[_rule(rule_id="R1"), _rule(rule_id="R2")])
    engine.current_doctrine = lambda: doc
    facts = TxFacts(buyer=B, provider=P, job_type="research agent", job_value_usd=500.0)
    with pytest.raises(RuleConflictError):
        engine.evaluate(facts, None)


def test_pool_payout_capped_positive(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon, value=900.0)
    res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                       evidence=[{"source": "TX_VERIFIED"}])
    s = res["settlement"]
    assert s["coverage"] == 0.0
    assert s["paid"] <= 900.0
