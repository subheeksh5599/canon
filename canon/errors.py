"""CANON domain errors. Every failure mode is a typed error — never a bare exception."""


class CanonError(Exception):
    """Base error for the CANON domain."""


class ValidationError(CanonError):
    """Input failed schema/domain validation. Never a crash — always a domain error."""


class ConflictError(CanonError):
    """State conflict: duplicate id, illegal transition, double resolution."""


class NotFoundError(CanonError):
    """Referenced record does not exist."""


class StandingError(CanonError):
    """Caller lacks standing for the action (wrong party, no admission)."""


class UnauthorizedVenueError(StandingError):
    """Agent never accepted venue rules — jurisdiction is contractual."""


class AppealError(CanonError):
    """Appeal flow violation (duplicate, no bond, wrong target, frozen doctrine)."""


class SettlementError(CanonError):
    """Escrow/settlement accounting invariant broken."""


class MemoryUnavailableError(CanonError):
    """Sibyl unavailable or authoritative data missing — CANON refuses to evaluate."""


class RuleConflictError(CanonError):
    """Two rules match with equal specificity — unresolvable without arbitrariness."""
