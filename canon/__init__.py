"""CANON — the exchange where agents transact under terms the economy itself writes.

Autonomous agents transact inside the CANON venue. Every deal's terms are
generated deterministically from collective precedent stored in Sibyl Memory:
cases (COLD/WARM) -> doctrine (REFERENCE) -> executable terms -> Base.

Delete Sibyl and CANON loses the historical evidence and active doctrine
required to construct authoritative transaction terms.
"""

from .errors import (
    CanonError,
    ConflictError,
    NotFoundError,
    ValidationError,
    StandingError,
    UnauthorizedVenueError,
    AppealError,
    SettlementError,
    MemoryUnavailableError,
    RuleConflictError,
)
from .types import (
    Outcome,
    CaseStatus,
    EvidenceConfidence,
    DoctrineStatus,
    TxState,
    AppealState,
    Jurisdiction,
    Rule,
    Doctrine,
    Terms,
    Case,
    Counterparty,
    Transaction,
    Claim,
    Appeal,
    VenueAdmission,
    TxFacts,
)
from .clock import Clock, utc_now
from .engine import Canon

__all__ = [
    "Canon",
    "CanonError",
    "ConflictError",
    "NotFoundError",
    "ValidationError",
    "StandingError",
    "UnauthorizedVenueError",
    "AppealError",
    "SettlementError",
    "MemoryUnavailableError",
    "RuleConflictError",
    "Outcome",
    "CaseStatus",
    "EvidenceConfidence",
    "DoctrineStatus",
    "TxState",
    "AppealState",
    "Jurisdiction",
    "Rule",
    "Doctrine",
    "Terms",
    "Case",
    "Counterparty",
    "Transaction",
    "Claim",
    "Appeal",
    "VenueAdmission",
    "TxFacts",
    "Clock",
    "utc_now",
]
