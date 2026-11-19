#!/usr/bin/env python3
# version: 0.1.0
"""Record tests/fixtures/046-t3-1-period-read-golden/{month,week}.json from
the `read_period` of the source tree passed as --tree.

The golden was recorded from `main` before spec 046 generalised the period
read (ADR-6): export main with `git archive main | tar -x -C <dir>` and pass
that dir. The fixtures and stub day readers come from the SAME tree
(tests/review_period_fixtures.py), so the recording is what that tree's code
produced from its own fakes.

Legitimate reasons to re-record: the fake month or fake week fixture in
tests/review_period_fixtures.py was edited for an unrelated reason, or the
period read's shape changed ON PURPOSE and the change was reviewed. Do NOT
re-record from a branch to make tests/test_review_period_golden.py pass —
a disagreement is the regression that test exists to catch.

Normalisation: none needed. The result holds only fixture paths, ISO dates
and counts — no tmp paths, no "today", no ms timestamps. Run under TZ=UTC
(as tests/conftest.py pins) so period_bounds_ms matches the suite. JSON is
written with sorted keys; list order is the reader's own and is pinned.

Usage: TZ=UTC python3 record.py --tree <exported source tree>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent


def capture(tree: Path) -> dict:
    """Run the fake month and fake week through ``tree``'s read_period."""
    sys.path.insert(0, str(tree / "tomo" / "scripts"))
    sys.path.insert(0, str(tree / "tests"))
    import review_period_fixtures as f

    return {
        "month": f.run(f.month_vault(), f.MARCH, f.month_sources()),
        "week": f.run(f.growth_vault(), f.W13, f.week_sources(moc_folders=[f.MOCS])),
    }


def dump(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True, type=Path, help="exported source tree (e.g. of main)")
    args = parser.parse_args()
    os.environ["TZ"] = "UTC"
    time.tzset()
    for name, result in capture(args.tree.resolve()).items():
        (OUT_DIR / f"{name}.json").write_text(dump(result), encoding="utf-8")


if __name__ == "__main__":
    main()
