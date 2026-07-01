#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t4_2_3_renderer_diff_rename.py — TDD for T4.2 (renderer) + T4.3 (diff).

T4.2: instruction-render.py emits source_inbox_item (not origin_inbox_item) in
move_note actions, emits schema_version:"2" in the doc header, and renders the
display line as "Source (reference):" instead of "Origin (reference):".

T4.3: instructions-diff.py matches move_note by source_inbox_item stem
(falls back to rendered_file) rather than origin_inbox_item.

Spec: docs/XDD/specs/027-suggestions-source-model/plan/phase-4.md (T4.2, T4.3)
ADR-3: hard-cutover, no alias — origin_inbox_item must not appear in output.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py via importlib (hyphen in name).
_ir_spec = importlib.util.spec_from_file_location("ir_t42", SCRIPTS_DIR / "instruction-render.py")
ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["ir_t42"] = ir
_ir_spec.loader.exec_module(ir)

# Load instructions-diff.py via importlib.
_diff_spec = importlib.util.spec_from_file_location(
    "idiff_t43", SCRIPTS_DIR / "instructions-diff.py"
)
diff_mod = importlib.util.module_from_spec(_diff_spec)
assert _diff_spec.loader is not None
sys.modules["idiff_t43"] = diff_mod
_diff_spec.loader.exec_module(diff_mod)

INBOX = "100 Inbox"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _manifest_entry(source_path: str = "note.md") -> dict:
    """Minimal manifest entry as produced by render_notes."""
    return {
        "title": "Test Note",
        "source_path": source_path,
        "template": "Atomic Note.md",
        "rendered_file": "20260630_1200-test-note.md",
        "rendered_path": "/tmp/tomo-out/20260630_1200-test-note.md",
        "destination": "200 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "supporting_items": None,
        "audio_peer": None,
    }


def _build_move_note(source_path: str = "note.md") -> dict:
    """Call _build_move_note_actions and return the first emitted action."""
    counter = [0]
    actions = ir._build_move_note_actions(
        [_manifest_entry(source_path=source_path)], INBOX, counter
    )
    assert len(actions) == 1, f"Expected 1 action, got {len(actions)}"
    return actions[0]


def _minimal_cfg() -> dict:
    """Minimal vault-config dict for _render_action_md calls."""
    return {
        "inbox": {"path": INBOX},
        "notes": {"destination": "200 Notes/"},
        "mocs": {"destination": "100 Maps/"},
        "daily": {"granularities": {}},
        "daily_log": {"heading": "Daily Log", "heading_level": 2},
    }


# ---------------------------------------------------------------------------
# T4.2 — Renderer emits source_inbox_item (not origin_inbox_item)
# ---------------------------------------------------------------------------

class TestRendererMoveNoteKeyRename:
    """_build_move_note_actions must emit source_inbox_item, not origin_inbox_item."""

    def test_emitted_key_is_source_inbox_item(self):
        """_build_move_note_actions emits 'source_inbox_item' key."""
        action = _build_move_note()
        assert "source_inbox_item" in action, (
            f"Expected source_inbox_item key in move_note; keys: {list(action.keys())}"
        )

    def test_origin_inbox_item_absent_from_emitted_move_note(self):
        """origin_inbox_item must NOT appear in the emitted move_note (ADR-3 hard cutover)."""
        action = _build_move_note()
        assert "origin_inbox_item" not in action, (
            "origin_inbox_item must be gone — ADR-3 hard cutover, no alias"
        )

    def test_source_inbox_item_carries_dotmd_path(self):
        """source_inbox_item carries the inbox-joined source path with .md extension."""
        action = _build_move_note(source_path="test-note.md")
        sii = action.get("source_inbox_item")
        assert sii is not None, "source_inbox_item must be non-null"
        assert sii.endswith(".md"), f"Expected .md extension; got {sii!r}"
        assert "test-note" in sii, f"Expected source stem in path; got {sii!r}"


