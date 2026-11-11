#!/usr/bin/env python3
# version: 0.2.0
"""test_review_doc_parse.py — lib/review_doc_parse.py and review-doc.py parse / replace
(spec 045 T3.7, PRD F5-AC1, F5-AC6, F6-AC1, Business Rules 1-3 and 7, Edge Cases,
SDD ENTITY ApprovedReview / ReviewDeliveryMeta, item identity).

Documents are built with review_doc.render_document and then edited the way
a user would in Obsidian, so parse and write agree on the shape: only an
exact column-0 line is the Approved line, a group heading or an item start
(an indented `  - [ ] Approved` or `  ## Done` is item text); Approved
ticked, unticked or missing; kept / unticked / deleted Tomo items by id; a
Tomo item rewritten without its links stays Tomo's and edited; `edited` is
structural — the item's ordered, de-duplicated `[[stem]]` link stems differ
from Pass 1's `pass1_links` (a dropped link, a reorder, a link added to a
link-less habit), a retyped text keeping its links is not edited (the
accepted limit), an id absent from the map is never guessed; an id-less or
copied-id ticked line is a user item; text verbatim with continuation lines
and escapes; everything unticked → nothing to deliver; unknown / duplicate
headings and a broken frontmatter warn and keep the items; the "nothing
found" line is never an item; the ApprovedReview record is in-process only.
Script: parse reads through Kado, prints counts and ids only and writes no
file, not-found without document or meta.json, --doc-path overrides, Kado
failures stop, a digest-version meta.json (pass1_items) is ignored; replace
needs --confirm (no Kado call before), --confirm writes over Tomo's document
from the kept files, resets meta.json and clears the stage, a non-Tomo file
is still doc-name-taken, --abort deletes read.json and proposals.json only;
write records only link-stem lists per Tomo item in meta.json — nothing
text-derived, a low-entropy habit line is not recoverable from it. All
data is synthetic.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib.kado_client import KadoAuthError, KadoConnectionError  # noqa: E402
from test_review_doc import GOOD, INBOX, MARKER, SCRIPT_PATH, WEEKLY, _config, _doc_input, stage, week_read  # noqa: E402

STEM = "2026-W13_review"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_doc_script_t37", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    _config(tmp_path)
    return tmp_path
DOC_PATH = f"{INBOX}2026-W13 Review.md"
GROUPS = {
    "done": [{"text": "Woche aufgeräumt", "links": ["2026-03-24", "2026-03-26"]},
             {"text": "zwei Zeilen\nzweite Zeile", "links": ["2026-03-25"]}],
    "open": [{"text": "Steuer offen", "links": ["2026-03-27"]}],
    "themes": [],
    "growth": [{"text": "Neue Notiz", "links": ["2026-03-24"]}],
    "habits": [{"text": "Sport: 6 von 7 Tagen", "links": []}],
}


# ---------------------------------------------------------------- helpers

def document(groups=None, **overrides) -> str:
    text, _ = rd.render_document(_doc_input(groups=groups if groups is not None else GROUPS, **overrides))
    return text


def line_of(text: str, item_id: str) -> str:
    [line] = [ln for ln in text.splitlines() if ln.endswith(f"%%{item_id}%%")]
    return line


def replace_line(text: str, old: str, new: str | None) -> str:
    lines = text.splitlines()
    index = lines.index(old)
    lines[index:index + 1] = [] if new is None else [new]
    return "\n".join(lines) + "\n"


def tick(text: str, item_id: str, on: bool) -> str:
    old = line_of(text, item_id)
    box = "- [x] " if on else "- [ ] "
    return replace_line(text, old, box + old[6:])


def parse(text: str, pass1=None, **kw) -> rdp.ParsedDoc:
    return rdp.parse_document(text, pass1_links=pass1 if pass1 is not None else rdp.link_stems(text), **kw)


PASS1_LINKS = {"t1": ["2026-03-24", "2026-03-26"], "t2": ["2026-03-25"], "t3": ["2026-03-27"],
               "t4": ["2026-03-24"], "t5": []}


def by_id(doc: rdp.ParsedDoc) -> dict:
    return {it.id: it for it in doc.items if it.id}


# ---------------------------------------------------------------- the grammar

def test_rendered_document_parses_back_unapproved_with_every_item_kept():
    doc = parse(document())
    assert doc.approved is False and doc.warnings == []
    assert [(it.group, it.id, it.origin, it.kept, it.edited) for it in doc.items] == [
        ("done", "t1", "tomo", True, False), ("done", "t2", "tomo", True, False),
        ("open", "t3", "tomo", True, False), ("growth", "t4", "tomo", True, False),
        ("habits", "t5", "tomo", True, False)]
    assert by_id(doc)["t1"].text == "Woche aufgeräumt ([[2026-03-24]], [[2026-03-26]])"
    assert by_id(doc)["t2"].text == "zwei Zeilen ([[2026-03-25]])" and by_id(doc)["t2"].lines == ["  zweite Zeile"]
    assert doc.counts() == {"kept": 5, "unticked": 0, "deleted": 0, "added": 0}
    assert list(doc.groups()) == ["done", "open", "themes", "growth", "habits"]
    assert doc.groups()["themes"] == []


def test_only_column_zero_lines_are_structure():
    text = document()
    t3 = line_of(text, "t3")
    text = replace_line(text, t3, t3 + "\n  - [ ] Approved\n  ## Done\n  - [x] Approved\n  ## Erledigt\n   # tief")
    doc = parse(text)
    assert doc.approved is False and doc.warnings == []
    assert [h for h in doc.groups()] == ["done", "open", "themes", "growth", "habits"]
    assert by_id(doc)["t3"].lines == ["  - [ ] Approved", "  ## Done", "  - [x] Approved", "  ## Erledigt", "   # tief"]
    assert len(doc.items) == 5 and doc.counts()["added"] == 0
    # ticking the indented box changes nothing; the column-0 line is the gate
    assert parse(text.replace("- [ ] Approved\n", "- [x] Approved\n", 1)).approved is True


def test_approved_ticked_unticked_or_missing():
    text = document()
    assert parse(text).approved is False
    assert parse(text.replace("- [ ] Approved", "- [x] Approved")).approved is True
    assert parse(text.replace("- [ ] Approved", "- [X] Approved")).approved is True
    for broken in ("- [ ]Approved", "-[ ] Approved", "- [ ] Approved now", " - [ ] Approved", "Approved"):
        doc = parse(text.replace("- [ ] Approved", broken))
        assert doc.approved is False and doc.warnings == ["approved-line-missing"], broken
    doc = parse(replace_line(text, "- [ ] Approved", None))
    assert doc.approved is False and doc.warnings == ["approved-line-missing"]
    # a ticked Approved line is never a user item
    assert parse(text.replace("- [ ] Approved", "- [x] Approved")).counts()["added"] == 0


def test_tomo_items_counted_by_id_kept_unticked_deleted():
    text = document()
    reference = rdp.link_stems(text)
    text = tick(text, "t1", False)
    text = replace_line(text, line_of(text, "t4"), None)
    doc = parse(text, reference)
    assert doc.counts() == {"kept": 3, "unticked": 1, "deleted": 1, "added": 0}
    assert by_id(doc)["t1"].kept is False and "t4" not in by_id(doc)
    assert doc.groups()["growth"] == []
    # without the link map the Pass 1 total still gives the deleted count; without either, nothing is guessed
    assert rdp.parse_document(text, pass1_total=5).counts()["deleted"] == 1
    assert rdp.parse_document(text).counts()["deleted"] == 0


def test_a_tomo_item_rewritten_without_its_links_is_kept_and_edited():
    text = document()
    text = replace_line(text, line_of(text, "t1"), "- [x] Woche wirklich aufgeräumt %%t1%%")
    doc = parse(text, rdp.link_stems(document()))
    t1 = by_id(doc)["t1"]
    assert (t1.origin, t1.kept, t1.edited, t1.text) == ("tomo", True, True, "Woche wirklich aufgeräumt")
    assert doc.counts() == {"kept": 5, "unticked": 0, "deleted": 0, "added": 0}


def test_link_stems_are_the_rendered_source_links_per_tomo_id_in_order():
    text = document()
    reference = rdp.link_stems(text)
    assert reference == PASS1_LINKS
    assert not any(re.fullmatch(r"[0-9a-f]{16,}", str(v)) for v in reference.values())
    # an alias or a heading on a link does not change its stem; a repeated link is one stem; a user line has no entry
    t1 = line_of(text, "t1")
    decorated = replace_line(text, t1, "- [x] Woche aufgeräumt ([[2026-03-24|Di]], [[2026-03-26#Abend]], [[2026-03-24]]) %%t1%%")
    assert rdp.link_stems(decorated)["t1"] == ["2026-03-24", "2026-03-26"]
    assert "t9" not in rdp.link_stems(text + "- [x] Meins ([[2026-03-28]])\n")
    # a link on a continuation line counts too, after the first line's
    assert rdp.link_stems(text.replace("  zweite Zeile", "  zweite Zeile [[2026-03-22]]"))["t2"] == ["2026-03-25", "2026-03-22"]


def test_edited_is_a_changed_link_list_and_a_missing_id_never_guesses():
    text = document()
    reference = rdp.link_stems(text)
    assert not any(it.edited for it in parse(text, reference).items)
    # unticking is not editing
    assert by_id(parse(tick(text, "t2", False), reference))["t2"].edited is False
    # a dropped link is an edit
    t1 = line_of(text, "t1")
    dropped = replace_line(text, t1, "- [x] Woche aufgeräumt ([[2026-03-24]]) %%t1%%")
    assert by_id(parse(dropped, reference))["t1"].edited is True
    # a reordered link list is an edit: the list is ordered, not a set
    reordered = replace_line(text, t1, "- [x] Woche aufgeräumt ([[2026-03-26]], [[2026-03-24]]) %%t1%%")
    assert by_id(parse(reordered, reference))["t1"].edited is True
    # a link repeated is the same list: de-duplicated
    doubled = replace_line(text, t1, "- [x] Woche aufgeräumt ([[2026-03-24]], [[2026-03-26]], [[2026-03-24]]) %%t1%%")
    assert by_id(parse(doubled, reference))["t1"].edited is False
    # a link-less habit is present with []: a link added to it is an edit (presence is `in`, not truthiness)
    assert reference["t5"] == [] and by_id(parse(text, reference))["t5"].edited is False
    t5 = line_of(text, "t5")
    linked = replace_line(text, t5, "- [x] Sport: 6 von 7 Tagen ([[2026-03-24]]) %%t5%%")
    assert by_id(parse(linked, reference))["t5"].edited is True
    # no entry for the id: edited stays False, whatever the links
    assert by_id(parse(dropped, {}))["t1"].edited is False
    assert by_id(parse(dropped, {"t2": ["2026-03-25"]}))["t1"].edited is False


def test_a_retyped_text_keeping_its_links_reads_unedited_the_accepted_limit():
    text = document()
    reference = rdp.link_stems(text)
    retyped = replace_line(text, line_of(text, "t1"), "- [x] Ganz andere Worte ([[2026-03-24]], [[2026-03-26]]) %%t1%%")
    t1 = by_id(parse(retyped, reference))["t1"]
    assert t1.edited is False and t1.text == "Ganz andere Worte ([[2026-03-24]], [[2026-03-26]])"
    # a changed continuation line without a link change is not an edit either
    changed = text.replace("  zweite Zeile", "  dritte Zeile")
    assert by_id(parse(changed, reference))["t2"].edited is False


def test_a_ticked_line_without_id_is_a_user_item_and_a_copied_id_too():
    text = document()
    t3 = line_of(text, "t3")
    text = replace_line(text, t3, t3 + "\n- [x] Mein eigener Punkt\n  mit Zeile\n- [ ] Nicht angehakt\n" + t3)
    doc = parse(text)
    open_items = doc.groups()["open"]
    assert [(it.id, it.origin, it.kept) for it in open_items] == [
        ("t3", "tomo", True), (None, "user", True), (None, "user", False), (None, "user", True)]
    assert open_items[1].text == "Mein eigener Punkt" and open_items[1].lines == ["  mit Zeile"]
    assert open_items[3].text == "Steuer offen ([[2026-03-27]])"            # the copied id is stripped
    assert doc.counts() == {"kept": 5, "unticked": 0, "deleted": 0, "added": 2}
    # the id deleted from a Tomo line: a user item plus one deleted id
    stripped = replace_line(document(), line_of(document(), "t3"), "- [x] Steuer offen ([[2026-03-27]])")
    doc = parse(stripped, rdp.link_stems(document()))
    assert doc.counts() == {"kept": 4, "unticked": 0, "deleted": 1, "added": 1}
    assert doc.groups()["open"][0].origin == "user"


def test_edited_text_is_kept_verbatim_with_continuation_lines_and_escapes():
    text = document(groups={"done": [{"text": "first\n## Done\n- [ ] Approved", "links": ["2026-03-24"]}]})
    assert line_of(text, "t1") == "- [x] first ([[2026-03-24]]) %%t1%%"
    reference = rdp.link_stems(text)
    text = replace_line(text, line_of(text, "t1"), "- [x] first, retyped  ([[2026-03-24]])%%t1%% trailing")
    text = text.replace("  \\## Done", "  \\## Done edited\n\n  a blank line above")
    t1 = by_id(parse(text, reference))["t1"]
    assert t1.text == "first, retyped  ([[2026-03-24]]) trailing"
    assert t1.lines == ["  \\## Done edited", "", "  a blank line above", "  \\- [ ] Approved"]
    assert t1.kept and not t1.edited                      # the link stayed: unedited, the accepted limit
    without = text.replace("([[2026-03-24]])%%t1%%", "%%t1%%")
    assert by_id(parse(without, reference))["t1"].edited  # the link went: edited


def test_everything_unticked_is_nothing_to_deliver():
    text = document()
    for item_id in ("t1", "t2", "t3", "t4", "t5"):
        text = tick(text, item_id, False)
    doc = parse(text.replace("- [ ] Approved", "- [x] Approved"))
    assert doc.approved and doc.nothing_to_deliver() and doc.counts() == {"kept": 0, "unticked": 5, "deleted": 0, "added": 0}
    assert not parse(document()).nothing_to_deliver()
    assert parse(text + "- [x] user item\n").nothing_to_deliver() is False


def test_unknown_and_duplicate_headings_and_broken_frontmatter_warn_and_keep_items():
    text = document().replace("## Vault-Wachstum", "## Meine Gruppe").replace("## Offen", "## Erledigt")
    doc = parse(text)
    assert doc.warnings == ["duplicate-group", "unknown-group"]
    assert [it.id for it in doc.groups()["done"]] == ["t1", "t2", "t3"]
    assert [it.id for it in doc.groups()["unknown"]] == ["t4"] and "growth" not in doc.groups()
    assert list(doc.groups())[-1] == "unknown" and doc.counts()["kept"] == 5
    # English headings parse too, whatever the frontmatter says
    assert list(parse(document(language="en")).groups()) == ["done", "open", "themes", "growth", "habits"]
    broken = document().replace("review_kind: week", "review_kind: [week")
    doc = parse(broken)
    assert doc.warnings == ["frontmatter-broken"] and doc.frontmatter == {} and len(doc.items) == 5
    doc = parse(document().replace("doc_type: review", "doc_type: other"))
    assert doc.warnings == ["frontmatter-broken"] and doc.frontmatter.get("review_period") == "2026-W13"
    assert parse("# no frontmatter\n- [ ] Approved\n").warnings == ["frontmatter-broken"]
    assert parse(document()).frontmatter["review_stem"] == "2026-W13_review"


def test_the_nothing_found_line_is_never_an_item():
    text = document()
    assert "- nichts gefunden" in text
    doc = parse(text)
    assert doc.groups()["themes"] == [] and not any("nichts" in it.text for it in doc.items)
    doc = parse(text.replace("- nichts gefunden", "- [x] nichts gefunden"))
    assert [it.origin for it in doc.groups()["themes"]] == ["user"]


def test_approved_review_record_keeps_only_kept_items_in_rendering_order():
    text = tick(document(), "t1", False)
    text = replace_line(text, line_of(text, "t4"), "- [x] Ganz neu\n- [ ] nicht\n" + line_of(text, "t4"))
    doc = parse(text.replace("- [ ] Approved", "- [x] Approved"))
    record = doc.approved_review(stem=STEM, doc_path=DOC_PATH)
    assert record["stem"] == STEM and record["doc_path"] == DOC_PATH and record["approved"] is True
    assert record["period"] == "2026-W13" and record["kind"] == "week" and record["language"] == "de"
    assert list(record["groups"]) == ["done", "open", "themes", "growth", "habits"]
    assert record["groups"]["done"] == [{"id": "t2", "origin": "tomo", "edited": False,
                                         "text": "zwei Zeilen ([[2026-03-25]])", "lines": ["  zweite Zeile"]}]
    assert record["groups"]["growth"] == [
        {"id": None, "origin": "user", "edited": False, "text": "Ganz neu", "lines": []},
        {"id": "t4", "origin": "tomo", "edited": False, "text": "Neue Notiz ([[2026-03-24]])", "lines": []}]
    assert record["warnings"] == [] and record["counts"] == {"kept": 4, "unticked": 1, "deleted": 0, "added": 1}
    public = doc.public_items()
    assert public["growth"] == [{"origin": "user", "kept": True, "edited": False},
                                {"origin": "user", "kept": False, "edited": False},
                                {"id": "t4", "origin": "tomo", "kept": True, "edited": False}]
    assert public["done"][0] == {"id": "t1", "origin": "tomo", "kept": False, "edited": False}
    assert "text" not in json.dumps(public) and "Ganz neu" not in json.dumps(public)


# ---------------------------------------------------------------- the script

def _run(mod, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles"] + argv)
    out, err = capsys.readouterr()
    assert MARKER not in out and MARKER not in err, "document text leaked to stdout/stderr"
    return code, (json.loads(out) if out else None), err


def written(mod, monkeypatch, capsys, instance, fake=None):
    """A Pass 1 write of GOOD; returns (fake, document text, stage dir)."""
    stem, path = stage(instance, week_read(), GOOD)
    fake = fake or ReviewFakeVault({f"{WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"})
    code, out, _ = _run(mod, monkeypatch, capsys, ["write", "--stem", stem, "--proposals", str(path), "--run-id", "r1"], fake)
    assert code == 0 and out["status"] == "written"
    return fake, fake.text(DOC_PATH), instance / "tomo-tmp" / "review" / stem


def test_write_records_only_link_stem_lists_per_tomo_item(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    raw = (stage_dir / "meta.json").read_text(encoding="utf-8")
    meta = json.loads(raw)
    assert meta["pass1_links"] == rdp.link_stems(text) and set(meta["pass1_links"]) == {"t1", "t2", "t3", "t4", "t5"}
    assert meta["pass1_links"]["t5"] == []                                  # the habit: present, no links
    assert all(isinstance(v, list) and all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", s) for s in v)
               for v in meta["pass1_links"].values())
    assert sum(meta["pass1_counts"].values()) == len(meta["pass1_links"])
    assert "pass1_items" not in meta and not re.search(r"[0-9a-f]{16,}", raw)
    assert "Woche" not in raw and "Steuer" not in raw and MARKER not in raw


def test_a_low_entropy_habit_line_is_not_recoverable_from_meta(mod, instance, monkeypatch, capsys):
    """"Sport: 6 von 7 Tagen" has eight values; a digest of any form of it would give the count away by enumeration."""
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    raw = (stage_dir / "meta.json").read_text(encoding="utf-8")
    habit = [it for it in rdp.parse_document(text).items if it.group == "habits"]
    assert len(habit) == 1 and "von" in habit[0].text and habit[0].id == "t5"
    forms = {habit[0].text, line_of(text, "t5"), "\n".join([habit[0].text, *habit[0].lines])}
    for form in forms:
        for word in form.replace("%%t5%%", "").split():
            if len(word) > 1:
                assert word not in raw, word
        for algo in ("sha256", "sha1", "md5"):
            digest = hashlib.new(algo, form.encode("utf-8")).hexdigest()
            assert digest not in raw and digest[:16] not in raw and digest[:8] not in raw
    assert not re.search(r"[0-9a-f]{8,}", raw)


def test_parse_reads_the_document_prints_counts_only_and_writes_no_file(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    meta_before = (stage_dir / "meta.json").read_text(encoding="utf-8")
    edited = text.replace("- [ ] Approved", "- [x] Approved")
    edited = replace_line(edited, line_of(edited, "t1"), f"- [x] {MARKER} umgeschrieben %%t1%%\n  {MARKER} Zeile")
    edited = tick(edited, "t2", False)
    edited = replace_line(edited, line_of(edited, "t3"), f"- [x] {MARKER} neu")
    fake.files[DOC_PATH] = edited
    code, out, err = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert code == 0 and err == ""
    assert out["status"] == "ok" and out["stem"] == STEM and out["doc_path"] == DOC_PATH
    assert out["approved"] is True and out["nothing_to_deliver"] is False and out["warnings"] == []
    assert out["counts"] == {"kept": 3, "unticked": 1, "deleted": 1, "added": 1}      # t1, t4, t5 kept; t3's id gone
    assert out["items"]["done"] == [{"id": "t1", "origin": "tomo", "kept": True, "edited": True}]
    assert out["items"]["open"] == [{"id": "t2", "origin": "tomo", "kept": False, "edited": False}]
    assert out["items"]["themes"] == [{"origin": "user", "kept": True, "edited": False}]
    assert "approved_path" not in out and "approved.json" not in json.dumps(out)
    assert [m for m, _ in fake.events][-1] == "read_note" and fake.events[-1][1] == DOC_PATH
    # nothing written: the stage holds meta.json alone, unchanged; the record is the lib's in-process value
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json"]
    assert (stage_dir / "meta.json").read_text(encoding="utf-8") == meta_before
    assert not list(instance.rglob("approved.json"))
    # an unapproved document is parsed too
    fake.files[DOC_PATH] = text
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert out["approved"] is False and out["counts"]["kept"] == 5
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json"]


def test_parse_ignores_a_digest_version_meta_and_guesses_no_edit(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    meta = json.loads((stage_dir / "meta.json").read_text(encoding="utf-8"))
    del meta["pass1_links"]
    meta["pass1_items"] = {"t1": "0" * 16, "t2": "1" * 16, "t3": "2" * 16, "t4": "3" * 16, "t5": "4" * 16}
    (stage_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    edited = replace_line(text, line_of(text, "t1"), f"- [x] {MARKER} ohne Links %%t1%%")
    edited = replace_line(edited, line_of(edited, "t4"), None)
    fake.files[DOC_PATH] = edited
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert code == 0 and out["status"] == "ok"
    assert not any(it["edited"] for group in out["items"].values() for it in group)
    assert out["counts"] == {"kept": 4, "unticked": 0, "deleted": 1, "added": 0}    # deleted from the counts sum


def test_parse_missing_document_or_meta_is_not_found_and_doc_path_overrides(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    del fake.files[DOC_PATH]
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert code == 0 and out == {"status": "not-found", "stem": STEM, "doc_path": DOC_PATH}
    moved = f"{INBOX}Renamed Review.md"
    fake.files[moved] = text
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM, "--doc-path", moved], fake)
    assert out["status"] == "ok" and out["doc_path"] == moved and out["counts"]["kept"] == 5
    (stage_dir / "meta.json").unlink()
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert code == 0 and out == {"status": "not-found", "stem": STEM}
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM, "--doc-path", moved], fake)
    assert out["status"] == "ok" and out["counts"]["deleted"] == 0 and not any(
        it.get("edited") for it in out["items"]["done"])
    # a non-review document at the path parses with a warning
    fake.files[DOC_PATH] = "---\ntitle: mine\n---\n# My own review\n- [x] Approved\n"
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM, "--doc-path", DOC_PATH], fake)
    assert out["status"] == "ok" and out["warnings"] == ["frontmatter-broken"] and out["approved"] is True
    assert sorted(p.name for p in stage_dir.iterdir()) == []


def test_parse_kado_failure_is_stopped_and_writes_nothing(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    fake.auth_error = KadoAuthError("401")
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert code == 0 and out["status"] == "stopped" and out["error"]["kind"] == "kado-auth"
    fake.auth_error = None
    fake.connection_error = KadoConnectionError("down")
    code, out, _ = _run(mod, monkeypatch, capsys, ["parse", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json"]


def _review_exists(mod, monkeypatch, capsys, instance):
    """Pass 1 written, then a second write refused with review-exists: the stage keeps read.json and proposals.json."""
    fake, text, stage_dir = written(mod, monkeypatch, capsys, instance)
    meta_before = (stage_dir / "meta.json").read_text(encoding="utf-8")
    stem, path = stage(instance, week_read(), GOOD)
    code, out, _ = _run(mod, monkeypatch, capsys, ["write", "--stem", stem, "--proposals", str(path), "--run-id", "r2"], fake)
    assert out["status"] == "refused" and out["problems"] == ["review-exists"]
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json", "proposals.json", "read.json"]
    return fake, text, stage_dir, meta_before


def test_replace_without_confirm_needs_confirm_and_names_the_document(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir, meta_before = _review_exists(mod, monkeypatch, capsys, instance)
    calls = fake.call_count
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", STEM], fake)
    assert code == 0 and out == {"status": "needs-confirm", "stem": STEM, "doc_path": DOC_PATH}
    assert fake.call_count == calls and fake.text(DOC_PATH) == text
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json", "proposals.json", "read.json"]
    assert (stage_dir / "meta.json").read_text(encoding="utf-8") == meta_before


def test_replace_confirm_writes_over_tomos_document_resets_meta_and_deletes_stage_files(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir, meta_before = _review_exists(mod, monkeypatch, capsys, instance)
    fake.files[DOC_PATH] = text.replace("- [ ] Approved", "- [x] Approved")       # the user's edits go
    (stage_dir / "meta.json").write_text(json.dumps({"stem": STEM, "steps_done": ["note"], "failed_step": "set_json",
                                                     "pass1_links": {"t9": ["x"]}}), encoding="utf-8")
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", STEM, "--confirm", "--run-id", "r3"], fake)
    assert code == 0 and out["status"] == "replaced" and out["doc_path"] == DOC_PATH
    assert out["counts"] == {"done": 1, "open": 1, "themes": 1, "growth": 1, "habits": 1}
    assert fake.writes[-1] == DOC_PATH and "- [ ] Approved" in fake.text(DOC_PATH) and "run_id: r3" in fake.text(DOC_PATH)
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json"]
    meta = json.loads((stage_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["steps_done"] == [] and meta["failed_step"] == "" and meta["run_id"] == "r3"
    assert meta["pass1_links"] == rdp.link_stems(fake.text(DOC_PATH)) and "t9" not in meta["pass1_links"]


def test_replace_confirm_on_a_non_tomo_document_is_still_doc_name_taken(mod, instance, monkeypatch, capsys):
    stem, path = stage(instance, week_read(), GOOD)
    mine = "---\ntitle: mine\n---\n# My own review\n"
    fake = ReviewFakeVault({DOC_PATH: mine, f"{WEEKLY}2026-W13.md": "# W13\n"})
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", stem, "--confirm"], fake)
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["doc-name-taken"]
    assert fake.writes == [] and fake.text(DOC_PATH) == mine
    assert (instance / "tomo-tmp" / "review" / stem / "read.json").exists() and path.exists()


def test_replace_abort_deletes_the_content_files_and_leaves_document_and_meta(mod, instance, monkeypatch, capsys):
    fake, text, stage_dir, meta_before = _review_exists(mod, monkeypatch, capsys, instance)
    calls = fake.call_count
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", STEM, "--abort"], fake)
    assert code == 0 and out == {"status": "aborted", "stem": STEM}
    assert fake.call_count == calls and fake.text(DOC_PATH) == text and DOC_PATH in fake.files
    assert sorted(p.name for p in stage_dir.iterdir()) == ["meta.json"]
    assert (stage_dir / "meta.json").read_text(encoding="utf-8") == meta_before
    # a second abort on an empty stage is fine
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", STEM, "--abort"], fake)
    assert code == 0 and out["status"] == "aborted"


def test_replace_confirm_and_abort_are_exclusive_and_replace_needs_a_stage(mod, instance, monkeypatch, capsys):
    with pytest.raises(SystemExit) as stop:
        mod.main(["replace", "--stem", STEM, "--confirm", "--abort"])
    assert stop.value.code == 2
    capsys.readouterr()
    code, out, _ = _run(mod, monkeypatch, capsys, ["replace", "--stem", STEM], ReviewFakeVault({}))
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["read-missing"]
