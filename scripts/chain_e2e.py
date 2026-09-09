"""CANON — reproducible real-chain end-to-end (Base Sepolia, real USDC).

Replays the entire venue loop against the LIVE deployment and prints every
transaction hash with its explorer link. Nothing is simulated: amounts come
from doctrine terms and each money event is a real USDC transfer signed from
env keys.

Run (from the repo root, after funding the venue + adjudicator wallets):
    source .env.base-sepolia   (exports SETTLE_KEY / ADJUDICATOR_KEY / CANONMARKET_ADDRESS)
    .venv/bin/python scripts/chain_e2e.py --db /tmp/e2e-canon.db

Budget: a --job 15 deal escrows ~14.3 USDC + a 5 USDC appeal bond fit one 20-USDC
drip; raise --job after more funding. --skip-appeal stops after the claim.

Exit 0 only when every step lands a receipt with status 1.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from canon.chain import ChainError, env_chain, explorer_url
from scripts.seed_history import BUYER, JUDGE, PROVIDER, PROVIDER2


def _admit_all(c: Canon) -> None:
    for actor in (BUYER, PROVIDER, PROVIDER2, JUDGE):
        c.admit(actor)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/tmp/e2e-canon.db")
    ap.add_argument("--job", type=float, default=15.0, help="job value in USD")
    ap.add_argument("--skip-appeal", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if db.exists():
        db.unlink()

    c = Canon(db)
    _admit_all(c)
    c.establish_charter()
    ch = env_chain()

    print(f"venue        {ch.venue}")
    print(f"adjudicator  {ch.adjudicator}   (split when setRoles executed)")
    print(f"market       {ch.market}")
    print(f"usdc venue   {ch.usdc_balance():.4f}")
    print(f"charter      v{c.doctrine_now().version} {c.doctrine_now().rules[0].rule_id} created_by={c.doctrine_now().rules[0].created_by_case}")

    # ------------------------------------------------------------------ deal
    t = c.evaluate(buyer=BUYER, provider=PROVIDER,
                   job_type="research agent", job_value_usd=args.job)
    print(f"\nterms        upfront {t.upfront_usd} · escrow {sum(t.milestones)} · "
          f"bond {t.bond_usd} · rule {t.rule_ids}")

    tx = c.create_tx(buyer=BUYER, provider=PROVIDER, job_type="research agent",
                     job_value_usd=args.job, terms=t)

    # canonical digest: sha256 of sorted terms json (same as the venue server)
    import hashlib, json
    digest = "0x" + hashlib.sha256(
        json.dumps(t.to_dict(), sort_keys=True).encode()).hexdigest()

    cid, h_create = ch.create_tx(buyer=BUYER, provider=PROVIDER,
                                  job_value_usd=args.job, upfront_usd=t.upfront_usd,
                                  escrow_usd=float(sum(t.milestones)),
                                  bond_usd=t.bond_usd, digest=digest)
    print(f"1 register   contract tx #{cid}  {explorer_url(h_create)}")

    h_fund = ch.fund(cid)
    tx = c.execute(tx.tx_id, chain_ref=h_fund)
    print(f"2 escrow     {explorer_url(h_fund)}   state={tx.state}")

    h_fail = ch.mark_completed(cid, ok=False)
    tx = c.fail(tx.tx_id, provider=PROVIDER)
    print(f"3 failed     {explorer_url(h_fail)}   state={tx.state}")

    held = ch.tx_onchain(cid)
    coverage = float(ch.pool_usdc())
    h_claim = ch.resolve_claim(cid, payee=BUYER,
                               escrow_refund_usd=held["escrow_locked_usd"],
                               coverage_usd=coverage)
    res = c.file_and_resolve_claim(tx_id=tx.tx_id, buyer=BUYER, verifier=JUDGE,
                                   evidence=[{"source": "TX_VERIFIED",
                                              "note": f"claim {h_claim}"}])
    print(f"4 claim      {explorer_url(h_claim)}   refund {held['escrow_locked_usd']} "
          f"+ bond {held['bond_usd']}  cases={len(c.cases.list_cases())}")

    # ------------------------------------------------------------------ appeal
    if not args.skip_appeal:
        a = c.open_appeal(challenger=PROVIDER2, target_rule_id="CANON-001-research",
                          arguments="real bonded appeal against the charter bond",
                          evidence=[{"source": "ATTESTATION", "note": "clean delivery record"}],
                          bond_usd=5.0)
        aid, h_open = ch.open_appeal(PROVIDER2, "CANON-001-research", bond_usd=5.0)
        print(f"5 appeal     #{aid}  {explorer_url(h_open)}")
        h_res = ch.resolve_appeal(aid, accepted=True)
        c.resolve_appeal(a.appeal_id, decision="ACCEPTED", adjudicator=JUDGE)
        doc = c.doctrine_now()
        print(f"6 amended    {explorer_url(h_res)}   doctrine v{doc.version} "
              f"rule={doc.rules[0].rule_id} bond_ratio={doc.rules[0].bond_ratio}")

    print("\nE2E PASS — every step above is a confirmed Base Sepolia transaction")
    print(f"usdc venue now {ch.usdc_balance():.4f} · contract {ch.contract_usdc():.4f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ChainError, Exception) as e:  # noqa: BLE001 - print and fail loudly
        print(f"E2E FAIL — {type(e).__name__}: {e}")
        sys.exit(1)
