#!/usr/bin/env python3
# version: 0.4.2
r"""test_review_instructions.py — lib/review_actions.py (spec 045 T4.1; PRD F4-AC7, F5-AC3 to F5-AC7,
F6-AC3, Edge Cases; SDD "the review section and the heading-level rule", ADR-3, ADR-8, ADR-13).

The approved review is built the way production builds it: review_doc.render_document → the user
ticks Approved (and edits) → review_doc_parse.parse_document → ParsedDoc.approved_review(). The
target note's text is handed in; nothing here calls Kado. What is pinned, as `test_actions_*`:
an existing target without the marker gets one insert_under_marker with `before` or `inside`
(never `after`) at the level review_config.place_level gives; the marker of the same period
turns it into one replace_section on the heading above the marker, also when that heading was
renamed (`heading-renamed`), with a body Hashi's identical-block check reads as already landed;
the same heading without the marker — or the marker under an own section, or under a heading an
earlier user heading shadows — is `user-heading-collision` with no action; the marker counts at
column 0 only, an indented copy (an item's continuation line) is not it; a note found by name
elsewhere is the target (`target_moved`), the lexically first hit whatever order the search
answered in; the flat folder wins over the year subfolder and the duplicate is named; a review
heading above level 5 is `place-too-deep`, an absent anchor `place-missing`, both with the
note's headings; an absent target yields a new note (variant, raw Templater template with
`templater_hint`, vanished variant with `variant_missing`, plain; a template whose frontmatter
holds `tomo:` or never closes its fence falls back to the plain note with `template_unmergeable`
holding the reason) stamped rendered-note/pending-move plus one move_note, the template's final
newline kept byte for byte; every item line is escaped once and
counted, a line review_doc already escaped lands with exactly one backslash; ids are stripped;
the content ends with one blank line and is byte-identical across builds; only kept items land
and empty groups leave no heading; kept items under an unknown heading are counted as `unlanded`
and named `unlanded-items` while the known ones still land, also next to `nothing-to-deliver`;
an unapproved, gate-less or empty review emits nothing; every heading emitted or matched is the
heading as Hashi's parser reads it (closing hashes kept, every ``` or ~~~ line toggles a fence,
no quoted fence) — `hashi_headings` here is a test-local copy of that rule — while a configured
anchor or the review heading matches it with or without closing hashes; a refused replace
(too deep, collision, no heading above the marker) reports mode `replace` and the found heading
as the place; every set validates against the producer schema, Tomo's Hashi copy and Hashi's
vendored copy.

The mirror is exact to ECMAScript, pinned as `test_hashi_mirror_*`: Hashi splits on `\n` only
and its `.` matches no line terminator, so a CRLF line or one holding U+2028/U+2029 is no
heading (`place-missing`, no anchor Hashi cannot resolve); its `\s` and `trim()` share one set
(WhiteSpace U+0009/000B/000C/FEFF + Zs, LineTerminator U+000A/000D/2028/2029) that Python's
`\s`/`strip()` do not (they add U+001C-001F and U+0085, lack U+FEFF), so `ra.JS_WS` is that set
and is compared with `unicodedata`. V8 22 oracle, `/^(#{1,6})\s+(.*)$/` then `.trim()`:
`## Woche\r` → no heading; `## Wo che` → no heading; `##﻿Woche` → `Woche`;
`## Woche` → `Woche`; `##　Woche　` → `Woche`; `##\u0085Woche` → no heading;
`## Woche\u0085` → `Woche\u0085` (kept); `##\u001CWoche` → no heading; `##᠎Woche` → no
heading; `##\r` → `` (empty text); `/^\s*(?:```|~~~)/` on `﻿```` → fence, on
`\u0085```` → no fence.
The review-instructions.py tests of T4.2 live in tests/test_review_deliver.py. All data is synthetic.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
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
from review_deliver_helpers import SCHEMA_PARAMS  # noqa: E402
from test_review_doc_parse import GROUPS, tick  # noqa: E402

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


# ECMAScript `\s` / `String.prototype.trim`, spelled here independently of ra.JS_WS: the V8 scan of
# every code point `/\s/` matches (see the docstring).
ES_WS = "\t\n\v\f\r   " + "".join(chr(c) for c in range(0x2000, 0x200B)) + "    　﻿"
ES_LINE_TERMINATORS = "\n\r  "
_ES_WS = f"[{re.escape(ES_WS)}]"
_ES_FENCE = re.compile(rf"^{_ES_WS}*(?:```|~~~)")
_ES_HEADING = re.compile(rf"^(#{{1,6}}){_ES_WS}+([^{re.escape(ES_LINE_TERMINATORS)}]*)\Z")


def hashi_headings(text: str) -> list[tuple[int, int, str]]:
    """Hashi's parseHeadings over fencedLineMask (markdownStructure.ts), reimplemented here on purpose
    with ECMAScript's character classes: ``^(#{1,6})\\s+(.*)$`` trimmed (``.`` matches no line
    terminator, ``$`` only the end), closing hashes kept; any ``^\\s*(```|~~~)`` line toggles the fence;
    the file is split on ``\\n`` only."""
    found = []
    fenced = False
    for i, line in enumerate(text.split("\n")):
        if _ES_FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = _ES_HEADING.match(line)
        if m:
            found.append((i, len(m.group(1)), m.group(2).strip(ES_WS)))
    return found


def hashi_resolves(text: str, value: str) -> tuple[int, int, str] | None:
    """anchorResolver.ts:100 — the first heading whose text equals ``value`` exactly."""
    return next((h for h in hashi_headings(text) if h[2] == value), None)


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
    # the marker proves a rerun: the refusal reports the replace it did not do, at the heading it found
    assert p.mode == "replace" and p.place == {"anchor": HEADING, "placement": "replace", "level": 2}
    assert p.headings[:3] == [PERIOD, HEADING, HEADING] and p.headings[-1] == OWN


def test_actions_own_sections_are_never_targeted():
    # the marker moved into the user's own section: never replaced
    moved = NOTE.replace("meine Worte", f"{MARKER}\n### Erledigt\n- alt")
    p = plan(target_text=moved)
    assert p.problems == ["user-heading-collision"] and p.actions == []
    assert p.mode == "replace" and p.place == {"anchor": OWN, "placement": "replace", "level": 2}
    # inside an own section: never inserted into
    p = plan(setup=setup(anchor=OWN, placement="inside"))
    assert p.problems == ["user-heading-collision"] and p.actions == []
    # before an own section is the SDD example and fine
    assert plan(setup=setup(anchor=OWN, placement="before")).problems == []


def test_actions_an_indented_marker_copy_is_not_the_marker():
    # the marker lands verbatim as an item's continuation line (`%%` is not structure to review_doc.neutralised)
    indented = f"  {MARKER}"
    assert rd.neutralised(indented.strip()) == MARKER
    # the real marker deleted, only the indented copy left under the review heading: no marker → collision
    without = landed_note().replace(f"{MARKER}\n", "", 1).replace(f"{FIRST_ITEM}\n", f"{FIRST_ITEM}\n{indented}\n", 1)
    assert MARKER not in without.split("\n") and indented in without.split("\n")
    p = plan(target_text=without)
    assert p.mode == "insert" and p.problems == ["user-heading-collision"] and p.actions == []
    # under a user heading with no review heading anywhere: a plain insert
    p = plan(target_text=NOTE.replace("text der Woche", f"- mein Punkt\n{indented}"))
    assert p.mode == "insert" and p.problems == [] and p.actions[0]["action"] == "insert_under_marker"
    # the real marker is matched with trailing whitespace, never with leading
    assert ra._marker_index([f"{MARKER}  \t"], MARKER) == 0
    assert ra._marker_index([f" {MARKER}"], MARKER) is None


def test_actions_a_marker_with_no_heading_above_it_is_place_missing():
    p = plan(target_text=f"{MARKER}\n- old\n\n## Woche\n")
    assert p.problems == ["place-missing"] and p.headings == ["Woche"] and p.actions == []
    # a rerun with nothing Hashi could address: the place is the (absent) heading, not the setup's anchor
    assert p.mode == "replace" and p.place == {"anchor": None, "placement": "replace", "level": None}


# ---------------------------------------------------------------- headings as Hashi reads them

def test_actions_replace_anchors_the_heading_as_hashi_reads_it_closing_hashes_kept():
    note = f"# {PERIOD}\n\n## Woche ##   \n{MARKER}\n### Erledigt\n- alt\n\n## {OWN}\nmeine Worte\n"
    p = plan(target_text=note)
    assert p.mode == "replace" and p.problems == ["heading-renamed"]
    [action] = p.actions
    assert action["action"] == "replace_section" and action["anchor"]["value"] == "Woche ##"
    assert p.place == {"anchor": "Woche ##", "placement": "replace", "level": 2}
    assert p.section_md.startswith(f"## Woche ##\n{MARKER}\n")
    # Hashi resolves the emitted value to the heading above the marker — and would not resolve the bare text
    assert hashi_resolves(note, action["anchor"]["value"]) == (2, 2, "Woche ##")
    assert hashi_resolves(note, "Woche") is None


def test_actions_a_configured_anchor_matches_with_or_without_closing_hashes_and_emits_hashis_text():
    note = NOTE.replace("## Woche\n", "## Woche ##\n", 1)
    p = plan(target_text=note, setup=setup(anchor="Woche", placement="inside"))
    assert p.problems == []
    [action] = p.actions
    assert action["anchor"]["value"] == "Woche ##" and p.place["anchor"] == "Woche ##"
    assert hashi_resolves(note, action["anchor"]["value"]) == (2, 2, "Woche ##")
    # the other way round: the user wrote the anchor with closing hashes, the note has none
    p = plan(setup=setup(anchor="Woche ##", placement="inside"))
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == "Woche"
    assert hashi_resolves(NOTE, "Woche") == (2, 2, "Woche")
    # the review heading too: `Tomo Review ##` above the marker is not a rename, and without the marker a collision
    landed = landed_note().replace(f"## {HEADING}\n", f"## {HEADING} ##\n", 1)
    p = plan(target_text=landed)
    assert p.mode == "replace" and p.problems == [] and p.actions[0]["anchor"]["value"] == f"{HEADING} ##"
    p = plan(target_text=NOTE.replace("## Woche\ntext der Woche", f"## {HEADING} ##\nmy own weekly thoughts"))
    assert p.problems == ["user-heading-collision"] and p.actions == []
    # an own section with closing hashes is still an own section
    p = plan(target_text=NOTE.replace(f"## {OWN}\n", f"## {OWN} ##\n", 1), setup=setup(anchor=OWN, placement="inside"))
    assert p.problems == ["user-heading-collision"] and p.actions == []


def test_actions_fences_toggle_as_hashi_toggles_them():
    # a fence opened with ``` and closed with ~~~ is closed to Hashi: the heading after it is an anchor
    toggled = NOTE.replace("text der Woche", "```\ncode\n~~~\n## Extra\nmore")
    assert [h[2] for h in hashi_headings(toggled)] == [PERIOD, "Woche", "Extra", OWN]
    p = plan(target_text=toggled, setup=setup(anchor="Extra"))
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == "Extra"
    # a quoted fence is no fence to Hashi: the heading between two `> ```` lines is an anchor
    quoted = NOTE.replace("text der Woche", "> ```\n## Extra\n> ```")
    assert [h[2] for h in hashi_headings(quoted)] == [PERIOD, "Woche", "Extra", OWN]
    p = plan(target_text=quoted, setup=setup(anchor="Extra"))
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == "Extra"
    # and the marker follows the same mask: under the toggled-closed fence it counts, under an open one not
    marked = NOTE.replace("text der Woche", f"```\ncode\n~~~\n{MARKER}\n- alt")
    assert plan(target_text=marked).mode == "replace"
    unclosed = NOTE.replace("text der Woche", f"```\n{MARKER}\n- alt")
    p = plan(target_text=unclosed)
    assert p.mode == "insert" and p.problems == ["place-missing"] and p.headings == [PERIOD, "Woche"]


# ---------------------------------------------------------------- the mirror is exact to ECMAScript

def test_hashi_mirror_a_crlf_target_has_no_heading_to_hashi_and_is_place_missing():
    crlf = NOTE.replace("\n", "\r\n")
    assert hashi_headings(crlf) == [] and ra.hashi_headings(crlf.split("\n")) == []
    p = plan(target_text=crlf)
    assert p.mode == "insert" and p.problems == ["place-missing"] and p.headings == [] and p.actions == []
    # the marker is Tomo's own match and still found on a CRLF line; with no heading above it to Hashi
    # the rerun is refused with an empty place, never with an anchor Hashi cannot resolve
    p = plan(target_text=landed_note().replace("\n", "\r\n"))
    assert p.mode == "replace" and p.problems == ["place-missing"] and p.actions == []
    assert p.place == {"anchor": None, "placement": "replace", "level": None} and p.headings == []
    # a lone CR is a line terminator to Hashi's `.` as well: the text group ends before it
    assert ra.hashi_headings(["## Woche\r", "##\r", "## \r"]) == [(1, 2, ""), (2, 2, "")]


@pytest.mark.parametrize("terminator", [" ", " "])
def test_hashi_mirror_a_heading_line_holding_a_js_line_terminator_is_no_heading(terminator):
    note = NOTE.replace("## Woche\n", f"## Wo{terminator}che\n", 1)
    assert [h[2] for h in hashi_headings(note)] == [PERIOD, OWN]
    p = plan(target_text=note, setup=setup(anchor=f"Wo{terminator}che"))
    assert p.problems == ["place-missing"] and p.headings == [PERIOD, OWN] and p.actions == []
    assert plan(target_text=note, setup=setup(anchor="Woche")).problems == ["place-missing"]


def test_hashi_mirror_js_ws_is_ecmascripts_whitespace_set():
    zs = {chr(c) for c in range(0x110000) if unicodedata.category(chr(c)) == "Zs"}
    assert set(ra.JS_WS) == zs | set("\t\v\f﻿") | set("\n\r  ")
    assert len(ra.JS_WS) == len(set(ra.JS_WS))
    assert set(ra.JS_WS) == set(ES_WS)                         # the test's own spelling agrees
    # the three characters that separate the two languages, each on the ECMAScript side
    assert "﻿" in ra.JS_WS and not "﻿".isspace()
    assert "\x85" not in ra.JS_WS and "\x85".isspace()
    assert "\x1c" not in ra.JS_WS and "\x1c".isspace()
    assert "᠎" not in ra.JS_WS                          # Cf since Unicode 6.3, not Zs


def test_hashi_mirror_a_bom_after_the_hashes_is_whitespace_and_trimmed():
    note = NOTE.replace("## Woche\n", "##﻿Woche﻿\n", 1)
    assert hashi_headings(note)[1] == (2, 2, "Woche")
    p = plan(target_text=note, setup=setup(anchor="Woche", placement="inside"))
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == "Woche"
    assert p.place == {"anchor": "Woche", "placement": "inside", "level": 3}
    # NBSP and the ideographic space are Zs: whitespace to both regexes
    assert ra.hashi_headings(["## Woche ", "##　Woche　"]) == [(0, 2, "Woche"), (1, 2, "Woche")]
    # tab, VT and FF are WhiteSpace too
    assert ra.hashi_headings(["##\tWoche\t", "##\v\fWoche"]) == [(0, 2, "Woche"), (1, 2, "Woche")]
    # and a BOM opens a fence line to Hashi, so the heading inside is no anchor
    assert ra.fenced_mask(["﻿```", "## x", "```"]) == [True, True, True]


@pytest.mark.parametrize("char", ["\x85", "\x1c", "᠎"])
def test_hashi_mirror_characters_outside_ecmascripts_set_are_text(char):
    # after the hashes it is not the required whitespace: no heading
    assert ra.hashi_headings([f"##{char}Woche"]) == [] and hashi_headings(f"##{char}Woche") == []
    assert ra.hashi_headings([f"## {char}Woche"]) == [(0, 2, f"{char}Woche")]
    # trailing, it is kept in the text: Hashi resolves `Woche<char>`, never `Woche`, and whatever the
    # plan emits for a bare `Woche` anchor (tolerant match, exact emission) is the text Hashi resolves
    note = NOTE.replace("## Woche\n", f"## Woche{char}\n", 1)
    assert hashi_headings(note)[1] == (2, 2, f"Woche{char}") and hashi_resolves(note, "Woche") is None
    p = plan(target_text=note, setup=setup(anchor=f"Woche{char}"))
    assert p.problems == [] and p.actions[0]["anchor"]["value"] == f"Woche{char}"
    p = plan(target_text=note, setup=setup(anchor="Woche"))
    assert all(hashi_resolves(note, a["anchor"]["value"]) == (2, 2, f"Woche{char}") for a in p.actions)
    assert p.problems == [] or (p.problems == ["place-missing"] and p.headings == [PERIOD, f"Woche{char}", OWN])
    # and it does not open a fence
    assert ra.fenced_mask([f"{char}```", "## x"]) == [False, False]


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


def test_actions_the_hit_elsewhere_is_the_lexically_first_whatever_order_the_search_answered():
    candidates = Period.week(2026, 13).note_paths(WEEKLY, "gggg-[W]ww")
    texts = {"Zettel/2026-W13.md": NOTE, "Archive/2026-W13.md": NOTE}
    reverse = ["Zettel/2026-W13.md", "Archive/2026-W13.md"]
    assert ra.locate_target(candidates, texts, reverse).path == "Archive/2026-W13.md"
    assert ra.locate_target(candidates, texts, reversed(reverse)).path == "Archive/2026-W13.md"


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
    # the place reported is the heading found above the marker, not the setup's anchor
    assert p.place == {"anchor": HEADING, "placement": "replace", "level": 6}


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


def test_actions_new_note_keeps_the_templates_final_newline_byte_for_byte():
    head, body_end = f"# {PERIOD}\n\n## Woche\n\n", "## In my own words"
    for tail in ("", "\n", "\n\n"):
        p = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw=head + body_end + tail))
        assert p.problems == []
        assert p.note_text.split("---\n", 2)[2] == f"{head}{p.section_md}\n{body_end}{tail}"
    # inside the last section of a template without a final newline: the section's own newline is the last byte
    p = plan(target_text=None, setup=setup(anchor=OWN, placement="inside", own_sections=[], template="t_week.md"),
             template=ra.Template(raw=head + body_end))
    assert p.note_text.split("---\n", 2)[2] == f"{head}{body_end}\n{p.section_md}"


