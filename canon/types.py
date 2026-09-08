"""CANON core types — schemas as plain dataclasses with strict validation.

Single source of truth lives at the schema level (Sibyl's own thesis):
records are validated on write and re-validated on read.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .errors import ValidationError, RuleConflictError

ZERO_ADDR = "0x0000000000000000000000000000000000000000"


class Outcome(str, Enum):
    DELIVERED = "DELIVERED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    FRAUD = "FRAUD"
    DISPUTED = "DISPUTED"

    @property
    def is_bad(self) -> bool:
        return self in (Outcome.FAILED, Outcome.FRAUD)

    @property
    def is_partial(self) -> bool:
        return self is Outcome.PARTIAL


class CaseStatus(str, Enum):
    RAW = "RAW"
    VALIDATED = "VALIDATED"
    RESOLVED = "RESOLVED"


class EvidenceConfidence(str, Enum):
    HIGH = "HIGH"      # verified on-chain transaction hash
    MEDIUM = "MEDIUM"  # signed attestation / adjudicator record
    LOW = "LOW"        # uncorroborated text — never alone seeds doctrine


class DoctrineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WEAKENING = "WEAKENING"
    CONTESTED = "CONTESTED"     # frozen while an appeal is open
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class TxState(str, Enum):
    PROPOSED = "PROPOSED"
    TERMED = "TERMED"
    FUNDED = "FUNDED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CLAIMED = "CLAIMED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


class AppealState(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class Jurisdiction(str, Enum):
    ACP_RESEARCH = "acp-research"   # the one vertical CANON ships

    @classmethod
    def validate(cls, value: str) -> "Jurisdiction":
        try:
            return cls(value)
        except ValueError:
            raise ValidationError(f"unknown jurisdiction: {value!r} (only {[j.value for j in cls]} is open)")


class Signal(str, Enum):
    NONE = "NONE"
    SIGNAL = "SIGNAL"        # 1 confirmed case
    MONITOR = "MONITOR"      # 2 confirmed cases
    CANDIDATE = "CANDIDATE"  # 3 confirmed cases -> candidate rule proposed
    ACTIVE = "ACTIVE"        # 5+ confirmed cases -> doctrine update activates


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(payload: Any) -> str:
    """Deterministic canonical hash over a JSON payload."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _json_default(o: Any) -> Any:
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "to_dict"):
        return o.to_dict()
    return str(o)


@dataclass(frozen=True)
class TxFacts:
    """Normalized facts about a proposed transaction — the only input the
    doctrine matcher may see. The LLM never touches the money path."""
    buyer: str
    provider: str
    job_type: str
    job_value_usd: float
    jurisdiction: str = Jurisdiction.ACP_RESEARCH.value

    def __post_init__(self) -> None:
        Jurisdiction.validate(self.jurisdiction)
        if not self.buyer or not self.provider:
            raise ValidationError("buyer and provider are required")
        if self.buyer == self.provider:
            raise ValidationError("buyer and provider cannot be the same agent")
        if self.job_value_usd <= 0:
            raise ValidationError("job value must be positive")
        if not self.job_type or not self.job_type.strip():
            raise ValidationError("job type is required")

    @property
    def pattern_key(self) -> str:
        """Normalized failure pattern signature for this job class."""
        return _normalize_job_type(self.job_type)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_job_type(job_type: str) -> str:
    t = job_type.strip().lower()
    # synonym map: one canonical pattern vocabulary
    synonyms = {
        "research": "research",
        "research agent": "research",
        "research-agent": "research",
        "data analysis": "analysis",
        "analysis": "analysis",
        "code": "code",
        "coding": "code",
        "software": "code",
        "writing": "writing",
        "content": "writing",
        "token audit": "audit",
        "audit": "audit",
    }
    return synonyms.get(t, t.replace(" ", "-")[:40])


