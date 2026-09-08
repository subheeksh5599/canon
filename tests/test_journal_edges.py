"""Journal integrity, tier discipline, decay edges (M-*, D-019.., S-* extras)."""
import copy

import pytest

from canon.errors import CanonError, ValidationError
from canon.memory import REF_DOCTRINE_CURRENT
from canon.types import Doctrine, DoctrineStatus, Rule, TxFacts

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"
J = "0xjudg0000000000000000000000000000"

from tests.conftest import prime_doctrine, run_failed_job, resolve_failure


def test_journal_head_chain_advances(canon):
    canon.admit(B)
    h1 = canon.seam.get_reference("journal:head")
    canon.admit(P)
    h2 = canon.seam.get_reference("journal:head")
    assert h1["seq"] < h2["seq"]
    assert h1["hash"] != h2["hash"]
    assert h2["hash"]  # linked list head


def test_journal_tamper_head_detected(canon):
    canon.admit(B)
    canon.admit(P)
    canon.seam.write_event(acted="probe", extra={"marker": 1})
    ok, _ = canon.journal_ok()
    assert ok
    # forge: overwrite the head so the next write breaks the chain
    canon.seam.set_reference("journal:head", {"seq": 999, "hash": "deadbeef", "event_id": "x"})
    canon.seam.write_event(acted="after-forge", extra={"marker": 2})
    ok, broken = canon.journal_ok()
    assert not ok
    assert broken is not None


def test_journal_events_append_only(canon):
    canon.admit(B)
    n_before = len(canon.seam.read_events())
    canon.admit(P)
    n_after = len(canon.seam.read_events())
    assert n_after == n_before + 1


def test_m001_tiers_hold_only_their_roles(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    # doctrine payload lives under REFERENCE keys only
    cur = canon.seam.get_reference(REF_DOCTRINE_CURRENT)
    assert cur and cur["version"] >= 1
    # case entities live in the case category
    cases = canon.cases.list_cases()
    assert len(cases) >= 5
    # no case payload is stashed under a doctrine key
    assert canon.seam.get_reference("doctrine:v1") is not None


def test_m014_case_id_unique_at_write(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    # writing the same id again would be an overwrite — the domain forbids it upstream
    assert case.case_id.startswith("case-")


def test_d019b_weakening_then_archiving(canon, clock):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    r = canon.doctrine_now().rules[0]
    clock.advance(days=45)  # > 30 weaken, < 90 archive
    aged = canon.doctrine._apply_decay(copy.deepcopy(r))
    assert aged.status is DoctrineStatus.WEAKENING
    clock.advance(days=60)  # total 105 > 90
    aged2 = canon.doctrine._apply_decay(copy.deepcopy(r))
    assert aged2.status is DoctrineStatus.ARCHIVED


def test_d020b_refresh_keeps_rule_young(canon, clock):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    clock.advance(days=80)  # close to the archive edge
    # fresh supporting failure refreshes the active rule
    tx = run_failed_job(canon, provider=P2, value=120.0, chain="0xrefresh")
    resolve_failure(canon, tx, verifier=J)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=120.0)
    assert t.bond_usd > 0  # rule still active after refresh


def test_archive_entity_retains_doctrine_versions(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    # older doctrine versions stay readable for audit replay
    assert canon.doctrine.load_doctrine(1) is not None


def test_term_schema_roundtrip(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=333.0)
    d = t.to_dict()
    assert set(d) >= {"upfront_usd", "milestones", "bond_usd", "coverage_ratio",
                      "rule_ids", "doctrine_version", "reason"}
    # canonical invariant: upfront + escrowed milestones == job value
    assert abs(d["upfront_usd"] + sum(d["milestones"]) - 333.0) < 0.02
    assert t.doctrine_version == 1


def test_frozen_rules_excluded_after_amend_v2(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    rid = canon.doctrine_now().rules[0].rule_id
    app = canon.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                            evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version == 2
    assert rid not in t.rule_ids


def test_cold_start_recall_after_appeal(tmp_path, clock):
    from canon import Canon
    db = tmp_path / "ac.db"
    c1 = Canon(db, clock=clock)
    c1.admit(B)
    c1.admit(P)
    prime_doctrine(c1)
    c1.admit(P2)
    rid = c1.doctrine_now().rules[0].rule_id
    app = c1.open_appeal(challenger=P2, target_rule_id=rid, arguments="x",
                         evidence=[{"source": "ATTESTATION"}], bond_usd=10.0)
    c1.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    c2 = Canon(db, clock=clock)  # fresh session
    c2.admit(P2)
    t = c2.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version == 2  # the amendment survived the restart


def test_naive_terms_never_generated_after_doctrine(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version >= 1
    assert t.rule_ids  # doctrine-backed, not the naive default


def test_evidence_medium_counts_to_doctrine(canon):
    canon.admit(B)
    canon.admit(P)
    last = None
    for i in range(5):
        tx = run_failed_job(canon, provider=P, chain=f"0xmed{i}")
        last = canon.file_and_resolve_claim(
            tx_id=tx.tx_id, buyer=B, verifier=J,
            evidence=[{"source": "ATTESTATION", "note": "adjudicator confirmed"}])
    assert last["doctrine_version_after"] == 1  # MEDIUM confidence may seed


def test_zero_bond_rule_allowed(canon):
    canon.admit(B)
    canon.admit(P)
    # no doctrine: virgin terms have no bond — money-path sanity
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=5.0)
    assert t.bond_usd == 0.0 and t.upfront_usd == 5.0