TOMO_TEMPLATE = f"---\ntags: weekly\ntomo:\n  foo: 1\n---\n# {PERIOD}\n\n## Woche\n\n## In my own words\n"


@pytest.mark.parametrize("which", ["raw", "variant"])
def test_actions_new_note_template_with_a_tomo_block_falls_back_to_the_plain_note(which):
    kw = dict(setup=setup(template="t_week.md", template_variant="t_week_tomo.md"))
    template = ra.Template(raw=TOMO_TEMPLATE, variant=None) if which == "raw" \
        else ra.Template(raw=RAW_TEMPLATE, variant=TOMO_TEMPLATE)
    p = plan(target_text=None, template=template, **kw)
    assert p.mode == "new-note" and p.problems == []
    assert p.template_unmergeable == "Frontmatter already carries a top-level 'tomo:' key."
    assert p.preview()["template_unmergeable"] == p.template_unmergeable
    [action] = p.actions
    assert action["action"] == "move_note" and action["destination"] == TARGET
    # the plain note, byte-identical to the one a missing template yields
    plain = plan(target_text=None, setup=setup(template="t_week.md", template_variant="t_week_tomo.md"))
    assert p.note_text == plain.note_text and p.place == plain.place and p.section_md == plain.section_md
    assert p.note_text.split("---\n", 2)[2] == f"# {PERIOD}\n\n{p.section_md}"
    assert frontmatter_of(p.note_text) == frontmatter_of(plain.note_text) and "foo" not in p.note_text
    assert p.templater_hint is False and p.variant_missing is (which == "raw")
    assert "template_unmergeable" not in plain.preview() and plain.template_unmergeable is None


