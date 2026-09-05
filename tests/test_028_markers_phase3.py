#!/usr/bin/env python3
# version: 0.1.1
"""test_028_markers_phase3.py — spec 028 Phase 3: relationship markers from profile (F-16).

Covers the read + write marker seams de-hardcoded in Phase 3:

  T3.1 lib/up_parse.parse_up_from_content       — parse via injected parent_marker
  T3.2 lib/render_actions                       — read regexes + write literals from markers,
                                                   byte-identical miyo add_relationship regression
  T3.3 moc-discovery.phase65_validate_existing_up — up:: state resolution via parent_marker
  T3.4 suggestion-parser                        — override header marker from suggestions-doc
                                                   conventions block, fallback to up::

CRITICAL: markers are identical in both bundled profiles (up:: / related::), so the
default-path assertions below double as the miyo/lyt byte-identity guard.

Stdlib + local libs only; Kado is faked. Run under ./venv/bin/python.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import lib.up_parse as up_parse  # noqa: E402
import lib.render_actions as ra  # noqa: E402


def _load_script(name: str, mod_name: str):
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


moc_discovery = _load_script("moc-discovery.py", "moc_discovery")
suggestion_parser = _load_script("suggestion-parser.py", "suggestion_parser")


# ──────────────────────────────────────────────────────────────────────────────
# T3.1 — up_parse.parse_up_from_content
# ──────────────────────────────────────────────────────────────────────────────


def test_up_parse_default_up_marker_byte_identical():
    """Default parent_marker keeps the exact up:: inline + frontmatter behaviour."""
    assert up_parse.parse_up_from_content("up:: [[Bar]]\n").target == "Bar"
    fm = '---\nup: "[[FMParent]]"\n---\nbody\n'
    r = up_parse.parse_up_from_content(fm)
    assert r.target == "FMParent"
    assert r.source == "frontmatter"


def test_up_parse_custom_parent_marker_inline():
    """A non-default parent_marker matches its own inline marker, not up::."""
    content = "parent:: [[Foo]]\n"
    assert up_parse.parse_up_from_content(content).target is None  # default up:: ignores it
    r = up_parse.parse_up_from_content(content, parent_marker="parent::")
    assert r.target == "Foo"
    assert r.source == "inline"


def test_up_parse_custom_parent_marker_frontmatter():
    """The frontmatter key follows the marker word of the injected marker."""
    content = '---\nparent: "[[Foo]]"\n---\nbody\n'
    r = up_parse.parse_up_from_content(content, parent_marker="parent::")
    assert r.target == "Foo"
    assert r.source == "frontmatter"


# ──────────────────────────────────────────────────────────────────────────────
# T3.2 — render_actions read/write markers
# ──────────────────────────────────────────────────────────────────────────────


def test_extract_first_up_marker_from_parent_marker():
    body = "parent:: [[X]]\n"
    assert ra.extract_first_up_marker(body) is None  # default up::
    assert ra.extract_first_up_marker(body, parent_marker="parent::") == "X"
    assert ra.extract_first_up_marker("up:: [[Y]]\n") == "Y"  # default unchanged


def test_extract_existing_related_from_peer_marker():
    assert ra._extract_existing_related("related:: [[A]], [[B]]") == ["A", "B"]
    assert ra._extract_existing_related("peer:: [[A]]") == []  # default related::
    assert ra._extract_existing_related(
        "peer:: [[A]], [[B]]", peer_marker="peer::"
    ) == ["A", "B"]


class _FakeKado:
    """Minimal Kado fake for render_actions write-path tests.

    stem → (path, body). Unregistered stems resolve to None (child-missing).
    """

    def __init__(self, notes: dict[str, tuple[str, str]]):
        self._notes = dict(notes)

    def resolve_stem_to_path(self, stem: str):
        if stem not in self._notes:
            raise ra.KadoError(f"NOT_FOUND: {stem!r}")
        return self._notes[stem][0]

    def read_note(self, path: str) -> dict:
        for _s, (p, body) in self._notes.items():
            if p == path:
                return {"content": body}
        raise ra.KadoError(f"NOT_FOUND path: {path!r}")


def test_emit_up_preservation_child_missing_uses_parent_marker():
    """child-missing sentinel line uses the injected parent_marker."""
    kado = _FakeKado({})  # every resolve → KadoError → child_path None
    actions = ra.emit_up_preservation_actions(
        "ghost", "New (MOC)", override_flag=False, kado_client=kado, counter=[0],
        parent_marker="parent::",
    )
    assert actions[0]["marker"] == "parent::"
    assert actions[0]["line"] == "parent:: [[New (MOC)]]"


def test_emit_up_preservation_rule_42_custom_markers():
    """Rule 4.2: existing parent link demoted to peer marker, new becomes parent."""
    kado = _FakeKado({
        "child-a": ("Atlas/202 Notes/child-a.md", "parent:: [[OldParent]]\n"),
        "OldParent": ("Atlas/200 Maps/OldParent.md", "# old\n"),
    })
    actions = ra.emit_up_preservation_actions(
        "child-a", "New Topic (MOC)", override_flag=False, kado_client=kado, counter=[0],
        parent_marker="parent::", peer_marker="peer::",
    )
    lines = [(a["marker"], a["line"]) for a in actions]
    assert lines == [
        ("parent::", "parent:: [[New Topic (MOC)]]"),
        ("peer::", "peer:: [[OldParent]]"),
    ]


_CFG = {
    "concepts.inbox": "0 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Log",
    "daily_log.heading_level": 2,
}


def _moc_proposal_manifest():
    return [{
        "action": "create_moc",
        "title": "New Topic (MOC)",
        "rendered_file": "new-topic.md",
        "destination": "Atlas/200 Maps/",
        "supporting_items": "child-a",
        "override_preserve_existing_up": False,
    }]


def _add_rel_lines(actions):
    return [(a["marker"], a["line"]) for a in actions if a.get("action") == "add_relationship"]


def test_build_actions_miyo_add_relationship_byte_identical():
    """miyo (default) add_relationship lines are byte-identical to the baseline."""
    kado = _FakeKado({
        "child-a": ("Atlas/202 Notes/child-a.md", "up:: [[OldParent]]\n"),
        "OldParent": ("Atlas/200 Maps/OldParent.md", "# old\n"),
    })
    actions, _skipped_assets = ra.build_actions(
        _moc_proposal_manifest(), [], [], [], _CFG,
        kado_client=kado,
    )
    assert _add_rel_lines(actions) == [
        ("up::", "up:: [[New Topic (MOC)]]"),
        ("related::", "related:: [[OldParent]]"),
    ]


def test_build_actions_threads_custom_markers():
    """Passing custom markers threads through the whole write path."""
    kado = _FakeKado({
        "child-a": ("Atlas/202 Notes/child-a.md", "parent:: [[OldParent]]\n"),
        "OldParent": ("Atlas/200 Maps/OldParent.md", "# old\n"),
    })
    actions, _skipped_assets = ra.build_actions(
        _moc_proposal_manifest(), [], [], [], _CFG,
        kado_client=kado, parent_marker="parent::", peer_marker="peer::",
    )
    assert _add_rel_lines(actions) == [
        ("parent::", "parent:: [[New Topic (MOC)]]"),
        ("peer::", "peer:: [[OldParent]]"),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# T3.3 — moc-discovery phase65 warning/state regex from parent_marker
# ──────────────────────────────────────────────────────────────────────────────


class _FakeKadoRead:
    def __init__(self, notes_by_path: dict[str, str]):
        self._notes = dict(notes_by_path)

    def read_note(self, path: str) -> dict:
        if path not in self._notes:
            raise FileNotFoundError(path)
        return {"content": self._notes[path]}


def _cache(moc_paths):
    return {"map_notes": [{"path": p, "title": s, "topics": []} for s, p in moc_paths]}


def test_phase65_default_up_marker_valid():
    """Default up:: resolves a valid parent unchanged (byte-identity guard)."""
    candidates = [moc_discovery.Candidate(stem="child", path="Atlas/202 Notes/child.md")]
    clusters = [{"topic": "t", "items": ["child"], "parent": "", "tags": []}]
    kado = _FakeKadoRead({"Atlas/202 Notes/child.md": "up:: [[MOC-X]]\n"})
    cache = _cache([("MOC-X", "Atlas/200 Maps/MOC-X.md")])
    out = moc_discovery.phase65_validate_existing_up(clusters, candidates, kado, cache)
    assert out[0]["existing_up"] == [{"stem": "child", "state": "valid", "target": "MOC-X"}]


def test_phase65_custom_parent_marker_resolves_state():
    """With parent_marker='parent::', a parent:: link is resolved (up:: would be absent)."""
    candidates = [moc_discovery.Candidate(stem="child", path="Atlas/202 Notes/child.md")]
    clusters = [{"topic": "t", "items": ["child"], "parent": "", "tags": []}]
    kado = _FakeKadoRead({"Atlas/202 Notes/child.md": "parent:: [[MOC-X]]\n"})
    cache = _cache([("MOC-X", "Atlas/200 Maps/MOC-X.md")])

    # default up:: sees no marker → absent
    out_default = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )
    assert out_default[0]["existing_up"][0]["state"] == "absent"

    out_custom = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache, parent_marker="parent::"
    )
    assert out_custom[0]["existing_up"] == [
        {"stem": "child", "state": "valid", "target": "MOC-X"}
    ]


# ──────────────────────────────────────────────────────────────────────────────
# T3.4 — suggestion-parser override header marker from conventions block
# ──────────────────────────────────────────────────────────────────────────────


def _write_suggestions_doc(tmpdir: str, conventions: dict | None) -> str:
    doc: dict = {"sections": [], "proposed_mocs": []}
    if conventions is not None:
        doc["conventions"] = conventions
    path = Path(tmpdir) / "suggestions-doc.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def test_parent_marker_from_doc_with_conventions_block():
    with tempfile.TemporaryDirectory() as td:
        p = _write_suggestions_doc(td, {"parent_marker": "parent::", "peer_marker": "peer::"})
        assert suggestion_parser._parent_marker_from_doc(p) == "parent::"


def test_parent_marker_from_doc_absent_block_falls_back():
    with tempfile.TemporaryDirectory() as td:
        p = _write_suggestions_doc(td, None)  # older artifact — no conventions block
        assert suggestion_parser._parent_marker_from_doc(p) == "up::"


def test_parent_marker_from_doc_missing_file_falls_back():
    assert suggestion_parser._parent_marker_from_doc("/nonexistent/suggestions-doc.json") == "up::"


_MOC_PROPOSAL_BODY = """---
tomo:
  doc_type: moc-proposal
---

### MOC01 — New Topic

- [x] Accept

#### {marker}-Handling Override

- [x] Bestehende {marker} behalten
"""


def test_moc_proposal_override_header_default_up_marker():
    body = _MOC_PROPOSAL_BODY.format(marker="up::")
    results = suggestion_parser.parse_moc_proposal_doc(body, filename="tomo-moc-proposal-x.md")
    assert results and results[0]["override_preserve_existing_up"] is True


def test_moc_proposal_override_header_custom_marker():
    body = _MOC_PROPOSAL_BODY.format(marker="parent::")
    # default up:: must NOT detect the parent::-Handling Override header
    default = suggestion_parser.parse_moc_proposal_doc(
        body, filename="tomo-moc-proposal-x.md"
    )
    assert default and default[0]["override_preserve_existing_up"] is False
    # injected parent:: detects it
    custom = suggestion_parser.parse_moc_proposal_doc(
        body, filename="tomo-moc-proposal-x.md", parent_marker="parent::"
    )
    assert custom and custom[0]["override_preserve_existing_up"] is True
