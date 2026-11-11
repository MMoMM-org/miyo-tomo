#!/usr/bin/env python3
# version: 0.1.0
"""test_review_instructions.py — lib/review_actions.py (spec 045 T4.1; PRD F4-AC7, F5-AC3 to F5-AC7,
F6-AC3, Edge Cases; SDD "the review section and the heading-level rule", ADR-3, ADR-8, ADR-13).

The approved review is built the way production builds it: review_doc.render_document → the user
ticks Approved (and edits) → review_doc_parse.parse_document → ParsedDoc.approved_review(). The
target note's text is handed in; nothing here calls Kado. What is pinned, as `test_actions_*`:
an existing target without the marker gets one insert_under_marker with `before` or `inside`
(never `after`) at the level review_config.place_level gives; the marker of the same period
turns it into one replace_section on the heading above the marker, also when that heading was
renamed (`heading-renamed`), with a body Hashi's identical-block check reads as already landed;
the same heading without the marker — or the marker under an own section, or under a heading an
earlier user heading shadows — is `user-heading-collision` with no action; a note found by name
elsewhere is the target (`target_moved`); the flat folder wins over the year subfolder and the
duplicate is named; a review heading above level 5 is `place-too-deep`, an absent anchor
`place-missing`, both with the note's headings; an absent target yields a new note (variant,
raw Templater template with `templater_hint`, vanished variant with `variant_missing`, plain)
stamped rendered-note/pending-move plus one move_note; every item line is escaped once and
counted, a line review_doc already escaped lands with exactly one backslash; ids are stripped;
the content ends with one blank line and is byte-identical across builds; only kept items land
and empty groups leave no heading; an unapproved, gate-less or empty review emits nothing; every
set validates against the producer schema, Tomo's Hashi copy and Hashi's vendored copy.
T4.2 adds the review-instructions.py tests to this file. All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
sys.path.insert(0, str(REPO / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_actions as ra  # noqa: E402
from lib import review_config as rc  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib.period import ISO, Period  # noqa: E402
from test_review_doc import INBOX, WEEKLY, _doc_input  # noqa: E402
from test_review_doc_parse import GROUPS, tick  # noqa: E402

SCHEMAS = [REPO / "tomo" / "schemas" / "instructions.schema.json",
           REPO / "tomo" / "schemas" / "hashi-instructions.schema.json"]
HASHI_VENDORED = Path("/Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json")

PERIOD = "2026-W13"
MARKER = f"%% tomo-review {PERIOD} %%"
TARGET = f"{WEEKLY}{PERIOD}.md"
OWN = "In my own words"
HEADING = "Tomo Review"
GENERATED = "2026-04-06T09:00:00Z"
NOTE = f"# {PERIOD}\n\n## Woche\ntext der Woche\n\n## {OWN}\nmeine Worte\n"
FIRST_ITEM = "- Woche aufgeräumt ([[2026-03-24]], [[2026-03-26]])"


# ---------------------------------------------------------------- helpers

def setup(**overrides) -> rc.ReviewSetup:
    fields = dict(kind="week", folder=WEEKLY, format="gggg-[W]ww", rule=ISO, heading=HEADING, anchor=OWN,
                  placement="before", inbox=INBOX, language="de", own_sections=[OWN])
    fields.update(overrides)
    return rc.ReviewSetup(**fields)


def document(groups=None) -> str:
    text, _ = rd.render_document(_doc_input(groups=GROUPS if groups is None else groups))
    return text.replace("- [ ] Approved", "- [x] Approved", 1)


def approved(text: str | None = None, pass1_text: str | None = None) -> dict:
    """The ApprovedReview record of the edited ``text``; ``pass1_text`` is the document as Pass 1 wrote it."""
    text = document() if text is None else text
    return rdp.parse_document(text, pass1_links=rdp.link_stems(pass1_text or document())).approved_review()


def plan(review=None, target=None, target_text=NOTE, template=None, **kw) -> ra.ReviewPlan:
    return ra.build_review_plan(review or approved(), kw.pop("setup", None) or setup(),
                                target or ra.Target(TARGET, target_text), template,
                                run_id="r-test", generated=GENERATED, **kw)


def instruction_set(p: ra.ReviewPlan) -> dict:
    return ra.build_review_instruction_set(p, stem=f"{PERIOD}_review", generated=GENERATED, profile="miyo")


def hashi_insert_before(text: str, anchor: str, content: str) -> str:
    """Hashi's insert_under_marker, placement before: the block above the anchor's heading line."""
    lines = text[:-1].split("\n") if text.endswith("\n") else text.split("\n")
    index = next(i for i, ln in enumerate(lines) if ln.startswith("#") and ln.split(" ", 1)[1] == anchor)
    lines[index:index] = content.split("\n")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def hashi_section_body(text: str, heading: str) -> list[str]:
    """The lines Hashi's replace_section compares with the content: heading line + 1 to the next
    heading of the same or a higher level (inclusive of the blank before it), or EOF."""
    lines = text[:-1].split("\n") if text.endswith("\n") else text.split("\n")
    heads = [(i, len(ln.split(" ", 1)[0]), ln.split(" ", 1)[1]) for i, ln in enumerate(lines)
             if ln.startswith("#") and " " in ln]
    i, level, _ = next(h for h in heads if h[2] == heading)
    end = next((j for j, lvl, _ in heads if j > i and lvl <= level), len(lines))
    return lines[i + 1:end]


def schema_errors(doc: dict, path: Path) -> list[str]:
    validator = jsonschema.Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
    return [e.message for e in validator.iter_errors(doc)]


# ---------------------------------------------------------------- insert

def test_actions_insert_before_the_anchor_when_the_target_has_no_marker():
    p = plan()
    assert p.mode == "insert" and p.problems == []
    [action] = p.actions
    assert action == {"id": "I01", "action": "insert_under_marker", "target_path": TARGET,
                      "anchor": {"type": "heading", "value": OWN}, "placement": "before",
                      "content": p.section_md}
    assert p.section_md.split("\n")[:4] == [f"## {HEADING}", MARKER, "### Erledigt", FIRST_ITEM]
    assert p.place == {"anchor": OWN, "placement": "before", "level": 2}


def test_actions_insert_inside_lands_one_level_deeper_and_never_after():
    p = plan(setup=setup(anchor="Woche", placement="inside"))
    [action] = p.actions
    assert action["placement"] == "inside" and action["anchor"]["value"] == "Woche"
    assert p.section_md.split("\n")[:3] == [f"### {HEADING}", MARKER, "#### Erledigt"]
    for placement in ("before", "inside"):
        [action] = plan(setup=setup(anchor="Woche", placement=placement)).actions
        assert action["placement"] != "after"


def test_actions_heading_levels_come_from_review_config_place_level(monkeypatch):
    calls = []

    def spy(placement, level):
        calls.append((placement, level))
        return 4

    monkeypatch.setattr(ra.rc, "place_level", spy)
    p = plan()
    assert calls == [("before", 2)]
    assert p.section_md.startswith(f"#### {HEADING}\n{MARKER}\n##### Erledigt\n")


# ---------------------------------------------------------------- rerun: marker, rename, collision

def landed_note() -> str:
    return hashi_insert_before(NOTE, OWN, plan().section_md)


def test_actions_rerun_replaces_the_section_above_the_marker_and_hashi_sees_it_as_landed():
    p = plan(target_text=landed_note())
    assert p.mode == "replace" and p.problems == []
    [action] = p.actions
    assert action == {"id": "I01", "action": "replace_section", "target_path": TARGET,
                      "anchor": {"type": "heading", "value": HEADING}, "content": action["content"]}
    assert action["content"].startswith(f"{MARKER}\n### Erledigt\n") and not action["content"].startswith("#")
    assert p.section_md == f"## {HEADING}\n" + action["content"]
    # Hashi's identical-body check: the body of the landed section is line-for-line the content
    assert hashi_section_body(landed_note(), HEADING) == action["content"].split("\n")
    assert hashi_section_body(landed_note(), OWN) == ["meine Worte"]          # the own section is untouched


def test_actions_rerun_finds_the_marker_under_a_renamed_heading():
    renamed = landed_note().replace(f"## {HEADING}", "## Rückblick der Woche")
    p = plan(target_text=renamed)
    assert p.mode == "replace" and p.problems == ["heading-renamed"]
    [action] = p.actions
    assert action["action"] == "replace_section" and action["anchor"]["value"] == "Rückblick der Woche"
    assert p.section_md.startswith("## Rückblick der Woche\n" + MARKER)
    assert p.place["anchor"] == "Rückblick der Woche"


def test_actions_a_marker_of_another_period_does_not_count():
    other = landed_note().replace(MARKER, "%% tomo-review 2026-W12 %%")
    p = plan(target_text=other)
    assert p.mode == "insert" and p.problems == ["user-heading-collision"] and p.actions == []


def test_actions_a_marker_inside_a_code_fence_is_quoted_text():
    fenced = NOTE.replace("text der Woche", f"```\n{MARKER}\n```")
    p = plan(target_text=fenced)
    assert p.mode == "insert" and p.actions[0]["action"] == "insert_under_marker"


def test_actions_a_user_heading_named_like_the_review_is_never_replaced():
    user_section = NOTE.replace("## Woche\ntext der Woche", f"## {HEADING}\nmy own weekly thoughts")
    p = plan(target_text=user_section)
    assert p.problems == ["user-heading-collision"]
    assert p.actions == [] and p.mode == "insert"


def test_actions_a_marker_under_a_heading_an_earlier_user_heading_shadows_is_a_collision():
    # Hashi resolves a heading anchor to the FIRST heading with that text — the user's one here.
    shadowed = landed_note().replace("## Woche\ntext der Woche", f"## {HEADING}\nthe user's own section")
    p = plan(target_text=shadowed)
    assert p.problems == ["user-heading-collision"] and p.actions == []


def test_actions_own_sections_are_never_targeted():
    # the marker moved into the user's own section: never replaced
    moved = NOTE.replace("meine Worte", f"{MARKER}\n### Erledigt\n- alt")
    p = plan(target_text=moved)
    assert p.problems == ["user-heading-collision"] and p.actions == []
    # inside an own section: never inserted into
    p = plan(setup=setup(anchor=OWN, placement="inside"))
    assert p.problems == ["user-heading-collision"] and p.actions == []
    # before an own section is the SDD example and fine
    assert plan(setup=setup(anchor=OWN, placement="before")).problems == []


def test_actions_a_marker_with_no_heading_above_it_is_place_missing():
    p = plan(target_text=f"{MARKER}\n- old\n\n## Woche\n")
    assert p.problems == ["place-missing"] and p.headings == ["Woche"] and p.actions == []


# ---------------------------------------------------------------- target lookup

def test_actions_a_target_found_by_name_elsewhere_is_the_target():
    candidates = Period.week(2026, 13).note_paths(WEEKLY, "gggg-[W]ww")
    target = ra.locate_target(candidates, {"Archive/2026-W13.md": NOTE}, ["Archive/2026-W13.md"])
    assert target == ra.Target("Archive/2026-W13.md", NOTE, True, [])
    p = plan(target=target)
    assert p.target_moved is True and p.actions[0]["target_path"] == "Archive/2026-W13.md"
    assert p.preview()["target_moved"] is True


def test_actions_the_flat_folder_wins_over_the_year_subfolder_and_the_duplicate_is_named():
    candidates = Period.week(2026, 13).note_paths(WEEKLY, "gggg-[W]ww")
    assert candidates == [TARGET, f"{WEEKLY}2026/{PERIOD}.md"]
    texts = {candidates[0]: NOTE, candidates[1]: NOTE, "Archive/2026-W13.md": NOTE}
    target = ra.locate_target(candidates, texts, ["Archive/2026-W13.md"])
    assert target.path == TARGET and target.moved is False and target.duplicates == [candidates[1]]
    p = plan(target=target)
    assert p.preview()["duplicates"] == [candidates[1]] and p.actions[0]["target_path"] == TARGET
    # the year subfolder alone is the target, not a duplicate
    target = ra.locate_target(candidates, {candidates[1]: NOTE}, [])
    assert (target.path, target.moved, target.duplicates) == (candidates[1], False, [])


def test_actions_nothing_anywhere_means_a_new_note_at_the_first_candidate():
    candidates = Period.week(2026, 13).note_paths(WEEKLY, "gggg-[W]ww")
    assert ra.locate_target(candidates, {}, []) == ra.Target(TARGET, None, False, [])


# ---------------------------------------------------------------- the level rule and the place

def test_actions_a_review_heading_above_level_5_is_place_too_deep():
    deep = f"# T\n## a\n### b\n#### c\n##### e\n###### f\n## {OWN}\n"
    p = plan(target_text=deep, setup=setup(anchor="e", placement="inside"))
    assert p.problems == ["place-too-deep"] and p.actions == []
    assert p.headings == ["T", "a", "b", "c", "e", "f", OWN]
    # level 5 itself is allowed: before a level-5 anchor, inside a level-4 one
    assert plan(target_text=deep, setup=setup(anchor="e", placement="before")).place["level"] == 5
    assert plan(target_text=deep, setup=setup(anchor="c", placement="inside")).place["level"] == 5
    # a replaced section keeps its heading's level and is refused above 5 too
    marked = f"# T\n## a\n### b\n#### c\n##### e\n###### {HEADING}\n{MARKER}\n- x\n\n## {OWN}\n"
    p = plan(target_text=marked)
    assert p.mode == "replace" and p.problems == ["place-too-deep"] and p.actions == []


def test_actions_a_missing_place_names_the_notes_headings():
    p = plan(setup=setup(anchor="Nicht da"))
    assert p.problems == ["place-missing"] and p.actions == []
    assert p.headings == [PERIOD, "Woche", OWN]
    # the caller's anchor override takes precedence over the setup
    p = plan(setup=setup(anchor="Nicht da"), anchor="Woche")
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == "Woche"


# ---------------------------------------------------------------- new note

RAW_TEMPLATE = "---\ntags: weekly\n---\n# <% tp.file.title %>\n\n## Woche\n\n## In my own words\n\n"
VARIANT = f"---\ntags: weekly\n---\n# {PERIOD}\n\n## Woche\n\n## In my own words\n\n"


def frontmatter_of(text: str) -> dict:
    return yaml.safe_load(text.split("---\n")[1])


def test_actions_new_note_from_the_template_variant():
    p = plan(target_text=None, setup=setup(template="t_week.md", template_variant="t_week_tomo.md"),
             template=ra.Template(raw=RAW_TEMPLATE, variant=VARIANT))
    assert p.mode == "new-note" and p.problems == []
    assert p.templater_hint is False and p.variant_missing is False
    [action] = p.actions
    assert action == {"id": "I01", "action": "move_note", "source": f"{INBOX}{PERIOD}.md", "destination": TARGET,
                      "title": PERIOD, "rendered_file": f"{PERIOD}.md", "source_inbox_item": None}
    assert p.note_path == f"{INBOX}{PERIOD}.md"
    assert "<%" not in p.note_text
    body = p.note_text.split("---\n", 2)[2]
    # the section's trailing newline becomes the blank line before the anchor, as Hashi's insert does
    assert body == f"# {PERIOD}\n\n## Woche\n\n{p.section_md}\n## In my own words\n\n"
    assert p.section_md.startswith(f"## {HEADING}\n{MARKER}\n### Erledigt\n")


def test_actions_new_note_is_stamped_rendered_note_pending_move_with_a_stable_block():
    p = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw=VARIANT))
    tomo = frontmatter_of(p.note_text)["tomo"]
    assert (tomo["doc_type"], tomo["state"], tomo["run_id"], tomo["updated_at"]) == \
        ("rendered-note", "pending-move", "r-test", GENERATED)
    assert frontmatter_of(p.note_text)["tags"] == "weekly"                 # the template's own keys stay
    again = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw=VARIANT))
    assert again.note_text == p.note_text
    plain = plan(target_text=None)                                        # no frontmatter → a fresh block
    assert frontmatter_of(plain.note_text)["tomo"]["state"] == "pending-move"


def test_actions_new_note_from_a_raw_templater_template_sets_the_hint():
    p = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw=RAW_TEMPLATE))
    assert p.templater_hint is True and p.variant_missing is False
    assert "<% tp.file.title %>" in p.note_text and p.section_md in p.note_text
    assert p.preview()["templater_hint"] is True and "variant_missing" not in p.preview()


def test_actions_new_note_with_a_vanished_variant_falls_back_to_raw():
    p = plan(target_text=None, setup=setup(template="t_week.md", template_variant="t_week_tomo.md"),
             template=ra.Template(raw=RAW_TEMPLATE, variant=None))
    assert p.variant_missing is True and p.templater_hint is True and "<%" in p.note_text
    assert p.preview()["variant_missing"] is True


def test_actions_new_note_inside_appends_at_the_end_of_the_anchors_section():
    p = plan(target_text=None, setup=setup(anchor="Woche", placement="inside", template="t_week.md"),
             template=ra.Template(raw=VARIANT))
    body = p.note_text.split("---\n", 2)[2]
    assert body == f"# {PERIOD}\n\n## Woche\n\n{p.section_md}\n## In my own words\n\n"
    assert p.section_md.startswith(f"### {HEADING}\n")
    # inside the last section: appended at the end of the note
    p = plan(target_text=None, setup=setup(anchor=OWN, placement="inside", own_sections=[], template="t_week.md"),
             template=ra.Template(raw=VARIANT))
    assert p.note_text.split("---\n", 2)[2] == f"# {PERIOD}\n\n## Woche\n\n## In my own words\n\n{p.section_md}\n"


def test_actions_new_note_plain_when_there_is_no_template():
    p = plan(target_text=None)
    assert p.mode == "new-note" and p.problems == [] and p.templater_hint is False
    assert p.note_text.split("---\n", 2)[2] == f"# {PERIOD}\n\n{p.section_md}"
    assert p.section_md.startswith(f"## {HEADING}\n{MARKER}\n### Erledigt\n")
    assert p.actions[0]["action"] == "move_note"


def test_actions_new_note_template_without_the_anchor_is_place_missing():
    p = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw="# T\n\n## Nur das\n"))
    assert p.problems == ["place-missing"] and p.headings == ["T", "Nur das"]
    assert p.actions == [] and p.note_text is None


# ---------------------------------------------------------------- the landed text

def test_actions_every_item_line_is_escaped_once_and_counted():
    groups = {"done": [{"text": "# keine Überschrift\n- [ ] kein Kasten\n> kein Zitat\n```\n--- kein Strich",
                        "links": ["2026-03-24"]}]}
    text = document(groups)
    # review_doc escaped Tomo's lines already; the user adds unescaped ones and a continuation line
    text = text.replace("%%t1%%", "%%t1%%\n  # vom Nutzer", 1)
    text = text.replace("## Offen\n- nichts gefunden", "## Offen\n- [x] > Zitat des Nutzers\n  - [ ] Unterpunkt\n  ~~~", 1)
    p = plan(approved(text, document(groups)))
    landed = p.section_md.split("\n")
    assert landed[2:] == ["### Erledigt",
                          "- \\# keine Überschrift ([[2026-03-24]])",
                          "  \\# vom Nutzer",
                          "  \\- [ ] kein Kasten",
                          "  \\> kein Zitat",
                          "  \\```",
                          "  \\--- kein Strich",
                          "### Offen",
                          "- \\> Zitat des Nutzers",
                          "  \\- [ ] Unterpunkt",
                          "  \\~~~",
                          ""]
    assert p.escaped_lines == 4                      # the user's lines only; Tomo's were escaped by review_doc
    assert "\\\\" not in p.section_md               # never a second backslash
    # idempotent: the predicate on an already landed item line changes nothing
    items = [ln[2:] for ln in landed if ln.startswith(("- ", "  "))]
    assert len(items) == 9 and all(rd.neutralised(ln) == ln for ln in items)


def test_actions_ids_are_stripped_and_the_content_is_stable_and_ends_with_one_blank_line():
    text = document().replace("- [x] Steuer offen ([[2026-03-27]]) %%t3%%",
                              "- [x] Steuer offen ([[2026-03-27]]) %%t3%%\n  mehr dazu %%t9%%")
    p = plan(approved(text))
    assert "%%t" not in p.section_md and "%%" not in p.section_md.replace(MARKER, "")
    assert "- Steuer offen ([[2026-03-27]])\n  mehr dazu\n" in p.section_md
    assert p.section_md.endswith("\n") and not p.section_md.endswith("\n\n")
    assert p.actions[0]["content"].split("\n")[-2:] == ["- Sport: 6 von 7 Tagen", ""]
    first = json.dumps(instruction_set(plan(approved(text))), sort_keys=True)
    second = json.dumps(instruction_set(plan(approved(text))), sort_keys=True)
    assert first == second


def test_actions_only_kept_items_land_and_empty_groups_leave_no_heading():
    text = tick(document(), "t1", False)                    # one of the two done items
    text = tick(text, "t3", False)                          # the only open item
    text = text.replace("- [x] Neue Notiz ([[2026-03-24]]) %%t4%%\n", "")   # deleted
    review = approved(text)
    assert review["counts"] == {"kept": 2, "unticked": 2, "deleted": 1, "added": 0}
    p = plan(review)
    assert p.section_md == (f"## {HEADING}\n{MARKER}\n### Erledigt\n- zwei Zeilen ([[2026-03-25]])\n  zweite Zeile\n"
                            "### Gewohnheiten\n- Sport: 6 von 7 Tagen\n")
    assert "### Offen" not in p.section_md and "### Wiederkehrende Themen" not in p.section_md


def test_actions_a_user_item_lands_like_tomos_and_an_unknown_group_does_not():
    text = document().replace("## Offen\n", "## Offen\n- [x] Mein Punkt\n", 1)
    text = text.replace("## Gewohnheiten\n", "## Eigene Gruppe\n- [x] verloren\n## Gewohnheiten\n", 1)
    review = approved(text)
    assert "unknown-group" in review["warnings"]
    p = plan(review)
    assert "- Mein Punkt\n" in p.section_md and "verloren" not in p.section_md


def test_actions_an_unapproved_gateless_or_empty_review_emits_nothing():
    unapproved = approved(document().replace("- [x] Approved", "- [ ] Approved", 1))
    p = plan(unapproved)
    assert p.problems == ["not-approved"] and p.actions == [] and p.section_md == ""
    gateless = approved(document().replace("- [x] Approved\n", "", 1))
    assert plan(gateless).problems == ["approved-line-missing"] and plan(gateless).actions == []
    text = document()
    for item_id in ("t1", "t2", "t3", "t4", "t5"):
        text = tick(text, item_id, False)
    empty = approved(text)
    assert plan(empty).problems == ["nothing-to-deliver"] and plan(empty).actions == []
    assert plan(empty, target_text=None).problems == ["nothing-to-deliver"]


# ---------------------------------------------------------------- the wire

@pytest.mark.parametrize("mode", ["insert", "replace", "new-note"])
@pytest.mark.parametrize("schema", SCHEMAS + ([HASHI_VENDORED] if HASHI_VENDORED.exists() else []),
                         ids=lambda p: p.name if p.parent.name == "schemas" else "hashi-vendored")
def test_actions_every_set_validates_against_both_schemas(mode, schema):
    p = {"insert": lambda: plan(), "replace": lambda: plan(target_text=landed_note()),
         "new-note": lambda: plan(target_text=None, template=ra.Template(raw=RAW_TEMPLATE))}[mode]()
    assert p.mode == mode and len(p.actions) == 1
    doc = instruction_set(p)
    assert doc["schema_version"] == "3" and doc["type"] == "tomo-instructions"
    assert doc["md_peer"] == f"{PERIOD}_review_instructions" and doc["generated"] == GENERATED
    assert schema_errors(doc, schema) == []