def test_actions_new_note_template_with_an_unclosed_frontmatter_fence_falls_back_to_the_plain_note():
    unclosed = f"---\ntags: weekly\n# {PERIOD}\n\n## Woche\n\n## In my own words\n"
    p = plan(target_text=None, setup=setup(template="t_week.md"), template=ra.Template(raw=unclosed))
    assert p.problems == [] and p.template_unmergeable == "Leading frontmatter fence is unclosed."
    assert p.note_text == plan(target_text=None).note_text and p.actions[0]["action"] == "move_note"
    assert p.preview()["template_unmergeable"] == "Leading frontmatter fence is unclosed."


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


def test_actions_unlanded_items_are_named_and_the_landed_ones_still_land():
    text = document()
    for item_id in ("t2", "t3", "t4", "t5"):
        text = tick(text, item_id, False)                      # t1 is the one landed item
    text = text.replace("## Gewohnheiten\n", "## Eigene Gruppe\n- [x] verloren\n- [x] auch verloren\n- [ ] nicht\n"
                        "## Gewohnheiten\n", 1)
    review = approved(text)
    assert "unknown-group" in review["warnings"]
    p = plan(review)
    assert p.problems == ["unlanded-items"] and p.unlanded == 2
    assert p.preview()["unlanded"] == 2 and p.preview()["problems"] == ["unlanded-items"]
    [action] = p.actions
    assert action["action"] == "insert_under_marker"
    assert p.section_md == f"## {HEADING}\n{MARKER}\n### Erledigt\n{FIRST_ITEM}\n"
    assert "verloren" not in p.section_md
    # with nothing unlanded the count is absent from the preview
    assert plan().unlanded == 0 and "unlanded" not in plan().preview()


