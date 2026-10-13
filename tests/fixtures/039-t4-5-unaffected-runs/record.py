#!/usr/bin/env python3
# version: 1.0.0
"""Record the spec-039 T4.5 baseline for runs that file no note.

A garden-audit run and a daily-only run (no confirmed item, so no Kado
client) through `instruction-render.py` `main()`, with the harness of
`tests/test_039_t4_5_wire_plan_into_pass_2.py` (`unaffected_runs`), so the
recording and the replay are one harness. Recorded at 0e8835a6 — the commit
before T4.5 was implemented — into `expected.json`.

Run from the repo root:
    ./venv/bin/python tests/fixtures/039-t4-5-unaffected-runs/record.py

NOT run by the suite. Re-run only for a deliberate, reviewed change of
baseline — and then the diff of `expected.json` is the review.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent
TESTS_DIR = FIXTURE_DIR.parents[1]
sys.path.insert(0, str(TESTS_DIR))

import test_039_t4_5_wire_plan_into_pass_2 as harness  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch, pytest.MonkeyPatch.context() as mp:
        results = harness.unaffected_runs(mp, Path(scratch))
    (FIXTURE_DIR / "expected.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
