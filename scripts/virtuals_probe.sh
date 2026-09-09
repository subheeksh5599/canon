#!/usr/bin/env bash
# Auto-verify Virtuals compute credits: polls the agent's compute endpoint.
# On first real 200 completion: writes proof, flips the README honesty row to
# EXERCISED with the real response id, commits and pushes. Never claims a 402.
set -u
KEY="acp-eb52e188614618c4e85b"
MARK="/home/arch/canon/docs/.virtuals-proof-committed"
LOG="/home/arch/canon/docs/virtuals-probe.log"
cd /home/arch/canon || exit 1

RESP=$(curl -s -m 45 https://compute.virtuals.io/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"moonshotai-kimi-k3-batch","messages":[{"role":"user","content":"Reply with exactly: CANON-OK"}],"max_tokens":16}' 2>/dev/null)

echo "$(date -u +%FT%TZ) ${RESP:0:120}" >> "$LOG"

if ! echo "$RESP" | grep -q '"choices"'; then
  exit 0  # still 402/insufficient — nothing to claim
fi

if [ -f "$MARK" ]; then exit 0; fi  # already flipped once

RID=$(echo "$RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('choices') or [{}])[0].get('message',{}).get('content','')[:40])" 2>/dev/null)
{
  echo "# Virtuals compute — exercised proof"
  echo ""
  echo "Real chat completion against the registered agent's Virtuals-hosted endpoint (model \`moonshotai-kimi-k3-batch\`)."
  echo ""
  echo '```json'
  echo "$RESP" | head -c 1200
  echo '```'
} > docs/virtuals-compute-proof.md

python3 - <<'PY'
import pathlib
p = pathlib.Path("README.md"); s = p.read_text()
old = "⚠️ its Virtuals compute endpoint returns 402 insufficient credits ($0 balance, DevRel approval pending) — the agent's inference isn't claimed"
new = "✅ its Virtuals-hosted compute endpoint returned a real completion (see docs/virtuals-compute-proof.md) — the agent's inference is exercised"
assert old in s, "target row text not found"
p.write_text(s.replace(old, new))
PY

git add README.md docs/virtuals-compute-proof.md
git -c user.name="subheeksh5599" -c user.email="komasubheeksh@gmail.com" commit -q -m "virtuals compute EXERCISED: real completion from the agent's Virtuals-hosted endpoint (Spark Tier credits active) — proof committed"
git push -q origin main && touch "$MARK" && echo "PROOF COMMITTED AND PUSHED"
