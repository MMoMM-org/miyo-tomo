# note_actions.py — the instruction set one /note draft delivers.
# version: 0.1.0
"""Build the Hashi instruction set of a /note draft from its draft state.

The set holds one ``move_note`` (I01) that files the inbox note at its
destination and, when the draft came from an inbox note that is not kept, one
``delete_source`` (I02) that depends on I01. ``note-instructions.py deliver``
writes it as ``<stem>_instructions.json``; a resumed delivery rebuilds it and
compares, so the builder reads only its arguments: no clock, no filesystem,
no Kado. The wire shape is ``tomo/schemas/hashi-instructions.schema.json``.

Design notes: docs/tomo/scripts/lib/note_actions.md
"""
from __future__ import annotations

import posixpath

from lib.note_meta import NoteDraftMeta
from lib.wire_version import wire_schema_version

WIRE_SCHEMA = "instructions.schema.json"
WIRE_TYPE = "tomo-instructions"
MOVE_ID = "I01"
DELETE_ID = "I02"
DELETE_REASON = "Replaced by a /note note"


def build_move_note(meta: NoteDraftMeta) -> dict:
    """Return the move_note action; only the keys the SDD names."""
    return {
        "id": MOVE_ID,
        "action": "move_note",
        "source": meta.inbox_file,
        "destination": meta.destination_file(),
        "title": meta.title,
        "rendered_file": posixpath.basename(meta.inbox_file),
        "source_inbox_item": meta.source_path,
    }


def build_delete_source(meta: NoteDraftMeta) -> dict | None:
    """Return the delete_source action, or None when there is no source or it is kept."""
    if not meta.source_path or meta.keep_source:
        return None
    return {
        "id": DELETE_ID,
        "action": "delete_source",
        "source_path": meta.source_path,
        "reason": DELETE_REASON,
        "depends_on": [MOVE_ID],
    }


def build_note_actions(meta: NoteDraftMeta) -> list[dict]:
    """Return the ordered actions: move_note, then delete_source when due."""
    delete = build_delete_source(meta)
    return [build_move_note(meta)] + ([delete] if delete else [])


def build_note_instruction_set(meta: NoteDraftMeta, *, profile: str | None) -> dict:
    """Return the whole instruction set document for ``meta``."""
    return {
        "schema_version": wire_schema_version(WIRE_SCHEMA),
        "type": WIRE_TYPE,
        "generated": meta.generated,
        "profile": profile,
        "md_peer": meta.instructions_stem(),
        "actions": build_note_actions(meta),
    }
