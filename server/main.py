"""CANON server — FastAPI wrapper over the real engine + real Sibyl Memory +
real Base Sepolia settlement (USDC).

Every money event mirrors to a genuine USDC transaction on Base Sepolia signed
by the operator key (env SETTLE_KEY / CANONMARKET_ADDRESS). When the chain is
not configured the settlement endpoints return an explicit error — nothing is
simulated, no fabricated hashes, no hardcoded chain references.

Memory-only endpoints (evaluate, doctrine, cases, judge lab) are the Sibyl
proofs and run regardless of chain config.

Run:  uvicorn server.main:app --port 8000  (from the repo root)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional

from canon import Canon
from canon.errors import CanonError
from canon.chain import ChainError, configured as chain_configured, env_chain, explorer_url
from scripts.seed_history import BUYER, PROVIDER, PROVIDER2, PROVIDER_VIRTUAL, JUDGE

ROOT = Path(__file__).resolve().parent.parent
# Persistent venue DB (env CANON_DB overrides; the live venue must not live in /tmp)
DEMO_DB = Path(os.environ.get("CANON_DB", str(Path(tempfile.gettempdir()) / "canon-server.db")))

# Load settlement env from the gitignored local env file (VPS uses systemd
# EnvironmentFile with the same keys). Never overrides real environment.
from canon.chain import load_env_file
load_env_file(ROOT / ".env.base-sepolia")

app = FastAPI(title="CANON", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_to_json(_, exc: Exception):
    """Never return a bare 500 shell — surface the real reason to the console."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500,
                        content={"error": f"{type(exc).__name__}: {exc}"})

market: dict[str, Any] = {"chain": {}}  # engine_id -> contract mirror registry


def _load_state(c: Canon, name: str, default):
    """Read a venue registry (txids / chain mirror) persisted as a WARM entity."""
    try:
        rec = c.seam.get_entity("market", name) or {}
        for probe in (rec, rec.get("body") or {}):
            if isinstance(probe, dict) and "value" in probe:
                return probe["value"]
    except Exception:
        pass
    return default


def _save_state(c: Canon, name: str, value) -> None:
    c.seam.set_entity("market", name, {"value": value})


def _persist(c: Canon) -> None:
    _save_state(c, "txids", market["txids"])
    _save_state(c, "chainmap", market["chain"])


def fresh_market() -> Canon:
    """Load the persistent venue market; a genuinely empty file is FOUNDED by
    charter (one declared rule, zero fabricated case evidence — see
    Canon.establish_charter). Never re-seeds on top of existing state."""
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    if DEMO_DB.exists() and DEMO_DB.stat().st_size > 0:
        canon = Canon(DEMO_DB)
    else:
        canon = Canon(DEMO_DB)
        canon.establish_charter()
    # admission is idempotent and runs every boot so venue members added after
    # founding (e.g. the Virtuals EconomyOS agent) are admitted on deploy
    for actor in (BUYER, PROVIDER, PROVIDER2, PROVIDER_VIRTUAL, JUDGE):
        canon.admit(actor)
    market["canon"] = canon
    market["txids"] = _load_state(canon, "txids", [])
    market["chain"] = _load_state(canon, "chainmap", {}) or {}
    return canon


def get_canon() -> Canon:
    c = market.get("canon")
    if c is None:
        c = fresh_market()
    return c


def err(exc: Exception) -> dict:
    return {"error": f"{type(exc).__name__}: {exc}"}


def ok(**kw) -> dict:
    return {"ok": True, **kw}


def terms_digest(terms: dict) -> str:
    """Canonical sha256 of the doctrine-generated terms — stored on-chain so
    post-funding tampering with the terms is visible to anyone."""
    canon = json.dumps(terms, sort_keys=True)
    return "0x" + hashlib.sha256(canon.encode()).hexdigest()


def chain_info(tx_dict: dict) -> dict:
    """Attach the real on-chain mirror + explorer links to an engine tx."""
    reg = market["chain"].get(tx_dict.get("tx_id")) or {}
    out = dict(tx_dict)
    out["chain"] = {"configured": chain_configured(), **reg}
    if reg.get("escrow"):
        out["chain_ref"] = reg["escrow"]
        out["explorer"] = explorer_url(reg["escrow"])
    return out


