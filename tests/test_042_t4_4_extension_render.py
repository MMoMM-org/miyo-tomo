#!/usr/bin/env python3
# version: 0.1.0
"""Spec 042 T4.4 — an accepted around:<MOC> extension, from confirmed item to wire.

Covers PRD F1-AC5, F3-AC3, F3-AC4 and the extension edge cases:
  - filter_missing_extension_targets withholds an extension whose MOC is gone;
  - _build_moc_extension_actions gives each ticked member the Rule 4.x outcome
    emit_up_preservation_actions gives a new MOC's child, and a link_to_moc
    only when outgoing(moc) does not already list it;
  - a failed outgoing call emits every line and is reported;
  - a MOC without an anchor still gets its link_to_moc (unresolved notice);
  - extend_moc never reaches instructions.json, which validates unchanged;
  - instructions-diff checks one add_relationship set and the link count per member.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import validate

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import KadoError  # noqa: E402
from test_instruction_render_up_preservation import _FakeKadoClient  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "instruction_render_t44", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ir)

_dspec = importlib.util.spec_from_file_location(
    "instructions_diff_t44", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_dspec)
assert _dspec.loader is not None
_dspec.loader.exec_module(diff)

MOC = "Health MOC"
MOC_PATH = "Atlas/200 Maps/Health MOC.md"
CFG = {
    "concepts.inbox": "100 Inbox",
    "concepts.calendar.granularities.daily.path": "Calendar/Daily",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["blocks"],
}


class _ExtensionKado(_FakeKadoClient):
    """The Rule 4.x fake plus the byName search the extension's MOC lookup uses.

    ``duplicates`` adds further paths with a registered stem; ``fail_search`` /
    ``fail_outgoing_for`` make the matching call raise like a Kado error.
    """

    def __init__(self, *a, duplicates=None, fail_search=False,
                 fail_outgoing_for=None, **kw):
        super().__init__(*a, **kw)
        self._duplicates = dict(duplicates or {})
        self._fail_search = fail_search
        self._fail_outgoing_for = fail_outgoing_for
        self.search_calls: list[str] = []
        self.graph_limits: list[int | None] = []

    def search_by_name(self, query: str, limit: int = 500) -> list[dict]:
        self.search_calls.append(query)
        if self._fail_search:
            raise KadoError("transport down")
        hits = [{"path": p} for stem, (p, _b) in self._notes.items() if query in stem]
        hits += [{"path": p} for p in self._duplicates.get(query, [])]
        return hits

    def graph(self, operation: str, path: str, limit: int | None = None) -> list[dict]:
        self.graph_limits.append(limit)
        if operation == "outgoing" and path == self._fail_outgoing_for:
            self.graph_calls.append((operation, path))
            raise KadoError("graph unavailable")
        return super().graph(operation, path, limit)

    def note_exists(self, path: str) -> bool:
        return any(p == path for p, _b in self._notes.values())


def _vault(moc_body: str = "> [!blocks] Members\n> - [[Sleep Debt]]\n", **kw) -> _ExtensionKado:
    """MOC linking Sleep Debt; Fresh Note has no up::, Other Up points elsewhere."""
    notes = {
        MOC: (MOC_PATH, moc_body),
        "Fresh Note": ("Atlas/202 Notes/Fresh Note.md", "# Fresh\n\nProse.\n"),
        "Other Up": ("Atlas/202 Notes/Other Up.md", "# Other\n\nup:: [[Fitness MOC]]\n"),
        "Sleep Debt": ("Atlas/202 Notes/Sleep Debt.md", "# Sleep\n\nProse.\n"),
        "Fitness MOC": ("Atlas/200 Maps/Fitness MOC.md", "# Fitness\n"),
    }
    existing = {"Sleep Debt", "Fresh Note", "Other Up", "Fitness MOC", MOC}
    return _ExtensionKado(notes=notes, existing_paths=existing, **kw)


def _extension(members=("Fresh Note", "Other Up", "Sleep Debt"), override=False,
               item_id="MOC01") -> dict:
    """The shape moc-proposal-parser 0.3.0 writes for an accepted extension."""
    return {
        "id": item_id,
        "action": "extend_moc",
        "target_moc": MOC,
        "supporting_items": list(members),
        "override_preserve_existing_up": override,
        "source_path": None,
    }


def _build(kado, confirmed, reports=None):
    actions, _assets = ir.build_actions(
        [], confirmed, [], [], CFG, kado_client=kado, extension_reports=reports,
    )
    return actions


def _of(actions, kind):
    return [a for a in actions if a["action"] == kind]


# ── filter_missing_extension_targets ─────────────────────────────────────────


def test_extension_whose_moc_is_gone_is_withheld_with_a_cause():
    kado = _vault()
    del kado._notes[MOC]
    kept, withheld = ir.filter_missing_extension_targets([_extension()], kado)
    assert kept == []
    assert withheld == [{
        "id": "MOC01", "target_moc": MOC, "kind": "absent",
        "reason": "no note by this name", "paths": [], "member_count": 3,
    }]


def test_withheld_extension_emits_nothing_for_its_members():
    kado = _vault()
    del kado._notes[MOC]
    kept, _withheld = ir.filter_missing_extension_targets([_extension()], kado)
    actions = _build(kado, kept)
    assert _of(actions, "add_relationship") == []
    assert _of(actions, "link_to_moc") == []


def test_present_moc_is_kept_with_its_path_stamped():
    kept, withheld = ir.filter_missing_extension_targets([_extension()], _vault())
    assert withheld == []
    assert kept[0]["target_moc_path"] == MOC_PATH


def test_substring_hit_is_not_the_moc():
    kado = _vault()
    kado._notes = {k: v for k, v in kado._notes.items() if k != MOC}
    kado._notes["Health MOC Archive"] = ("Atlas/Health MOC Archive.md", "")
    _kept, withheld = ir.filter_missing_extension_targets([_extension()], kado)
    assert withheld[0]["kind"] == "absent"


def test_failed_lookup_withholds_as_unverifiable():
    _kept, withheld = ir.filter_missing_extension_targets(
        [_extension()], _vault(fail_search=True)
    )
    assert withheld[0]["kind"] == "unverifiable"


def test_two_notes_with_the_moc_stem_withhold_as_ambiguous():
    kado = _vault(duplicates={MOC: ["Archive/Health MOC.md"]})
    kept, withheld = ir.filter_missing_extension_targets([_extension()], kado)
    assert kept == []
    assert withheld[0]["kind"] == "ambiguous"
    assert withheld[0]["paths"] == [MOC_PATH, "Archive/Health MOC.md"]


def test_filter_leaves_other_items_alone_and_asks_nothing_for_them():
    kado = _vault()
    other = {"id": "S01", "action": "create_note", "template": "t.md", "source_path": "x"}
    kept, withheld = ir.filter_missing_extension_targets([other], kado)
    assert kept == [other] and withheld == []
    assert kado.search_calls == []


def test_no_client_keeps_the_extension():
    kept, withheld = ir.filter_missing_extension_targets([_extension()], None)
    assert len(kept) == 1 and withheld == []


# ── _build_moc_extension_actions ─────────────────────────────────────────────


RULE_CASES = {
    "4.1 no up, default": ("# c\n", False),
    "4.2 valid up, default": ("up:: [[Fitness MOC]]\n", False),
    "4.3 broken up, default": ("up:: [[Gone MOC]]\n", False),
    "4.4 no up, override": ("# c\n", True),
    "4.5 valid up, override": ("up:: [[Fitness MOC]]\n", True),
    "self-link": (f"up:: [[{MOC}]]\n", False),
}


@pytest.mark.parametrize("case", sorted(RULE_CASES))
def test_member_gets_the_same_rule_4x_outcome_as_a_new_mocs_child(case):
    """F1-AC5 / F3-AC3: extension members reuse emit_up_preservation_actions."""
    body, override = RULE_CASES[case]

    def kado():
        k = _vault()
        k._notes["child"] = ("Atlas/202 Notes/child.md", body)
        k._existing.add("child")
        return k

    direct = ir.emit_up_preservation_actions(child_stem="child", new_moc_stem=MOC,
                                             override_flag=override,
                                             kado_client=kado(), counter=[0])
    built = _of(_build(kado(), [_extension(["child"], override)]), "add_relationship")

    def shape(acts):
        return [(a["target_moc_path"], a["marker"], a["line"]) for a in acts]

    assert shape(built) == shape(direct)


def test_three_member_extension_emits_up_for_all_and_lines_for_unlinked():
    """F3-AC3 + F3-AC4 on one extension: one no-up, one other-up, one already linked."""
    reports: list[dict] = []
    actions = _build(_vault(), [_extension()], reports)
    rels = [(a["target_moc_path"], a["line"]) for a in _of(actions, "add_relationship")]
    assert rels == [
        ("Atlas/202 Notes/Fresh Note.md", "up:: [[Health MOC]]"),
        ("Atlas/202 Notes/Other Up.md", "up:: [[Health MOC]]"),
        ("Atlas/202 Notes/Other Up.md", "related:: [[Fitness MOC]]"),
        ("Atlas/202 Notes/Sleep Debt.md", "up:: [[Health MOC]]"),
    ]
    links = _of(actions, "link_to_moc")
    assert [(a["target_moc"], a["line_to_add"]) for a in links] == [
        (MOC, "- [[Fresh Note]]"),
        (MOC, "- [[Other Up]]"),
    ]
    assert reports == [{
        "id": "MOC01", "target_moc": MOC, "target_moc_path": MOC_PATH,
        "members": ["Fresh Note", "Other Up", "Sleep Debt"],
        "already_linked": ["Sleep Debt"], "outgoing_checked": True,
        "no_relationship": [],
    }]


def test_member_already_linked_by_the_moc_gets_up_but_no_line():
    """F3-AC4: the MOC lists Sleep Debt in its body, so no duplicate bullet."""
    actions = _build(_vault(), [_extension(["Sleep Debt"])])
    assert [a["line"] for a in _of(actions, "add_relationship")] == ["up:: [[Health MOC]]"]
    assert _of(actions, "link_to_moc") == []


def test_already_linked_is_asked_once_with_outgoing_and_no_limit():
    kado = _vault()
    _build(kado, [_extension()])
    moc_calls = [c for c in kado.graph_calls if c[1] == MOC_PATH]
    assert moc_calls == [("outgoing", MOC_PATH)]
    assert all(op != "neighbors" for op, _p in kado.graph_calls)
    assert set(kado.graph_limits) == {None}


def test_a_backlink_alone_does_not_count_as_linked():
    """A member linking TO the MOC is not listed BY it — it still gets its line."""
    kado = _vault(moc_body="> [!blocks] Members\n")
    kado._notes["Fresh Note"] = ("Atlas/202 Notes/Fresh Note.md", f"see [[{MOC}]]\n")
    actions = _build(kado, [_extension(["Fresh Note"])])
    assert [a["line_to_add"] for a in _of(actions, "link_to_moc")] == ["- [[Fresh Note]]"]


def test_outgoing_failure_emits_every_line_and_reports_it():
    reports: list[dict] = []
    actions = _build(_vault(fail_outgoing_for=MOC_PATH), [_extension()], reports)
    assert [a["line_to_add"] for a in _of(actions, "link_to_moc")] == [
        "- [[Fresh Note]]", "- [[Other Up]]", "- [[Sleep Debt]]",
    ]
    assert reports[0]["outgoing_checked"] is False
    assert reports[0]["already_linked"] == []


def test_missing_and_self_linked_members_are_reported_without_a_relationship():
    kado = _vault()
    kado._notes["Done"] = ("Atlas/202 Notes/Done.md", f"up:: [[{MOC}]]\n")
    reports: list[dict] = []
    _build(kado, [_extension(["Ghost", "Done"])], reports)
    assert reports[0]["no_relationship"] == [
        {"member": "Ghost", "cause": "child-missing"},
        {"member": "Done", "cause": "up-already-points-to-moc"},
    ]


def test_no_client_builds_nothing_for_an_extension():
    actions, _ = ir.build_actions([], [_extension()], [], [], CFG, kado_client=None)
    assert actions == []


# ── instruction-render main(): wire, notices, withholding ────────────────────


def _run_main(monkeypatch, tmp_path, kado, confirmed):
    sug = tmp_path / "parsed.json"
    sug.write_text(json.dumps({"confirmed_items": confirmed, "daily_updates": [],
                               "skipped": []}), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(ir, "load_config", lambda _p: dict(CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: kado)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(sug), "--output-dir", str(out),
        "--config", str(cfg_file), "--tag-handler-groups-dir", str(tmp_path / "none"),
    ])
    rc = ir.main()
    doc = json.loads((out / "instructions.json").read_text(encoding="utf-8"))
    md = (out / "instructions.md").read_text(encoding="utf-8")
    return rc, doc, md


def test_main_renders_the_extension_onto_the_unchanged_wire(monkeypatch, tmp_path, capsys):
    rc, doc, md = _run_main(monkeypatch, tmp_path, _vault(), [_extension()])
    assert rc == 0  # the drop_sources == WITHDRAWAL_GUARDS assert held
    kinds = [a["action"] for a in doc["actions"]]
    assert "extend_moc" not in kinds and "create_moc" not in kinds
    assert kinds.count("add_relationship") == 4 and kinds.count("link_to_moc") == 2
    validate(doc, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    assert doc["tomo"]["extensions"][0]["already_linked"] == ["Sleep Debt"]
    assert "SKIP: no template" not in capsys.readouterr().err
    assert not (tmp_path / "out" / "manifest.json").read_text().strip("[] \n")


def test_main_moc_without_anchor_still_emits_the_line(monkeypatch, tmp_path):
    kado = _vault(moc_body="")
    rc, doc, md = _run_main(monkeypatch, tmp_path, kado, [_extension(["Fresh Note"])])
    assert rc == 0
    links = [a for a in doc["actions"] if a["action"] == "link_to_moc"]
    assert len(links) == 1 and links[0]["anchor"]["value"] is None
    assert "- **Anchor:** (unresolved callout, placement: after)" in md
    assert [a["action"] for a in doc["actions"]].count("add_relationship") == 1


def test_main_reports_a_failed_already_linked_check(monkeypatch, tmp_path):
    kado = _vault(fail_outgoing_for=MOC_PATH)
    rc, doc, md = _run_main(monkeypatch, tmp_path, kado, [_extension()])
    assert rc == 0
    assert (
        "**Already-linked check unavailable** — [[Health MOC]]: Kado could not "
        "list the MOC's links, so a line was added for every ticked member. "
        "Remove any duplicate line from the MOC after applying."
    ) in md


def test_main_withholds_an_extension_whose_moc_is_gone(monkeypatch, tmp_path):
    kado = _vault()
    del kado._notes[MOC]
    rc, doc, md = _run_main(monkeypatch, tmp_path, kado, [_extension()])
    assert rc == 0
    assert doc["actions"] == []
    assert doc["tomo"]["withheld_extensions"][0]["kind"] == "absent"
    assert (
        "- [[Health MOC]] — no note by this name; nothing was written for its "
        "3 member(s). Check whether the MOC was renamed or deleted; to extend "
        "it, run `/moc-propose around:` with its current name."
    ) in md


def test_a_member_listed_twice_is_expanded_once(monkeypatch, tmp_path):
    """supporting_items may repeat a member, in any case; each gets one set of actions."""
    members = ("Fresh Note", "fresh note", "Other Up", "Fresh Note")
    rc, doc, _md = _run_main(monkeypatch, tmp_path, _vault(), [_extension(members)])
    assert rc == 0
    rels = [a for a in doc["actions"] if a["action"] == "add_relationship"]
    links = [a for a in doc["actions"] if a["action"] == "link_to_moc"]
    keys = [(a["target_moc_path"], a["line"]) for a in rels]
    assert len(keys) == len(set(keys))
    assert not any("fresh note" in k[0] for k in keys)
    assert len(links) == 2
    assert doc["tomo"]["extensions"][0]["members"] == ["Fresh Note", "Other Up"]


# ── instructions-diff ───────────────────────────────────────────────────────


@pytest.fixture
def rendered(monkeypatch, tmp_path):
    _rc, doc, _md = _run_main(monkeypatch, tmp_path, _vault(), [_extension()])
    parsed = {"confirmed_items": [_extension()], "daily_updates": [], "skipped": []}
    return parsed, doc


def test_diff_accepts_three_ticked_with_one_already_linked(rendered):
    parsed, doc = rendered
    rc, _obs = diff.run_diff(parsed, doc)
    assert rc == 0


def test_diff_fails_on_a_missing_add_relationship(rendered):
    parsed, doc = rendered
    bad = copy.deepcopy(doc)
    bad["actions"] = [a for a in bad["actions"]
                      if not (a["action"] == "add_relationship"
                              and a["target_moc_path"].endswith("Fresh Note.md"))]
    assert diff.run_diff(parsed, bad)[0] == 1


def test_diff_fails_on_an_extra_link_to_moc(rendered):
    parsed, doc = rendered
    bad = copy.deepcopy(doc)
    extra = copy.deepcopy(next(a for a in bad["actions"] if a["action"] == "link_to_moc"))
    extra.update(id="X99", line_to_add="- [[Sleep Debt]]", source_note_title="Sleep Debt")
    bad["actions"].append(extra)
    assert diff.run_diff(parsed, bad)[0] == 1


def test_diff_fails_on_a_link_sitting_on_the_wrong_member(rendered, capsys):
    """Total link_to_moc count is right, but Sleep Debt (already linked) got
    the line Other Up was owed."""
    parsed, doc = rendered
    bad = copy.deepcopy(doc)
    links = [a for a in bad["actions"] if a["action"] == "link_to_moc"]
    moved = next(a for a in links if a["source_note_title"] == "Other Up")
    moved.update(source_note_title="Sleep Debt", line_to_add="- [[Sleep Debt]]")
    assert len(links) == 2
    rc, _obs = diff.run_diff(parsed, bad)
    assert rc == 1
    assert "[DIFF want=" in capsys.readouterr().out


def test_diff_fails_when_the_extension_was_never_rendered(rendered):
    parsed, doc = rendered
    bad = copy.deepcopy(doc)
    del bad["tomo"]["extensions"]
    assert diff.run_diff(parsed, bad)[0] == 1


def test_diff_accepts_a_withheld_extension(monkeypatch, tmp_path):
    kado = _vault()
    del kado._notes[MOC]
    _rc, doc, _md = _run_main(monkeypatch, tmp_path, kado, [_extension()])
    parsed = {"confirmed_items": [_extension()], "daily_updates": [], "skipped": []}
    rc, obs = diff.run_diff(parsed, doc)
    assert rc == 0
    assert any("withheld" in o and MOC in o for o in obs)


def test_diff_does_not_expect_a_move_for_an_extension():
    expected = diff.derive_expected(
        {"confirmed_items": [_extension()], "daily_updates": [], "skipped": []}
    )
    assert expected["counts"]["move_note"] == 0
    assert expected["counts"]["delete_source"] == 0
    assert "MOC01" not in expected["by_item"]


def test_diff_accepts_a_member_listed_twice(monkeypatch, tmp_path):
    """The renderer expands a repeated member once; the diff must expect the same."""
    members = ("Fresh Note", "fresh note", "Other Up")
    ext = _extension(members)
    _rc, doc, _md = _run_main(monkeypatch, tmp_path, _vault(), [ext])
    parsed = {"confirmed_items": [ext], "daily_updates": [], "skipped": []}
    rc, _obs = diff.run_diff(parsed, doc)
    assert rc == 0


def test_diff_matches_already_linked_case_insensitively(rendered):
    """A record spelling the already-linked member in another case still names it (H2)."""
    parsed, doc = rendered
    assert diff.run_diff(parsed, doc)[0] == 0
    respelled = copy.deepcopy(doc)
    record = respelled["tomo"]["extensions"][0]
    assert record["already_linked"] == ["Sleep Debt"]
    record["already_linked"] = ["sleep debt"]
    assert diff.run_diff(parsed, respelled)[0] == 0


def test_diff_matches_no_relationship_case_insensitively(monkeypatch, tmp_path):
    """A no_relationship member spelled in another case still exempts it (H2)."""
    ext = _extension(["Ghost", "Fresh Note"])
    _rc, doc, _md = _run_main(monkeypatch, tmp_path, _vault(), [ext])
    parsed = {"confirmed_items": [ext], "daily_updates": [], "skipped": []}
    assert diff.run_diff(parsed, doc)[0] == 0
    record = doc["tomo"]["extensions"][0]
    assert [n["member"] for n in record["no_relationship"]] == ["Ghost"]
    record["no_relationship"][0]["member"] = "ghost"
    assert diff.run_diff(parsed, doc)[0] == 0
