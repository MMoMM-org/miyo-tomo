#!/usr/bin/env python3
"""Regenerate tests/fixtures/038-wire-baseline/payload.json from commit 50d8f1b.

Run this ONLY when the pre-038 reference commit itself is deliberately
re-chosen (e.g. a correction to which commit represents "pre-038"). Do NOT
run it because today's build_wire_payload() output changed -- a moving
baseline would silence the exact regression the diff test is meant to catch.

Usage: python3 generate_baseline.py
Must be run with the repo root as the current working directory.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_COMMIT = "50d8f1b"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUT_PATH = Path(__file__).resolve().parent / "payload.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    scratch = tempfile.mkdtemp(prefix="tomo-038-wire-baseline-")
    # git worktree add refuses a non-empty directory, but requires the parent
    # to exist and the target itself to be absent or empty; mkdtemp gives us
    # an empty one, which satisfies it.
    subprocess.run(
        ["git", "worktree", "add", "--detach", scratch, BASELINE_COMMIT],
        cwd=REPO_ROOT,
        check=True,
    )
    try:
        scripts_dir = Path(scratch) / "tomo" / "scripts"
        sys.path.insert(0, str(scripts_dir))
        test_mod = _load_module(
            "baseline_test_suggestions_wire_emit",
            Path(scratch) / "tests" / "test_suggestions_wire_emit.py",
        )
        render_mod = _load_module(
            "baseline_suggestions_render", scripts_dir / "suggestions-render.py"
        )
        payload = render_mod.build_wire_payload(test_mod._doc())
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=REPO_ROOT, check=False)

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT_PATH} ({len(payload)} top-level keys)")


if __name__ == "__main__":
    main()
