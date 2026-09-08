#!/usr/bin/env python3
# version: 0.1.0
"""record-run-cost.py — Append this run's observed Kado cost to the history.

The terminal step for the two actions whose entry cannot be written by
inbox-triage.py: `suggest` and `fan-resolve` both run the reducer AFTER triage
has finished, so the destination-folder counts do not exist yet when triage
writes routing-plan.json. This script runs once the reducer has, reads triage's
own metrics back from the routing plan and the folder counts from the
suggestions document, and appends the single entry for the run.

The three actions that terminate inside triage (idle, synthesize, transcribe)
record themselves — they never reach the reducer, so their entries carry no
folder fields at all.

Measurement must never fail a run: every failure path warns and exits 0.

Usage:
    python3 scripts/record-run-cost.py \
        --run-id <run-id> \
        [--routing-plan tomo-tmp/routing-plan.json] \
        [--suggestions-doc tomo-tmp/suggestions-doc.json] \
        [--cost-history state/inbox-cost-history.jsonl]

Exit codes:
    0 — always. A missing artefact costs the entry (or its folder fields), not
        the run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.cost_history import DEFAULT_HISTORY_PATH, record_from_artifacts  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description="Append this run's observed Kado cost to the cost history."
    )
    p.add_argument("--run-id", required=True, help="Run-id string for the entry")
    p.add_argument(
        "--routing-plan",
        default="tomo-tmp/routing-plan.json",
        help="Routing plan carrying triage's metrics "
             "(default: tomo-tmp/routing-plan.json)",
    )
    p.add_argument(
        "--suggestions-doc",
        default="tomo-tmp/suggestions-doc.json",
        help="Reducer output carrying the destination-folder counts "
             "(default: tomo-tmp/suggestions-doc.json)",
    )
    p.add_argument(
        "--cost-history",
        default=DEFAULT_HISTORY_PATH,
        help=f"History JSONL to append to (default: {DEFAULT_HISTORY_PATH})",
    )
    args = p.parse_args()

    written = record_from_artifacts(
        run_id=args.run_id,
        routing_plan_path=args.routing_plan,
        suggestions_doc_path=args.suggestions_doc,
        history_path=args.cost_history,
    )
    print(
        f"record-run-cost: {'recorded' if written else 'not recorded'} "
        f"run_id={args.run_id} → {args.cost_history}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
