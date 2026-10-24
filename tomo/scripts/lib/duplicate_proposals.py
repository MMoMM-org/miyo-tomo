# duplicate_proposals.py — turn a proposed MOC that already exists into a candidate.
# version: 0.1.0
"""The reducer's backstop against proposing a MOC the vault already has.

The analyst nominates MOCs by meaning from a name list and is told not to
propose one that exists, but it is an LLM: a "Vacations" proposal next to an
existing "Vacation (MOC)" still reaches the owner as a "create MOC" offer
unless something deterministic catches it. This module is that catch.

Key: the cluster key `build_topic_clusters` already groups proposals by —
`normalise_topic(strip_moc_marker(x, suffix))` — applied to both the proposal
and every eligible thematic MOC title, so "Vacations", "vacation" and
"Vacation (MOC)" meet on one key and a two-item cluster ("Project",
"Projects") converts all-or-nothing.

Only eligible, non-classification MOCs count: eligibility (the exclude tag)
was decided by the shared-ctx builder and is read, never recomputed here;
classification (Dewey) MOCs are not link targets for a thematic proposal.

On a hit the proposal is cleared and every matching path is appended to the
action's candidates as `{path, score: 0.0, pre_check: false}` — unticked, no
anchor, after the analyst's own candidates, never twice. The owner decides
whether to link; Tomo stops offering to create a duplicate.

Fail-open: without a readable context nothing converts, which is the
behaviour before this module existed.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.topic_clusters import normalise_topic, strip_moc_marker


def cluster_key(title: str, suffix: str | None) -> str:
    return normalise_topic(strip_moc_marker(title or "", suffix))


def load_eligible_mocs(shared_ctx_path: Path | str | None, suffix: str | None) -> dict[str, list[str]]:
    """Map cluster key -> [paths] of the context's eligible thematic MOCs; {} on any failure."""
    if not shared_ctx_path:
        return {}
    try:
        ctx = json.loads(Path(shared_ctx_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    mocs = ctx.get("mocs") if isinstance(ctx, dict) else None
    if not isinstance(mocs, list):
        return {}
    eligible: dict[str, list[str]] = {}
    for moc in mocs:
        if not isinstance(moc, dict) or moc.get("is_classification"):
            continue
        path, title = moc.get("path"), moc.get("title")
        if not (isinstance(path, str) and path and isinstance(title, str)):
            continue
        key = cluster_key(title, suffix)
        if key and path not in eligible.setdefault(key, []):
            eligible[key].append(path)
    return eligible


def convert_duplicate_proposal(action: dict, eligible: dict[str, list[str]], suffix: str | None) -> bool:
    """Clear a needs_new_moc proposal that names an existing MOC; True when converted."""
    if not action.get("needs_new_moc") or action.get("suppressed"):
        return False
    key = cluster_key(action.get("proposed_moc_topic") or "", suffix)
    paths = eligible.get(key) if key else None
    if not paths:
        return False
    action["needs_new_moc"] = False
    action["proposed_moc_topic"] = None
    candidates = action.setdefault("candidate_mocs", [])
    listed = {c.get("path") for c in candidates if isinstance(c, dict)}
    for path in paths:
        if path not in listed:
            candidates.append({"path": path, "score": 0.0, "pre_check": False})
            listed.add(path)
    return True
