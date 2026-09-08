#!/usr/bin/env python3
# version: 0.3.0
"""conftest.py — Host-side pytest bootstrap for the Tomo test suite.

Injects /tmp/claude/py_deps onto sys.path so jsonschema (a Tomo runtime dep
that's pre-installed in the Docker image but not in the host venv) is
resolvable when tests load producer scripts that transitively import it.

Docker tests don't need this; the path is harmless if missing.

Also excludes test-kado.py from collection: it is a live Kado connectivity
script (needs a running MCP server), not a pytest module — every one of its
functions takes ordinary arguments from its own main(), which pytest would
otherwise misread as unresolvable fixture requests. It stays runnable
directly as `python3 tests/test-kado.py`.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if os.path.isdir(_DEPS) and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

collect_ignore = ["test-kado.py"]

# Scripts that write to the instance's persistent state directory address it
# cwd-relative (state/moc-squelch.json, state/inbox-cost-history.jsonl) — correct
# for the instance runtime, and a trap for a host test that drives an entry point
# without redirecting the path: the run appends into the repo working tree, where
# it survives the test and shows up as an untracked file. The guard names the
# offending test instead of leaving the directory to be found by `git status`.
_REPO_STATE_DIR = Path(__file__).resolve().parent.parent / "state"


@pytest.fixture(autouse=True)
def _no_repo_state_writes():
    existed = _REPO_STATE_DIR.exists()
    yield
    if _REPO_STATE_DIR.exists() and not existed:
        contents = sorted(p.name for p in _REPO_STATE_DIR.iterdir())
        shutil.rmtree(_REPO_STATE_DIR, ignore_errors=True)
        pytest.fail(
            f"this test wrote {contents} into the repo's own state/ directory — "
            "pass the script's state/history path under tmp_path instead of "
            "letting the cwd-relative default apply"
        )