def test_actions_only_unlanded_items_is_nothing_to_deliver_and_unlanded_items():
    text = document()
    for item_id in ("t1", "t2", "t3", "t4", "t5"):
        text = tick(text, item_id, False)
    text = text.replace("## Gewohnheiten\n", "## Eigene Gruppe\n- [x] verloren\n## Gewohnheiten\n", 1)
    p = plan(approved(text))
    assert p.problems == ["nothing-to-deliver", "unlanded-items"] and p.unlanded == 1 and p.actions == []
    assert plan(approved(text), target_text=None).problems == ["nothing-to-deliver", "unlanded-items"]


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
@pytest.mark.parametrize("schema", SCHEMA_PARAMS)
def test_actions_every_set_validates_against_both_schemas(mode, schema):
    p = {"insert": lambda: plan(), "replace": lambda: plan(target_text=landed_note()),
         "new-note": lambda: plan(target_text=None, template=ra.Template(raw=RAW_TEMPLATE))}[mode]()
    assert p.mode == mode and len(p.actions) == 1
    doc = instruction_set(p)
    assert doc["schema_version"] == "3" and doc["type"] == "tomo-instructions"
    assert doc["md_peer"] == f"{PERIOD}_review_instructions" and doc["generated"] == GENERATED
    assert schema_errors(doc, schema) == []
