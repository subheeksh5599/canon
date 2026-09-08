"""CANON server — FastAPI wrapper over the real engine + real Sibyl Memory.

Every endpoint runs the actual Canon engine on a local Sibyl file. Nothing is
mocked: terms come from doctrine stored in Sibyl, the journal is chain-hashed,
and the judge-lab endpoints run the same proofs as the CLI gate artifacts.

Run:  uvicorn server.main:app --port 8000  (from the repo root)
"""
from __future__ import annotations

import hashlib
import os
import shutil
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
from scripts.seed_history import BUYER, PROVIDER, PROVIDER2, JUDGE, seed

ROOT = Path(__file__).resolve().parent.parent
DEMO_DB = Path(tempfile.gettempdir()) / "canon-server.db"
SIM_CHAIN = "0x" + "c" * 40  # local simulated settlement marker (no key loaded)

app = FastAPI(title="CANON", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

market: dict[str, Any] = {}


def fresh_market() -> Canon:
    canon = Canon(DEMO_DB)
    seed(canon)
    market["canon"] = canon
    market["txids"] = []
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


class EvaluateIn(BaseModel):
    provider: str = PROVIDER
    job_type: str = "research agent"
    job_value_usd: float = 400.0


class TxIn(BaseModel):
    provider: str = PROVIDER
    job_type: str = "research agent"
    job_value_usd: float = 400.0


class ActionIn(BaseModel):
    provider: str = PROVIDER


class ClaimIn(BaseModel):
    evidence_source: str = "TX_VERIFIED"   # TX_VERIFIED | ATTESTATION | TEXT
    note: str = "no delivery"


class AppealIn(BaseModel):
    challenger: str = PROVIDER2
    target_rule_id: str
    arguments: str
    bond_usd: float = 20.0
    evidence_source: str = "ATTESTATION"


class ResolveIn(BaseModel):
    decision: str = "ACCEPTED"


# ------------------------------------------------------------------ market
@app.get("/api/status")
def status():
    c = get_canon()
    try:
        return ok(
            doctrine_version=c.doctrine_now().version,
            cases=len(c.cases.list_cases()),
            pool=c.pool_balance(),
            journal_ok=c.journal_ok()[0],
            actors={"buyer": BUYER, "provider_scarred": PROVIDER, "provider_new": PROVIDER2,
                    "adjudicator": JUDGE},
            db=str(DEMO_DB),
            simulated_settlement=True,
            note="local demo settlement marker — Base deployment pending key",
        )
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
        market.setdefault("txids", []).append(tx.tx_id)
        return ok(tx=tx.to_dict(), terms=t.to_dict())
    except CanonError as e:
        return err(e)


@app.get("/api/transactions")
def list_txs():
    c = get_canon()
    out = []
    for tid in market.get("txids", []):
        try:
            tx = c.venue.require_tx(tid)
            out.append(tx.to_dict())
        except Exception:
            pass
    out.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return ok(transactions=out)


@app.post("/api/transactions/{tx_id}/execute")
def execute(tx_id: str):
    c = get_canon()
    try:
        tx = c.execute(tx_id, chain_ref=f"0x{SIM_CHAIN}{uuid.uuid4().hex[:8]}")
        return ok(tx=tx.to_dict())
    except CanonError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/complete")
def complete(tx_id: str, body: ActionIn):
    c = get_canon()
    try:
        tx = c.complete(tx_id, provider=body.provider)
        return ok(tx=tx.to_dict())
    except CanonError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/fail")
def fail(tx_id: str, body: ActionIn):
    c = get_canon()
    try:
        tx = c.fail(tx_id, provider=body.provider)
        return ok(tx=tx.to_dict())
    except CanonError as e:
        return err(e)


@app.post("/api/transactions/{tx_id}/claim")
def claim(tx_id: str, body: ClaimIn):
    c = get_canon()
    try:
        res = c.file_and_resolve_claim(
            tx_id=tx_id, buyer=BUYER, verifier=JUDGE,
            evidence=[{"source": body.evidence_source, "note": body.note}])
        return ok(result=res)
    except CanonError as e:
        return err(e)


@app.get("/api/transactions/{tx_id}")
def tx_detail(tx_id: str):
    c = get_canon()
    try:
        tx = c.venue.require_tx(tx_id)
        return ok(tx=tx.to_dict(), provenance=c.provenance(tx_id))
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
        return ok(appeal=a.to_dict())
    except CanonError as e:
        return err(e)


@app.post("/api/appeals/{appeal_id}/resolve")
def resolve_appeal(appeal_id: str, body: ResolveIn):
    c = get_canon()
    try:
        a = c.resolve_appeal(appeal_id, decision=body.decision, adjudicator=JUDGE)
        return ok(appeal=a.to_dict(), doctrine_version=c.doctrine_now().version)
    except CanonError as e:
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


# ----------------------------------------------------------------- judge lab
def _naive_terms():
    tmp = Path(tempfile.mktemp(suffix=".db"))
    c = Canon(tmp)
    c.admit(BUYER)
    c.admit(PROVIDER2)
    return c.evaluate(buyer=BUYER, provider=PROVIDER2,
                      job_type="research agent", job_value_usd=400.0).to_dict()


@app.get("/api/judge/coldstart")
def judge_coldstart():
    try:
        tmp = Path(tempfile.mktemp(suffix=".db"))
        c = Canon(tmp)
        seed(c)
        c.admit(PROVIDER2)
        recalled = c.evaluate(buyer=BUYER, provider=PROVIDER2,
                              job_type="research agent", job_value_usd=400.0).to_dict()
        naive = _naive_terms()
        return ok(pass_=naive["bond_usd"] == 0.0 and recalled["bond_usd"] > 0.0,
                  virgin_terms=naive, recalled_terms=recalled,
                  doctrine_version=c.doctrine_now().version, ts=c.clock.iso())
    except CanonError as e:
        return err(e)


@app.get("/api/judge/deletion")
def judge_deletion():
    try:
        # copy the live db so the demo market survives the test
        src = DEMO_DB
        tmp = Path(tempfile.mktemp(suffix=".db"))
        if src.exists():
            shutil.copy2(src, tmp)
        c = Canon(tmp)
        with_memory = c.doctrine_now().version
        c.seam.delete_all()
        fresh = Canon(tmp)
        refusal = None
        try:
            fresh.admit(BUYER)
            fresh.evaluate(buyer=BUYER, provider=PROVIDER,
                           job_type="research agent", job_value_usd=400.0)
        except CanonError as e:
            refusal = f"{type(e).__name__}: {e}"
        return ok(pass_=refusal is not None, doctrine_before=with_memory, refusal=refusal)
    except CanonError as e:
        return err(e)


@app.get("/api/judge/ablation")
def judge_ablation():
    try:
        naive = _naive_terms()
        tmp = Path(tempfile.mktemp(suffix=".db"))
        c = Canon(tmp)
        seed(c)
        c.admit(PROVIDER2)
        governed = c.evaluate(buyer=BUYER, provider=PROVIDER2,
                              job_type="research agent", job_value_usd=400.0).to_dict()
        return ok(pass_=governed["bond_usd"] > naive["bond_usd"],
                  naive=naive, governed=governed,
                  reduction=round(1 - governed["upfront_usd"] / naive["upfront_usd"], 4))
    except CanonError as e:
        return err(e)


@app.get("/api/health")
def health():
    return ok(engine="canon", up=True, ts=time.time())