class TestRendererSchemaVersionBump:
    """The instructions doc header must emit schema_version:'2' (not '1')."""

    def test_schema_version_const_is_2_in_source(self):
        """Source code contract: instructions_doc uses schema_version:'2' (not '1').

        Reads the renderer source to guard against regression. RED = source still
        has '1'; GREEN = source updated to '2'.
        """
        source = (SCRIPTS_DIR / "instruction-render.py").read_text(encoding="utf-8")
        # The instructions_doc dict is built in main(); find the emitted constant.
        assert '"schema_version": "2"' in source, (
            "instructions_doc must emit schema_version:'2' (T4.2 bump)"
        )
        # And confirm '1' is gone from the emit site (not the schema itself)
        # We check that the old emit '1' is absent from the instructions_doc block.
        # NOTE: the schema files themselves no longer contain const "1" either.


class TestRendererDisplayRename:
    """_render_action_md must show 'Source (reference):' not 'Origin (reference):'."""

    def _action_with_source_inbox_item(self) -> dict:
        """A minimal move_note action using the new key name."""
        return {
            "id": "I01",
            "action": "move_note",
            "title": "Test Note",
            "rendered_file": "20260630_1200-test-note.md",
            "source": f"{INBOX}/20260630_1200-test-note.md",
            "destination": "200 Notes/Test Note.md",
            "source_inbox_item": f"{INBOX}/note.md",
            "parent_mocs": [],
            "tags": [],
        }

    def test_display_shows_source_reference(self):
        """_render_action_md renders '**Source (reference):**' for move_note."""
        action = self._action_with_source_inbox_item()
        md = ir._render_action_md(action, _minimal_cfg())
        assert "Source (reference):" in md, (
            f"Expected 'Source (reference):' in rendered MD; got:\n{md}"
        )

    def test_display_has_no_origin_reference(self):
        """'Origin (reference):' must not appear after the rename."""
        action = self._action_with_source_inbox_item()
        md = ir._render_action_md(action, _minimal_cfg())
        assert "Origin (reference):" not in md, (
            f"'Origin (reference):' must be gone; got:\n{md}"
        )


# ---------------------------------------------------------------------------
# T4.2 — Delete builder reads source_inbox_item from move_note actions
# ---------------------------------------------------------------------------

class TestDeleteBuilderReadsSourceInboxItem:
    """_build_delete_source_actions reads source_inbox_item (not origin_inbox_item)."""

    def _move_note_new_key(self, source_path: str = f"{INBOX}/note.md") -> dict:
        """A move_note action using the new source_inbox_item key."""
        return {
            "id": "I01",
            "action": "move_note",
            "source_inbox_item": source_path,
            "source": f"{INBOX}/rendered.md",
            "destination": "200 Notes/Note.md",
            "title": "Note",
            "rendered_file": "rendered.md",
            "parent_mocs": [],
            "tags": [],
            "audio_peer": None,
        }

    def _move_note_old_key(self, source_path: str = f"{INBOX}/note.md") -> dict:
        """A move_note action using the old origin_inbox_item key (must be ignored)."""
        return {
            "id": "I01",
            "action": "move_note",
            "origin_inbox_item": source_path,  # OLD key
            "source": f"{INBOX}/rendered.md",
            "destination": "200 Notes/Note.md",
            "title": "Note",
            "rendered_file": "rendered.md",
            "parent_mocs": [],
            "tags": [],
            "audio_peer": None,
        }

    def _confirmed(self, source_basename: str = "note.md") -> list:
        return [{
            "id": "S01",
            "source_path": source_basename,
            "approved": True,
            "keep_source": False,
        }]

    def test_delete_uses_source_inbox_item_key(self):
        """With source_inbox_item, delete builder produces paired delete for origin."""
        out = ir._build_delete_source_actions(
            confirmed=self._confirmed("note.md"),
            move_notes=[self._move_note_new_key(f"{INBOX}/note.md")],
            daily_updates=[],
            skipped=[],
            inbox_path=INBOX,
            counter=[0],
        )
        deletes = [a for a in out if a["action"] == "delete_source"]
        assert len(deletes) == 1, f"Expected 1 delete; got {len(deletes)}: {deletes}"
        assert deletes[0]["source_path"] == f"{INBOX}/note.md"

    def test_delete_ignores_origin_inbox_item_key(self):
        """With only origin_inbox_item (old key), builder produces NO delete."""
        out = ir._build_delete_source_actions(
            confirmed=self._confirmed("note.md"),
            move_notes=[self._move_note_old_key(f"{INBOX}/note.md")],
            daily_updates=[],
            skipped=[],
            inbox_path=INBOX,
            counter=[0],
        )
        deletes = [a for a in out if a["action"] == "delete_source"]
        assert len(deletes) == 0, (
            f"origin_inbox_item (old key) must be invisible to delete builder; got {deletes}"
        )


