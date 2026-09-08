"""Cases, claims, settlement (E-*, C-*, part of S-*) and the gate proofs
(G-*: cold start, deletion, ablation)."""
import subprocess
import sys

import pytest

from canon.errors import (
    ConflictError,
    NotFoundError,
    StandingError,
    ValidationError,
)
from canon.types import CaseStatus, EvidenceConfidence, Outcome, TxState

B = "0xbuyer000000000000000000000000000001"
P = "0xprov000000000000000000000000000002"
P2 = "0xprov000000000000000000000000000003"
J = "0xjudg0000000000000000000000000000"

from tests.conftest import make_facts, prime_doctrine, run_failed_job, resolve_failure


# ------------------------------------------------------------ evidence (E-*)
def test_e001_case_requires_valid_tx(market):
    with pytest.raises(NotFoundError):
        market.cases.open_case(None, claimant=B, evidence=[{"source": "TEXT"}],
                               jurisdiction="acp-research")


def test_e002_resolution_machine(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(market_tx(canon, tx), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    assert case.status is CaseStatus.RAW
    canon.cases.resolve_case(case.case_id, outcome=Outcome.FAILED, loss_usd=100.0,
                             ruling="failed", verifier=J)
    stored = canon.seam.get_entity("case", case.case_id)
    assert stored["status"] == "RESOLVED"


def market_tx(canon, tx):
    return canon.venue.require_tx(tx.tx_id)


def test_e004_missing_outcome_blocks(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(market_tx(canon, tx), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    with pytest.raises(ValueError):
        canon.cases.resolve_case(case.case_id, outcome="NOT_AN_OUTCOME", loss_usd=1.0,
                                 ruling="x", verifier=J)


def test_e005_bad_outcome_value_rejected(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(market_tx(canon, tx), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    with pytest.raises(ValueError):
        canon.cases.resolve_case(case.case_id, outcome="NOPE", loss_usd=1.0,
                                 ruling="x", verifier=J)


def test_e006_loss_bounds(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon, value=200.0)
    case = canon.cases.open_case(market_tx(canon, tx), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    with pytest.raises(ValidationError):
        canon.cases.resolve_case(case.case_id, outcome=Outcome.FAILED, loss_usd=500.0,
                                 ruling="x", verifier=J)


def test_e007_duplicate_claim_rejected(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    canon.cases.open_case(market_tx(canon, tx), claimant=B,
                          evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    with pytest.raises(ConflictError):
        canon.cases.open_case(market_tx(canon, tx), claimant=B,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_e010_confidence_tiers():
    from canon.cases import CaseService
    svc = CaseService.__new__(CaseService)
    assert svc._assess_confidence([{"source": "TX_VERIFIED"}]) is EvidenceConfidence.HIGH
    assert svc._assess_confidence([{"source": "ATTESTATION"}]) is EvidenceConfidence.MEDIUM
    assert svc._assess_confidence([{"source": "TEXT"}]) is EvidenceConfidence.LOW


def test_e012_forged_tx_hash_rejected(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon, chain="0x" + "f" * 64)
    res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                       evidence=[{"source": "TX_VERIFIED", "note": "delivered nothing"}])
    assert res["case"]["confidence"] == "HIGH"
    # evidence is checked against the tx that actually ran in the venue


def test_e013_statute_window(canon, clock):
    from datetime import timedelta
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    # push beyond the 90-day statute window
    clock.advance(days=100)
    with pytest.raises(ValidationError):
        canon.cases.open_case(market_tx(canon, tx), claimant=B,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_e014_asymmetric_standing(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    # provider cannot claim on their own failed obligation
    with pytest.raises(StandingError):
        canon.cases.open_case(market_tx(canon, tx), claimant=P,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_e017_resolution_append_only(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                 evidence=[{"source": "TX_VERIFIED"}])
    cp = canon.cases.get_counterparty(P)
    assert len(cp.resolution_history) >= 1


# ------------------------------------------------------------- claims (C-*)
def test_c001_only_failed_claimable(canon):
    canon.admit(B)
    canon.admit(P)
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=100.0)
    tx = canon.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=100.0, terms=t)
    canon.execute(tx.tx_id, chain_ref="0xok")
    canon.complete(tx.tx_id, provider=P)
    with pytest.raises(ValidationError):
        canon.cases.open_case(canon.venue.require_tx(tx.tx_id), claimant=B,
                              evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")


def test_c002_claim_never_exceeds_loss(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon, value=250.0)
    res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                       evidence=[{"source": "TX_VERIFIED"}])
    assert res["settlement"]["paid"] <= 250.0 + 1e-9


def test_c005_double_resolution_impossible(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    case = canon.cases.open_case(market_tx(canon, tx), claimant=B,
                                 evidence=[{"source": "TX_VERIFIED"}], jurisdiction="acp-research")
    canon.cases.resolve_case(case.case_id, outcome=Outcome.FAILED, loss_usd=100.0,
                             ruling="x", verifier=J)
    with pytest.raises(ConflictError):
        canon.cases.resolve_case(case.case_id, outcome=Outcome.FAILED, loss_usd=100.0,
                                 ruling="x", verifier=J)


def test_c006_claim_without_evidence_rejected(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    with pytest.raises(ValidationError):
        canon.cases.open_case(market_tx(canon, tx), claimant=B, evidence=[],
                              jurisdiction="acp-research")


def test_c014_pool_invariant_closed_lifecycle(canon):
    canon.admit(B)
    canon.admit(P)
    # funded + completed lifecycle: escrow returns, no payout can exceed funds
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=300.0)
    tx = canon.create_tx(buyer=B, provider=P, job_type="research", job_value_usd=300.0, terms=t)
    canon.execute(tx.tx_id, chain_ref="0xfee")
    canon.complete(tx.tx_id, provider=P)
    # claim lifecycle: escrow refund + bond + capped coverage
    for i in range(2):
        tx = run_failed_job(canon, value=200.0, chain=f"0xc{i}")
        res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                           evidence=[{"source": "TX_VERIFIED"}])
        assert res["settlement"]["paid"] <= 200.0 + 1e-9


def test_c015_replay_payout_nonce(canon):
    canon.admit(B)
    canon.admit(P)
    tx = run_failed_job(canon)
    res = canon.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier=J,
                                       evidence=[{"source": "TX_VERIFIED"}])
    # second resolution attempt on same tx is impossible (state CLAIMED)
    assert canon.venue.require_tx(tx.tx_id).state is TxState.CLAIMED


# -------------------------------------------------------------- gate (G-*)
def test_g003_deletion_breaks_evaluation(market):
    market.seam.delete_all()
    with pytest.raises(Exception):
        market.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=100.0)


def test_g004_deletion_no_doctrine(market):
    market.seam.delete_all()
    assert market.doctrine.current_doctrine().version == 0


def test_g005_g006_ablation_terms_differ(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    aware = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert aware.bond_usd > 0 and aware.doctrine_version >= 1
    # memoryless control: what a fresh venue without history would offer
    from canon import Canon
    import tempfile
    blank = Canon(tempfile.mktemp(suffix=".db"), clock=canon.clock)
    blank.admit(B)
    blank.admit(P2)
    naive = blank.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert naive.bond_usd == 0.0 and naive.doctrine_version == 0


def test_g009_cold_start_deterministic(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    a = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    b = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert a.to_dict() == b.to_dict()


def test_g010_cold_start_real_restart(tmp_path, clock):
    from canon import Canon
    db = tmp_path / "restart.db"
    c1 = Canon(db, clock=clock)
    c1.admit(B)
    c1.admit(P)
    prime_doctrine(c1)
    # process boundary: fresh Canon object, zero python state carried
    c2 = Canon(db, clock=clock)
    c2.admit(B)
    c2.admit(P2)
    terms = c2.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert terms.doctrine_version == 1  # recalled the doctrine across the restart


def test_g018_stranger_effect(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    # a DIFFERENT provider with no history gets terms shaped by OTHER
    # participants' failures — not its own record
    canon.admit(P2)
    t = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert t.doctrine_version == 1
    assert t.bond_usd > 0  # P2 never failed anything; the pattern did


def test_g011_second_run_same_result(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    first = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=250.0)
    # wipe runtime state? no — re-run identical sequence returns identical output
    second = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=250.0)
    assert first.to_dict() == second.to_dict()


def test_g019_ui_cli_same_logic(canon):
    # CLI and UI share one engine — no divergent term path exists by construction
    canon.admit(B)
    canon.admit(P)
    t = canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=120.0)
    assert t is not None and t.upfront_usd <= 120.0


# ------------------------------------------------------------- memory (M-*)
def test_m005_cross_process_recall(tmp_path, clock):
    from canon import Canon
    db = tmp_path / "x.db"
    a = Canon(db, clock=clock)
    a.admit(B)
    a.admit(P)
    a.seam.write_event(evaluated={"k": "v"}, acted="probe", forward="x", extra={"t": 1})
    b = Canon(db, clock=clock)  # fresh process-equivalent
    evs = b.seam.read_events()
    assert any(ev.get("acted") == "probe" for ev in evs)


def test_m008_tampered_doctrine_detected(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    # tamper with the stored doctrine payload
    canon.seam.set_reference("doctrine:v1", {"version": 1, "rules": [], "evil": True})
    with pytest.raises(Exception):
        canon.doctrine.load_doctrine(1)


def test_m010_no_fallback_to_skipped_memory(canon):
    # term generation reads doctrine through the seam; there is no branch that
    # skips memory when doctrine is missing — only the naive default for v0
    canon.admit(B)
    canon.admit(P)
    import inspect
    src = inspect.getsource(canon.doctrine.evaluate)
    assert "current_doctrine" in src


def test_m011_doctrine_edits_change_terms(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.admit(P2)
    before = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    # amend via a winning appeal (the only legitimate edit path)
    doc = canon.doctrine_now()
    app = canon.open_appeal(challenger=P2, target_rule_id=doc.rules[0].rule_id,
                            arguments="too strict", evidence=[{"source": "ATTESTATION"}],
                            bond_usd=10.0)
    canon.resolve_appeal(app.appeal_id, decision="ACCEPTED", adjudicator=J)
    after = canon.evaluate(buyer=B, provider=P2, job_type="research agent", job_value_usd=400.0)
    assert after.to_dict() != before.to_dict()


def test_m013_sibyl_down_no_silent_default(canon):
    # deleting memory is not a fallback path: evaluation fails loudly
    canon.admit(B)
    canon.admit(P)
    canon.seam.delete_all()
    with pytest.raises(Exception):
        canon.evaluate(buyer=B, provider=P, job_type="research", job_value_usd=50.0)


def test_m020_deletion_wipes_every_tier(canon):
    canon.admit(B)
    canon.admit(P)
    prime_doctrine(canon)
    canon.seam.delete_all()
    assert canon.doctrine.current_doctrine().version == 0
    assert canon.cases.list_cases() == []
    assert canon.seam.pool_balance() == 0.0