def chain_ctx():
    """Return the chain handle or raise a clear configuration error."""
    if not chain_configured():
        raise ChainError(
            "settlement chain not configured — set SETTLE_KEY + CANONMARKET_ADDRESS "
            "env (Base Sepolia), then create the deal again")
    return env_chain()


class EvaluateIn(BaseModel):
    provider: str = PROVIDER
    job_type: str = "research agent"
    job_value_usd: float = 20.0


class TxIn(BaseModel):
    provider: str = PROVIDER
    job_type: str = "research agent"
    job_value_usd: float = 20.0


class ActionIn(BaseModel):
    provider: str = PROVIDER


class ClaimIn(BaseModel):
    evidence_source: str = "TX_VERIFIED"   # TX_VERIFIED | ATTESTATION | TEXT
    note: str = "no delivery"


class AppealIn(BaseModel):
    challenger: str = PROVIDER2
    target_rule_id: str
    arguments: str
    bond_usd: float = 5.0
    evidence_source: str = "ATTESTATION"


class ResolveIn(BaseModel):
    decision: str = "ACCEPTED"


# ------------------------------------------------------------------ market
@app.get("/api/status")
def status():
    c = get_canon()
    try:
        st = ok(
            doctrine_version=c.doctrine_now().version,
            cases=len(c.cases.list_cases()),
            pool=c.pool_balance(),
            journal_ok=c.journal_ok()[0],
            actors={"buyer": BUYER, "provider_scarred": PROVIDER, "provider_new": PROVIDER2,
                    "adjudicator": JUDGE},
        )
        if chain_configured():
            ch = env_chain()
            # chain is authoritative for money: show the real on-chain pool
            st["pool"] = float(ch.pool_usdc())
            st.update(
                settlement="onchain",
                chain_id=ch.chain_id,
                venue_address=ch.venue,
                market_address=str(ch.market),
                usdc_balance_usd=str(ch.usdc_balance()),
                contract_usdc_usd=str(ch.contract_usdc()),
                pool_onchain_usd=str(ch.pool_usdc()),
            )
        else:
            st.update(settlement="not-configured",
                      note="set SETTLE_KEY + CANONMARKET_ADDRESS (Base Sepolia) to enable real settlement")
        return st
    except Exception as e:
        return err(e)


@app.post("/api/reset")
def reset():
    if DEMO_DB.exists():
        DEMO_DB.unlink()
    c = fresh_market()
    return ok(doctrine_version=c.doctrine_now().version,
              cases=len(c.cases.list_cases()))


# ------------------------------------------------------------------ flow
@app.post("/api/evaluate")
def evaluate(body: EvaluateIn):
    c = get_canon()
    try:
        t = c.evaluate(buyer=BUYER, provider=body.provider, job_type=body.job_type,
                       job_value_usd=body.job_value_usd)
        return ok(terms=t.to_dict())
    except CanonError as e:
        return err(e)


@app.post("/api/transactions")
def create_tx(body: TxIn):
    c = get_canon()
    try:
        t = c.evaluate(buyer=BUYER, provider=body.provider, job_type=body.job_type,
                       job_value_usd=body.job_value_usd)
        tx = c.create_tx(buyer=BUYER, provider=body.provider, job_type=body.job_type,
                         job_value_usd=body.job_value_usd, terms=t)
        # real on-chain registration under the doctrine terms digest
        ch = chain_ctx()
        cid, hash_ = ch.create_tx(
            buyer=BUYER, provider=body.provider,
            job_value_usd=body.job_value_usd, upfront_usd=t.upfront_usd,
            escrow_usd=float(sum(t.milestones) or 0.0), bond_usd=t.bond_usd,
            digest=terms_digest(t.to_dict()))
        market["chain"][tx.tx_id] = {"contract_id": cid, "create": hash_}
        market.setdefault("txids", []).append(tx.tx_id)
        _persist(c)
        return ok(tx=chain_info(tx.to_dict()), terms=t.to_dict())
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.get("/api/transactions")
def list_txs():
    c = get_canon()
    out = []
    for tid in market.get("txids", []):
        try:
            tx = c.venue.require_tx(tid)
            out.append(chain_info(tx.to_dict()))
        except Exception:
            pass
    out.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return ok(transactions=out)


