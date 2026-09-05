#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_2_attachments_review_surface.py — attachments on both review channels.

Covers T3.2 (spec 031 Phase 3): render_create_atomic_note's markdown output and
the structured `item` mirror built by the reducer's per-action loop both carry
the same `attachments` list for the same item (CON-5). Also covers the
Should-have unresolved/ambiguous embed reporting line, rendered only when
non-empty.

Spec: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-3.md (T3.2)
Ref: PRD/AC-F3.1, AC-F3.2, AC-F3.4; SDD/Constraints CON-5
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer_t32", "suggestions-reducer.py")
render_create_atomic_note = _reducer.render_create_atomic_note

ATTACHMENT_PATH = "100 Inbox/Images/prag-karte.jpg"


def _base_action(**overrides) -> dict:
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "Prague Trip",
        "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    action.update(overrides)
    return action


# ---------------------------------------------------------------------------
# Markdown channel — **Attachments:** line
# ---------------------------------------------------------------------------


def test_attachments_line_names_each_path():
    """An item with attachments renders an **Attachments:** line naming each path."""
    action = _base_action(attachments=[ATTACHMENT_PATH, "100 Inbox/scan.pdf"])
    md = render_create_atomic_note(action, "prague-trip", "")
    assert f"**Attachments:** `{ATTACHMENT_PATH}`" in md
    assert "`100 Inbox/scan.pdf`" in md


def test_no_attachments_line_when_list_absent():
    """An item with no attachments renders no **Attachments:** line."""
    action = _base_action()
    md = render_create_atomic_note(action, "prague-trip", "")
    assert "**Attachments:**" not in md


def test_no_attachments_line_when_list_empty():
    """An empty attachments list also renders no **Attachments:** line."""
    action = _base_action(attachments=[])
    md = render_create_atomic_note(action, "prague-trip", "")
    assert "**Attachments:**" not in md


# ---------------------------------------------------------------------------
# **Source:** line must be unchanged for a voice item with audio_peer —
# no regression on the positional wikilink encoding (suggestion-parser.py:712).
# ---------------------------------------------------------------------------


def test_source_line_unchanged_for_audio_peer_item_with_attachments():
    """Adding attachments must not touch the **Source:** line's wikilink encoding."""
    action = _base_action(
        audio_peer="100 Inbox/recording.m4a",
        attachments=[ATTACHMENT_PATH],
    )
    md = render_create_atomic_note(action, "voice-note", "")
    source_line = md.split("\n")[0]
    assert source_line == "**Source:** [[voice-note]] + [[recording.m4a]]"


# ---------------------------------------------------------------------------
# Unresolved-embed reporting (Should-have) — **Unresolved embeds:** line
# ---------------------------------------------------------------------------


def test_unresolved_embeds_line_rendered_when_present():
    """Unresolved/ambiguous embeds render an **Unresolved embeds:** line."""
    action = _base_action(
        unresolved_embeds=[
            {"embed_target": "karte.jpg", "status": "ambiguous", "candidate_count": 2},
            {"embed_target": "missing.jpg", "status": "unresolved", "candidate_count": 0},
        ]
    )
    md = render_create_atomic_note(action, "prague-trip", "")
    assert "**Unresolved embeds:**" in md
    line = next(ln for ln in md.split("\n") if ln.startswith("**Unresolved embeds:**"))
    assert "`karte.jpg`" in line and "ambiguous — 2 candidates" in line
    assert "`missing.jpg`" in line and "unresolved" in line


def test_no_unresolved_embeds_line_when_absent():
    """No unresolved_embeds data → no **Unresolved embeds:** line (CON-8 shape)."""
    action = _base_action()
    md = render_create_atomic_note(action, "prague-trip", "")
    assert "**Unresolved embeds:**" not in md


def test_no_unresolved_embeds_line_when_empty():
    """An empty unresolved_embeds list also renders no line."""
    action = _base_action(unresolved_embeds=[])
    md = render_create_atomic_note(action, "prague-trip", "")
    assert "**Unresolved embeds:**" not in md