@dataclass
class Rule:
    """One doctrine rule: triggers -> deterministic term modifiers."""
    rule_id: str
    status: DoctrineStatus = DoctrineStatus.ACTIVE
    created_by_case: Optional[str] = None
    effective_at: str = field(default_factory=_now_iso)
    supersedes: Optional[str] = None
    amended_by_appeal: Optional[str] = None
    # triggers
    job_classes: Optional[list[str]] = None       # None = any class
    min_job_value_usd: float = 0.0
    require_new_counterparty: bool = False
    require_failure_rate_ge: Optional[float] = None   # 0..1 pattern failure rate
    min_supporting_cases: int = 0
    # term modifiers
    upfront_cap_ratio: float = 1.0     # fraction of job value payable upfront
    milestone_count_min: int = 1
    bond_ratio: float = 0.0            # fraction of job value held as bond
    coverage_ratio: float = 0.0        # fraction of loss covered by pool
    # evidence provenance
    supporting_case_ids: list[str] = field(default_factory=list)
    evidence_confidence: EvidenceConfidence = EvidenceConfidence.HIGH
    last_supported_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValidationError("rule_id required")
        if not (0.0 <= self.upfront_cap_ratio <= 1.0):
            raise ValidationError("upfront_cap_ratio outside [0,1]")
        if self.milestone_count_min < 1:
            raise ValidationError("milestone_count_min must be >= 1")
        if not (0.0 <= self.bond_ratio <= 1.0):
            raise ValidationError("bond_ratio outside [0,1]")
        if not (0.0 <= self.coverage_ratio <= 1.0):
            raise ValidationError("coverage_ratio outside [0,1]")
        if self.require_failure_rate_ge is not None and not (0.0 <= self.require_failure_rate_ge <= 1.0):
            raise ValidationError("require_failure_rate_ge outside [0,1]")
        if self.min_job_value_usd < 0:
            raise ValidationError("min_job_value_usd negative")
        try:
            self.evidence_confidence = EvidenceConfidence(self.evidence_confidence)
        except ValueError:
            raise ValidationError(f"bad evidence confidence {self.evidence_confidence!r}")

    def specificity(self) -> int:
        """Number of active trigger conditions — specificity tiebreak in matching."""
        n = 0
        if self.job_classes:
            n += 1
        if self.min_job_value_usd > 0:
            n += 1
        if self.require_new_counterparty:
            n += 1
        if self.require_failure_rate_ge is not None:
            n += 1
        if self.min_supporting_cases > 0:
            n += 1
        return n

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Doctrine:
    """A versioned, self-amending body of rules. Stored in REFERENCE tier."""
    version: int
    rules: list[Rule] = field(default_factory=list)
    effective_at: str = field(default_factory=_now_iso)
    supersedes: Optional[int] = None
    activated_by_case: Optional[str] = None
    amended_by_appeal: Optional[str] = None

    def rule(self, rule_id: str) -> Rule:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        raise KeyError(rule_id)

    def active_rules(self, now: Optional[datetime] = None) -> list[Rule]:
        return [r for r in self.rules if r.status is DoctrineStatus.ACTIVE]

    def diff(self, other: "Doctrine") -> list[dict[str, Any]]:
        """Changes FROM other (older) TO self (newer): added, removed, modified."""
        mine = {r.rule_id: r for r in self.rules}
        theirs = {r.rule_id: r for r in other.rules}
        out: list[dict[str, Any]] = []
        for rid in sorted(set(mine) | set(theirs)):
            if rid not in mine and rid in theirs:
                out.append({"rule": rid, "change": "REMOVED"})
            elif rid not in theirs and rid in mine:
                out.append({"rule": rid, "change": "ADDED", "rule": mine[rid].to_dict()})
            elif mine[rid].to_dict() != theirs[rid].to_dict():
                out.append({"rule": rid, "change": "MODIFIED", "rule": mine[rid].to_dict()})
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "effective_at": self.effective_at,
            "supersedes": self.supersedes,
            "activated_by_case": self.activated_by_case,
            "amended_by_appeal": self.amended_by_appeal,
            "rules": [r.to_dict() for r in self.rules],
        }


