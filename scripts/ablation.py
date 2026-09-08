"""Gate artifact 3 — ablation: history-aware CANON vs memoryless CANON.

Same venue, same agents, same job, same capital. Only memory differs.
Reports the measurable memory delta: upfront required, bond required,
coverage, repeat-failure terms.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canon import Canon
from scripts.seed_history import BUYER, PROVIDER2  # noqa: F401
from scripts.seed_history import seed

JOB = {"buyer": BUYER, "provider": PROVIDER2, "job_type": "research agent", "job_value_usd": 400.0}


def main() -> int:
    import tempfile

    # memoryless arm: fresh db, no history
    blank = Canon(tempfile.mktemp(suffix=".db"))
    blank.admit(BUYER)
    blank.admit(PROVIDER2)
    naive = blank.evaluate(**JOB)

    # history-aware arm: same request against a seeded market
    aware = Canon(tempfile.mktemp(suffix=".db"))
    seed(aware)
    aware.admit(PROVIDER2)
    governed = aware.evaluate(**JOB)

    print("ABLATION  history-aware CANON vs memoryless CANON")
    print(f"  memoryless : upfront {naive.upfront_usd:>8.2f}  bond {naive.bond_usd:>6.2f}  coverage {naive.coverage_ratio}  doctrine v{naive.doctrine_version}")
    print(f"  history    : upfront {governed.upfront_usd:>8.2f}  bond {governed.bond_usd:>6.2f}  coverage {governed.coverage_ratio}  doctrine v{governed.doctrine_version}")
    upfront_reduction = 1 - governed.upfront_usd / naive.upfront_usd
    print(f"  capital at risk reduced by {upfront_reduction:.0%} on identical work")
    assert naive.bond_usd == 0.0 and governed.bond_usd > 0.0
    return 0


if __name__ == "__main__":
    sys.exit(main())
