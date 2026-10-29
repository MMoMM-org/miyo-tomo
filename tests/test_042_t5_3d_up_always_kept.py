#!/usr/bin/env python3
# version: 0.1.0
"""Spec 042 T5.3d — an existing up:: is always kept; the doc says what happens.

Owner decision 2026-10-29: no user-written up:: is dropped. Rule 4.3 is
retired, so a target that is not a MOC or does not exist is handled like a
valid one (Rule 4.2 / 4.5), with no kado-graph check. The proposal doc labels
each case by what render will do; Phase 6.5 rows and link members carry the
broken reason the label needs.

Mechanisms each test falsifies:
  - render: the 4.3 branch (drop) and the up_target_is_broken graph check;
  - doc: the "broken — ignored" branch of _child_annotation and a reason that
    is not threaded through _link_member_lines;
  - data: a Phase 6.5 that classifies without a reason, a LinkMember that
    drops the cache's up_broken_reason, member dicts that do not copy it;
  - diff: instructions-diff counting add_relationship per member.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib import link_members as lm  # noqa: E402
from lib import render_actions as ra  # noqa: E402
from test_042_t4_4_extension_render import (  # noqa: E402
    MOC,
    _build,
    _extension,
    _of,
    _run_main,
    _vault,
)
from test_042_t4_4_extension_render import diff as _diff  # noqa: E402
from test_instruction_render_up_preservation import _FakeKadoClient  # noqa: E402
from test_reducer_moc_proposal_mode import (  # noqa: E402
    _Cfg,
    _extension_doc,
    _extension_report,
    _link_member,
    _link_report,
    render_moc_proposal_doc,
)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_disc = _load("moc_discovery_t53d", "moc-discovery.py")
_reducer = _load("suggestions_reducer_t53d", "suggestions-reducer.py")

NEW_MOC = "New MOC"
ARROW_RELATED = "→ becomes `related::`"


class _NoGraphKado(_FakeKadoClient):
    """The Rule 4.x fake whose graph() fails the test: render must not ask."""

    def graph(self, operation, path, limit=None):  # noqa: ARG002
        raise AssertionError(f"render asked kado-graph {operation!r} for {path!r}")


def _child(target: str, existing: set[str]) -> _NoGraphKado:
    body = f"# child\n\nup:: [[{target}]]\n"
    return _NoGraphKado(
        notes={"child": ("Atlas/202 Notes/child.md", body)}, existing_paths=existing,
    )


def _emit(kado, override: bool) -> list[tuple[str, str]]:
    actions = ra.emit_up_preservation_actions(
        "child", NEW_MOC, override_flag=override, kado_client=kado, counter=[0],
    )
    return [(a["marker"], a["line"]) for a in actions]


# ── Render ───────────────────────────────────────────────────────────────────

# not-a-moc: the target is a real note that is not a MOC.
# unresolved: no note by that name exists.
_TARGETS = {
    "not-a-moc": ("Some Plain Note", {"Some Plain Note"}),
    "unresolved": ("Gone MOC", set()),
}


@pytest.mark.parametrize("reason", sorted(_TARGETS))
def test_override_unticked_keeps_any_existing_up_as_related(reason):
    """Rule 4.2 for every target: new MOC up::, old target related::."""
    target, existing = _TARGETS[reason]
    assert _emit(_child(target, existing), override=False) == [
        ("up::", f"up:: [[{NEW_MOC}]]"),
        ("related::", f"related:: [[{target}]]"),
    ]


@pytest.mark.parametrize("reason", sorted(_TARGETS))
def test_override_ticked_keeps_any_existing_up_untouched(reason):
    """Rule 4.5 for every target: the old up:: stays, new MOC related::."""
    target, existing = _TARGETS[reason]
    assert _emit(_child(target, existing), override=True) == [
        ("related::", f"related:: [[{NEW_MOC}]]"),
    ]


def test_self_link_guard_still_emits_nothing():
    assert _emit(_child(NEW_MOC, set()), override=False) == []


def test_the_broken_target_check_is_gone():
    """Rule 4.3's only helper is removed, not left behind unused."""
    assert not hasattr(ra, "up_target_is_broken")


def test_extension_member_with_unresolved_up_keeps_it_as_related():
    """extend_moc goes through the same function: no drop there either."""
    kado = _vault()
    kado._notes["child"] = ("Atlas/202 Notes/child.md", "up:: [[Gone MOC]]\n")
    kado._existing.add("child")
    rels = _of(_build(kado, [_extension(["child"])]), "add_relationship")
    assert [(a["marker"], a["line"]) for a in rels] == [
        ("up::", f"up:: [[{MOC}]]"),
        ("related::", "related:: [[Gone MOC]]"),
    ]
    assert not any(op == "dangling" for op, _p in kado.graph_calls)


def test_diff_accepts_two_relationship_actions_for_an_unresolved_member(
    monkeypatch, tmp_path,
):
    """Paired consumer: 4.2's two actions on a once-4.3 member still reconcile."""
    kado = _vault()
    kado._notes["child"] = ("Atlas/202 Notes/child.md", "up:: [[Gone MOC]]\n")
    kado._existing.add("child")
    ext = _extension(["child"])
    rc, doc, _md = _run_main(monkeypatch, tmp_path, kado, [ext])
    assert rc == 0
    rels = [a for a in doc["actions"] if a["action"] == "add_relationship"]
    assert len(rels) == 2
    parsed = {"confirmed_items": [ext], "daily_updates": [], "skipped": []}
    assert _diff.run_diff(parsed, doc)[0] == 0


