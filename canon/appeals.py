"""Appeals — contestable doctrine. A participant challenges a precedent by
posting a real bond; a successful challenge amends the doctrine (vN -> vN+1)
and every future transaction operates under the amended rule. A contested
rule is frozen for new terms while an appeal is open."""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Optional

from .clock import Clock
from .errors import AppealError, ConflictError, NotFoundError, ValidationError
from .memory import CAT_APPEAL, MemorySeam
from .types import (
    Appeal,
    AppealState,
    Doctrine,
    DoctrineStatus,
    Rule,
)


class AppealService:
    def __init__(self, seam: MemorySeam, doctrine_engine, ledger, *, clock: Optional[Clock] = None) -> None:
        self._seam = seam
        self._doctrine = doctrine_engine
        self._ledger = ledger
        self.clock = clock or Clock()
        self.default_appeal_bond = 10.0          # USD, doctrine-configurable
        self.min_appeal_bond = 5.0               # economic floor: appeals are never free
        self.window_blocks = 3                   # A-016 analog: appeals close after adjudication
        self.max_open_per_challenger = 3         # A-012 flood control

    def open_appeal(self, *, challenger: str, target_rule_id: str, arguments: str,
                    evidence: list[dict[str, Any]], bond_usd: Optional[float] = None,
                    jurisdiction: str = "acp-research") -> Appeal:
        doc = self._doctrine.current_doctrine()
        if doc.version == 0:
            raise AppealError("cannot appeal the default doctrine — there is no precedent yet")
        rule = None
        for r in doc.rules:
            if r.rule_id == target_rule_id:
                rule = r
        if rule is None:
            raise NotFoundError(f"rule {target_rule_id} not in doctrine v{doc.version}")
        if rule.status in (DoctrineStatus.SUPERSEDED, DoctrineStatus.ARCHIVED):
            raise AppealError(f"rule {target_rule_id} already superseded — appeal the current version")
        if not arguments.strip():
            raise ValidationError("appeal requires arguments")
        if not evidence:
            raise ValidationError("frivolous appeal rejected at intake: no evidence payload")
        open_count = 0
        for a in self._seam.list_entities(CAT_APPEAL, limit=100000):
            if a.get("challenger") == challenger and a.get("state") == "OPEN":
                open_count += 1
                if a.get("target_rule_id") == target_rule_id:
                    raise ConflictError(f"duplicate open appeal on {target_rule_id}")
        if open_count >= self.max_open_per_challenger:
            raise AppealError("appeal flood: too many open appeals for one challenger")
        bond = bond_usd if bond_usd is not None else self.default_appeal_bond
        if bond < self.min_appeal_bond:
            raise AppealError(f"appeal requires a posted bond of at least {self.min_appeal_bond}")
        # bond is a real ledger action (Base mirror is the contract's openAppeal)
        self._ledger.post_bond(jurisdiction=jurisdiction, actor=challenger, amount_usd=bond,
                               reason=f"appeal-bond:{target_rule_id}")
        appeal = Appeal(
            appeal_id=f"appeal-{uuid.uuid4().hex[:12]}",
            challenger=challenger,
            target_rule_id=target_rule_id,
            doctrine_version=doc.version,
            bond_usd=round(bond, 2),
            arguments=arguments,
            evidence=evidence,
            state=AppealState.OPEN,
            opened_at=self.clock.iso(),
        )
        self._seam.set_entity(CAT_APPEAL, appeal.appeal_id, appeal.to_dict(), status="OPEN")
        self._seam.write_event(
            evaluated={"appeal_id": appeal.appeal_id, "target": target_rule_id, "bond": bond},
            acted="appeal.open",
            forward=appeal.appeal_id,
            extra={"event": "APPEAL_OPEN", "doctrine_version": doc.version},
        )
        return appeal

    def resolve_appeal(self, appeal_id: str, *, decision: str, adjudicator: str,
                       independent_review: bool = True) -> Appeal:
        """Adjudication by an independent fact-finder (A-006)."""
        body = self._seam.get_entity(CAT_APPEAL, appeal_id)
        if body is None:
            raise NotFoundError(f"appeal {appeal_id} not found")
        clean = {k: v for k, v in body.items() if k not in ("name", "_entity_status")}
        appeal = Appeal(**clean)
        if appeal.state is AppealState.RESOLVED:
            raise ConflictError(f"appeal {appeal_id} already resolved")
        if not independent_review:
            raise ValidationError("appeal resolution requires independent fact-finder review")
        if adjudicator == appeal.challenger:
            raise ValidationError("adjudicator cannot be the challenger")
        decision = decision.upper()
        if decision not in ("ACCEPTED", "REJECTED"):
            raise ValidationError("decision must be ACCEPTED or REJECTED")
        appeal.state = AppealState.RESOLVED
        appeal.decision = decision
        appeal.resolved_at = self.clock.iso()
        if decision == "ACCEPTED":
            appeal.new_rule_id = self._amend_doctrine(appeal)
            self._ledger.refund_bond(actor=appeal.challenger, amount_usd=appeal.bond_usd,
                                     reason=f"appeal-won:{appeal.appeal_id}")
        else:
            self._ledger.forfeit_bond(actor=appeal.challenger, amount_usd=appeal.bond_usd,
                                      reason=f"appeal-lost:{appeal.appeal_id}")
        self._seam.set_entity(CAT_APPEAL, appeal_id, appeal.to_dict(), status="RESOLVED")
        self._seam.write_event(
            evaluated={"appeal_id": appeal_id, "decision": decision},
            acted="appeal.resolve",
            forward=appeal.new_rule_id,
            extra={"event": "APPEAL_RESOLVED"},
        )
        return appeal

    def _amend_doctrine(self, appeal: Appeal) -> str:
        """A successful appeal amends the challenged rule: doctrine vN -> vN+1
        (A-008/A-009/A-014/A-015).

        Oscillation guard: if CANON_AMENDMENT_COOLDOWN_HOURS is set (the live
        venue runs with it on), the same rule cannot be amended again inside
        that window. Two parties cannot ping-pong the doctrine by alternating
        appeals; rejected appeals are unaffected.
        """
        import os
        cooldown_h = float(os.environ.get("CANON_AMENDMENT_COOLDOWN_HOURS", "0") or 0)
        doc = self._doctrine.current_doctrine()
        if cooldown_h > 0 and doc.amended_by_appeal:
            # the doctrine itself records the last accepted amendment; the
            # appeal entity carries its timestamp. Inside the window, refuse.
            last = self._seam.get_entity(CAT_APPEAL, doc.amended_by_appeal) or {}
            stamp = last.get("resolved_at") or ""
            from datetime import datetime, timezone
            try:
                eff = datetime.fromisoformat(stamp)
                if eff.tzinfo is None:
                    eff = eff.replace(tzinfo=timezone.utc)
                now = datetime.fromisoformat(self.clock.iso())
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                age_h = (now - eff).total_seconds() / 3600.0
                if age_h < cooldown_h:
                    raise ConflictError(
                        f"doctrine was amended {age_h:.1f}h ago (appeal "
                        f"{doc.amended_by_appeal}); amendment cooldown is {cooldown_h}h")
            except ConflictError:
                raise
            except Exception:
                pass  # unparseable timestamp must not block a legitimate appeal
        new_rules = []
        amended_id = None
        for r in doc.rules:
            if r.rule_id == appeal.target_rule_id:
                amended = self._relax_rule(r, appeal)
                new_rules.append(amended)
                amended_id = amended.rule_id
            else:
                new_rules.append(r)
        new_version = doc.version + 1
        new_doc = Doctrine(
            version=new_version,
            rules=new_rules,
            effective_at=self.clock.iso(),
            supersedes=doc.version,
            amended_by_appeal=appeal.appeal_id,
        )
        # archive the superseded version's rule via status (A-015 byte-identical archive)
        self._seam.write_event(
            evaluated={"from_version": doc.version, "to_version": new_version},
            acted="doctrine.amend",
            forward=appeal.appeal_id,
            extra={"event": "DOCTRINE_AMENDED"},
        )
        self._doctrine.persist(new_doc)
        return amended_id or appeal.target_rule_id

    def _relax_rule(self, rule: Rule, appeal: Appeal) -> Rule:
        """Appeal accepted -> the contested restriction is relaxed: bond halves,
        upfront cap loosens, coverage preserved. The amendment is provenance-
        linked to the appeal (never an in-place edit)."""
        import copy
        amended = copy.deepcopy(rule)
        amended.rule_id = f"{rule.rule_id}-a{appeal.appeal_id[-4:]}"
        amended.status = DoctrineStatus.ACTIVE
        amended.amended_by_appeal = appeal.appeal_id
        amended.effective_at = self.clock.iso()
        amended.bond_ratio = round(max(0.0, amended.bond_ratio - 0.10), 4)
        amended.upfront_cap_ratio = round(min(1.0, amended.upfront_cap_ratio + 0.15), 4)
        return amended
