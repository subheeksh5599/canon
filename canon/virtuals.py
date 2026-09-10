"""canon/virtuals.py — the venue's Virtuals EconomyOS integration.

The registered agent ("Canon Venue Provider") produces its deliverable through
its own Virtuals-hosted compute endpoint. The venue records the generation id
and the real response with the job, so the settlement is tied to work the agent
actually produced on the Virtuals stack — not a scripted string.

Env: VIRTUALS_API_KEY (never committed), VIRTUALS_COMPUTE_URL (default below).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "https://compute.virtuals.io/v1/chat/completions"
DEFAULT_MODEL = "deepseek-deepseek-chat"


class VirtualsComputeError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("VIRTUALS_API_KEY"))


def generate(prompt: str, *, model: str | None = None,
             max_tokens: int = 200, timeout: int = 90) -> dict:
    """One real completion on the agent's Virtuals-hosted compute.

    Returns {generation_id, model, content, usage}. Raises on any non-200 so a
    caller can never mistake a failure for a deliverable.
    """
    key = os.environ.get("VIRTUALS_API_KEY")
    if not key:
        raise VirtualsComputeError("VIRTUALS_API_KEY not configured")
    body = json.dumps({
        "model": model or os.environ.get("VIRTUALS_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        os.environ.get("VIRTUALS_COMPUTE_URL", DEFAULT_URL), data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:  # noqa: PERF203
        raise VirtualsComputeError(f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}") from e
    except Exception as e:  # noqa: BLE001
        raise VirtualsComputeError(f"{type(e).__name__}: {e}") from e

    choices = payload.get("choices") or []
    if not choices:
        raise VirtualsComputeError(f"no choices in response: {str(payload)[:200]}")
    return {
        "generation_id": payload.get("id"),
        "model": payload.get("model"),
        "content": (choices[0].get("message") or {}).get("content", ""),
        "usage": payload.get("usage") or {},
    }
