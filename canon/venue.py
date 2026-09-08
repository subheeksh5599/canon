"""Venue — jurisdiction is contractual. Agents transact INSIDE CANON because
CANON is where matching, terms, escrow, and dispute resolution live. A direct
Base transfer outside the venue carries none of CANON's guarantees (V-005/V-006)."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from .clock import Clock
from .errors import (
    ConflictError,
    NotFoundError,
    StandingError,
    UnauthorizedVenueError,
    ValidationError,
)
from .memory import CAT_AGENT, CAT_COUNTERPARTY, CAT_TX, MemorySeam
from .types import Jurisdiction, Outcome, Transaction, TxState, VenueAdmission, ZERO_ADDR

VENUE_RULES_VERSION = 1


class Venue:
    def __init__(self, seam: MemorySeam, *, clock: Optional[Clock] = None) -> None:
        self._seam = seam
        self.clock = clock or Clock()

    # ------------------------------------------------------------- admission
    def admit(self, agent: str, jurisdiction: str = Jurisdiction.ACP_RESEARCH.value) -> VenueAdmission:
        Jurisdiction.validate(jurisdiction)
        if not agent or len(agent) < 6:
            raise ValidationError("agent identity required (wallet or agent id)")
        existing = self._seam.get_entity(CAT_AGENT, f"agent:{agent}")
        if existing and existing.get("status") == "ACTIVE":
            clean = {k: v for k, v in existing.items() if k not in ("name", "_entity_status")}
            return VenueAdmission(**clean)
        admission = VenueAdmission(
            agent=agent,
            jurisdiction=jurisdiction,
            rules_version=VENUE_RULES_VERSION,
            admitted_at=self.clock.iso(),
            status="ACTIVE",
        )
        self._seam.set_entity(CAT_AGENT, f"agent:{agent}", admission.to_dict(), status="ACTIVE")
        self._seam.write_event(
            evaluated={"agent": agent},
            acted="venue.admit",
            forward=agent,
            extra={"event": "VENUE_ADMIT", "rules_version": VENUE_RULES_VERSION},
        )
        return admission

    def _require_active(self, agent: str) -> None:
        rec = self._seam.get_entity(CAT_AGENT, f"agent:{agent}")
        if rec is None:
            raise UnauthorizedVenueError(
                f"{agent} has not accepted CANON venue rules — direct transfers are outside the venue"
            )
        if rec.get("status") != "ACTIVE":
            raise UnauthorizedVenueError(f"{agent} is suspended from the venue")

    def require_active(self, agent: str) -> None:
        """Public admission gate — used by the evaluation path: agents only
        transact under CANON terms inside the venue."""
        self._require_active(agent)

    def suspend(self, agent: str, reason: str = "adjudicated") -> None:
        rec = self._seam.get_entity(CAT_AGENT, f"agent:{agent}")
        if rec is None:
            raise NotFoundError(f"no admission for {agent}")
        rec["status"] = "SUSPENDED"
        self._seam.set_entity(CAT_AGENT, f"agent:{agent}", rec, status="SUSPENDED")
        self._seam.write_event(
            evaluated={"agent": agent, "reason": reason},
            acted="venue.suspend",
            forward=agent,
            extra={"event": "VENUE_SUSPEND"},
        )

    def admission(self, agent: str) -> Optional[VenueAdmission]:
        rec = self._seam.get_entity(CAT_AGENT, f"agent:{agent}")
        if rec is None:
            return None
        clean = {k: v for k, v in rec.items() if k not in ("name", "_entity_status")}
        return VenueAdmission(**clean)

    # ---------------------------------------------------------- transactions
    def create_transaction(self, *, buyer: str, provider: str, job_type: str,
                           job_value_usd: float, jurisdiction: str = Jurisdiction.ACP_RESEARCH.value,
                           terms=None, tx_id: Optional[str] = None) -> Transaction:
        self._require_active(buyer)
        self._require_active(provider)
        Jurisdiction.validate(jurisdiction)
        if not job_type or not job_type.strip():
            raise ValidationError("job type required")
        if job_value_usd <= 0:
            raise ValidationError("job value must be positive")
        if buyer == provider:
            raise ValidationError("buyer and provider cannot be the same agent")
        tx = Transaction(
            tx_id=tx_id or f"tx-{uuid.uuid4().hex[:12]}",
            buyer=buyer, provider=provider,
            job_type=job_type, job_value_usd=float(job_value_usd),
            jurisdiction=jurisdiction, state=TxState.PROPOSED,
            created_at=self.clock.iso(),
        )
        if terms is not None:
            tx.terms = terms
            tx.state = TxState.TERMED
        self._seam.set_hot(f"tx:{tx.tx_id}", tx.to_dict())
        self._seam.write_event(
            evaluated={"tx_id": tx.tx_id, "buyer": buyer, "provider": provider,
                       "job_type": job_type, "value": job_value_usd},
            acted="tx.create",
            forward=tx.tx_id,
            extra={"event": "TX_CREATE"},
        )
        return tx

    def get_tx(self, tx_id: str) -> Optional[Transaction]:
        hot = self._seam.get_hot(f"tx:{tx_id}")
        if hot is not None:
            return self._tx_from(hot)
        cold = self._seam.get_entity(CAT_TX, tx_id)
        if cold is not None:
            return self._tx_from(cold)
        return None

    def _tx_from(self, body: dict[str, Any]) -> Transaction:
        t = Transaction(
            tx_id=body["tx_id"], buyer=body["buyer"], provider=body["provider"],
            job_type=body["job_type"], job_value_usd=float(body["job_value_usd"]),
            jurisdiction=body["jurisdiction"],
            state=TxState(body.get("state", "PROPOSED")),
            created_at=body.get("created_at", ""),
            funded_at=body.get("funded_at"),
            completed_at=body.get("completed_at"),
            outcome=body.get("outcome"),
            escrow_locked_usd=float(body.get("escrow_locked_usd", 0.0)),
            chain_ref=body.get("chain_ref"),
        )
        terms = body.get("terms")
        if terms:
            from .types import Terms
            t.terms = Terms(
                upfront_usd=float(terms["upfront_usd"]),
                milestones=tuple(float(m) for m in terms["milestones"]),
                bond_usd=float(terms["bond_usd"]),
                coverage_ratio=float(terms["coverage_ratio"]),
                rule_ids=tuple(terms["rule_ids"]),
                doctrine_version=int(terms["doctrine_version"]),
                reason=terms["reason"],
            )
        return t

    def _save(self, tx: Transaction) -> None:
        self._seam.set_hot(f"tx:{tx.tx_id}", tx.to_dict())

    def _transition(self, tx: Transaction, to: TxState) -> None:
        legal = self._legal_transitions(tx.state, to)
        if not legal:
            raise ConflictError(f"illegal transition {tx.state.value} -> {to.value}")
        tx.state = to
        self._save(tx)

    @staticmethod
    def _legal_transitions(fr: TxState, to: TxState) -> bool:
        legal = {
            TxState.PROPOSED: {TxState.TERMED, TxState.CANCELLED},
            TxState.TERMED: {TxState.FUNDED, TxState.CANCELLED},
            TxState.FUNDED: {TxState.IN_PROGRESS, TxState.CANCELLED},
            TxState.IN_PROGRESS: {TxState.COMPLETED, TxState.FAILED, TxState.DISPUTED},
            TxState.COMPLETED: set(),
            TxState.FAILED: {TxState.CLAIMED},
            TxState.DISPUTED: {TxState.COMPLETED, TxState.FAILED},
            TxState.CLAIMED: set(),
            TxState.CANCELLED: set(),
        }
        return to in legal.get(fr, set())

    def mark_termed(self, tx_id: str, terms) -> Transaction:
        tx = self.require_tx(tx_id)
        if tx.state is TxState.TERMED and tx.terms == terms:
            return tx  # idempotent — same terms re-marked is a no-op
        if tx.state is not TxState.PROPOSED:
            raise ConflictError("transaction already termed with different terms")
        tx.terms = terms
        self._transition(tx, TxState.TERMED)
        return tx

    def fund(self, tx_id: str, *, chain_ref: str) -> Transaction:
        tx = self.require_tx(tx_id)
        if tx.terms is None:
            raise ValidationError("no terms — evaluate before funding")
        if not chain_ref or chain_ref == ZERO_ADDR:
            raise ValidationError("funding requires a real Base transaction reference")
        if tx.escrow_locked_usd == 0.0:
            raise ValidationError("escrow must be locked before funding")
        tx.chain_ref = chain_ref
        tx.funded_at = self.clock.iso()
        self._transition(tx, TxState.FUNDED)
        self._seam.write_event(
            evaluated={"tx_id": tx_id, "chain_ref": chain_ref},
            acted="tx.fund",
            forward=tx_id,
            extra={"event": "TX_FUNDED"},
        )
        return tx

    def begin(self, tx_id: str) -> Transaction:
        tx = self.require_tx(tx_id)
        self._transition(tx, TxState.IN_PROGRESS)
        return tx

    def complete(self, tx_id: str, *, outcome="DELIVERED", chain_ref: Optional[str] = None) -> Transaction:
        tx = self.require_tx(tx_id)
        if outcome not in ("DELIVERED", "PARTIAL"):
            raise ValidationError("complete() is only for delivered work")
        tx.outcome = Outcome(outcome)
        tx.completed_at = self.clock.iso()
        if chain_ref:
            tx.chain_ref = chain_ref
        self._transition(tx, TxState.COMPLETED)
        self._seam.write_event(
            evaluated={"tx_id": tx_id, "outcome": outcome},
            acted="tx.complete",
            forward=tx_id,
            extra={"event": "TX_COMPLETED"},
        )
        return tx

    def fail(self, tx_id: str) -> Transaction:
        tx = self.require_tx(tx_id)
        tx.outcome = Outcome.FAILED
        tx.completed_at = self.clock.iso()
        self._transition(tx, TxState.FAILED)
        self._seam.write_event(
            evaluated={"tx_id": tx_id},
            acted="tx.fail",
            forward=tx_id,
            extra={"event": "TX_FAILED"},
        )
        return tx

    def require_tx(self, tx_id: str) -> Transaction:
        tx = self.get_tx(tx_id)
        if tx is None:
            raise NotFoundError(f"transaction {tx_id} not found")
        return tx

    def list_hot_txs(self) -> list[dict[str, Any]]:
        out = []
        for body in self._seam.list_entities(CAT_AGENT, limit=1):  # placeholder to keep seam warm
            pass
        # HOT tier has no list API on the client; track via COLD events instead
        return out

    def counterparty(self, provider: str):
        body = self._seam.get_entity(CAT_COUNTERPARTY, f"cp:{provider}")
        if body is None:
            return None
        from .types import Counterparty
        clean = {k: v for k, v in body.items() if k not in ("name", "_entity_status")}
        return Counterparty(**clean)