# ---------------------------------------------------------------------------
# Structured mirror — the `item` dict built by the reducer's per-action loop
# (CON-5). Driven end-to-end via the real item-result.json -> suggestions-doc.json
# path (subprocess), matching the pattern in test_suggestions_reducer_multi_atomic.py.
# ---------------------------------------------------------------------------

_extra = str(SCRIPTS_DIR)
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}


def _write_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": "test-t32",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _write_state(path: Path, stem: str) -> None:
    path.write_text(json.dumps({
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "status": "done",
        "run_id": "test-t32",
        "ts": "2026-09-05T10:00:00Z",
    }) + "\n", encoding="utf-8")


def _write_result(items_dir: Path, stem: str, atomic_overrides: dict) -> None:
    """`attachments` in atomic_overrides is NOT applied to the action here —
    the analyst never produces this field (ADR-2); `_write_resolved_attachments`
    is the actual source, consumed via merge_resolved_attachments."""
    items_dir.mkdir(parents=True, exist_ok=True)
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "Prague Trip",
        "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "needs_new_moc": False,
        "tags_to_add": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "alternatives": [],
    }
    action.update({k: v for k, v in atomic_overrides.items() if k != "attachments"})
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "force_atomic": False,
        "actions": [action],
        "issues": [],
        "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _write_resolved_attachments(path: Path, stem: str, attachments: list | None) -> None:
    """The reducer sources `attachments` from this map, keyed by source path,
    not from the item-result.json's action (Phase 6 gap fix — the analyst
    never produces this field; merge_resolved_attachments is authoritative)."""
    entry = {"attachments": attachments, "unresolved_embeds": []} if attachments is not None else {}
    path.write_text(json.dumps({f"100 Inbox/{stem}.md": entry} if entry else {}), encoding="utf-8")


def _run_reducer(tmp_path: Path, stem: str, atomic_overrides: dict) -> dict:
    items_dir = tmp_path / "items"
    shared_ctx = tmp_path / "shared-ctx.json"
    resolved_attachments = tmp_path / "resolved-attachments.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _write_shared_ctx(shared_ctx)
    _write_resolved_attachments(resolved_attachments, stem, atomic_overrides.get("attachments"))
    _write_state(state, stem)
    _write_result(items_dir, stem, atomic_overrides)

    result = subprocess.run(
        [
            sys.executable, str(REDUCER_PATH),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", "test-t32",
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--output", str(output),
            "--resolved-attachments", str(resolved_attachments),
            "--no-kado",
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, (
        f"reducer exit {result.returncode};\nstderr:\n{result.stderr}"
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _atomic_action(doc: dict) -> dict:
    return doc["sections"][0]["actions"][0]


def test_structured_item_mirror_carries_identical_attachments_list(tmp_path):
    """The structured `item` dict carries the identical attachments list (CON-5)."""
    attachments = [ATTACHMENT_PATH, "100 Inbox/scan.pdf"]
    doc = _run_reducer(tmp_path, "prague-trip", {"attachments": attachments})
    action = _atomic_action(doc)
    assert action["item"]["attachments"] == attachments


def test_structured_item_mirror_defaults_to_empty_list(tmp_path):
    """An item without attachments carries an empty list on the structured mirror."""
    doc = _run_reducer(tmp_path, "prague-trip", {})
    action = _atomic_action(doc)
    assert action["item"]["attachments"] == []


def test_both_channels_carry_the_same_attachments_list_for_the_same_item(tmp_path):
    """CON-5: markdown and structured mirror must be in lockstep for one item."""
    attachments = [ATTACHMENT_PATH]
    doc = _run_reducer(tmp_path, "prague-trip", {"attachments": attachments})
    action = _atomic_action(doc)
    for path in attachments:
        assert f"`{path}`" in action["rendered_md"]
    assert action["item"]["attachments"] == attachments
