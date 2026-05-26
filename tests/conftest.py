#!/usr/bin/env python3
# version: 0.1.0
"""conftest.py — Host-side pytest bootstrap for the Tomo test suite.

Injects /tmp/claude/py_deps onto sys.path so jsonschema (a Tomo runtime dep
that's pre-installed in the Docker image but not in the host venv) is
resolvable when tests load producer scripts that transitively import it.

Docker tests don't need this; the path is harmless if missing.
"""
from __future__ import annotations

import os
import sys

_DEPS = "/tmp/claude/py_deps"
if os.path.isdir(_DEPS) and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)
