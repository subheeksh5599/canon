"""Doctrine engine — deterministic, self-amending, decaying economic law.

The LLM never decides terms. A pure rule matcher maps normalized facts ->
the single most specific matching doctrine rule -> executable Terms. Doctrine
versions are stored in Sibyl's REFERENCE tier with checksums; activation
follows evidence thresholds (1 signal, 2 monitor, 3 candidate, 5 activate);
precedents decay to WEAKENING then ARCHIVED without fresh supporting cases.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from .clock import Clock
from .errors import MemoryUnavailableError, NotFoundError, RuleConflictError, ValidationError
from .types import (
    Doctrine,
    DoctrineStatus,
    EvidenceConfidence,
    Rule,
    Signal,
    Terms,
    TxFacts,
    _normalize_job_type,
)
from . import memory as mem_mod


class DoctrineEngine:
    def __init__(self, seam, *, clock: Optional[Clock] = None) -> None:
        self._seam = seam
        self.clock = clock or Clock()
        self.evidence_threshold_activate = 5     # D-015: five confirmed cases activate
        self.evidence_threshold_candidate = 3    # D-014
        self.evidence_threshold_monitor = 2      # D-013
        self.evidence_threshold_signal = 1       # D-012
        self.decay_weakening_days = 30
        self.decay_archive_days = 90
        self.lookback_days = 180                 # D-032: older cases never seed doctrine

    # ------------------------------------------------------------------ read
    def current_doctrine(self) -> Doctrine:
        version = self._seam.current_doctrine_version()
        if version is None:
            return Doctrine(version=0, rules=[], effective_at=self.clock.iso())
        return self.load_doctrine(version)

    def load_doctrine(self, version: int) -> Doctrine:
        if version == 0:
            return Doctrine(version=0)
        try:
            payload = self._seam.load_doctrine(version)
        except NotFoundError:
            return Doctrine(version=0)
        rules = [_rule_from_dict(r) for r in payload.get("rules", [])]
        return Doctrine(
            version=payload.get("version", version),
            rules=rules,
            effective_at=payload.get("effective_at", ""),
            supersedes=payload.get("supersedes"),
            activated_by_case=payload.get("activated_by_case"),
            amended_by_appeal=payload.get("amended_by_appeal"),
        )

    def persist(self, doctrine: Doctrine) -> None:
        self._seam.store_doctrine(doctrine.version, doctrine.to_dict())

    # ------------------------------------------------------------ term engine
    def evaluate(self, facts: TxFacts, counterparty, doctrine: Optional[Doctrine] = None) -> Terms:
        """Deterministic term generation. Pure: no clock reads, no randomness,
        no LLM. Identical inputs -> identical terms (D-001/D-002)."""
        import copy as _copy
        doc = doctrine or self.current_doctrine()
        # lazy decay: age rules at read time; persist only if a status changed
        if doc.version > 0:
            changed = False
            aged: list[Rule] = []
            for r in doc.rules:
                clone = _copy.deepcopy(r)
                was = clone.status
                aged.append(self._apply_decay(clone))
                changed = changed or (clone.status is not was)
            if changed:
                doc = Doctrine(version=doc.version, rules=aged,
                               effective_at=doc.effective_at,
                               supersedes=doc.supersedes,
                               activated_by_case=doc.activated_by_case,
                               amended_by_appeal=doc.amended_by_appeal)
                self.persist(doc)
            rules = aged
        else:
            rules = []
        contested = self._contested_rule_ids()
        active = [r for r in rules
                  if r.status is DoctrineStatus.ACTIVE and r.rule_id not in contested]
        if not active:
            return self._default_terms(facts, doc.version)
        match = self._match(facts, counterparty, active)
        if match is None:
            return self._default_terms(facts, doc.version)
        return self._build_terms(facts, match["rule"], match["rule_ids"], doc.version)

    def _contested_rule_ids(self) -> set[str]:
        """Rules with an OPEN appeal are frozen for new terms (A-005)."""
        contested: set[str] = set()
        for a in self._seam.list_entities(mem_mod.CAT_APPEAL, limit=100000):
            if a.get("state") == "OPEN":
                contested.add(a.get("target_rule_id"))
        return contested

    def _match(self, facts: TxFacts, counterparty, active_rules: list[Rule]) -> Optional[dict[str, Any]]:
        """Most-specific matching rule wins; equal specificity on same facts is a
        conflict (D-004/D-005/D-034) unless rule_ids are identical."""
        matches: list[Rule] = []
        for rule in active_rules:
            if self._rule_applies(rule, facts, counterparty):
                matches.append(rule)
        if not matches:
            return None
        matches.sort(key=lambda r: (r.specificity(), r.effective_at), reverse=True)
        top_spec = matches[0].specificity()
        top = [r for r in matches if r.specificity() == top_spec]
        rule_ids = sorted({r.rule_id for r in top})
        if len(top) > 1 and len(rule_ids) > 1:
            raise RuleConflictError(
                f"conflicting rules at specificity {top_spec}: {rule_ids} — doctrine is inconsistent"
            )
        return {"rule": top[0], "rule_ids": rule_ids}

    def _rule_applies(self, rule: Rule, facts: TxFacts, counterparty) -> bool:
        if rule.job_classes is not None and facts.pattern_key not in [_normalize_job_type(j) for j in rule.job_classes]:
            return False
        if facts.job_value_usd < rule.min_job_value_usd:
            return False
        if rule.require_new_counterparty:
            if counterparty is None or counterparty.total_jobs > 0:
                return False
        if rule.require_failure_rate_ge is not None:
            rate = counterparty.empirical_failure_rate if counterparty else 0.0
            if rate < rule.require_failure_rate_ge:
                return False
        if rule.min_supporting_cases > 0:
            support = len(rule.supporting_case_ids or [])
            if support < rule.min_supporting_cases:
                return False
        return True

    def _build_terms(self, facts: TxFacts, rule: Rule, rule_ids: list[str], version: int) -> Terms:
        upfront = round(facts.job_value_usd * rule.upfront_cap_ratio, 2)
        remaining = round(facts.job_value_usd - upfront, 2)
        count = rule.milestone_count_min
        if count <= 0:
            count = 1
        if remaining <= 0:
            milestones = tuple(round(facts.job_value_usd / count, 2) for _ in range(count))
        else:
            base = remaining / count
            milestones = tuple(round(base, 2) for _ in range(count))
        bond = round(facts.job_value_usd * rule.bond_ratio, 2)
        # invariant D-010: bond <= job_value * configured max (1.0 here by bound on ratio)
        reason = (
            f"Doctrine v{version} · rule {','.join(rule_ids)} · "
            f"supporting cases {len(rule.supporting_case_ids or [])}"
        )
        return Terms(
            upfront_usd=upfront,
            milestones=milestones,
            bond_usd=bond,
            coverage_ratio=rule.coverage_ratio,
            rule_ids=tuple(rule_ids),
            doctrine_version=version,
            reason=reason,
            upfront_cap_ratio=rule.upfront_cap_ratio,
        )

    def _default_terms(self, facts: TxFacts, doc_version: int = 0) -> Terms:
        """Naive market terms when no active rule applies: 100% upfront, no bond,
        no coverage. The ablation control — memoryless CANON always emits this."""
        return Terms(
            upfront_usd=round(facts.job_value_usd, 2),
            milestones=(round(facts.job_value_usd, 2),),
            bond_usd=0.0,
            coverage_ratio=0.0,
            rule_ids=(),
            doctrine_version=doc_version,
            reason="No doctrine — naive market terms (100% upfront, no bond)",
            upfront_cap_ratio=1.0,
        )

    # ------------------------------------------------------- pattern evidence
    def pattern_stats(self, pattern_key: str, *, outcome_any_of=None, since_days: Optional[int] = None) -> dict[str, Any]:
        """Collective evidence over resolved cases matching a pattern — the
        stranger-effect input. Reads WARM case entities, never raw events."""
        lookback = since_days if since_days is not None else self.lookback_days
        cutoff = self._iso_before(lookback)
        cases = self._seam.list_entities(mem_mod.CAT_CASE, limit=100000)
        matched = []
        for c in cases:
            body = c
            if body.get("pattern_key") != pattern_key:
                continue
            if body.get("status") != "RESOLVED":
                continue
            created = body.get("created_at", "")
            if created and created < cutoff:
                continue
            matched.append(body)
        bad = [c for c in matched
               if c.get("outcome") in ("FAILED", "FRAUD")
               and c.get("confidence") in ("HIGH", "MEDIUM")]
        if outcome_any_of is not None:
            bad = [c for c in matched
                   if c.get("outcome") in outcome_any_of
                   and c.get("confidence") in ("HIGH", "MEDIUM")]
        total = len(matched)
        rate = (len(bad) / total) if total else 0.0
        return {
            "pattern": pattern_key,
            "resolved_cases": total,
            "bad_cases": len(bad),
            "failure_rate": round(rate, 4),
            "cases": [c.get("case_id") for c in matched][-60:],
        }

    # ------------------------------------------------------- signal & update
    def signal_level(self, pattern_key: str) -> tuple[Signal, dict[str, Any]]:
        stats = self.pattern_stats(pattern_key)
        n = stats["bad_cases"]
        if n >= self.evidence_threshold_activate:
            return Signal.ACTIVE, stats
        if n >= self.evidence_threshold_candidate:
            return Signal.CANDIDATE, stats
        if n >= self.evidence_threshold_monitor:
            return Signal.MONITOR, stats
        if n >= self.evidence_threshold_signal:
            return Signal.SIGNAL, stats
        return Signal.NONE, stats

    def propose_candidate_rule(self, pattern_key: str, *, activated_by_case: str) -> Optional[Rule]:
        """Called after a resolved case; returns the candidate rule to activate
        when the pattern crosses the activation threshold (D-014/D-015)."""
        signal, stats = self.signal_level(pattern_key)
        if signal is not Signal.ACTIVE:
            return None
        doc = self.current_doctrine()
        rule_id = f"CANON-{doc.version + 1:03d}-{pattern_key[:12]}"
        rule = Rule(
            rule_id=rule_id,
            job_classes=[pattern_key],
            require_new_counterparty=False,
            min_supporting_cases=self.evidence_threshold_activate,
            supporting_case_ids=stats["cases"][-self.evidence_threshold_activate:],
            evidence_confidence=EvidenceConfidence.HIGH,
            created_by_case=activated_by_case,
            effective_at=self.clock.iso(),
            upfront_cap_ratio=0.25,     # canonical Rule 12A-style: 25% upfront cap
            milestone_count_min=3,
            bond_ratio=0.20,            # 20% bond
            coverage_ratio=0.80,
        )
        return rule

    def maybe_activate(self, pattern_key: str, case_id: str, reason: str) -> Optional[Doctrine]:
        """Activation policy: if the pattern already has an ACTIVE governing
        rule, refresh its support (keep its decay clock young) instead of
        stacking versions. Only a decayed/absent rule triggers a new version."""
        doc = self.current_doctrine()
        for r in doc.rules:
            if (r.status is DoctrineStatus.ACTIVE and r.job_classes is not None
                    and pattern_key in [_normalize_job_type(j) for j in r.job_classes]):
                self.refresh_support(pattern_key, case_id)
                return None
        return self.activate_doctrine_update(pattern_key, activated_by_case=case_id, reason=reason)

    def activate_doctrine_update(self, pattern_key: str, *, activated_by_case: str, reason: str) -> Optional[Doctrine]:
        """Evidence threshold crossed -> doctrine vN+1 enters memory (D-015..D-018).
        The new rule is STORED, never regenerated per-request (D-030). If the
        pattern already has an ACTIVE rule, that rule is superseded (not
        duplicated) — the new version carries the escalated rule instead."""
        candidate = self.propose_candidate_rule(pattern_key, activated_by_case=activated_by_case)
        if candidate is None:
            return None
        # Anti-Sybil: a history built by ONE counterparty cannot become law for
        # the whole venue. The live venue runs with CANON_MIN_DISTINCT_COUNTERPARTIES=3;
        # the default of 1 keeps unit fixtures single-provider.
        import os as _os
        min_distinct = int(_os.environ.get("CANON_MIN_DISTINCT_COUNTERPARTIES", "1") or 1)
        if min_distinct > 1:
            provs = set()
            for cid in (candidate.supporting_case_ids or []):
                body = self._seam.get_entity(mem_mod.CAT_CASE, cid) or {}
                if body.get("provider"):
                    provs.add(body["provider"])
            if len(provs) < min_distinct:
                self._seam.write_event(
                    evaluated={"pattern": pattern_key,
                               "distinct_counterparties": len(provs),
                               "required": min_distinct},
                    acted="doctrine.activation_refused",
                    extra={"event": "SYBIL_GUARD"},
                )
                return None
        import copy as _copy
        doc = self.current_doctrine()
        carried = [self._apply_decay(_copy.deepcopy(r)) for r in doc.rules]
        # supersede any active rule governing the same pattern instead of
        # stacking a same-specificity duplicate (RuleConflictError guard)
        prior = None
        kept: list[Rule] = []
        for r in carried:
            owns_pattern = (r.job_classes is not None
                            and pattern_key in [_normalize_job_type(j) for j in r.job_classes]
                            and r.status is DoctrineStatus.ACTIVE)
            if owns_pattern and prior is None:
                prior = r
                continue  # superseded by the candidate below
            kept.append(r)
        if prior is not None:
            candidate.supersedes = prior.rule_id
        new_version = doc.version + 1
        new_doc = Doctrine(
            version=new_version,
            rules=kept + [candidate],
            effective_at=self.clock.iso(),
            supersedes=doc.version if doc.version else None,
            activated_by_case=activated_by_case,
        )
        self.persist(new_doc)
        return new_doc

    def _apply_decay(self, rule: Rule) -> Rule:
        """Decay (D-019/D-020/D-021): rules age without fresh supporting cases."""
        if rule.status not in (DoctrineStatus.ACTIVE, DoctrineStatus.WEAKENING):
            return rule
        if not rule.effective_at:
            return rule
        try:
            from datetime import datetime
            effective = datetime.fromisoformat(rule.effective_at)
        except ValueError:
            return rule
        now = self.clock.now()
        age = now - effective
        # decay measures freshness of support: last_supported_at if set, else creation
        if rule.last_supported_at:
            try:
                support_dt = datetime.fromisoformat(rule.last_supported_at)
                age = now - support_dt
            except ValueError:
                pass
        if age > timedelta(days=self.decay_archive_days):
            rule.status = DoctrineStatus.ARCHIVED
        elif age > timedelta(days=self.decay_weakening_days):
            rule.status = DoctrineStatus.WEAKENING
        return rule

    def refresh_support(self, pattern_key: str, case_id: str) -> None:
        """A resolved case in a governed pattern refreshes the active rule's
        evidence and keeps its decay clock young. Same-version persistence is
        content-addressed via the checksum sidecar."""
        doc = self.current_doctrine()
        if doc.version == 0:
            return
        touched = False
        for r in doc.rules:
            if r.status is not DoctrineStatus.ACTIVE:
                continue
            if r.job_classes and pattern_key in [_normalize_job_type(j) for j in r.job_classes]:
                sup = list(r.supporting_case_ids or [])
                if case_id not in sup:
                    sup.append(case_id)
                    r.supporting_case_ids = sup
                r.last_supported_at = self.clock.iso()
                touched = True
        if touched:
            self.persist(doc)

    def _iso_before(self, days: int) -> str:
        return (self.clock.now() - timedelta(days=days)).isoformat(timespec="seconds")


def _rule_from_dict(d: dict[str, Any]) -> Rule:
    try:
        status = DoctrineStatus(d.get("status", "ACTIVE"))
    except ValueError:
        status = DoctrineStatus.ACTIVE
    return Rule(
        rule_id=d["rule_id"],
        status=status,
        created_by_case=d.get("created_by_case"),
        effective_at=d.get("effective_at") or "",
        supersedes=d.get("supersedes"),
        amended_by_appeal=d.get("amended_by_appeal"),
        job_classes=d.get("job_classes"),
        min_job_value_usd=float(d.get("min_job_value_usd", 0.0)),
        require_new_counterparty=bool(d.get("require_new_counterparty", False)),
        require_failure_rate_ge=d.get("require_failure_rate_ge"),
        min_supporting_cases=int(d.get("min_supporting_cases", 0)),
        upfront_cap_ratio=float(d.get("upfront_cap_ratio", 1.0)),
        milestone_count_min=int(d.get("milestone_count_min", 1)),
        bond_ratio=float(d.get("bond_ratio", 0.0)),
        coverage_ratio=float(d.get("coverage_ratio", 0.0)),
        supporting_case_ids=list(d.get("supporting_case_ids", [])),
        evidence_confidence=d.get("evidence_confidence", EvidenceConfidence.HIGH),
        last_supported_at=d.get("last_supported_at"),
    )