@dataclass(frozen=True)
class Terms:
    """Executable deal terms — the output CANON produces. NEVER a score."""
    upfront_usd: float
    milestones: tuple[float, ...]      # each milestone value; len >= 1
    bond_usd: float
    coverage_ratio: float              # pool covers this fraction of verified loss
    rule_ids: tuple[str, ...]
    doctrine_version: int
    reason: str
    upfront_cap_ratio: float = 1.0

    def __post_init__(self) -> None:
        if self.upfront_usd < 0:
            raise ValidationError("negative upfront")
        if not self.milestones or any(m <= 0 for m in self.milestones):
            raise ValidationError("milestones must be positive and non-empty")
        if self.bond_usd < 0:
            raise ValidationError("negative bond")
        if not (0.0 <= self.coverage_ratio <= 1.0):
            raise ValidationError("coverage outside [0,1]")

    @property
    def total_milestones(self) -> float:
        return sum(self.milestones)

    def to_dict(self) -> dict[str, Any]:
        return {
            "upfront_usd": round(self.upfront_usd, 4),
            "milestones": [round(m, 4) for m in self.milestones],
            "total_milestones": round(self.total_milestones, 4),
            "bond_usd": round(self.bond_usd, 4),
            "coverage_ratio": self.coverage_ratio,
            "rule_ids": list(self.rule_ids),
            "doctrine_version": self.doctrine_version,
            "reason": self.reason,
        }


@dataclass
class Case:
    case_id: str
    tx_id: str
    buyer: str
    provider: str
    job_type: str
    job_value_usd: float
    contract_terms: dict[str, Any]
    evidence: list[dict[str, Any]]
    status: CaseStatus = CaseStatus.RAW
    outcome: Optional[Outcome] = None
    loss_usd: float = 0.0
    ruling: Optional[str] = None
    confidence: EvidenceConfidence = EvidenceConfidence.LOW
    precedent_id: Optional[str] = None
    pattern_key: str = ""
    created_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.case_id or not self.tx_id:
            raise ValidationError("case_id and tx_id required")
        if self.loss_usd < 0:
            raise ValidationError("loss cannot be negative")
        if self.job_value_usd < 0:
            raise ValidationError("negative job value")
        if self.loss_usd > self.job_value_usd:
            raise ValidationError("loss cannot exceed transaction value")
        self.pattern_key = _normalize_job_type(self.job_type)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Counterparty:
    """WARM entity: factual history, never a score."""
    provider: str
    jurisdiction: str
    completed_jobs: int = 0
    failed_jobs: int = 0
    partial_jobs: int = 0
    claim_count: int = 0
    disputed_jobs: int = 0
    clean_jobs_since_failure: int = 0
    resolution_history: list[str] = field(default_factory=list)
    first_seen_at: str = field(default_factory=_now_iso)

    @property
    def total_jobs(self) -> int:
        return self.completed_jobs + self.failed_jobs + self.partial_jobs

    @property
    def empirical_failure_rate(self) -> float:
        if self.total_jobs == 0:
            return 0.0
        return self.failed_jobs / self.total_jobs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VenueAdmission:
    agent: str
    jurisdiction: str
    rules_version: int
    admitted_at: str
    status: str = "ACTIVE"   # ACTIVE | SUSPENDED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Transaction:
    tx_id: str
    buyer: str
    provider: str
    job_type: str
    job_value_usd: float
    jurisdiction: str
    state: TxState = TxState.PROPOSED
    terms: Optional[Terms] = None
    terms_snapshot_hash: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    funded_at: Optional[str] = None
    completed_at: Optional[str] = None
    outcome: Optional[Outcome] = None
    escrow_locked_usd: float = 0.0
    chain_ref: Optional[str] = None      # Base transaction hash once executed

    def __post_init__(self) -> None:
        Jurisdiction.validate(self.jurisdiction)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["terms"] = self.terms.to_dict() if self.terms else None
        return d


@dataclass
class Claim:
    claim_id: str
    tx_id: str
    case_id: Optional[str] = None
    claimant: str = ""
    amount_usd: float = 0.0
    status: str = "OPEN"     # OPEN | RESOLVED
    payout_usd: float = 0.0
    resolved_at: Optional[str] = None
    resolution_ref: Optional[str] = None   # Base payout hash

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Appeal:
    appeal_id: str
    challenger: str
    target_rule_id: str
    doctrine_version: int
    bond_usd: float
    arguments: str
    evidence: list[dict[str, Any]]
    state: AppealState = AppealState.OPEN
    decision: Optional[str] = None        # ACCEPTED | REJECTED
    new_rule_id: Optional[str] = None
    opened_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
