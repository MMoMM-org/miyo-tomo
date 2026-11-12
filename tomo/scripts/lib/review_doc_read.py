# review_doc_read.py — the one reader of the /review document for Pass 2: path, note read, parse with pass1_links.
# version: 0.1.1
"""Read the edited review document back for ``parse``, ``preview`` and ``deliver`` (spec 045 T4.2).

``doc_path_of(meta, override)`` is the path a Pass 2 command reads: the
caller's ``--doc-path`` or ``meta.json``'s ``doc_path``; None when neither
names one. ``read_document(vault, doc_path, meta)`` reads the note through
Kado and parses it with ``review_doc_parse.parse_document``, handing it the
``pass1_links`` map and the ``pass1_counts`` total of ``meta`` so ``edited``
and ``deleted`` are computed one way for every command. It returns a
``DocRead`` — the path, the text, Kado's ``modified`` stamp (the guard for
the delivered mark) and the ``ParsedDoc`` — or None when nothing is at the
path. A refused key or a dead connection raises ``review_vault.Stopped``
with the SDD's error kinds; any other read failure stops the same way
(``review_vault.kado_stops``, shared with the script's own reads).

Design notes: docs/tomo/scripts/lib/review_doc_read.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lib import review_doc_parse as rdp
from lib.kado_client import KadoNotFoundError
from lib.review_vault import kado_stops


@dataclass
class DocRead:
    doc_path: str
    text: str
    modified: Optional[int]
    parsed: rdp.ParsedDoc


def doc_path_of(meta: Optional[dict], override: Optional[str] = None) -> Optional[str]:
    """The document's vault path: ``override`` first, else ``meta.json``'s ``doc_path``."""
    path = override or (meta or {}).get("doc_path")
    return path if isinstance(path, str) and path else None


def read_document(vault, doc_path: str, meta: Optional[dict]) -> Optional[DocRead]:
    """The document at ``doc_path`` parsed with ``meta``'s Pass 1 map; None when nothing is there."""
    with kado_stops():
        try:
            note = vault.client.read_note(doc_path)
        except KadoNotFoundError:
            return None
    text = note.get("content")
    if not isinstance(text, str):
        return None
    meta = meta or {}
    pass1 = meta.get("pass1_links") if isinstance(meta.get("pass1_links"), dict) else None
    counts = meta.get("pass1_counts") if isinstance(meta.get("pass1_counts"), dict) else {}
    total = sum(n for n in counts.values() if isinstance(n, int))
    modified = note.get("modified")
    return DocRead(doc_path, text, modified if isinstance(modified, int) else None,
                   rdp.parse_document(text, pass1_links=pass1, pass1_total=total))
