"""Real settlement: the registered Virtuals EconomyOS agent (Prov-03) transacts
inside the CANON venue. Venue advances escrow+bond (CCP), agent delivers, escrow
pays out to the agent's wallet 0x1776e.... All money real (Base Sepolia USDC)."""
import json
import urllib.request

BASE = "https://canon-venue.vercel.app/api"
AGENT = "0x1776eba1f2c74b141d0c337ffcdbb0e40d77876b"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


# 1. evaluate a $16 research job under the live doctrine (charter v2)
t = post("/evaluate", {"provider": AGENT, "job_type": "research", "job_value_usd": 16.0})
print("terms:", json.dumps(t.get("terms", t), indent=0)[:400])
escrow = sum(m if isinstance(m, (int, float)) else m["amount"] for m in (t.get("terms") or {}).get("milestones", []))
bond = (t.get("terms") or {}).get("bond_usd")
print(f"escrow {escrow} + bond {bond} = {escrow + bond}")

# 2. create (registers on-chain)
tx = post("/transactions", {"provider": AGENT, "job_type": "research", "job_value_usd": 16.0})
print("create response:", json.dumps(tx)[:400])
tid = tx["tx"]["tx_id"]
print("created:", tid)

# 3. execute — venue advances escrow + bond (real USDC pull)
ex = post(f"/transactions/{tid}/execute", {})
print("executed:", ex.get("detail") or ex.get("chain_ref") or ex)

# 4. complete — the agent delivers; escrow pays out to the agent wallet
co = post(f"/transactions/{tid}/complete", {"provider": AGENT})
print("completed:", json.dumps(co)[:300])
