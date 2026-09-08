"""Injectable clock so doctrine decay, statutes, and freshness are testable
with deterministic time, while production uses UTC wall time."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


class Clock:
    def __init__(self) -> None:
        self._offset = timedelta(0)
        self._fixed: Optional[datetime] = None

    def now(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        return datetime.now(timezone.utc) + self._offset

    def iso(self) -> str:
        return self.now().isoformat(timespec="seconds")

    # --- test controls ---
    def freeze(self, at: datetime) -> None:
        self._fixed = at.astimezone(timezone.utc)

    def advance(self, **kw) -> None:
        if self._fixed is not None:
            self._fixed = self._fixed + timedelta(**kw)
        else:
            self._offset = self._offset + timedelta(**kw)

    def reset(self) -> None:
        self._fixed = None
        self._offset = timedelta(0)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
