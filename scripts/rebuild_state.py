"""Rebuild live venue state after the audit-wipe: real deal -> claim -> appeal.
All money real (Base Sepolia USDC). Prints every hash."""
import json
import urllib.request

BASE = "https://canon-venue.vercel.app/api"
BUYER = "0x3991d5267e013fb9d5f2fbb30b8f3d8ff97c1ad9"
PROVIDER = "0x20fd7bec60829230a1cfbe4caf25a12ab2e49aa9"
PROVIDER2 = "0x31eafd3fe36d6c891ea5b369a876166dffabf320"


def post(path, payload, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)


# 1. real deal, provider fails, claim verified -> case on record
t = post("/evaluate", {"provider": PROVIDER, "job_type": "research", "job_value_usd": 2.0})
print("terms v" + str(t["terms"]["doctrine_version"]), "bond", t["terms"]["bond_usd"])
tx = post("/transactions", {"provider": PROVIDER, "job_type": "research", "job_value_usd": 2.0})["tx"]
tid = tx["tx_id"]
print("created", tid)
print("escrow:", str(post(f"/transactions/{tid}/execute", {})["tx"]["chain_ref"])[:20])
post(f"/transactions/{tid}/fail", {"provider": PROVIDER})
res = post(f"/transactions/{tid}/claim", {"evidence_source": "TX_VERIFIED", "note": "audit restore"})
print("claim:", str(res.get("claim_tx_hash"))[:20], "| doctrine v", res["result"]["doctrine_version_after"])

# 2. bond an appeal against the charter rule and win it -> doctrine v2
rule_id = get("/doctrine")["doctrine"]["rules"][0]["rule_id"]
ap = post("/appeals", {"challenger": PROVIDER2, "target_rule_id": rule_id,
                       "arguments": "bond disproportionate for first-time providers",
                       "evidence": [{"source": "ATTESTATION", "note": "restore"}],
                       "bond_usd": 5.0})
print("appeal:", str(ap.get("chain_ref") or "")[:20], ap.get("appeal", {}).get("appeal_id"))
r = post(f"/appeals/{ap['appeal']['appeal_id']}/resolve", {"decision": "ACCEPTED"})
print("resolved:", r.get("decision"), "-> doctrine v", r.get("doctrine_version") or r.get("doctrine", {}).get("version"))

st = get("/status")
print("LIVE STATE: doctrine v%s, cases %s" % (st.get("doctrine_version"), st.get("cases")))
