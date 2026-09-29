#!/usr/bin/env python3
# version: 0.1.0
"""attachment_conflict_states.py — Shared marker for the rename-impossible
attachment-conflict state (spec 037 T2.2/T2.4, owner decision 2026-09-23).

`suggestions-reducer.py` renders the "no free name was available" remedy
line and `suggestion-parser.py` reads it back to resolve the owner's ticks.
Before this module the marker text was a bare literal duplicated in both
files — nothing enforced that a reword of one kept the other in sync. This
phase already reworded that exact line twice for unrelated reasons (removing
an executor name, then an internal retry count); a third reword would pass
every existing test while silently breaking the parser's detection, handing
Pass 3 a `remedy: rename` with `proposed_name: null` — the Rule 6 violation
the 2026-09-23 decision exists to prevent. One constant, imported by both,
makes that drift a single edit instead of two that must be kept in step.
"""
from __future__ import annotations

RENAME_IMPOSSIBLE_MARKER = "no free name available"
