"""Charter founding battery (H-001..H-009): the live venue is FOUNDED by one
declared rule with zero fabricated case evidence; every case on record must be
a real executed transaction; the charter is amended by appeals and dies with
the memory like any other doctrine."""
import tempfile

import pytest

from canon import Canon
from canon.errors import CanonError
from scripts.seed_history import BUYER, PROVIDER, PROVIDER2, JUDGE


@pytest.fixture
def charter_market():
    db = tempfile.mktemp(suffix=".db")
    c = Canon(db)
    c.admit(BUYER)
    c.admit(PROVIDER)
    c.admit(PROVIDER2)
    doc = c.establish_charter()
    return c, doc


def test_charter_founds_doctrine_v1_with_declared_provenance(charter_market):
    c, doc = charter_market
    assert doc is not None and doc.version == 1
    rule = doc.rules[0]
    assert rule.rule_id == "CANON-001-research"
    assert rule.created_by_case == "charter"   # declared policy, not a fake case
    assert rule.supporting_case_ids == []      # zero fabricated evidence
    assert rule.min_supporting_cases == 0
    now = c.doctrine_now()
    assert now.version == 1


def test_charter_is_not_called_twice(charter_market):
    c, doc = charter_market
    assert c.establish_charter() is None
    assert c.doctrine_now().version == 1


def test_charter_terms_match_declared_ratios(charter_market):
    c, _ = charter_market
    t = c.evaluate(buyer=BUYER, provider=PROVIDER,
                   job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version == 1
    assert t.upfront_usd == 100.0            # 25% cap
    assert list(t.milestones) == [100.0] * 3
    assert t.bond_usd == 80.0                # 20%
    assert t.coverage_ratio == 0.8


def test_charter_survives_reload():
    db = tempfile.mktemp(suffix=".db")
    c1 = Canon(db)
    c1.admit(PROVIDER)
    c1.establish_charter()
    c2 = Canon(db)  # genuinely fresh process over the same file
    assert c2.doctrine_now().version == 1
    assert c2.doctrine_now().rules[0].created_by_case == "charter"


def test_deletion_gate_holds_on_charter_market():
    """The deletion gate applies to charter markets too: no Sibyl -> no
    admission -> no doctrine -> no terms (H-005)."""
    db = tempfile.mktemp(suffix=".db")
    c = Canon(db)
    c.admit(BUYER)
    c.admit(PROVIDER)
    c.establish_charter()
    assert c.doctrine_now().version == 1
    c.seam.delete_all()
    fresh = Canon(db)
    fresh.admit(BUYER)
    with pytest.raises(CanonError):
        fresh.evaluate(buyer=BUYER, provider=PROVIDER,
                       job_type="research agent", job_value_usd=20.0)


def test_real_case_is_journaled_evidence_and_charter_holds(charter_market):
    """A real executed failure on a charter market is journaled as real
    TX_VERIFIED evidence; the charter keeps governing until enough real cases
    accumulate to refresh/amend it. No case is fabricated."""
    c, _ = charter_market
    for _ in range(2):
        t = c.evaluate(buyer=BUYER, provider=PROVIDER,
                       job_type="research agent", job_value_usd=20.0)
        tx = c.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                         job_value_usd=20.0, terms=t)
        c.execute(tx.tx_id, chain_ref="0x" + "f" * 64)
        c.fail(tx.tx_id, provider=PROVIDER)
        c.file_and_resolve_claim(tx_id=tx.tx_id, buyer=BUYER, verifier=JUDGE,
                                 evidence=[{"source": "TX_VERIFIED",
                                            "note": "escrow 0x" + "f" * 64}])
    cases = c.cases.list_cases()
    assert len(cases) == 2
    assert all(cs["evidence"][0]["source"] == "TX_VERIFIED" for cs in cases)
    # charter still governs (v1), provenance untouched by real evidence below
    # the refresh threshold
    assert c.doctrine_now().version == 1
    assert c.doctrine_now().rules[0].created_by_case == "charter"


def test_five_real_cases_refresh_charter_support(charter_market):
    """Five real resolved failures on the governed pattern refresh the charter
    rule's support (decay clock stays young) — evidence, not replacement."""
    c, _ = charter_market
    for _ in range(5):
        t = c.evaluate(buyer=BUYER, provider=PROVIDER,
                       job_type="research agent", job_value_usd=20.0)
        tx = c.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                         job_value_usd=20.0, terms=t)
        c.execute(tx.tx_id, chain_ref="0x" + "f" * 64)
        c.fail(tx.tx_id, provider=PROVIDER)
        c.file_and_resolve_claim(tx_id=tx.tx_id, buyer=BUYER, verifier=JUDGE,
                                 evidence=[{"source": "TX_VERIFIED",
                                            "note": "escrow 0x" + "f" * 64}])
    rule = c.doctrine_now().rules[0]
    assert rule.created_by_case == "charter"
    assert rule.last_supported_at is not None  # refreshed by real evidence


def test_appeal_amends_charter_doctrine(charter_market):
    c, _ = charter_market
    a = c.open_appeal(challenger=PROVIDER2, target_rule_id="CANON-001-research",
                      arguments="bond is too heavy for verified work",
                      evidence=[{"source": "ATTESTATION", "note": "clean record"}],
                      bond_usd=5.0)
    c.resolve_appeal(a.appeal_id, decision="ACCEPTED", adjudicator=JUDGE)
    doc = c.doctrine_now()
    assert doc.version == 2
    assert doc.supersedes == 1
    v2_rule = doc.rules[0]
    assert v2_rule.rule_id != "CANON-001-research"     # relaxed copy governs
    assert v2_rule.created_by_case == "charter"        # provenance preserved
    assert v2_rule.bond_ratio < 0.20                   # relaxed by the appeal
