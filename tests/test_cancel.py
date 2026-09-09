"""Cancel semantics: TERMED (unfunded) deals can be abandoned — no money
moves and no on-chain escrow exists. Funded deals cannot be cancelled through
this path (a funded cancel would refund the buyer while the clearinghouse
advanced the collateral)."""
import pytest

from canon.errors import ConflictError
from tests.conftest import make_facts

BUYER = "0xbuyer000000000000000000000000000001"
PROVIDER = "0xprov000000000000000000000000000002"


def _termed(market, value=400.0):
    f = make_facts(value=value)
    t = market.evaluate(buyer=BUYER, provider=PROVIDER, job_type=f.job_type, job_value_usd=value)
    return market.create_tx(buyer=BUYER, provider=PROVIDER, job_type=f.job_type,
                            job_value_usd=value, terms=t)


def test_termed_deal_can_be_cancelled(market):
    tx = _termed(market)
    assert tx.state.value == "TERMED"
    done = market.cancel(tx.tx_id)
    assert done.state.value == "CANCELLED"


def test_cancel_is_illegal_twice(market):
    tx = _termed(market)
    market.cancel(tx.tx_id)
    with pytest.raises(ConflictError):
        market.cancel(tx.tx_id)  # CANCELLED -> CANCELLED is illegal


def test_funded_deal_cannot_be_cancelled(market):
    tx = _termed(market)
    tx = market.execute(tx.tx_id, chain_ref="0xdead")
    assert tx.state.value == "FUNDED"
    with pytest.raises(ConflictError):
        market.cancel(tx.tx_id)


def test_cancel_of_missing_tx_raises(market):
    with pytest.raises(Exception):
        market.cancel("tx-nope")
