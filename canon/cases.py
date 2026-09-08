"""Case lifecycle — only RESOLVED cases with verifiable evidence may seed
doctrine. Evidence confidence: on-chain tx verification HIGH, signed
attestation MEDIUM, uncorroborated text LOW (never sufficient alone)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from .clock import Clock
from .errors import ConflictError, NotFoundError, StandingError, ValidationError
from .memory import CAT_CASE, CAT_COUNTERPARTY, CAT_TX, MemorySeam
from .types import (
    Case,
    CaseStatus,
    Claim,
    Counterparty,
    EvidenceConfidence,
    Outcome,
    TxFacts,
    TxState,
    _normalize_job_type,
)


class CaseService:
    def __init__(self, seam: MemorySeam, *, clock: Optional[Clock] = None) -> None:
        self._seam = seam
        self.clock = clock or Clock()
        self.statute_days = 90  # S-021/E-013: claims after the window are rejected

    # ------------------------------------------------------------- ingestion
    def open_case(self, tx, claimant: str, *, evidence: list[dict[str, Any]],
                  jurisdiction: str) -> Case:
        """Buyer on a FAILED/FRAUD transaction opens a case (standing C-010)."""
        if tx is None:
            raise NotFoundError("transaction not found")
        if tx.buyer != claimant:
            raise StandingError("only the buyer on the transaction can file a claim")
        if tx.outcome not in (Outcome.FAILED, Outcome.FRAUD):
            raise ValidationError("only FAILED or FRAUD transactions can be claimed")
        # statute window (E-013)
        if tx.completed_at:
            from datetime import datetime
            done = datetime.fromisoformat(tx.completed_at)
            if (self.clock.now() - done) > timedelta(days=self.statute_days):
                raise ValidationError("claim filed outside the statute window")
        existing = self._seam.list_entities(CAT_CASE, limit=100000)
        for c in existing:
            if c.get("tx_id") == tx.tx_id and c.get("status") != "RESOLVED":
                raise ConflictError(f"an open case already exists for tx {tx.tx_id}")
        conf = self._assess_confidence(evidence)
        case_id = f"case-{tx.tx_id}"
        case = Case(
            case_id=case_id,
            tx_id=tx.tx_id,
            buyer=tx.buyer,
            provider=tx.provider,
            job_type=tx.job_type,
            job_value_usd=tx.job_value_usd,
            contract_terms=tx.terms.to_dict() if tx.terms else {},
            evidence=evidence,
            status=CaseStatus.RAW,
            confidence=conf,
            pattern_key=_normalize_job_type(tx.job_type),
            created_at=self.clock.iso(),
        )
        self._seam.set_entity(CAT_CASE, case_id, case.to_dict(), status=CaseStatus.RAW.value)
        self._seam.write_event(
            evaluated={"tx_id": tx.tx_id, "claimant": claimant},
            acted="case.open",
            forward=case_id,
            extra={"event": "CASE_OPEN", "confidence": conf.value},
        )
        return case

    def _assess_confidence(self, evidence: list[dict[str, Any]]) -> EvidenceConfidence:
        if not evidence:
            raise ValidationError("claim without evidence cannot resolve (C-006)")
        best = EvidenceConfidence.LOW
        for ev in evidence:
            src = str(ev.get("source", "")).upper()
            if src == "TX_VERIFIED":
                best = EvidenceConfidence.HIGH
            elif src == "ATTESTATION" and best is not EvidenceConfidence.HIGH:
                best = EvidenceConfidence.MEDIUM
        return best

    def resolve_case(self, case_id: str, *, outcome: Outcome, loss_usd: float,
                     ruling: str, verifier: str) -> Case:
        """Adjudicator resolves the case; only resolved evidence can become
        precedent (E-002/E-003/E-018)."""
        body = self._seam.get_entity(CAT_CASE, case_id)
        if body is None:
            raise NotFoundError(f"case {case_id} not found")
        case = self._case_from(body)
        if case.status is CaseStatus.RESOLVED:
            raise ConflictError(f"case {case_id} already resolved (C-005 double-resolution)")
        outcome = Outcome(outcome)  # ValueError on unknown outcome (E-004/E-005)
        if loss_usd < 0 or loss_usd > case.job_value_usd:
            raise ValidationError("loss outside [0, job value]")
        if verifier == case.buyer or verifier == case.provider:
            raise ValidationError("adjudicator cannot be a party to the case (S-019 role conflict)")
        case.status = CaseStatus.RESOLVED
        case.outcome = outcome
        case.loss_usd = round(loss_usd, 2)
        case.ruling = ruling
        case.resolved_at = self.clock.iso()
        if case.confidence is EvidenceConfidence.LOW and outcome in (Outcome.FAILED, Outcome.FRAUD):
            # LOW confidence can resolve a case but can never seed doctrine
            case.precedent_id = None
        else:
            case.precedent_id = f"P-{case_id}"
        self._seam.set_entity(CAT_CASE, case_id, case.to_dict(), status=CaseStatus.RESOLVED.value)
        self._seam.write_event(
            evaluated={"case_id": case_id, "outcome": outcome.value, "loss": loss_usd},
            acted="case.resolve",
            forward=case.precedent_id,
            extra={"event": "CASE_RESOLVED", "confidence": case.confidence.value},
        )
        return case

    def record_outcome_on_counterparty(self, case: Case) -> Counterparty:
        """Update the provider's WARM file (E-016/E-017 append-only history)."""
        name = f"cp:{case.provider}"
        body = self._seam.get_entity(CAT_COUNTERPARTY, name) or {}
        cp = Counterparty(
            provider=case.provider,
            jurisdiction="acp-research",
            completed_jobs=int(body.get("completed_jobs", 0)),
            failed_jobs=int(body.get("failed_jobs", 0)),
            partial_jobs=int(body.get("partial_jobs", 0)),
            claim_count=int(body.get("claim_count", 0)),
            disputed_jobs=int(body.get("disputed_jobs", 0)),
            clean_jobs_since_failure=int(body.get("clean_jobs_since_failure", 0)),
            resolution_history=list(body.get("resolution_history", [])),
            first_seen_at=body.get("first_seen_at") or self.clock.iso(),
        )
        if case.outcome is Outcome.FAILED or case.outcome is Outcome.FRAUD:
            cp.failed_jobs += 1
            cp.clean_jobs_since_failure = 0
        elif case.outcome is Outcome.PARTIAL:
            cp.partial_jobs += 1
        elif case.outcome is Outcome.DELIVERED:
            cp.completed_jobs += 1
            cp.clean_jobs_since_failure += 1
        cp.claim_count += 1
        cp.resolution_history.append(case.case_id)
        self._seam.set_entity(CAT_COUNTERPARTY, name, cp.to_dict())
        return cp

    def get_counterparty(self, provider: str) -> Optional[Counterparty]:
        body = self._seam.get_entity(CAT_COUNTERPARTY, f"cp:{provider}")
        if body is None:
            return None
        clean = {k: v for k, v in body.items() if k not in ("name", "_entity_status")}
        return Counterparty(**clean)

    def note_success(self, provider: str) -> Counterparty:
        cp = self.get_counterparty(provider) or Counterparty(provider=provider, jurisdiction="acp-research")
        cp.completed_jobs += 1
        cp.clean_jobs_since_failure += 1
        self._seam.set_entity(CAT_COUNTERPARTY, f"cp:{provider}", cp.to_dict())
        return cp

    def list_cases(self, *, resolved_only: bool = False) -> list[dict[str, Any]]:
        cases = self._seam.list_entities(CAT_CASE, limit=100000)
        if resolved_only:
            cases = [c for c in cases if c.get("status") == "RESOLVED"]
        return cases

    def _case_from(self, body: dict[str, Any]) -> Case:
        return Case(
            case_id=body["case_id"], tx_id=body["tx_id"],
            buyer=body["buyer"], provider=body["provider"],
            job_type=body["job_type"], job_value_usd=float(body["job_value_usd"]),
            contract_terms=body.get("contract_terms", {}),
            evidence=body.get("evidence", []),
            status=CaseStatus(body.get("status", "RAW")),
            outcome=Outcome(body["outcome"]) if body.get("outcome") else None,
            loss_usd=float(body.get("loss_usd", 0.0)),
            ruling=body.get("ruling"),
            confidence=EvidenceConfidence(body.get("confidence", "LOW")),
            precedent_id=body.get("precedent_id"),
            pattern_key=body.get("pattern_key", ""),
            created_at=body.get("created_at", ""),
            resolved_at=body.get("resolved_at"),
        )