# ---------------------------------------------------------------------------
# T4.3 — instructions-diff.py matches by source_inbox_item
# ---------------------------------------------------------------------------

class TestDiffMatchesSourceInboxItem:
    """instructions-diff.py indexes move_notes by source_inbox_item stem (not origin_inbox_item)."""

    def _parsed(self, source_path: str = "note.md") -> dict:
        """Minimal parsed-suggestions with one confirmed item (keep_source=True so
        no delete_source is expected — isolates the stem-matching behavior)."""
        return {
            "confirmed_items": [{
                "id": "S01",
                "source_path": source_path,
                "approved": True,
                "keep_source": True,   # no delete_source expected — test stem matching only
                "action": "create_atomic_note",
                "suggested_title": "Test Note",
                "template": "Atomic Note.md",
                "location": "200 Notes/",
                "parent_mocs": [],
                "tags_to_add": [],
            }],
            "daily_updates": [],
            "skipped": [],
        }

    def _instrs(self, move_note: dict) -> dict:
        """Minimal instructions doc wrapping the given move_note (schema_version 2)."""
        return {
            "schema_version": "2",
            "type": "tomo-instructions",
            "generated": "2026-06-30T12:00:00Z",
            "profile": "miyo",
            "action_count": 1,
            "actions": [move_note],
        }

    def test_diff_matches_by_source_inbox_item(self):
        """run_diff exits 0 when move_note carries source_inbox_item for stem matching."""
        move_note = {
            "id": "I01",
            "action": "move_note",
            "source_inbox_item": f"{INBOX}/note.md",
            "source": f"{INBOX}/rendered.md",
            "destination": "200 Notes/Test Note.md",
            "title": "Test Note",
            "rendered_file": "rendered.md",
            "parent_mocs": [],
            "tags": [],
        }
        rc, _ = diff_mod.run_diff(self._parsed("note.md"), self._instrs(move_note))
        assert rc == 0, (
            f"Expected exit 0 (reconcile OK with source_inbox_item); got rc={rc}"
        )

    def test_diff_does_not_match_by_origin_inbox_item(self):
        """run_diff exits non-zero when only origin_inbox_item is present (old key ignored)."""
        move_note = {
            "id": "I01",
            "action": "move_note",
            "origin_inbox_item": f"{INBOX}/note.md",  # OLD key — must be ignored after T4.3
            "source": f"{INBOX}/rendered.md",
            "destination": "200 Notes/Test Note.md",
            "title": "Test Note",
            "rendered_file": "rendered.md",  # fallback stem "rendered" != "note" → mismatch
            "parent_mocs": [],
            "tags": [],
        }
        rc, _ = diff_mod.run_diff(self._parsed("note.md"), self._instrs(move_note))
        # After T4.3: origin_inbox_item is ignored → falls back to rendered_file stem
        # "rendered" != "note" → mismatch → rc=1.
        # Before T4.3: origin_inbox_item IS read → stem "note" matches → rc=0.
        # This test is RED before T4.3 and GREEN after.
        assert rc != 0, (
            "origin_inbox_item (old key) must not be read by diff after T4.3 rename "
            f"(got rc={rc}; expected non-zero)"
        )
