# classification_candidates.py — keep classification MOCs out of a note's candidates.
# version: 0.1.0
"""The reducer's backstop for the Classification Guard.

A classification (Dewey-layer) MOC is a MOC-only container: it links to
thematic MOCs, never to a note. The analyst is told not to nominate one, but
it tells them apart only by the name's Dewey pattern. The shared context marks
every MOC with `is_classification`, so this module enforces the rule exactly:
a candidate whose path the context flags is removed from the action.

The flag decides, not the title: a thematic MOC that merely looks numbered
stays. Fail-open: without a readable context nothing is dropped.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_classification_paths(shared_ctx_path: Path | str | None) -> set[str]:
    """Paths the context flags `is_classification: true`; empty on any failure."""
    if not shared_ctx_path:
        return set()
    try:
        ctx = json.loads(Path(shared_ctx_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    mocs = ctx.get("mocs") if isinstance(ctx, dict) else None
    if not isinstance(mocs, list):
        return set()
    return {m["path"] for m in mocs
            if isinstance(m, dict) and m.get("is_classification") is True and isinstance(m.get("path"), str)}


def drop_classification_candidates(action: dict, classification_paths: set[str]) -> int:
    """Remove flagged candidates from `action["candidate_mocs"]` in place; return how many."""
    candidates = action.get("candidate_mocs")
    if not classification_paths or not isinstance(candidates, list):
        return 0
    kept = [c for c in candidates if not (isinstance(c, dict) and c.get("path") in classification_paths)]
    dropped = len(candidates) - len(kept)
    if dropped:
        action["candidate_mocs"] = kept
    return dropped
