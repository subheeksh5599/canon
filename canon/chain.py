"""CANON — Base Sepolia settlement (real USDC, real transactions).

Every money event in the demo mirrors to a genuine USDC transfer on Base
Sepolia, signed by the venue operator key (env: SETTLE_KEY). Nothing here is
simulated: amounts are token units pulled from the engine's terms, and each
call returns a real transaction hash.

Contract topology (CanonMarket.sol):
  - venue = operator wallet (SETTLE_KEY) — advances escrow/bonds (CCP model)
  - adjudicator = same operator key in the demo (setRoles can split later)
  - token  = USDC on Base Sepolia
  - Tx/Appeal ids returned by the contract are mirrored by engine ids in the
    server registry (market["chain"]).
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from web3 import Web3
from web3.exceptions import ContractLogicError

USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7E"
RPC_DEFAULT = "https://sepolia.base.org"
EXPLORER = "https://sepolia.basescan.org"

# ------------------------------------------------------------------ ABI (minimal)
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "a", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"constant": False, "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable",
     "type": "function"},
    {"constant": True, "inputs": [{"name": "o", "type": "address"}, {"name": "s", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view",
     "type": "function"},
]

MARKET_ABI = [
    {"inputs": [{"name": "i", "type": "uint256"}], "name": "txs",
     "outputs": [{"name": "buyer", "type": "address"}, {"name": "provider", "type": "address"},
                 {"name": "jobValue", "type": "uint256"}, {"name": "upfront", "type": "uint256"},
                 {"name": "escrowLocked", "type": "uint256"}, {"name": "bond", "type": "uint256"},
                 {"name": "status", "type": "uint8"}, {"name": "termsDigest", "type": "string"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "pool", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "venue", "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "adjudicator", "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token", "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "txCounter", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "appealCounter", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "buyer", "type": "address"}, {"name": "provider", "type": "address"},
                 {"name": "jobValue", "type": "uint256"}, {"name": "upfront", "type": "uint256"},
                 {"name": "milestoneTotal", "type": "uint256"}, {"name": "bond", "type": "uint256"},
                 {"name": "termsDigest", "type": "string"}], "name": "createTransaction",
     "outputs": [{"name": "txId", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "txId", "type": "uint256"}], "name": "fund",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "txId", "type": "uint256"}, {"name": "milestoneIndex", "type": "uint256"},
                 {"name": "amount", "type": "uint256"}], "name": "releaseMilestone",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "txId", "type": "uint256"}, {"name": "ok", "type": "bool"}],
     "name": "markCompleted", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "txId", "type": "uint256"}, {"name": "payee", "type": "address"},
                 {"name": "escrowRefund", "type": "uint256"}, {"name": "coverage", "type": "uint256"}],
     "name": "resolveClaim", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "challenger", "type": "address"}, {"name": "targetRuleId", "type": "string"},
                 {"name": "bondAmount", "type": "uint256"}], "name": "openAppeal",
     "outputs": [{"name": "appealId", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "appealId", "type": "uint256"}, {"name": "accepted", "type": "bool"},
                 {"name": "refundChallenger", "type": "bool"}], "name": "resolveAppeal",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "txId", "type": "uint256"}], "name": "cancel",
     "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]

GAS = 300_000


class ChainError(Exception):
    """A real transaction failed or the chain is not configured."""


class Chain:
    def __init__(self, rpc: str, key: str, market: str, token: str = USDC_BASE_SEPOLIA):
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        if not self.w3.is_connected():
            raise ChainError(f"cannot reach {rpc}")
        self.key = key
        self.venue = Web3.to_checksum_address(self.w3.eth.account.from_key(key).address)
        self.market = Web3.to_checksum_address(market)
        self.token = Web3.to_checksum_address(token)
        self._market_c = self.w3.eth.contract(address=self.market, abi=MARKET_ABI)
        self._token_c = self.w3.eth.contract(address=self.token, abi=ERC20_ABI)
        self.chain_id = self.w3.eth.chain_id

    # ------------------------------------------------------------- reads
    def usdc_balance(self, who: Optional[str] = None) -> Decimal:
        addr = Web3.to_checksum_address(who or self.venue)
        raw = self._token_c.functions.balanceOf(addr).call()
        return Decimal(raw) / Decimal(1_000_000)

    def pool_usdc(self) -> Decimal:
        return Decimal(self._market_c.functions.pool().call()) / Decimal(1_000_000)

    def contract_usdc(self) -> Decimal:
        return self.usdc_balance(str(self.market))

    def tx_onchain(self, contract_id: int) -> dict:
        b, p, jv, up, esc, bnd, st, digest = self._market_c.functions.txs(contract_id).call()
        return {"buyer": b, "provider": p, "job_value_usd": jv / 1e6,
                "escrow_locked_usd": esc / 1e6, "bond_usd": bnd / 1e6,
                "status": st, "terms_digest": digest}

    # ------------------------------------------------------------- send
    def _send(self, fn, label: str) -> str:
        try:
            tx = fn.build_transaction({
                "from": self.venue, "nonce": self.w3.eth.get_transaction_count(self.venue),
                "gas": GAS, "gasPrice": self.w3.eth.gas_price,
                "chainId": self.chain_id,
            })
        except ContractLogicError as e:
            raise ChainError(f"{label}: {e}") from e
        signed = self.w3.eth.account.sign_transaction(tx, self.key)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=90, poll_latency=2)
        if rcpt.status != 1:
            raise ChainError(f"{label}: reverted {h.hex()}")
        return h.hex()

    def _ensure_allowance(self) -> None:
        cur = self._token_c.functions.allowance(self.venue, self.market).call()
        if cur < 2 ** 128:
            fn = self._token_c.functions.approve(self.market, 2 ** 255 - 1)
            self._send(fn, "approve USDC")

    @staticmethod
    def usd_to_units(usd: float) -> int:
        return int(round(float(usd) * 1_000_000))

    # ------------------------------------------------------------- ops
    def create_tx(self, buyer: str, provider: str, job_value_usd: float, upfront_usd: float,
                  escrow_usd: float, bond_usd: float, digest: str) -> tuple[int, str]:
        fn = self._market_c.functions.createTransaction(
            Web3.to_checksum_address(buyer), Web3.to_checksum_address(provider),
            self.usd_to_units(job_value_usd), self.usd_to_units(upfront_usd),
            self.usd_to_units(escrow_usd), self.usd_to_units(bond_usd), digest)
        h = self._send(fn, "createTransaction")
        rcpt = self.w3.eth.get_transaction_receipt(h)
        cid = None
        for log in rcpt.logs:
            if log.address.lower() == self.market.lower() and len(log.topics) >= 2:
                cid = int.from_bytes(log.topics[1], "big")  # indexed txId
        if cid is None:
            # fall back to counter read post-tx
            cid = self._market_c.functions.txCounter().call()
        return cid, h

    def fund(self, contract_id: int) -> str:
        self._ensure_allowance()
        return self._send(self._market_c.functions.fund(contract_id), "fund escrow+bond")

    def mark_completed(self, contract_id: int, ok: bool) -> str:
        return self._send(self._market_c.functions.markCompleted(contract_id, ok),
                          "markCompleted")

    def resolve_claim(self, contract_id: int, payee: str, escrow_refund_usd: float,
                      coverage_usd: float) -> str:
        return self._send(self._market_c.functions.resolveClaim(
            contract_id, Web3.to_checksum_address(payee),
            self.usd_to_units(escrow_refund_usd), self.usd_to_units(coverage_usd)),
            "resolveClaim")

    def open_appeal(self, challenger: str, rule_id: str, bond_usd: float) -> tuple[int, str]:
        self._ensure_allowance()
        fn = self._market_c.functions.openAppeal(
            Web3.to_checksum_address(challenger), rule_id, self.usd_to_units(bond_usd))
        h = self._send(fn, "openAppeal")
        aid = None
        for log in self.w3.eth.get_transaction_receipt(h).logs:
            if log.address.lower() == self.market.lower() and len(log.topics) >= 2:
                aid = int.from_bytes(log.topics[1], "big")
        return aid or self._market_c.functions.appealCounter().call(), h

    def resolve_appeal(self, appeal_id: int, accepted: bool) -> str:
        return self._send(self._market_c.functions.resolveAppeal(
            appeal_id, accepted, accepted), "resolveAppeal")


_chain: Optional[Chain] = None
_configured: Optional[bool] = None


def load_env_file(path: Path | str | None = None) -> None:
    """Load KEY=VALUE lines (no dotenv dep). Never overrides real env."""
    p = Path(path) if path else Path(__file__).resolve().parent.parent / ".env.base-sepolia"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def env_chain() -> Chain:
    """Build from env: BASE_RPC_URL, SETTLE_KEY, CANONMARKET_ADDRESS."""
    global _chain, _configured
    key = os.environ.get("SETTLE_KEY", "").strip()
    market = os.environ.get("CANONMARKET_ADDRESS", "").strip()
    rpc = os.environ.get("BASE_RPC_URL", RPC_DEFAULT).strip()
    if not key or not market:
        _configured = False
        raise ChainError("chain not configured: SETTLE_KEY and CANONMARKET_ADDRESS env required")
    if _chain is None or _configured is False:
        _chain = Chain(rpc, key, market)
        _configured = True
    return _chain


def configured() -> bool:
    try:
        env_chain()
        return True
    except ChainError:
        return False


def explorer_url(tx_hash: str) -> str:
    return f"{EXPLORER}/tx/{tx_hash}"
