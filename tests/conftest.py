#!/usr/bin/env python3
# version: 0.2.0
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
import sys

_DEPS = "/tmp/claude/py_deps"
if os.path.isdir(_DEPS) and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

collect_ignore = ["test-kado.py"]
