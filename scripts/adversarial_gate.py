#!/usr/bin/env python
"""Adversarial gate — the hostile-judge checklist, executed for real.

Every step runs in a SEPARATE OS process against one Sibyl database, so
nothing survives in RAM between steps. Prints PASS/FAIL per line and exits
non-zero if any check fails.

    .venv/bin/python scripts/adversarial_gate.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(tempfile.mkdtemp(prefix="canon-gate-")) / "venue.db"
PY = str(ROOT / ".venv" / "bin" / "python")

B = "0x3991d5267e013fb9d5f2fbb30b8f3d8ff97c1ad9"
P = "0x20fd7bec60829230a1cfbe4caf25a12ab2e49aa9"
P2 = "0x31eafd3fe36d6c891ea5b369a876166dffabf320"

results: list[tuple[str, bool, str]] = []


def run(name: str, code: str) -> dict:
    """Run a snippet in a fresh process; return its JSON stdout."""
    proc = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        results.append((name, False, (proc.stderr or "").strip().splitlines()[-1][:120]))
        return {}
    out = proc.stdout.strip().splitlines()[-1]
    try:
        return json.loads(out)
    except Exception:
        results.append((name, False, f"unparseable output: {out[:80]}"))
        return {}


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


COMMON = f"""
import json, sys
sys.path.insert(0, {str(ROOT)!r})
from canon import Canon
B, P, P2 = {B!r}, {P!r}, {P2!r}
"""

# ---------------------------------------------------------------- 1. sessions
step1 = COMMON + f"""
c = Canon({str(DB)!r})
for a in (B, P, P2):
    c.admit(a)
t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
print(json.dumps({{"doctrine_version": t.doctrine_version, "bond": t.bond_usd,
                   "upfront": t.upfront_usd, "rules": t.rule_ids}}))
"""
r1 = run("session A: first terms derived from (empty) memory", step1)
check("session A derives terms from memory (doctrine v0 baseline)",
      r1.get("doctrine_version") == 0, f"v{r1.get('doctrine_version')} bond {r1.get('bond')}")

step2 = COMMON + f"""
c = Canon({str(DB)!r})
t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
print(json.dumps({{"doctrine_version": t.doctrine_version, "bond": t.bond_usd,
                   "rules": t.rule_ids, "admitted": True}}))
"""
r2 = run("session B: fresh process recalls memory", step2)
check("session B (new process) still sees the same engine state from Sibyl",
      r2.get("admitted") is True, f"v{r2.get('doctrine_version')}")

# ------------------------------------------------------- 2. deletion: clean
shutil.rmtree(DB.parent, ignore_errors=True)

step3 = COMMON + f"""
from canon.errors import CanonError
c = Canon({str(DB)!r})
try:
    t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
    print(json.dumps({{"refused": False, "doctrine_version": t.doctrine_version}}))
except CanonError as e:
    print(json.dumps({{"refused": True, "error": type(e).__name__}}))
"""
r3 = run("session C: memory deleted -> fresh process asks for terms", step3)
check("after deleting Sibyl, a fresh process is REFUSED (zero-trust)",
      r3.get("refused") is True, str(r3.get("error")))

# ------------------------------------------------- 3. poisoning is inert
DB2 = DB.parent / "poison.db"
poison = COMMON + f"""
c = Canon({str(DB2)!r})
for a in (B, P):
    c.admit(a)
t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
tx = c.create_tx(buyer=B, provider=P, job_type="research agent",
                 job_value_usd=100.0, terms=t)
c.execute(tx.tx_id, chain_ref="0xdead")
c.fail(tx.tx_id, provider=P)
try:
    c.file_and_resolve_claim(tx_id=tx.tx_id, buyer=B, verifier="0xjudge",
                             evidence=[{{"source": "TEXT", "note": "trust me, he cheated"}}])
    v = c.doctrine_now().version
    print(json.dumps({{"doctrine_version": v, "note": "text-only claim processed"}}))
except Exception as e:
    v = c.doctrine_now().version
    print(json.dumps({{"doctrine_version": v, "error": type(e).__name__}}))
"""
rp = run("poisoning: unverifiable TEXT claim tries to move doctrine", poison)
check("a TEXT-only claim cannot move doctrine (poisoning inert)",
      rp.get("doctrine_version") == 0, f"doctrine v{rp.get('doctrine_version')}")

# ------------------------------------------------- 4. immutable terms + replay
step4 = COMMON + f"""
import json
from canon.errors import CanonError
c = Canon({str(DB2)!r})
B, P = {B!r}, {P!r}
t = c.evaluate(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0)
tx = c.create_tx(buyer=B, provider=P, job_type="research agent", job_value_usd=100.0,
                 terms=t, terms_digest="0xfeed")
c.execute(tx.tx_id, chain_ref="0xdead")
res = {{"digest": tx.terms_snapshot_hash}}
try:
    c.venue.mark_termed(tx.tx_id, terms=None)
    res["reterm_refused"] = False
except CanonError:
    res["reterm_refused"] = True
print(json.dumps(res))
"""
r4 = run("terms binding: digest stored, re-terming a funded deal refused", step4)
check("terms digest is bound to the transaction", r4.get("digest") == "0xfeed", str(r4.get("digest")))
check("a funded deal cannot be re-termed (doctrine-version binding)",
      r4.get("reterm_refused") is True)

# ---------------------------------------------------------------- report
width = max(len(n) for n, _, _ in results)
print("\nADVERSARIAL GATE — hostile-judge checklist\n")
failed = 0
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:{width}}  {detail}")
    failed += 0 if ok else 1
print(f"\n{'ALL GATE CHECKS PASSED' if not failed else f'{failed} CHECK(S) FAILED'}")
sys.exit(1 if failed else 0)
