#!/usr/bin/env python3
# version: 0.2.0
"""test_instruction_render_collision_guard.py — filename collision guard (C5, F-41).

T5.1 (XDD-016): Verifies that _disambiguate_filename() produces distinct filenames
when multiple atomic notes from one source would otherwise slugify to the same
filename, and raises loudly when the suffix space is exhausted.

Tests:
  1. test_distinct_titles_no_suffix — 2 distinct slugs → 2 distinct filenames unchanged
  2. test_identical_titles_get_suffix — 2 identical slugs → first unsuffixed, second _01
  3. test_suffix_reflects_action_order — first unsuffixed, second _01, third _02, etc.
  4. test_exhausted_suffix_raises — collision beyond _99 raises ValueError
  5. test_loop_degrades_gracefully_on_exhaustion — call-site ValueError caught, errors
     incremented, remaining items still render and appear in the manifest (W1 coverage)

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
SDD:  C5 (filename collision guard), ADR-7
AC:   PRD/A6 (N distinct notes per source)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_distinct_titles_no_suffix():
    """Two atomics with distinct slugified titles produce distinct filenames
    without any numeric suffix (common-case path must be byte-for-byte
    unchanged — CON-2 regression guarantee, PRD/A6).
    """
    used: set[str] = set()

    filename_a = ir._disambiguate_filename("2026-06-11_0900_alpha.md", used)
    used.add(filename_a)
    filename_b = ir._disambiguate_filename("2026-06-11_0900_beta.md", used)
    used.add(filename_b)

    assert filename_a == "2026-06-11_0900_alpha.md"
    assert filename_b == "2026-06-11_0900_beta.md"
    assert filename_a != filename_b


def test_identical_titles_get_suffix():
    """Two atomics that slugify to the same filename: first occurrence keeps the
    base name; second occurrence gets _01 suffix.
    Both files are distinct — no overwrite (SDD/ADR-7).
    """
    used: set[str] = set()
    base = "2026-06-11_0900_duplicate-topic.md"

    first = ir._disambiguate_filename(base, used)
    used.add(first)
    second = ir._disambiguate_filename(base, used)
    used.add(second)

    # First occurrence: no suffix needed
    assert first == base
    # Second occurrence: _01 suffix
    assert second == "2026-06-11_0900_duplicate-topic_01.md"
    assert first != second


def test_suffix_reflects_action_order():
    """First occurrence is unsuffixed, second gets _01, third gets _02, etc.
    Suffix sequence reflects stable iteration order.
    """
    used: set[str] = set()
    base = "2026-06-11_0900_same-slug.md"

    first = ir._disambiguate_filename(base, used)
    used.add(first)
    second = ir._disambiguate_filename(base, used)
    used.add(second)
    third = ir._disambiguate_filename(base, used)
    used.add(third)

    assert first == base
    assert second == "2026-06-11_0900_same-slug_01.md"
    assert third == "2026-06-11_0900_same-slug_02.md"
    # All three are distinct
    assert len({first, second, third}) == 3


def test_exhausted_suffix_raises():
    """When suffix space is exhausted (collision even after _99) the function
    raises ValueError naming the slug — never silently overwrites (SDD/Error Handling).
    """
    # Pre-fill `used` with base + _01 through _99
    base = "2026-06-11_0900_crowded.md"
    stem = "2026-06-11_0900_crowded"
    used: set[str] = {base}
    for i in range(1, 100):
        used.add(f"{stem}_{i:02d}.md")

    with pytest.raises((ValueError, RuntimeError)):
        ir._disambiguate_filename(base, used)


def test_loop_degrades_gracefully_on_exhaustion(monkeypatch, tmp_path):
    """Render loop catches ValueError from _disambiguate_filename, increments
    errors, and continues — remaining items still appear in the manifest.

    W1/W2 (XDD-016): The try/except at the call site matches the existing
    graceful-degradation pattern; one bad item never aborts the whole run.
    """
    # Two confirmed items that both have a template (so they reach the
    # _disambiguate_filename call site).
    suggestions = {
        "confirmed_items": [
            {
                "id": "item-1",
                "action": "create_note",
                "title": "Collision Topic",
                "template": "templates/atomic.md",
                "source_path": "",
                "tags": [],
                "parent_moc": "",
                "parent_mocs": [],
                "destination": "200 Notes/",
                "summary": "",
            },
            {
                "id": "item-2",
                "action": "create_note",
                "title": "Safe Topic",
                "template": "templates/atomic.md",
                "source_path": "",
                "tags": [],
                "parent_moc": "",
                "parent_mocs": [],
                "destination": "200 Notes/",
                "summary": "",
            },
        ],
        "daily_updates": [],
        "skipped": [],
    }
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")

    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    # Stub load_config so we never need a real YAML file.
    monkeypatch.setattr(
        ir,
        "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox",
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )

    # Stub KadoClient so we never hit a real vault.
    fake_client = MagicMock()
    monkeypatch.setattr(ir, "KadoClient", lambda: fake_client)

    # Stub read_template to return a minimal template string.
    monkeypatch.setattr(ir, "read_template", lambda _client, _ref: "# {{title}}\n")

    # Stub render_via_script so the render step always succeeds.
    monkeypatch.setattr(
        ir,
        "render_via_script",
        lambda _tmpl, _tokens, _cfg: "# Rendered\n",
    )

    # Stub _disambiguate_filename: raise ValueError for item-1, succeed for item-2.
    real_disambiguate = ir._disambiguate_filename
    call_count = {"n": 0}

    def _fake_disambiguate(base_filename: str, used_filenames: set) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ValueError("exhausted for slug 'collision-topic' — test injection")
        return real_disambiguate(base_filename, used_filenames)

    monkeypatch.setattr(ir, "_disambiguate_filename", _fake_disambiguate)

    # Stub downstream steps that require a real vault (path validation and
    # action builders call Kado; we want to isolate the render loop only).
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: [])
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(ir, "render_instructions_md", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "backfill_supporting_items_parents", lambda _items: None)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(tmp_path / "out"),
            "--config", str(cfg_file),
        ],
    )

    rc = ir.main()

    # main() should complete without raising; non-zero rc is acceptable since
    # one item errored, but it must not crash with an unhandled exception.
    assert isinstance(rc, int)

    # The manifest must contain item-2 (the surviving item) and NOT item-1.
    manifest_path = tmp_path / "out" / "manifest.json"
    assert manifest_path.exists(), "manifest.json must be written even when one item errors"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in manifest]
    assert "item-1" not in ids, "errored item must not appear in the manifest"
    assert "item-2" in ids, "surviving item must appear in the manifest"