@app.post("/api/transactions/{tx_id}/execute")
def execute(tx_id: str):
    c = get_canon()
    try:
        reg = market["chain"].get(tx_id)
        if not reg or not reg.get("contract_id"):
            raise ChainError("no on-chain registration for this tx (chain was off when created)")
        ch = chain_ctx()
        # money first: escrow + bond actually locked in USDC on Base Sepolia
        hash_ = ch.fund(reg["contract_id"])
        tx = c.execute(tx_id, chain_ref=hash_)
        market["chain"][tx_id]["escrow"] = hash_
        _persist(c)
        return ok(tx=chain_info(tx.to_dict()))
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/complete")
def complete(tx_id: str, body: ActionIn):
    c = get_canon()
    try:
        tx = c.complete(tx_id, provider=body.provider)
        reg = market["chain"].get(tx_id)
        if reg and reg.get("contract_id"):
            ch = chain_ctx()
            hash_ = ch.mark_completed(reg["contract_id"], ok=True)
            market["chain"][tx_id]["complete"] = hash_
            _persist(c)
        return ok(tx=chain_info(tx.to_dict()))
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/fail")
def fail(tx_id: str, body: ActionIn):
    c = get_canon()
    try:
        tx = c.fail(tx_id, provider=body.provider)
        reg = market["chain"].get(tx_id)
        if reg and reg.get("contract_id"):
            ch = chain_ctx()
            hash_ = ch.mark_completed(reg["contract_id"], ok=False)
            market["chain"][tx_id]["fail"] = hash_
            _persist(c)
        return ok(tx=chain_info(tx.to_dict()))
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/claim")
def claim(tx_id: str, body: ClaimIn):
    c = get_canon()
    try:
        reg = market["chain"].get(tx_id)
        if not reg or not reg.get("contract_id"):
            raise ChainError("no on-chain registration for this tx")
        res = c.file_and_resolve_claim(
            tx_id=tx_id, buyer=BUYER, verifier=JUDGE,
            evidence=[{"source": body.evidence_source, "note": body.note}])
        ch = chain_ctx()
        held = ch.tx_onchain(reg["contract_id"])
        # chain truth: refund what the contract actually holds for this tx
        escrow_refund = held["escrow_locked_usd"]
        coverage = float(ch.pool_usdc())  # only real pool funds can cover
        hash_ = ch.resolve_claim(reg["contract_id"], payee=BUYER,
                                 escrow_refund_usd=escrow_refund, coverage_usd=coverage)
        market["chain"][tx_id]["claim"] = hash_
        _persist(c)
        tx = c.venue.require_tx(tx_id)
        return ok(result=res, tx=chain_info(tx.to_dict()), claim_tx_hash=hash_,
                  claim_explorer=explorer_url(hash_),
                  escrow_refund_usd=escrow_refund, coverage_usd=coverage)
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.get("/api/transactions/{tx_id}")
def tx_detail(tx_id: str):
    c = get_canon()
    try:
        tx = c.venue.require_tx(tx_id)
        return ok(tx=chain_info(tx.to_dict()), provenance=c.provenance(tx_id))
    except CanonError as e:
        return err(e)


# --------------------------------------------------------------- state views
@app.get("/api/cases")
def cases():
    c = get_canon()
    return ok(cases=c.cases.list_cases())


@app.get("/api/doctrine")
def doctrine():
    c = get_canon()
    d = c.doctrine_now()
    versions = []
    for v in range(1, d.version + 1):
        try:
            versions.append(c.doctrine.load_doctrine(v).to_dict())
        except Exception:
            pass
    return ok(version=d.version, rules=[r.to_dict() for r in d.rules],
              versions=versions)


