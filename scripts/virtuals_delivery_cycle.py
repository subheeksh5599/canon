"""Real cycle: the Virtuals agent delivers work produced on its OWN Virtuals-hosted
compute, and the venue settles it in USDC. Every step real."""
import json
import urllib.request

BASE = "https://canon-venue.vercel.app/api"
AGENT = "0x1776eba1f2c74b141d0c337ffcdbb0e40d77876b"


def post(path, payload=None, timeout=240):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


import os
JOB = float(os.environ.get("JOB_USD", "3.0"))
t = post("/evaluate", {"provider": AGENT, "job_type": "research", "job_value_usd": JOB})
print("terms: v%s escrow %.2f bond %.2f" % (
    t["terms"]["doctrine_version"], sum(t["terms"]["milestones"]), t["terms"]["bond_usd"]))

tx = post("/transactions", {"provider": AGENT, "job_type": "research", "job_value_usd": JOB})["tx"]
tid = tx["tx_id"]
print("tx:", tid, "| terms digest:", tx.get("terms_snapshot_hash"))

print("escrow:", post(f"/transactions/{tid}/execute")["tx"]["chain_ref"])

d = post(f"/virtuals/deliver/{tid}")
print("VIRTUALS COMPUTE generation:", d["generation"], "| model:", d["model"])
print("deliverable:", d["content"][:220].replace("\n", " "))
print("cost $:", (d.get("usage") or {}).get("cost"))

done = post(f"/transactions/{tid}/complete", {"provider": AGENT})["tx"]
print("state:", done["state"])
print("chain:", {k: (v[:18] if isinstance(v, str) else v) for k, v in (done.get("chain") or {}).items()})
