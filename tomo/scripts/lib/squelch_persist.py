# squelch_persist.py — Persist squelch entries when a proposal-doc is rejected.
# version: 0.1.0
"""Write SquelchEntry records for each rejected cluster in a MOC proposal-doc.

Called at archival time (via mark-captured.py) when a ``tomo-moc-proposal-*.md``
file is being marked as captured.  Identifies rejected clusters (those whose
``- [ ] Accept`` was NOT ticked), computes a stable topic signature per cluster,
and appends/replaces entries in the squelch registry.

Public API:

    persist_rejected_clusters(
        proposal_doc_text: str,
        filename: str,
        registry_path: str | Path,
        config: dict,
    ) -> int
        Returns the number of new squelch entries written.

Stdlib only — no new dependencies.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Resolve lib/ relative to this file ───────────────────────────────────────
_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent

# ── Import sibling lib modules without installing the package ─────────────────
sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.squelch import SquelchEntry, add_or_replace, load_registry, save_registry_atomic
from lib.topic_signature import compute_topic_signature

# ── Load suggestion-parser.py (hyphen in filename → importlib) ────────────────
_PARSER_PATH = _SCRIPTS_DIR / "suggestion-parser.py"
_parser_spec = importlib.util.spec_from_file_location(
    "_suggestion_parser_squelch", _PARSER_PATH
)
if _parser_spec is None or _parser_spec.loader is None:
    raise ImportError(f"Cannot load suggestion-parser.py from {_PARSER_PATH}")

_parser_mod = importlib.util.module_from_spec(_parser_spec)
_parser_spec.loader.exec_module(_parser_mod)  # type: ignore[union-attr]

_enumerate_all_moc_sections = _parser_mod.enumerate_all_moc_sections  # type: ignore[attr-defined]
_parse_moc_proposal_doc = _parser_mod.parse_moc_proposal_doc  # type: ignore[attr-defined]
_is_moc_proposal_doc = _parser_mod._is_moc_proposal_doc  # type: ignore[attr-defined]


def persist_rejected_clusters(
    proposal_doc_text: str,
    filename: str,
    registry_path: "str | Path",
    config: dict,
    *,
    run_id: str = "",
) -> int:
    """Parse a proposal-doc, identify rejected clusters, write squelch entries.

    Args:
        proposal_doc_text: Full text of the ``tomo-moc-proposal-*.md`` document.
        filename:          Filename (or path) used for dispatch detection.
        registry_path:     Path to ``state/moc-squelch.json`` sidecar.
        config:            Dict with at least ``squelch_runs`` (int, default 3).
        run_id:            Optional run UUID to stamp on new entries.

    Returns:
        Number of SquelchEntry records written (0 if all clusters accepted or
        document is not a proposal-doc).
    """
    if not _is_moc_proposal_doc(proposal_doc_text, filename=filename):
        return 0

    squelch_runs: int = int(config.get("squelch_runs", 3))

    # ── Enumerate ALL sections ────────────────────────────────────────────────
    all_sections = _enumerate_all_moc_sections(proposal_doc_text)

    # ── Find accepted cluster IDs ─────────────────────────────────────────────
    accepted_proposals = _parse_moc_proposal_doc(proposal_doc_text, filename=filename)
    accepted_ids = {p["moc_id"].upper() for p in accepted_proposals}

    # ── Compute rejected = all − accepted ─────────────────────────────────────
    rejected = [
        (moc_id, title, cand_stems, topic_kws)
        for moc_id, title, cand_stems, topic_kws in all_sections
        if moc_id.upper() not in accepted_ids
    ]

    if not rejected:
        return 0

    registry = load_registry(registry_path)
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for moc_id, title, cand_stems, topic_kws in rejected:
        cluster = {
            "topic_keywords": topic_kws,
            "candidate_stems": cand_stems,
        }
        signature = compute_topic_signature(cluster)
        entry = SquelchEntry(
            topic_signature=signature,
            topic_keywords=topic_kws,
            rejected_at_run_id=run_id,
            runs_remaining=squelch_runs,
            first_seen_at=now_iso,
        )
        registry = add_or_replace(registry, entry)

    save_registry_atomic(registry_path, registry, last_run_id=run_id)
    return len(rejected)
