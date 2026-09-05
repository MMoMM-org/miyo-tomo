#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t6_2_regression_no_attachments_unchanged.py — Phase 6 T6.2.

CON-8: "Tomo is near MVP; runs on notes without attachments must produce a
byte-identical instruction set to today's." For an attachment-free fixture,
spec 031 must change NOTHING observable: the actions list
(lib.render_actions.build_actions), and the suggestions-document rendering
(suggestions-reducer.render_create_atomic_note) must be byte-identical to
the pre-spec-031 baseline.

Technique (spec 032's T6.2 pattern, `tests/test_032_t6_2_regression_inline_
unchanged.py`): load the module as it stood at the pre-031 branch point via
``git show <sha>:<path>`` into a tempfile, exec it under a DISTINCT module
name, run it side-by-side with the current module on the SAME input, and
assert equality.

Baseline SHA: 8e140c5 — the branch point, confirmed by the team lead.

No golden files are written or regenerated here, and none ever will be by
this test: there is nothing to regenerate. `_next_id(counter)` is called
only inside `_build_move_asset_actions`'s per-attachment loop
(`lib/render_actions.py`), so an attachment-free run consumes no ID and
`out.extend([])` adds nothing — there is no ID shift for an attachment-free
fixture to except from full equality. The plan's "except for action IDs
where the new slot shifts them" applies only to fixtures WITH attachments,
which this task does not test. So: byte-identical, full stop. Any diff on
an attachment-free fixture is a defect to report, not a tolerance to widen.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_REDUCER_PATH = _SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

_PRE_031_SHA = "8e140c5"  # the branch point (confirmed by team lead)


def _version_line(content: str) -> str:
    """The first `# version: ...` line, wherever it falls — its position
    varies (line 1 for a lib/ module with no shebang, line 4 for a script
    with a multi-line header comment before it)."""
    return next(ln for ln in content.splitlines() if ln.startswith("# version:"))


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_from_git(name: str, sha: str, repo_relative_path: str):
    """Load `sha:repo_relative_path` as a module under a distinct `name`.

    Written to a fresh tempfile under $TMPDIR — never touches the working
    tree. Returns the executed module, with its own source's version line
    stashed on it (the tempfile is gone once this returns).
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:{repo_relative_path}"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    with tempfile.TemporaryDirectory() as td:
        old_path = pathlib.Path(td) / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    mod._t62_source_version_line = _version_line(content)
    return mod


def _load_reducer_from_git(name: str, sha: str):
    """Like ``_load_from_git``, but for suggestions-reducer.py specifically.

    suggestions-reducer.py resolves ``tag-handler-group.py`` at import time
    via ``Path(__file__).resolve().parent / "tag-handler-group.py"`` (same
    script directory) — a bare tempfile breaks that. Place a copy of the
    CURRENT tag-handler-group.py alongside it (its ``group_id`` helper is
    untouched by spec 031 and never exercised by render_create_atomic_note
    on an attachment-free fixture; only the import needs to succeed).
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:tomo/scripts/suggestions-reducer.py"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    thg_content = (_SCRIPTS_DIR / "tag-handler-group.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        old_path = td_path / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        (td_path / "tag-handler-group.py").write_text(thg_content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    mod._t62_source_version_line = _version_line(content)
    return mod


def _load_render_actions_from_git(name: str, sha: str):
    """Like ``_load_from_git``, but for lib/render_actions.py specifically.

    render_actions.py resolves ``tag-handler-group.py`` at import time via
    ``Path(__file__).resolve().parent.parent`` (scripts/lib/x.py ->
    scripts/) — a bare tempfile breaks that. Mirror the real scripts/lib/
    layout inside the tempdir instead, using the CURRENT
    tag-handler-group.py (its ``group_id`` helper is untouched by spec 031
    and never exercised by build_actions on an attachment-free fixture;
    only the import needs to succeed).
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:tomo/scripts/lib/render_actions.py"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    thg_content = (_SCRIPTS_DIR / "tag-handler-group.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        (td_path / "lib").mkdir()
        old_path = td_path / "lib" / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        (td_path / "tag-handler-group.py").write_text(thg_content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    mod._t62_source_version_line = _version_line(content)
    return mod


# ---------------------------------------------------------------------------
# NEW (current HEAD) modules
# ---------------------------------------------------------------------------
new_render_actions = _load("render_actions_t62_new", _SCRIPTS_DIR / "lib" / "render_actions.py")
new_build_actions = new_render_actions.build_actions
new_reducer = _load("suggestions_reducer_t62_new", _REDUCER_PATH)

# ---------------------------------------------------------------------------
# OLD (pre-031, 8e140c5) modules — DISTINCT names, loaded from git history,
# never from the working tree.
# ---------------------------------------------------------------------------
old_render_actions = _load_render_actions_from_git("render_actions_t62_old", _PRE_031_SHA)
old_build_actions = old_render_actions.build_actions
old_reducer = _load_reducer_from_git("suggestions_reducer_t62_old", _PRE_031_SHA)

# Sanity: the two render_actions modules really are different objects loaded
# from different sources, at different versions — guards against the
# "loaded the new module twice" trap a reviewer hit in an earlier spec.
# old_render_actions' version line was stashed from git-show content (its
# tempfile is gone by now); new_render_actions' is read straight from the
# working-tree file it was loaded from, which is still on disk.
assert old_render_actions is not new_render_actions
assert old_render_actions.__file__ != new_render_actions.__file__
_new_render_actions_version_line = _version_line(
    (_SCRIPTS_DIR / "lib" / "render_actions.py").read_text(encoding="utf-8")
)
assert old_render_actions._t62_source_version_line != _new_render_actions_version_line

assert old_reducer is not new_reducer
assert old_reducer.__file__ != new_reducer.__file__
_new_reducer_version_line = _version_line(_REDUCER_PATH.read_text(encoding="utf-8"))
assert old_reducer._t62_source_version_line != _new_reducer_version_line


# ---------------------------------------------------------------------------
# Fixtures — deliberately attachment-free
# ---------------------------------------------------------------------------

CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _plain_manifest_entry() -> dict:
    return {
        "id": "S01", "action": None, "title": "Dresden — Snow city",
        "source_path": "dresden.md", "rendered_file": "2026-09-06_1200_dresden.md",
        "destination": "Atlas/202 Notes/", "parent_moc": "Japan (MOC)",
        "parent_mocs": ["Japan (MOC)"], "tags": [],
        # No "attachments" key at all — mirrors a pre-031 manifest entry.
    }


def _plain_confirmed_item() -> dict:
    return {
        "id": "S01", "action": None, "title": "Dresden — Snow city",
        "source_path": "dresden.md", "tags": [],
        "parent_moc": "Japan (MOC)", "parent_mocs": ["Japan (MOC)"],
        "candidate_mocs": [],
    }


def _voice_manifest_entry() -> dict:
    return {
        "id": "V01", "action": None, "title": "Interview Notes",
        "source_path": "2026-04-08-interview-transcript.md",
        "rendered_file": "2026-09-06_1300_interview-notes.md",
        "destination": "Atlas/202 Notes/", "parent_moc": "",
        "parent_mocs": [], "tags": [],
        "audio_peer": "2026-04-08_1430_interview.m4a",
    }


def _voice_confirmed_item() -> dict:
    return {
        "id": "V01", "action": None, "title": "Interview Notes",
        "source_path": "2026-04-08-interview-transcript.md",
        "tags": [], "parent_moc": "", "parent_mocs": [], "candidate_mocs": [],
        "audio_peer": "2026-04-08_1430_interview.m4a",
        "keep_source": False,
    }


# ---------------------------------------------------------------------------
# T6.2 — instruction set (actions list) byte-identity
# ---------------------------------------------------------------------------

class TestActionsListByteIdentical:
    def test_plain_atomic_note_no_attachments(self):
        manifest = [_plain_manifest_entry()]
        confirmed = [_plain_confirmed_item()]

        old_actions = old_build_actions(manifest, confirmed, [], [], CFG)
        new_actions, new_skipped_assets = new_build_actions(manifest, confirmed, [], [], CFG)

        assert new_skipped_assets == []
        assert new_actions == old_actions
        assert "move_asset" not in {a["action"] for a in new_actions}

    def test_voice_item_audio_peer_and_paired_delete_source_untouched(self):
        """CON-8's third clause: a voice item's audio_peer behaviour —
        including its paired delete_source for BOTH the transcript origin
        and the audio file — is untouched by spec 031."""
        manifest = [_voice_manifest_entry()]
        confirmed = [_voice_confirmed_item()]

        old_actions = old_build_actions(manifest, confirmed, [], [], CFG)
        new_actions, new_skipped_assets = new_build_actions(manifest, confirmed, [], [], CFG)

        assert new_skipped_assets == []
        assert new_actions == old_actions

        deletes = [a for a in new_actions if a["action"] == "delete_source"]
        deleted_paths = {d["source_path"] for d in deletes}
        assert len(deletes) == 2, f"expected paired delete (transcript + audio), got {deletes}"
        assert "100 Inbox/2026-04-08-interview-transcript.md" in deleted_paths
        assert "100 Inbox/2026-04-08_1430_interview.m4a" in deleted_paths
        assert "move_asset" not in {a["action"] for a in new_actions}


# ---------------------------------------------------------------------------
# T6.2 — suggestions-document rendering byte-identity (AC-F3.2)
# ---------------------------------------------------------------------------

class TestSuggestionsDocByteIdentical:
    def _action(self) -> dict:
        return {
            "kind": "create_atomic_note",
            "source_stem": "dresden",
            "suggested_title": "Dresden — Snow city",
            "template": "Atomic Note.md",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [
                {"path": "Atlas/200 Maps/Japan (MOC).md", "score": 0.7, "pre_check": False}
            ],
            "tags_to_add": [],
            "atomic_note_worthiness": 0.8,
            "classification": None,
            # No "attachments" / "unresolved_embeds" keys — mirrors a
            # pre-031 action dict (and a post-031 one where the resolved-
            # attachments map has nothing for this source).
        }

    def test_render_create_atomic_note_byte_identical(self):
        action = self._action()
        old_md = old_reducer.render_create_atomic_note(action, "dresden", "MOC")
        new_md = new_reducer.render_create_atomic_note(action, "dresden", "MOC")
        assert new_md == old_md
        assert "**Attachments:**" not in new_md
        assert "**Unresolved embeds:**" not in new_md

    def test_render_with_empty_attachments_key_still_byte_identical(self):
        """An action dict WITH the new keys present but empty (the shape
        merge_resolved_attachments produces for a source absent from the
        resolved map) must render identically to one without the keys at
        all — CON-8's guarantee holds regardless of which shape reaches the
        renderer."""
        action = self._action()
        action["attachments"] = []
        action["unresolved_embeds"] = []
        new_md = new_reducer.render_create_atomic_note(action, "dresden", "MOC")
        old_md = old_reducer.render_create_atomic_note(self._action(), "dresden", "MOC")
        assert new_md == old_md
