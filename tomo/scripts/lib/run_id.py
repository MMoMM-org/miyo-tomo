# run_id.py — the run-identifier format, shared by every entry point.
# version: 0.1.0
"""Generate the run id that stamps a run's artefacts and its cost-history entry.

Format: ``YYYY-MM-DDTHH-MM-SSZ-<6 hex chars>``.

Lives in lib/ because two entry points mint one: ``run-id.py`` (the CLI the
skills call before dispatching Pass 1) and ``inbox-triage.py`` (which records
its own cost for the actions that terminate before any skill has minted one).

Stdlib only — no new dependencies.
"""

from __future__ import annotations

import time
import uuid


def generate() -> str:
    """Return a fresh run id."""
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    return f"{stamp}-{uuid.uuid4().hex[:6]}"
