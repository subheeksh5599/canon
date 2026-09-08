"""Canon — the facade that wires venue + doctrine + cases + appeals + ledger
over the Sibyl memory seam. This is the public API the scripts and tests drive.
Every high-level action is memory-first: it reads/writes through MemorySeam
and journals each step to the COLD event chain."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .appeals import AppealService
from .cases import CaseService
from .clock import Clock
from .doctrine import DoctrineEngine
from .errors import MemoryUnavailableError, NotFoundError, SettlementError, ValidationError
from .ledger import Ledger
from .memory import MemorySeam, CAT_APPEAL, CAT_CASE, CAT_CLAIM, CAT_COUNTERPARTY
from .types import (
    Appeal,
    Case,
    Claim,
    Doctrine,
    EvidenceConfidence,
    Outcome,
    Terms,
    Transaction,
    TxFacts,
    TxState,
)
from .venue import Venue


class Canon:
    def __init__(self, db_path: str | Path, *, clock: Optional[Clock] = None,
                 tenant_id: str = "canon-venue") -> None:
        self.clock = clock or Clock()
        self._seam = MemorySeam(db_path, clock=self.clock, tenant_id=tenant_id)
        self.venue = Venue(self._seam, clock=self.clock)
        self.doctrine = DoctrineEngine(self._seam, clock=self.clock)
        self.cases = CaseService(self._seam, clock=self.clock)
        self.ledger = Ledger(self._seam, clock=self.clock)
        self.appeals = AppealService(self._seam, self.doctrine, self.ledger, clock=self.clock)

    # ------------------------------------------------------------------ state
    @property
    def seam(self) -> MemorySeam:
        return self._seam

    @property
    def db_path(self) -> Path:
        return self._seam.db_path

    # ------------------------------------------------------------- venue flow
    def admit(self, agent: str) -> Any:
        return self.venue.admit(agent)

    def establish_charter(self, *, rule_id: str = "CANON-001-research",
                          job_class: str = "research",
                          upfront_cap_ratio: float = 0.25,
                          milestone_count_min: int = 3,
                          bond_ratio: float = 0.20,
                          coverage_ratio: float = 0.80) -> Any:
        """Found the venue with ONE declared charter rule — provenance is the
        charter itself (created_by_case='charter', zero fabricated case
        evidence). Every case subsequently recorded is a real executed
        transaction; the charter is amended only by appeals or decay."""
        from .types import Rule, Doctrine
        if self.doctrine.current_doctrine().version > 0:
            return None  # already founded
        rule = Rule(
            rule_id=rule_id,
            job_classes=[job_class],
            require_new_counterparty=False,
            min_supporting_cases=0,
            supporting_case_ids=[],
            created_by_case="charter",  # provenance: declared founding policy, not case evidence
            effective_at=self.clock.iso(),
            upfront_cap_ratio=upfront_cap_ratio,
            milestone_count_min=milestone_count_min,
            bond_ratio=bond_ratio,
            coverage_ratio=coverage_ratio,
        )
        doc = Doctrine(version=1, rules=[rule], effective_at=self.clock.iso(),
                       supersedes=None, activated_by_case="charter")
        self.doctrine.persist(doc)
        self._seam.write_event(acted="venue", evaluated={"version": 1, "rule_id": rule_id},
                               extra={"event": "DOCTRINE_CHARTER", "rule_id": rule_id})
        return doc

    def evaluate(self, *, buyer: str, provider: str, job_type: str,
                 job_value_usd: float) -> Terms:
        """The heart: recall collective precedent -> current doctrine ->
        deterministic terms. No doctrine possible without Sibyl (G-003/G-004)."""
        try:
            _version = self._seam.current_doctrine_version()
        except Exception as exc:
            raise MemoryUnavailableError(f"cannot evaluate without Sibyl: {exc}") from exc
        self.venue.require_active(buyer)
        self.venue.require_active(provider)
        facts = TxFacts(buyer=buyer, provider=provider, job_type=job_type,
                        job_value_usd=job_value_usd)
        cp = self.venue.counterparty(provider)
        terms = self.doctrine.evaluate(facts, cp)
        self._seam.write_event(
            evaluated=facts.to_dict(),
            acted="venue.evaluate",
            forward=terms.to_dict(),
            extra={"event": "TX_EVALUATED", "doctrine_version": terms.doctrine_version,
                   "rule_ids": list(terms.rule_ids)},
        )
        return terms

    def create_tx(self, *, buyer: str, provider: str, job_type: str, job_value_usd: float,
                  terms: Optional[Terms] = None, tx_id: Optional[str] = None,
                  jurisdiction: str = "acp-research") -> Transaction:
        return self.venue.create_transaction(
            buyer=buyer, provider=provider, job_type=job_type,
            job_value_usd=job_value_usd, terms=terms, tx_id=tx_id,
            jurisdiction=jurisdiction,
        )

    def execute(self, tx_id: str, *, chain_ref: str) -> Transaction:
        """Accept terms -> escrow locks on the ledger (Base mirror) -> FUNDED.
        Terms at funding time are immutable for the life of the job (T-016/T-017)."""
        tx = self.venue.require_tx(tx_id)
        if tx.terms is None:
            raise ValidationError("cannot fund a transaction with no terms — evaluate first")
        terms = tx.terms
        upfront = terms.upfront_usd
        bond = terms.bond_usd
        escrow_remaining = terms.total_milestones
        tx = self.venue.mark_termed(tx_id, terms)
        locked = self.ledger.lock_escrow(tx_id=tx_id, total_usd=escrow_remaining, buyer=tx.buyer)
        tx = self.venue.require_tx(tx_id)
        tx.escrow_locked_usd = locked
        self._seam.set_hot(f"tx:{tx_id}", tx.to_dict())
        tx = self.venue.fund(tx_id, chain_ref=chain_ref)
        self._seam.write_event(
            evaluated={"tx_id": tx_id, "upfront": upfront, "bond": bond, "escrow": escrow_remaining},
            acted="tx.execute",
            forward=tx_id,
            extra={"event": "TX_EXECUTE", "chain_ref": chain_ref},
        )
        return tx

    def complete(self, tx_id: str, *, provider: str, outcome: str = "DELIVERED",
                 chain_ref: Optional[str] = None) -> Transaction:
        tx = self.venue.require_tx(tx_id)
        if tx.provider != provider:
            from .errors import StandingError
            raise StandingError("only the provider completes their own job")
        if tx.state is TxState.FUNDED:
            self.venue.begin(tx_id)
        tx = self.venue.complete(tx_id, outcome=outcome, chain_ref=chain_ref)
        if outcome == "DELIVERED":
            self.cases.note_success(provider)
        self._seam.write_event(
            evaluated={"tx_id": tx_id},
            acted="tx.completed",
            forward=tx_id,
            extra={"event": "TX_COMPLETED", "outcome": outcome},
        )
        return tx

    def fail(self, tx_id: str, *, provider: str) -> Transaction:
        tx = self.venue.require_tx(tx_id)
        if tx.provider != provider:
            from .errors import StandingError
            raise StandingError("only the provider on the transaction can mark failure")
        if tx.state is TxState.FUNDED:
            self.venue.begin(tx_id)
        tx = self.venue.fail(tx_id)
        self._seam.write_event(
            evaluated={"tx_id": tx_id},
            acted="tx.failed",
            forward=tx_id,
            extra={"event": "TX_FAILED"},
        )
        return tx

    # ------------------------------------------------------------ claim path
    def file_and_resolve_claim(self, *, tx_id: str, buyer: str, verifier: str,
                               evidence: list[dict[str, Any]]) -> dict[str, Any]:
        """Full claim lifecycle: open -> validate -> resolve -> counterparty
        update -> doctrine signal/activation. Returns the settlement record."""
        tx = self.venue.require_tx(tx_id)
        case = self.cases.open_case(tx, claimant=buyer, evidence=evidence, jurisdiction=tx.jurisdiction)
        loss = tx.job_value_usd
        case = self.cases.resolve_case(
            case.case_id, outcome=Outcome.FAILED, loss_usd=round(loss, 2),
            ruling="provider failed to deliver", verifier=verifier,
        )
        self.cases.record_outcome_on_counterparty(case)
        settlement = self.settle_claim(tx=tx, case=case)
        # doctrine: activate on threshold; otherwise keep the governing rule fresh
        pattern = case.pattern_key
        signal, stats = self.doctrine.signal_level(pattern)
        activated = None
        if signal.value == "ACTIVE":
            activated = self.doctrine.maybe_activate(
                pattern, case.case_id,
                reason=f"{stats['bad_cases']} confirmed failures in {pattern}",
            )
        self._seam.write_event(
            evaluated={"tx_id": tx_id, "case_id": case.case_id, "signal": signal.value,
                       "doctrine": activated.version if activated else None},
            acted="claim.resolved",
            forward=case.case_id,
            extra={"event": "CLAIM_RESOLVED", "signal": signal.value},
        )
        return {"case": case.to_dict(), "settlement": settlement, "signal": signal.value,
                "doctrine_version_after": (activated.version if activated
                                           else self.doctrine.current_doctrine().version)}

    def settle_claim(self, *, tx: Transaction, case: Case) -> dict[str, Any]:
        """Money path of a resolved claim. Compensation order:
        1) remaining milestone escrow refunded to buyer;
        2) provider bond forfeited toward the loss;
        3) pool coverage tops up (coverage_ratio of the residual), only as far
        as pool balance allows — never beyond, never negative (C-002/C-014)."""
        if case.loss_usd <= 0:
            return {"paid": 0.0, "escrow_refund": 0.0, "bond_applied": 0.0, "coverage": 0.0}
        escrow_refund = min(case.loss_usd, tx.terms.total_milestones if tx.terms else 0.0)
        if escrow_refund > 0:
            self.ledger.refund_escrow(tx_id=tx.tx_id, amount_usd=escrow_refund, buyer=tx.buyer)
        residual = max(0.0, case.loss_usd - escrow_refund)
        bond = (tx.terms.bond_usd if tx.terms else 0.0)
        bond_applied = min(residual, bond)
        if bond_applied > 0:
            self.ledger.forfeit_bond(actor=tx.provider, amount_usd=bond_applied,
                                     reason=f"claim:{case.case_id}")
            residual = max(0.0, residual - bond_applied)
        coverage_ratio = tx.terms.coverage_ratio if tx.terms else 0.0
        coverage = min(residual, residual * coverage_ratio,
                       max(0.0, self._seam.pool_balance()))
        if coverage > 0:
            self.ledger.pay_claim(claim_id=case.case_id, amount_usd=coverage, payee=tx.buyer)
        total_paid = round(escrow_refund + bond_applied + coverage, 2)
        claim_id = f"claim-{case.case_id}"
        claim = Claim(claim_id=claim_id, tx_id=tx.tx_id, case_id=case.case_id,
                      claimant=tx.buyer, amount_usd=total_paid, status="RESOLVED",
                      payout_usd=total_paid, resolved_at=self.clock.iso())
        self._seam.set_entity(CAT_CLAIM, claim_id, claim.to_dict(), status="RESOLVED")
        tx = self.venue.require_tx(tx.tx_id)
        self.venue._transition(tx, TxState.CLAIMED)
        return {"paid": total_paid, "escrow_refund": escrow_refund,
                "bond_applied": bond_applied, "coverage": coverage}

    # ---------------------------------------------------------------- appeals
    def open_appeal(self, *, challenger: str, target_rule_id: str, arguments: str,
                    evidence: list[dict[str, Any]], bond_usd: Optional[float] = None) -> Appeal:
        return self.appeals.open_appeal(challenger=challenger, target_rule_id=target_rule_id,
                                        arguments=arguments, evidence=evidence, bond_usd=bond_usd)

    def resolve_appeal(self, appeal_id: str, *, decision: str, adjudicator: str) -> Appeal:
        return self.appeals.resolve_appeal(appeal_id, decision=decision, adjudicator=adjudicator)

    def doctrine_now(self) -> Doctrine:
        return self.doctrine.current_doctrine()

    # ---------------------------------------------------------------- proofs
    def memory_intact(self) -> bool:
        """Gate helper: is authoritative memory present and un-tampered?"""
        try:
            v = self._seam.current_doctrine_version()
            if v and v > 0:
                self._seam.load_doctrine(v)
            ok, _ = self._seam.verify_journal()
            return ok
        except Exception:
            return False

    def provenance(self, tx_id: str) -> list[dict[str, Any]]:
        """Causality trail for a transaction: cases recalled -> doctrine ->
        rule -> terms -> events (T-022/T-035)."""
        trail = []
        for ev in self._seam.read_events(limit=100000):
            extra = ev.get("extra") or {}
            acted = ev.get("acted")
            if isinstance(acted, str) and ("tx_id" in str(ev.get("evaluated")) or tx_id in str(extra) or tx_id in str(ev.get("forward"))):
                trail.append({"ts": ev.get("ts"), "acted": acted, "extra": extra,
                              "hash": extra.get("hash")})
        return trail[-40:]

    def pool_balance(self) -> float:
        return self._seam.pool_balance()

    def journal_ok(self) -> tuple[bool, Optional[str]]:
        return self._seam.verify_journal()
