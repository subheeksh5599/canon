"""Appeals suite (A-001..A-020): bonds, freeze, amendment, abuse controls."""
import pytest

from canon.errors import (
    AppealError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from canon.types import AppealState

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"
J = "0xjudg0000000000000000000000000000"

from tests.conftest import prime_doctrine


@pytest.fixture()
def ruled(canon):
    """Venue with doctrine v1 active."""
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    return canon


def active_rule_id(canon):
    return canon.doctrine_now().rules[0].rule_id


# ------------------------------------------------------------- open (A-*)
def test_a001_no_bond_rejected(ruled):
    with pytest.raises(AppealError):
        ruled.open_appeal(challenger=P2, target_rule_id=active_rule_id(ruled),
                          arguments="x", evidence=[{"source": "ATTESTATION"}], bond_usd=0.0)


def test_a002_bond_recorded(ruled):
    app = ruled.open_appeal(challenger=P2, target_rule_id=active_rule_id(ruled),
                            arguments="x", evidence=[{"source": "ATTESTATION"}], bond_usd=50.0)
    assert app.bond_usd == 50.0


def test_a003_targets_one_precedent(ruled):
    with pytest.raises(NotFoundError):
        ruled.open_appeal(challenger=P2, target_rule_id="CANON-999-none",
                          arguments="x", evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)


def test_a004_duplicate_open_rejected(ruled):
    rid = active_rule_id(ruled)
    ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                      evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    with pytest.raises(ConflictError):
        ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="y",
                          evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)


def test_a005_open_appeal_freezes_rule(ruled):
    rid = active_rule_id(ruled)
    ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                      evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    # rule frozen: a new evaluation must not apply it -> naive or other terms
    t = ruled.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=300.0)
    assert rid not in t.rule_ids


def test_a006_requires_independent_review(ruled):
    app = ruled.open_appeal(challenger=P2, target_rule_id=active_rule_id(ruled),
                            arguments="x", evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    with pytest.raises(ValidationError):
        ruled.appeals.resolve_appeal(app.appeal_id, decision="ACCEPTED",
                                     adjudicator=P2, independent_review=False)


def test_a007_losing_forfeits_winning_refunds(ruled):
    rid = active_rule_id(ruled)
    loser = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="bad",
                              evidence=[{"source": "TEXT"}], bond_usd=25.0)
    ruled.resolve_appeal(loser.appeal_id, decision="REJECTED", adjudicator=J)
    # forfeited bond returns to the pool as income
    entries = ruled.seam.get_reference("pool:ledger")["entries"]
    assert any("appeal-lost" in e["reason"] and e["delta"] == 25.0 for e in entries)


def test_a008_win_amends_doctrine(ruled):
    rid = active_rule_id(ruled)
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="valid appeal",
                            evidence=[{"source": "ATTESTATION", "note": "clean record"}], bond_usd=10.0)
    resolved = ruled.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    d = ruled.doctrine_now()
    assert d.version == 2
    assert resolved.new_rule_id is not None
    assert resolved.new_rule_id != rid


def test_a009_amended_rule_used_next(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    rid = active_rule_id(canon)
    app = canon.open_appeal(challenger=P2, target_rule_id=rid, arguments="too harsh",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version == 2
    assert t.bond_usd < 80.0  # relaxed below the v1 20% bond


def test_a010_superseded_rule_cannot_be_appealed(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    rid = active_rule_id(canon)
    app = canon.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    # the ORIGINAL rule id is gone from the current doctrine -> appealing it fails
    with pytest.raises((AppealError, NotFoundError)):
        canon.open_appeal(challenger=P2, target_rule_id=rid, arguments="again",
                          evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)


def test_a011_frivolous_no_evidence_rejected(ruled):
    with pytest.raises(ValidationError):
        ruled.open_appeal(challenger=P2, target_rule_id=active_rule_id(ruled),
                          arguments="please", evidence=[], bond_usd=10.0)


def test_a012_flood_cap(ruled):
    from canon.types import Doctrine
    from tests.test_doctrine import _rule
    # install a doctrine with four distinct rules so we can open 4 appeals
    doc = Doctrine(version=9, rules=[_rule(rule_id="F1"), _rule(rule_id="F2"),
                                     _rule(rule_id="F3"), _rule(rule_id="F4")])
    ruled.doctrine.persist(doc)
    for rid in ("F1", "F2", "F3"):
        ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments=f"a{rid}",
                          evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    with pytest.raises(AppealError):
        ruled.open_appeal(challenger=P2, target_rule_id="F4", arguments="flood",
                          evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)


def test_a013_evidence_becomes_case_record(ruled):
    app = ruled.open_appeal(challenger=P2, target_rule_id=active_rule_id(ruled),
                            arguments="x", evidence=[{"source": "ATTESTATION", "note": "y"}],
                            bond_usd=10.0)
    assert app.evidence[0]["source"] == "ATTESTATION"


def test_a014_amended_rule_provenance(ruled):
    rid = active_rule_id(ruled)
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    resolved = ruled.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    d = ruled.doctrine_now()
    amended = [r for r in d.rules if r.rule_id == resolved.new_rule_id][0]
    assert amended.amended_by_appeal == app.appeal_id


def test_a015_pre_appeal_version_intact(ruled):
    rid = active_rule_id(ruled)
    v1_before = ruled.doctrine.load_doctrine(1).to_dict()
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    ruled.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    assert ruled.doctrine.load_doctrine(1).to_dict() == v1_before  # archived intact


def test_a018_lost_appeal_no_mutation(ruled):
    rid = active_rule_id(ruled)
    v1 = ruled.doctrine_now().to_dict()
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="bad",
                            evidence=[{"source": "TEXT"}], bond_usd=10.0)
    ruled.resolve_appeal(app.appeal_id, decision="REJECTED", adjudicator=J)
    assert ruled.doctrine_now().to_dict() == v1


def test_a019_restart_mid_appeal_resumes(tmp_path, clock):
    from canon import Canon
    db = tmp_path / "a.db"
    c1 = Canon(db, clock=clock)
    c1.admit(B)
    c1.admit(P)
    prime_doctrine(c1)
    c1.admit(P2)
    rid = active_rule_id(c1)
    app = c1.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                         evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    # fresh session sees the OPEN appeal and can still resolve it
    c2 = Canon(db, clock=clock)
    body = c2.seam.get_entity("appeal", app.appeal_id)
    assert body["state"] == "OPEN"
    resolved = c2.appeals.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    assert resolved.state is AppealState.RESOLVED


def test_a020_appeal_result_queryable(ruled):
    rid = active_rule_id(ruled)
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    ruled.resolve_appeal(app.appeal_id, decision="REJECTED", adjudicator=J)
    body = ruled.seam.get_entity("appeal", app.appeal_id)
    assert body["decision"] == "REJECTED"
    assert body["state"] == "RESOLVED"


@pytest.mark.parametrize("decision", ["ACCEPTED", "REJECTED"])
def test_decision_paths_settle_bond(ruled, decision):
    rid = active_rule_id(ruled)
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=30.0)
    resolved = ruled.resolve_appeal(app.appeal_id, decision=decision, adjudicator=J)
    entries = ruled.seam.get_reference("pool:ledger")["entries"]
    tag = "appeal-won" if decision == "ACCEPTED" else "appeal-lost"
    assert any(tag in e["reason"] and e["delta"] == 30.0 for e in entries)


def test_challenger_cannot_adjudicate(ruled):
    rid = active_rule_id(ruled)
    app = ruled.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    with pytest.raises(ValidationError):
        ruled.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=P2)