@app.post("/api/appeals")
def open_appeal(body: AppealIn):
    c = get_canon()
    try:
        a = c.open_appeal(challenger=body.challenger, target_rule_id=body.target_rule_id,
                          arguments=body.arguments,
                          evidence=[{"source": body.evidence_source, "note": "appeal"}],
                          bond_usd=body.bond_usd)
        # real appeal bond on Base Sepolia (venue advances as CCP)
        ch = chain_ctx()
        aid, hash_ = ch.open_appeal(body.challenger, body.target_rule_id, bond_usd=body.bond_usd)
        market["chain"].setdefault(f"appeal:{a.appeal_id}", {})["contract_id"] = aid
        market["chain"][f"appeal:{a.appeal_id}"]["open"] = hash_
        _persist(c)
        return ok(appeal=a.to_dict(), appeal_tx_hash=hash_, appeal_explorer=explorer_url(hash_))
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.post("/api/appeals/{appeal_id}/resolve")
def resolve_appeal(appeal_id: str, body: ResolveIn):
    c = get_canon()
    try:
        a = c.resolve_appeal(appeal_id, decision=body.decision, adjudicator=JUDGE)
        reg = market["chain"].get(f"appeal:{appeal_id}")
        if reg and reg.get("contract_id"):
            ch = chain_ctx()
            hash_ = ch.resolve_appeal(reg["contract_id"], accepted=body.decision == "ACCEPTED")
            market["chain"][f"appeal:{appeal_id}"]["resolve"] = hash_
            _persist(c)
        return ok(appeal=a.to_dict(), doctrine_version=c.doctrine_now().version)
    except CanonError as e:
        return err(e)
    except ChainError as e:
        return err(e)


@app.get("/api/appeals")
def appeals():
    c = get_canon()
    return ok(appeals=c.seam.list_entities("appeal"))


@app.get("/api/memory")
def memory_view():
    c = get_canon()
    events = []
    for ev in c.seam.read_events(limit=200):
        extra = ev.get("extra") or {}
        events.append({"seq": extra.get("seq"), "ts": ev.get("ts"),
                       "acted": ev.get("acted"), "event": extra.get("event"),
                       "hash": (extra.get("hash") or "")[:12]})
    return ok(journal_ok=c.journal_ok()[0], events=events[::-1])


@app.get("/api/chain")
def chain_view():
    """Transparency: every real settlement tx with its explorer link."""
    if not chain_configured():
        return ok(configured=False, note="settlement chain not configured")
    ch = env_chain()
    return ok(configured=True, chain_id=ch.chain_id, venue=ch.venue,
              market=str(ch.market), usdc_balance_usd=str(ch.usdc_balance()),
              contract_usdc_usd=str(ch.contract_usdc()), pool_usdc_usd=str(ch.pool_usdc()),
              mirror=market.get("chain", {}))


# ------------------------------------------------------------------ verification
@app.get("/api/verify/deletion")
def verify_deletion():
    """The real deletion gate against a copy of the LIVE market: remove the
    Sibyl layer and the venue cannot construct terms. No fixture, no seed."""
    try:
        src = DEMO_DB
        tmp = Path(tempfile.mktemp(suffix=".db"))
        if src.exists():
            # consistent copy: the venue db runs in SQLite WAL mode, so a raw
            # file copy misses committed data sitting in -wal
            con = sqlite3.connect(src)
            try:
                out = sqlite3.connect(tmp)
                try:
                    con.backup(out)
                finally:
                    out.close()
            finally:
                con.close()
        c = Canon(tmp)
        with_memory = c.doctrine_now().version
        c.seam.delete_all()
        fresh = Canon(tmp)
        refusal = None
        try:
            fresh.admit(BUYER)
            fresh.evaluate(buyer=BUYER, provider=PROVIDER,
                           job_type="research agent", job_value_usd=20.0)
        except CanonError as e:
            refusal = f"{type(e).__name__}: {e}"
        return ok(pass_=refusal is not None, doctrine_before=with_memory, refusal=refusal)
    except CanonError as e:
        return err(e)


@app.get("/api/health")
def health():
    return ok(engine="canon", up=True, ts=time.time())
