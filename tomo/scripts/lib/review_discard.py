# review_discard.py — mark an open /review document discarded through Kado: one read, one guarded merge.
# version: 0.1.0
"""The Kado half of ``review-doc.py discard`` (spec 047 walk F-R5-2).

``discard(client, doc_path)`` reads the document's frontmatter with its
``modified``, checks that it is Tomo's review document (``tomo.doc_type``
``review``) and merges ``tomo.state: discarded`` (``review_state.DOC_STATE_DISCARDED``)
with that ``modified`` as ``expected_modified``. The file, its body and every
other key stay as they are; nothing is deleted. It returns None when the mark
landed, else the closed stop reason as a dict: ``{"reason": "doc-missing"}``
(NOT_FOUND on the read or the merge), ``{"reason": "not-a-review"}``,
``{"reason": "doc-changed", "conflict": open-unsaved|changed-since-read|unknown}``
(``review_kado_conflict.is_conflict``), ``{"reason": "kado-failed", "error":
{kind, code?}}`` for any other Kado failure (``review_kado_conflict.error_of``:
the class name and Kado's uppercase code, never its message), also with kind
``modified-missing`` when the read reported no ``modified`` to guard the merge
with (nothing is merged unguarded). The stage is the caller's.

Design notes: docs/tomo/scripts/lib/review_discard.md
"""
from __future__ import annotations

from typing import Optional

from lib import review_kado_conflict as rkc
from lib.kado_client import KadoError, KadoNotFoundError
from lib.review_state import DOC_STATE_DISCARDED

DOC_TYPE = "review"                                   # review_doc.DOC_TYPE
DOC_MISSING, NOT_A_REVIEW, DOC_CHANGED, KADO_FAILED = "doc-missing", "not-a-review", "doc-changed", "kado-failed"
REASONS = (DOC_MISSING, NOT_A_REVIEW, DOC_CHANGED, KADO_FAILED)
MODIFIED_MISSING = "modified-missing"                 # the read gave no stamp to guard the merge with


def _stamp(found: dict) -> Optional[int]:
    modified = found.get("modified") if isinstance(found, dict) else None
    return modified if isinstance(modified, int) and not isinstance(modified, bool) else None


def _is_review(found: dict) -> bool:
    content = found.get("content") if isinstance(found, dict) else None
    tomo = content.get("tomo") if isinstance(content, dict) else None
    return isinstance(tomo, dict) and tomo.get("doc_type") == DOC_TYPE


def discard(client, doc_path: str) -> Optional[dict]:
    """Mark the review document at ``doc_path`` discarded; None on success, else the stop reason."""
    try:
        found = client.read_frontmatter(doc_path)
    except KadoNotFoundError:
        return {"reason": DOC_MISSING}
    except KadoError as exc:
        return {"reason": KADO_FAILED, "error": rkc.error_of(exc)}
    if not _is_review(found):
        return {"reason": NOT_A_REVIEW}
    modified = _stamp(found)
    if modified is None:
        return {"reason": KADO_FAILED, "error": {"kind": MODIFIED_MISSING}}
    try:
        client.write_frontmatter(doc_path, {"tomo": {"state": DOC_STATE_DISCARDED}}, mode="merge",
                                 expected_modified=modified)
    except KadoNotFoundError:
        return {"reason": DOC_MISSING}
    except KadoError as exc:
        if rkc.is_conflict(exc):
            return {"reason": DOC_CHANGED, "conflict": rkc.conflict_reason(exc)}
        return {"reason": KADO_FAILED, "error": rkc.error_of(exc)}
    return None
