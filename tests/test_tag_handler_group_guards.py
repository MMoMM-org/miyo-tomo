#!/usr/bin/env python3
# version: 0.2.0
"""test_tag_handler_group_guards.py — T4.2 (spec 024 Phase 4).

The two Pass-1 guards (FR-11 / FR-12) that stop an unappliable tag-handler group
from reaching a Hashi instruction:
  - FR-11 target note missing on disk  → "create it first" checkbox, no Approve.
  - FR-12 marker absent in an existing target → error item, no Approve.
  - happy path (target + marker present) → normal approvable block → instruction.

Marker-existence is a filesystem-access path (Constitution L1 denial-path
coverage), so it is exercised through a FAKE Kado client whose read_note returns
note bodies / raises KadoNotFoundError — never pre-supplied guard input.

The gate is structural: a guarded block renders WITHOUT a `- [x] Approve` box,
so suggestion-parser never extracts its group id and instruction-render emits no
insert_under_marker. The end-to-end test proves that chain.

Fixtures conform to tomo/schemas/tag-handler-group.schema.json.
Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §5; requirements FR-11/FR-12/AC-4.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_group_mod = _load("tag_handler_group", "tag-handler-group.py")
_reducer_mod = _load("suggestions_reducer", "suggestions-reducer.py")
_parser_mod = _load("suggestion_parser", "suggestion-parser.py")
_render_mod = _load("instruction_render", "instruction-render.py")

group_id = _group_mod.group_id
annotate_tag_handler_group_guards = _reducer_mod.annotate_tag_handler_group_guards
render_tag_handler_group = _reducer_mod.render_tag_handler_group
render_tag_handler_updates_block = _reducer_mod.render_tag_handler_updates_block
_marker_present = _reducer_mod._marker_present
parse_tag_handler_groups = _parser_mod.parse_tag_handler_groups
_build_insert_under_marker_actions = _render_mod._build_insert_under_marker_actions

from lib.kado_client import KadoNotFoundError  # noqa: E402


# ── Fake vault ────────────────────────────────────────────────────────────────


class FakeKado:
    """A fake Kado client. read_note returns {content} for known paths and
    raises KadoNotFoundError for absent ones — the filesystem-access surface
    the marker guard reads through (FR-12)."""

    def __init__(self, notes: dict[str, str]):
        # notes: {vault_path(.md): full file content incl. frontmatter}
        self._notes = notes
        self.reads: list[str] = []

    def read_note(self, path: str) -> dict:
        self.reads.append(path)
        if path not in self._notes:
            raise KadoNotFoundError(f"not found: {path}")
        return {"content": self._notes[path]}


_NOTE_WITH_MARKER = (
    "---\ntype: dev-log\n---\n\n"
    "# Tomo Dev Log\n\n"
    "## Captures\n\n"
    "- 2026-06-20 — earlier entry\n"
)
_NOTE_WITHOUT_MARKER = (
    "---\ntype: dev-log\n---\n\n"
    "# Tomo Dev Log\n\n"
    "## Notes\n\n"
    "- something else\n"
)


def _group(
    *,
    handler: str = "tsukai",
    target_path: str | None = "Efforts/400 On/Tomo Dev Log.md",
    marker: str = "## Captures",
    composed_block: str = "### 2026-06-23\n\n- Shipped X (feature)",
    source_paths: list[str] | None = None,
    placement: str | None = "inside",
) -> dict:
    g: dict[str, Any] = {
        "schema_version": "1",
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "composed_block": composed_block,
        "source_paths": source_paths or ["100 Inbox/MiYo-Tsukai-Tomo-cap-1.md"],
    }
    if placement is not None:
        g["placement"] = placement
    return g


# ── _marker_present helper ────────────────────────────────────────────────────


def test_marker_present_matches_heading():
    assert _marker_present(_NOTE_WITH_MARKER, "## Captures") is True


def test_marker_present_absent():
    assert _marker_present(_NOTE_WITHOUT_MARKER, "## Captures") is False


def test_marker_present_whitespace_tolerant():
    """Extra spaces in the note heading still match the config marker."""
    body = "# Title\n\n##   Captures  \n\n- x\n"
    assert _marker_present(body, "## Captures") is True


def test_marker_present_not_substring():
    """A heading that merely contains the marker text is NOT a match."""
    body = "# Title\n\n## Captures and More\n"
    assert _marker_present(body, "## Captures") is False


# ── Guard annotation: the three outcomes ──────────────────────────────────────


def test_guard_ok_when_target_and_marker_present():
    g = _group()
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITH_MARKER})
    tally = annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "ok"
    assert tally["ok"] == 1


def test_guard_target_missing():
    """FR-11: target note absent on disk → guard=target_missing (fake-vault read)."""
    g = _group()
    client = FakeKado({})  # empty vault — read_note raises NotFound
    tally = annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "target_missing"
    assert tally["target_missing"] == 1


def test_guard_marker_missing():
    """FR-12: target exists but marker heading absent → guard=marker_missing."""
    g = _group()
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITHOUT_MARKER})
    tally = annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "marker_missing"
    assert tally["marker_missing"] == 1


def test_guard_reads_md_normalised_path():
    """An extensionless target_path is read as .md (Kado note read is .md-only)."""
    g = _group(target_path="Efforts/400 On/Tomo Dev Log")  # no extension
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITH_MARKER})
    annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "ok"
    assert client.reads == ["Efforts/400 On/Tomo Dev Log.md"]


def test_guard_fail_open_none_client():
    """No Kado client (offline/test) → guard stays unset, never blocks (fail-open)."""
    g = _group()
    tally = annotate_tag_handler_group_guards([g], None)
    assert "guard" not in g
    assert tally == {"ok": 0, "target_missing": 0, "marker_missing": 0}


def test_guard_fail_open_transient_error():
    """A non-not-found read error keeps guard='ok' — never block on a transient fault."""
    class _Boom:
        def read_note(self, path):
            raise RuntimeError("kado 500")

    g = _group()
    annotate_tag_handler_group_guards([g], _Boom())
    assert g["guard"] == "ok"


def test_guard_fail_open_empty_response():
    """An empty/anomalous read response ({} — no raise) fails open to ok, NOT
    marker_missing (W1): with no body, marker presence is indeterminate, so the
    group must not be blocked on a transport glitch."""
    class _Empty:
        def read_note(self, path):
            return {}  # empty dict, no content, no exception

    g = _group()
    annotate_tag_handler_group_guards([g], _Empty())
    assert g["guard"] == "ok"


def test_guard_null_target_untouched():
    """A group whose target_path is already null is left for the unresolved path."""
    g = _group(target_path=None)
    client = FakeKado({})
    annotate_tag_handler_group_guards([g], client)
    assert "guard" not in g


def test_guard_dedup_one_read_per_target():
    """Two groups sharing (target, marker) read the target once."""
    g1 = _group()
    g2 = _group(source_paths=["100 Inbox/MiYo-Tsukai-Tomo-cap-2.md"])
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITH_MARKER})
    annotate_tag_handler_group_guards([g1, g2], client)
    assert g1["guard"] == "ok" and g2["guard"] == "ok"
    assert client.reads == ["Efforts/400 On/Tomo Dev Log.md"]  # deduped


# ── Render: guarded blocks carry no Approve box ───────────────────────────────


def test_render_target_missing_no_approve_box():
    g = _group()
    g["guard"] = "target_missing"
    block = render_tag_handler_group(g)
    assert "Create it first" in block
    assert "- [x] Approve" not in block
    assert "- [ ] Approve" not in block


def test_render_marker_missing_no_approve_box():
    g = _group()
    g["guard"] = "marker_missing"
    block = render_tag_handler_group(g)
    assert "Marker not found" in block
    assert "`## Captures`" in block
    assert "- [x] Approve" not in block


def test_render_ok_keeps_approve_box():
    g = _group()
    g["guard"] = "ok"
    block = render_tag_handler_group(g)
    assert "- [x] Approve" in block


def test_render_absent_guard_keeps_approve_box():
    """A group with no guard key (e.g. fail-open) still renders approvable."""
    g = _group()  # no "guard"
    block = render_tag_handler_group(g)
    assert "- [x] Approve" in block


# ── End-to-end: guarded group → no instruction ────────────────────────────────


def _approved_then_actions(groups: list[dict]) -> list[dict]:
    """Run the gate chain: render section → parse approved ids → build actions."""
    md = render_tag_handler_updates_block(groups)
    approved = parse_tag_handler_groups(md)
    return _build_insert_under_marker_actions(groups, approved, [0])


def test_e2e_target_missing_emits_no_instruction():
    g = _group()
    g["guard"] = "target_missing"
    assert _approved_then_actions([g]) == []


def test_e2e_marker_missing_emits_no_instruction():
    g = _group()
    g["guard"] = "marker_missing"
    assert _approved_then_actions([g]) == []


def test_e2e_ok_emits_instruction():
    g = _group()
    g["guard"] = "ok"
    actions = _approved_then_actions([g])
    assert len(actions) == 1
    assert actions[0]["action"] == "insert_under_marker"
    assert actions[0]["target_path"] == g["target_path"]


def test_e2e_mixed_only_ok_group_emits():
    """A guarded group and an ok group together → exactly one instruction (the ok one)."""
    ok = _group(target_path="Efforts/400 On/Tomo Dev Log.md")
    ok["guard"] = "ok"
    bad = _group(handler="reading-log", target_path="Atlas/Reading Log.md")
    bad["guard"] = "marker_missing"
    actions = _approved_then_actions([ok, bad])
    assert len(actions) == 1
    assert actions[0]["target_path"] == "Efforts/400 On/Tomo Dev Log.md"


# ── Full annotate→render→parse→build chain through the fake vault ─────────────


def test_full_chain_marker_missing_via_fake_vault():
    """Drive the WHOLE chain from a real Kado read: a note that exists but lacks
    the marker yields no instruction, with the guard decided by the fake read."""
    g = _group()
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITHOUT_MARKER})
    annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "marker_missing"
    assert _approved_then_actions([g]) == []


def test_full_chain_ok_via_fake_vault():
    g = _group()
    client = FakeKado({"Efforts/400 On/Tomo Dev Log.md": _NOTE_WITH_MARKER})
    annotate_tag_handler_group_guards([g], client)
    assert g["guard"] == "ok"
    actions = _approved_then_actions([g])
    assert len(actions) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
