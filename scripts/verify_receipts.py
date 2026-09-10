#!/usr/bin/env python
"""Re-verify every on-chain claim in the README, live, over RPC.

Usage:  .venv/bin/python scripts/verify_receipts.py
Exits non-zero if any receipt fails, so it doubles as a gate.
"""
import sys
from pathlib import Path

from web3 import Web3

RPC = "https://sepolia.base.org"
MARKET = "0x802d15d159B15F91f1663D2b86e90132F6da4D06"
VENUE = "0x087ef173fb6F253DabFa89fA3a7756C5E8b1A1dA"
ADJUDICATOR = "0x617B0e8d15c3A48dDF2EC70AB17bF7CC7DbF3046"
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7E"
AGENT = "0x1776eba1f2c74b141d0c337ffcdbb0e40d77876b"

# every hash quoted in the README receipts
TXS = {
    "deploy CanonMarket": "0xfe5bdfd3ff688ae34c7d9f0282022783e2f28bc6cd5082c4963a216bffa0c346",
    "run 1 register": "0x80bb3cb9da46a18be896bef1fb2e4c88149624a9a3a7aaa06a4f57c5ddf471eb",
    "run 1 escrow": "0x9153c66f5be882235b4facd0c82098002091cce24332b8de524fe0e491ebb9b7",
    "run 1 claim": "0x26de681aa4f64f3c2e123e1e67935c52613be52c7b5f8388548adfb5cfe045b1",
    "run 1 final": "0x8fad0e3707ac773c18ec9e25679caa374fd65936ae7fd2d85d8e37a9c22e1c9f",
    "roles split": "0xa00e04186511a6e97ac87fef5ca5fdfb6bb0965d975ab397f63949c29a5ea47d",
    "charter register $16": "0xd956af44165f06995141c2b683ce5980857b8eff706d9a4995fa0e8d3bff175c",
    "charter escrow": "0x67c0dc0d3487ab9342e23b4c2af3ff4b036e0981680d0c9a0ce48696015cb2da",
    "charter fail": "0x1788ccde346239f4968b93a9c5e35cf7e2ae56ca062845f4ed9c9f57802116b8",
    "charter claim (adjudicator)": "0xc2deaefd772dfb169788e2825330848635b790490ac24e6930ea8ccb7abe3e29",
    "appeal open ($5 bond)": "0xcb3f5465f4d33240d0c7b2a631b9433969e470ff302d4e57ff2084b2c2053402",
    "appeal accepted -> v2": "0xd3e09df285d643a04210f4dac0f741380fed11f3ab754417a3873be74c6c88e6",
    "agent deal register": "0x3b3020d64fc1cc2199d02e499067d906b6b1236e1a042d615b79b5784c3bff71",
    "agent deal escrow": "0x28dd0366e1e67e231eb1926078f75309fde63fea6102c7c5f922297e176474d1",
    "agent deal payout ($9.60 -> agent)": "0x292c599db990f78c038091667a0528888fdda1683be4e603374326fac5323690",
}


def main() -> int:
    w3 = Web3(Web3.HTTPProvider(RPC))
    if not w3.is_connected():
        print("RPC unreachable:", RPC)
        return 2
    bad = 0
    print(f"{'receipt':44s} status")
    for label, h in TXS.items():
        try:
            r = w3.eth.get_transaction_receipt(Web3.to_hex(hexstr=h))
            ok = r["status"] == 1
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"{label:44s} ERROR {type(e).__name__}")
        print(f"{label:44s} {'OK' if ok else 'FAIL'}")
        bad += 0 if ok else 1

    def bal(addr):
        c = w3.eth.contract(address=Web3.to_checksum_address(USDC),
                            abi=[{"name": "balanceOf", "type": "function", "stateMutability": "view",
                                  "inputs": [{"name": "a", "type": "address"}],
                                  "outputs": [{"name": "", "type": "uint256"}]}])
        return c.functions.balanceOf(Web3.to_checksum_address(addr)).call() / 1e6

    def role(name):
        c = w3.eth.contract(address=Web3.to_checksum_address(MARKET),
                            abi=[{"name": name, "type": "function", "stateMutability": "view",
                                  "inputs": [], "outputs": [{"name": "", "type": "address"}]}])
        return c.functions[name]().call()

    print("\nroles and balances (live)")
    print(" venue          ", role("venue"), "usdc", bal(VENUE))
    print(" adjudicator    ", role("adjudicator"), "usdc", bal(ADJUDICATOR))
    print(" contract usdc  ", bal(MARKET))
    print(" virtuals agent ", bal(AGENT))

    print(f"\n{'ALL RECEIPTS VERIFIED' if bad == 0 else f'{bad} FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
