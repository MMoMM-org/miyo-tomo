#!/usr/bin/env python3
"""Regenerate tests/fixtures/038-wire-baseline/{payload,input_doc}.json from
commit 50d8f1b.

Two, and only two, legitimate reasons to run this:
  1. The pre-038 reference commit itself is deliberately re-chosen (e.g. a
     correction to which commit represents "pre-038").
  2. tests/test_suggestions_wire_emit.py's `_doc()` fixture was edited for an
     unrelated reason. The baseline means "what the pre-038 producer emits
     from THIS input" -- once `_doc()` changes, input_doc.json is stale and
     the comparison test (test_038_t2_4_wire_baseline_diff.py) will refuse to
     run until this is re-run, naming the drift rather than producing a
     confusing key diff.

Do NOT run it because today's build_wire_payload() output changed with
`_doc()` held fixed -- that is the regression the diff test exists to catch,
and a moving baseline would silence it.

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
INPUT_OUT_PATH = Path(__file__).resolve().parent / "input_doc.json"


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
        input_doc = test_mod._doc()
        payload = render_mod.build_wire_payload(input_doc)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=REPO_ROOT, check=False)

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Captured alongside the payload so the diff test can tell "the producer
    # changed" (a finding) apart from "the input fixture changed" (regenerate):
    # the baseline means "what the pre-038 producer emits from THIS input", so
    # the input itself has to be pinned too, not just its output.
    INPUT_OUT_PATH.write_text(
        json.dumps(input_doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUT_PATH} ({len(payload)} top-level keys) "
        f"and {INPUT_OUT_PATH}"
    )


if __name__ == "__main__":
    main()
