#!/usr/bin/env python3
# version: 1.0.0
"""Record the spec-039 T6.3 baseline for an untouched suggestions document (F1-AC7).

Runs `run_untouched` from `tests/test_039_t6_3_untouched_document_baseline.py`
(one harness for recording and replay) against the source tree given by
`--root`, and writes `expected.json` beside this file. Recorded from the
merge-base `d583cd31` (spec 038 as merged, before any spec 039 commit):

    mkdir -p "$TMPDIR/base" && git archive d583cd31 | tar -x -C "$TMPDIR/base"
    ./venv/bin/python tests/fixtures/039-t6-3-untouched-baseline/record.py \\
        --root "$TMPDIR/base"

NOT run by the suite. Re-record only for a deliberate, reviewed change of
baseline — and then the diff of `expected.json` is the review.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent
TESTS_DIR = FIXTURE_DIR.parents[1]
sys.path.insert(0, str(TESTS_DIR))

import test_039_t6_3_untouched_document_baseline as harness  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="source tree to record from")
    args = parser.parse_args()
    scripts_dir = Path(args.root).resolve() / "tomo" / "scripts"
    with tempfile.TemporaryDirectory() as scratch, pytest.MonkeyPatch.context() as mp:
        result = harness.run_untouched(scripts_dir, Path(scratch), mp)
    (FIXTURE_DIR / "expected.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
