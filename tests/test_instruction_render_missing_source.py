#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_missing_source.py — missing-source guardrail (#116).

When a confirmed item's source note no longer exists (e.g. a stale suggestion
re-processed after the source was deleted or already moved), the renderer used
to fail-open to an empty body and fabricate an empty stub note. Worse, the item
stayed in `confirmed`, so build_actions still emitted a link_to_moc pointing at
a note that was never created.

`filter_missing_source_notes` drops such items from `confirmed` BEFORE the
render loop and build_actions, so no downstream action references the missing
source.

Two levels:
  - unit matrix over filter_missing_source_notes (drop / keep / fail-open)
  - integration: a dropped item produces no link_to_moc (the dangling-link bug)

Issue: https://github.com/MMoMM-org/miyo-tomo/issues/116
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoError  # noqa: E402
from lib.render_resolve import filter_missing_source_notes  # noqa: E402

# Load instruction-render's action builders (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)

INBOX = "100 Inbox"


def _client_with_present(present_stems: set[str]) -> MagicMock:
    """Fake KadoClient whose note_exists returns True only for present stems.

    Mirrors the real note_exists contract: it catches KadoNotFoundError
    internally and RETURNS False for an absent note (it does not propagate).
    """
    client = MagicMock()

    def _note_exists(path: str) -> bool:
        stem = path.rsplit("/", 1)[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        return stem in present_stems

    client.note_exists.side_effect = _note_exists
    return client


def _atomic(item_id: str, source_stem: str) -> dict:
    """A confirmed atomic-note item: template + source_path + a parent MOC."""
    return {
        "id": item_id,
        "action": "create_note",
        "title": f"{source_stem} note",
        "template": "Atomic Note.md",
        "source_path": source_stem,
        "parent_mocs": ["Topics MOC"],
        "candidate_mocs": [],
        "tags": [],
    }


# ── unit matrix ────────────────────────────────────────────────────────────


def test_drops_item_with_missing_source():
    confirmed = [_atomic("present", "Present"), _atomic("missing", "Gone")]
    client = _client_with_present({"Present"})
    kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
    assert [i["id"] for i in kept] == ["present"]
    assert [i["id"] for i in dropped] == ["missing"]


def test_keeps_item_without_template():
    """Instruction-only items (link_to_moc, update_daily) have no template and
    must never be dropped even if their source_path is absent."""
    confirmed = [{"id": "link-only", "action": "link_to_moc", "source_path": "Gone"}]
    client = _client_with_present(set())  # everything absent
    kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
    assert dropped == []
    assert [i["id"] for i in kept] == ["link-only"]


def test_keeps_item_without_source_path():
    """Synthesized MOC proposals have a template but no source_path — keep them."""
    confirmed = [{"id": "moc", "action": "create_moc", "template": "MOC.md"}]
    client = _client_with_present(set())
    kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
    assert dropped == []
    assert [i["id"] for i in kept] == ["moc"]


def test_fail_open_on_transient_error():
    """A non-not-found Kado error must NOT drop the item (never drop on a
    transient error — same policy as filter_missing_daily_notes)."""
    confirmed = [_atomic("item", "Whatever")]
    client = MagicMock()
    client.note_exists.side_effect = KadoError("transport blew up")
    kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
    assert dropped == []
    assert [i["id"] for i in kept] == ["item"]


def test_fail_open_when_client_none():
    confirmed = [_atomic("item", "Whatever")]
    kept, dropped = filter_missing_source_notes(confirmed, None, INBOX)
    assert dropped == []
    assert [i["id"] for i in kept] == ["item"]


# ── integration: no dangling link_to_moc for a dropped item ──────────────────


def test_dropped_item_produces_no_link_to_moc():
    """After filtering, the missing-source item must not yield a link_to_moc —
    otherwise a note that was never created gets linked into a MOC."""
    confirmed = [_atomic("present", "Present"), _atomic("missing", "Gone")]
    client = _client_with_present({"Present"})

    kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
    assert [i["id"] for i in dropped] == ["missing"]

    links = ir._build_link_to_moc_actions(kept, [0])
    blob = " ".join(str(a) for a in links)
    assert "Present note" in blob, f"present item lost its link: {links}"
    assert "Gone note" not in blob, (
        f"dangling link_to_moc emitted for missing-source item: {links}"
    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
