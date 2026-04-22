#!/usr/bin/env python3
# run-id.py — Generate a unique run id and write it to stdout + optional file.
# version: 0.1.0
#
# Format: YYYY-MM-DDTHH-MM-SSZ-<6 hex chars>
#
# Usage:
#   python3 scripts/run-id.py                 # prints to stdout
#   python3 scripts/run-id.py --out <path>    # also writes to <path>

from __future__ import annotations

import argparse
import sys
import time
import uuid


def generate() -> str:
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a run id.")
    p.add_argument("--out", default=None, help="Write the id to this file as well")
    args = p.parse_args()
    rid = generate()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(rid + "\n")
    sys.stdout.write(rid + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
