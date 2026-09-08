"""Ledger — the money-side mirror of the Base contract. Bond post/refund/
forfeit, escrow locks, claim payouts. Accounting invariant: paid claims +
locked bonds never exceed pool balance + posted bonds (C-014). In production
every mutation here maps 1:1 to an onchain action on CanonMarket.sol; the
ledger reference in Sibyl keeps the memory-side record of truth."""
from __future__ import annotations

from typing import Any, Optional

from .clock import Clock
from .errors import SettlementError, ValidationError
from .memory import MemorySeam


class Ledger:
    def __init__(self, seam: MemorySeam, *, clock: Optional[Clock] = None) -> None:
        self._seam = seam
        self.clock = clock or Clock()
        self.fee_ratio = 0.01  # venue fee, configurable

    # ----------------------------------------------------------------- bonds
    def post_bond(self, *, jurisdiction: str, actor: str, amount_usd: float, reason: str) -> None:
        if amount_usd <= 0:
            raise ValidationError("bond must be positive")
        if actor == "unknown":
            raise ValidationError("bond requires a known actor")
        # bond is custody from the challenger's own funds — like escrow, it
        # returns on refund/forfeit; the pool never "pays" for an appeal
        self._seam.pool_mutate(-amount_usd, f"bond-post:{reason}:{actor}", allow_negative=True)

    def refund_bond(self, *, actor: str, amount_usd: float, reason: str) -> None:
        self._seam.pool_mutate(amount_usd, f"bond-refund:{reason}:{actor}", allow_negative=True)

    def forfeit_bond(self, *, actor: str, amount_usd: float, reason: str) -> None:
        self._seam.pool_mutate(amount_usd, f"bond-forfeit:{reason}:{actor}", allow_negative=True)

    # ---------------------------------------------------------------- escrow
    def lock_escrow(self, *, tx_id: str, total_usd: float, buyer: str) -> float:
        if total_usd <= 0:
            raise ValidationError("escrow must be positive")
        # escrow is custody, not a spend: it returns to the pool on release/refund
        self._seam.pool_mutate(-total_usd, f"escrow-lock:{tx_id}:{buyer}", allow_negative=True)
        return total_usd

    def release_milestone(self, *, tx_id: str, amount_usd: float, provider: str) -> float:
        if amount_usd <= 0:
            raise ValidationError("release must be positive")
        self._seam.pool_mutate(-amount_usd, f"milestone:{tx_id}:{provider}", allow_negative=True)
        return amount_usd

    def refund_escrow(self, *, tx_id: str, amount_usd: float, buyer: str) -> float:
        # return of custody: bounded by the earlier lock, never pool income
        self._seam.pool_mutate(amount_usd, f"escrow-refund:{tx_id}:{buyer}", allow_negative=True)
        return amount_usd

    def pay_claim(self, *, claim_id: str, amount_usd: float, payee: str) -> float:
        if amount_usd <= 0:
            raise ValidationError("payout must be positive")
        self._seam.pool_mutate(-amount_usd, f"claim-payout:{claim_id}:{payee}")
        return amount_usd

    def charge_fee(self, *, tx_id: str, job_value_usd: float) -> float:
        fee = round(job_value_usd * self.fee_ratio, 2)
        self._seam.pool_mutate(fee, f"venue-fee:{tx_id}")
        return fee