# ── Doc labels ───────────────────────────────────────────────────────────────

_NOT_A_MOC = f"(existing up:: [[X]] {ARROW_RELATED})"
_UNRESOLVED = f"(existing up:: [[X]] — note not found {ARROW_RELATED})"


@pytest.mark.parametrize(
    ("row", "label"),
    [
        ({"state": "valid", "target": "X"}, _NOT_A_MOC),
        ({"state": "absent", "target": None}, "(no up:: yet)"),
        ({"state": "broken", "target": "X", "reason": "not-a-moc"}, _NOT_A_MOC),
        ({"state": "broken", "target": "X", "reason": "unresolved"}, _UNRESOLVED),
        # A report from before T5.3d: no reason → the not-a-moc wording.
        ({"state": "broken", "target": "X"}, _NOT_A_MOC),
    ],
    ids=["valid", "absent", "not-a-moc", "unresolved", "no-reason"],
)
def test_topic_member_label(row, label):
    assert _reducer._child_annotation("c", [{"stem": "c", **row}]) == label


def test_unresolved_label_uses_the_exact_characters():
    label = _reducer._child_annotation(
        "c", [{"stem": "c", "state": "broken", "target": "X", "reason": "unresolved"}]
    )
    assert "—" in label and "→" in label and "`related::`" in label


def test_link_member_labels_carry_the_reason():
    members = [
        {**_link_member("Plain", ["Sleep Debt"], up_state="broken", up_target="Notey"),
         "up_broken_reason": "not-a-moc"},
        {**_link_member("Lost", ["Sleep Debt"], up_state="broken", up_target="Gone"),
         "up_broken_reason": "unresolved"},
    ]
    _, body = render_moc_proposal_doc(_link_report(members), _Cfg())
    assert (
        f"- [ ] [[Plain]] (existing up:: [[Notey]] {ARROW_RELATED}) — linked with [[Sleep Debt]]"
    ) in body
    assert (
        f"- [ ] [[Lost]] (existing up:: [[Gone]] — note not found {ARROW_RELATED})"
        " — linked with [[Sleep Debt]]"
    ) in body


def test_extension_member_label_carries_the_reason():
    report = _extension_report()
    report["extension"]["members"][0].update(
        up_state="broken", up_target="Gone", up_broken_reason="unresolved",
    )
    _, body = _extension_doc(report)
    assert (
        f"- [ ] [[argon]] (existing up:: [[Gone]] — note not found {ARROW_RELATED})"
    ) in body


def test_no_doc_says_broken_ignored():
    source = (SCRIPTS_DIR / "suggestions-reducer.py").read_text(encoding="utf-8")
    assert "broken — ignored" not in source


# ── Data: Phase 6.5 rows ─────────────────────────────────────────────────────


class _ReadOnlyKado:
    def __init__(self, notes):
        self._notes = notes

    def read_note(self, path):
        return {"content": self._notes[path]}


def test_phase65_broken_rows_carry_the_reason():
    """not-a-moc when the target is a cached non-MOC note, else unresolved."""
    notes = {
        "N/valid.md": "up:: [[Real MOC]]\n",
        "N/plain.md": "up:: [[Plain Note]]\n",
        "N/gone.md": "up:: [[Gone MOC]]\n",
        "N/none.md": "# no parent\n",
    }
    cache = {
        "map_notes": [{"path": "Maps/Real MOC.md", "title": "Real MOC"}],
        "entries": [
            {"path": "Maps/Real MOC.md", "kind": "moc", "stem": "Real MOC"},
            {"path": "Notes/Plain Note.md", "kind": "note", "stem": "Plain Note"},
        ],
    }
    stems = ["valid", "plain", "gone", "none"]
    candidates = [_disc.Candidate(stem=s, path=f"N/{s}.md") for s in stems]
    clusters = [{"items": stems}]
    rows = _disc.phase65_validate_existing_up(clusters, candidates, _ReadOnlyKado(notes), cache)
    assert rows[0]["existing_up"] == [
        {"stem": "valid", "state": "valid", "target": "Real MOC"},
        {"stem": "plain", "state": "broken", "target": "Plain Note", "reason": "not-a-moc"},
        {"stem": "gone", "state": "broken", "target": "Gone MOC", "reason": "unresolved"},
        {"stem": "none", "state": "absent", "target": None},
    ]


# ── Data: link members ───────────────────────────────────────────────────────


def test_link_member_carries_the_cached_broken_reason():
    entry = {"stem": "Lost", "up_state": "broken", "up_target": "Gone",
             "up_broken_reason": "unresolved"}
    member = lm._link_member("Atlas/Lost.md", ["a.md"], entry)
    assert member.up_broken_reason == "unresolved"


def test_link_member_from_an_old_cache_has_no_reason():
    entry = {"stem": "Lost", "up_state": "broken", "up_target": "Gone"}
    assert lm._link_member("Atlas/Lost.md", [], entry).up_broken_reason is None


def test_member_dict_copies_the_reason_only_when_broken():
    broken = lm.LinkMember("Lost", "Atlas/Lost.md", [], "broken", "Gone", "unresolved")
    valid = lm.LinkMember("Kept", "Atlas/Kept.md", [], "valid", "MOC", None)
    assert _disc._member_up_fields(broken) == {
        "up_state": "broken", "up_target": "Gone", "up_broken_reason": "unresolved",
    }
    assert _disc._member_up_fields(valid) == {"up_state": "valid", "up_target": "MOC"}
