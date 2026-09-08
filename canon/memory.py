"""MemorySeam — the ONLY module that imports sibyl_memory_client.

Every CANON read/write goes through this seam. Tier roles are enforced here:
HOT=transaction state, WARM=entities (agents, counterparties, cases),
COLD=append-only event journal, REFERENCE=doctrine + policy, ARCHIVE=retired
records. A chain hash links every journal event to its predecessor; the
current doctrine checksum is verified before every evaluation. There is no
fallback path: if memory is missing, evaluation raises MemoryUnavailableError.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sibyl_memory_client import MemoryClient, NotFoundError as SibylNotFound

from .errors import (
    ConflictError,
    MemoryUnavailableError,
    NotFoundError,
    ValidationError,
)
from .types import sha256, _json_default

CAT_AGENT = "agent"
CAT_COUNTERPARTY = "counterparty"
CAT_CASE = "case"
CAT_CLAIM = "claim"
CAT_APPEAL = "appeal"
CAT_TX = "tx"             # cold record after settlement/archive
REF_DOCTRINE_CURRENT = "doctrine:current"
REF_DOCTRINE_PREFIX = "doctrine:v"
REF_VENUE_RULES = "venue:rules"
REF_POOL = "pool:ledger"
CHAIN_HEAD = "journal:head"


def _merge_entity(rec: dict[str, Any]) -> dict[str, Any]:
    """Flatten the client's entity wrapper into the stored body plus identity
    fields, so domain code reads body['case_id'] directly."""
    out = dict(rec.get("body") or {})
    out.setdefault("name", rec.get("name"))
    out.setdefault("_entity_status", rec.get("status"))
    return out


def _b(evaluated: Any = None, acted: Any = None, forward: Any = None, extra: Any = None) -> dict[str, Any]:
    return {"evaluated": evaluated, "acted": acted, "forward": forward, "extra": extra}


class MemorySeam:
    def __init__(self, path: str | Path, *, clock=None, tenant_id: str = "canon-venue") -> None:
        from .clock import Clock

        self.clock = clock or Clock()
        self._path = Path(path).expanduser()
        self._tenant_id = tenant_id
        try:
            self._client = MemoryClient.local(self._path, tenant_id=tenant_id)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise MemoryUnavailableError(f"sibyl unavailable at {self._path}: {exc}") from exc

    # ------------------------------------------------------------------ paths
    @property
    def db_path(self) -> Path:
        return self._path

    def tenant(self) -> str:
        return self._tenant_id

    # ------------------------------------------------------------- HOT state
    def set_hot(self, key: str, body: dict[str, Any]) -> None:
        self._client.set_state(key, body)

    def get_hot(self, key: str) -> dict[str, Any] | None:
        try:
            rec = self._client.get_state(key)
        except SibylNotFound:
            return None
        if rec is None:
            return None
        if isinstance(rec, dict) and "body" in rec:
            return rec["body"]
        return rec

    def clear_hot(self, key: str) -> None:
        # set_state(None) unsupported; delete via cold write is not allowed,
        # so HOT entries that finish lifecycle move to COLD record + tombstone.
        try:
            self._client.set_state(key, {"__archived__": True})
        except Exception:  # pragma: no cover
            pass

    # ---------------------------------------------------------- WARM entities
    def set_entity(self, category: str, name: str, body: dict[str, Any] | list[Any], *, status: str | None = None) -> None:
        if not category or not name:
            raise ValidationError("entity category and name required")
        self._client.set_entity(category, name, body, status=status)

    def get_entity(self, category: str, name: str) -> dict[str, Any] | None:
        try:
            rec = self._client.get_entity(category, name)
        except SibylNotFound:
            return None
        if rec is None:
            return None
        return _merge_entity(rec)

    def list_entities(self, category: str | None = None, *, limit: int = 500) -> list[dict[str, Any]]:
        recs = self._client.list_entities(category=category, limit=limit)
        return [_merge_entity(r) for r in recs]

    def search_entities(self, query: str, *, category: str | None = None, limit: int = 50):
        return self._client.search_entities(query, category=category, limit=limit)

    def archive_entity(self, category: str, name: str, reason: str | None = None) -> None:
        self._client.archive_entity(category, name, reason=reason)

    def delete_entity(self, category: str, name: str) -> bool:
        return self._client.delete_entity(category, name)

    # ------------------------------------------------------------- COLD events
    def write_event(self, *, evaluated: Any = None, acted: Any = None,
                    forward: Any = None, extra: Any = None) -> str:
        head = self._read_head()
        prev = head["hash"] if head else "genesis"
        seq = (head["seq"] + 1) if head else 1
        ts = self.clock.iso()
        payload = {
            "seq": seq,
            "ts": ts,
            "evaluated": evaluated,
            "acted": acted,
            "forward": forward,
            "extra": extra,
            "prev": prev,
        }
        chain_hash = sha256(payload)
        payload["hash"] = chain_hash
        event_id = self._client.write_event(
            evaluated=payload["evaluated"],
            acted=payload["acted"],
            forward=payload["forward"],
            extra={"seq": seq, "prev": prev, "hash": chain_hash, **({} if extra is None else extra)},
            ts=ts,
        )
        self._client.set_reference(CHAIN_HEAD, {"seq": seq, "hash": chain_hash, "event_id": event_id})
        return event_id

    def _read_head(self) -> dict[str, Any] | None:
        return self.get_reference(CHAIN_HEAD)

    def read_events(self, *, limit: int = 200, since: str | None = None) -> list[dict[str, Any]]:
        return self._client.read_events(limit=limit, since=since)

    def verify_journal(self) -> tuple[bool, Optional[str]]:
        """Re-derive the chain hash over the full journal; returns (ok, broken_at)."""
        events = self._client.read_events(limit=100000)
        # read order is not guaranteed chronological — sort by our seq chain
        events = sorted(events, key=lambda e: int(((e.get("extra") or {}).get("seq", 0)) or 0))
        prev = "genesis"
        for ev in events:
            extra = ev.get("extra") or {}
            seq = extra.get("seq")
            h = extra.get("hash")
            prev_rec = extra.get("prev")
            if prev_rec != prev:
                return False, f"chain gap at seq {seq}: expected prev {prev}, got {prev_rec}"
            if h is None:
                return False, f"missing hash at seq {seq}"
            orig_extra = {k: v for k, v in extra.items() if k not in ("seq", "prev", "hash")}
            body = {
                "seq": seq,
                "ts": ev.get("ts"),
                "evaluated": ev.get("evaluated"),
                "acted": ev.get("acted"),
                "forward": ev.get("forward"),
                "extra": orig_extra,
                "prev": prev_rec,
            }
            if sha256(body) != h:
                return False, f"hash mismatch at seq {seq}"
            prev = h
        return True, None

    # ---------------------------------------------------------- REFERENCE tier
    def set_reference(self, key: str, body: Any, *, metadata: dict[str, Any] | None = None) -> None:
        self._client.set_reference(key, body, metadata=metadata)

    def get_reference(self, key: str) -> dict[str, Any] | None:
        rec = self._client.get_reference(key)
        if rec is None:
            return None
        body = rec.get("body")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except (ValueError, TypeError):
                return {"__raw__": body}
        return body if isinstance(body, dict) else {"__value__": body}

    def store_doctrine(self, version: int, payload: dict[str, Any]) -> None:
        checksum = sha256(payload)
        self._client.set_reference(f"{REF_DOCTRINE_PREFIX}{version}", payload)
        # sidecar checksum reference — tamper detection without trusting get_reference metadata
        self._client.set_reference(f"doctrine:v{version}:meta", {"checksum": checksum})
        self._client.set_reference(REF_DOCTRINE_CURRENT,
                                   {"version": int(version), "checksum": checksum, "updated_at": self.clock.iso()})

    def current_doctrine_version(self) -> Optional[int]:
        cur = self.get_reference(REF_DOCTRINE_CURRENT)
        if not cur:
            return None
        try:
            return int(cur.get("version"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def load_doctrine(self, version: int) -> dict[str, Any]:
        payload = self.get_reference(f"{REF_DOCTRINE_PREFIX}{version}")
        if payload is None:
            raise NotFoundError(f"doctrine v{version} not found")
        meta = self.get_reference(f"doctrine:v{version}:meta") or {}
        meta_checksum = meta.get("checksum")
        if meta_checksum and sha256(payload) != meta_checksum:
            raise MemoryUnavailableError(f"doctrine v{version} failed checksum — tampered or corrupt")
        return payload

    def doctrine_checksum(self, version: int) -> Optional[str]:
        meta = self.get_reference(f"doctrine:v{version}:meta") or {}
        return meta.get("checksum")

    # ----------------------------------------------------------- ledger/pool
    def pool_balance(self) -> float:
        rec = self.get_reference(REF_POOL)
        return float((rec or {}).get("balance_usd", 0.0))

    def pool_mutate(self, delta_usd: float, reason: str, *, allow_negative: bool = False) -> float:
        rec = self.get_reference(REF_POOL) or {"balance_usd": 0.0, "entries": []}
        new_balance = float(rec.get("balance_usd", 0.0)) + delta_usd
        if new_balance < -1e-9 and not allow_negative:
            from .errors import SettlementError
            raise SettlementError(f"pool would go negative: {new_balance}")
        rec["balance_usd"] = round(new_balance, 6)
        entries = rec.setdefault("entries", [])
        entries.append({"delta": round(delta_usd, 6), "reason": reason, "ts": self.clock.iso()})
        if len(entries) > 5000:
            rec["entries"] = entries[-2000:]
        self._client.set_reference(REF_POOL, rec)
        return new_balance

    # ------------------------------------------------------------- integrity
    def delete_all(self) -> None:
        """Deletion test helper: wipe every tier. After this, CANON cannot
        construct authoritative terms — that IS the product claim."""
        for cat in (CAT_AGENT, CAT_COUNTERPARTY, CAT_CASE, CAT_CLAIM, CAT_APPEAL, CAT_TX):
            for ent in self._client.list_entities(category=cat, limit=100000):
                try:
                    self._client.delete_entity(cat, ent.get("name") or ent.get("category_name", ""))
                except Exception:  # pragma: no cover
                    pass
        try:
            Path(self._path).unlink()
        except FileNotFoundError:
            pass
        # reopen fresh (schema is idempotent)
        self._client = MemoryClient.local(self._path, tenant_id=self._tenant_id)
