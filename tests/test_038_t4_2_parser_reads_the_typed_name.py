#!/usr/bin/env python3
"""test_038_t4_2_parser_reads_the_typed_name.py — spec 038 T4.2.

The owner types a rename target into the suggestions markdown and Pass 2 uses
it. Until this task the markdown accepted the keystrokes and dropped them:
`_join_attachment_conflict_remedies` read `proposed_name` from the structured
suggestions-doc by `source` and the rendered text was never consulted
(`tests/test_037_typed_rename_target_is_ignored.py`, whose strict xfail this
task removes).

Three mechanisms are under test here, and each has its own mutation:

1. **The name is read from the markdown.** Mutation: restore the
   `proposed_names = {c.get("source"): c.get("proposed_name") ...}` lookup in
   `_join_attachment_conflict_remedies` and return it as the answer — every
   `test_an_overtyped_name_*` case goes green-to-red because the doc's
   computed name comes back instead of the typed one.

2. **The renderer's own folder join is un-rendered first** (owner ruling
   2026-10-02). `render_attachment_conflicts_block` puts
   `_asset_dest_join(asset_folder, proposed_name)` — a full destination PATH —
   in the backticks, so the natural owner edit keeps the folder and would hit
   T3.1's `separator_present` refusal. Mutations: drop the prefix strip (the
   in-place edit then refuses `separator_present`, and the untouched default
   refuses too); or implement it as `rsplit("/", 1)[-1]` instead of an exact
   prefix match (`test_a_different_folder_typed_is_refused` goes red — a
   basename() would accept `Archive/…` by silently discarding the folder the
   owner typed, which is the ADR-5 rewrite this spec exists to prevent).

3. **The `rename_impossible` override turns on the absence of a NAME, not on
   the presence of the marker** (owner ruling 2026-10-02), and it is settled
   BEFORE the typed-name guard can see the line. Mutations: restore
   `rename_impossible = RENAME_IMPOSSIBLE_MARKER in label` (case (a) below
   goes red — the typed name is discarded and the entry resolves to `ignore`);
   or drop the override entirely (case (b) goes red — an untouched empty
   backtick pair would be reported as an owner-supplied blank name, and T3.4
   would render a refusal bullet for a name nobody typed).

**Fixtures come from the real renderer**, not hand-built markdown: the two
old-shape fixtures this task replaced in `tests/test_037_t2_4_parse_remedy.py`
existed because someone hand-built a line the renderer later changed. The one
exception is `test_a_half_edited_line_with_no_closing_backtick_is_refused`,
whose input no renderer can produce — it is a half-finished owner edit, and
its docstring says so.

Every refusal assertion names its `reason`. "Resolves to a refusal" is true
both before and after this change for DIFFERENT reasons — a broken prefix
strip refuses `separator_present` where an emptied line must refuse `blank` —
so polarity alone would distinguish nothing.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    _asset_dest_join,
    _build_move_asset_actions,
)
from lib.typed_name_check import check_typed_name  # noqa: E402


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


PARSER = _load("suggestion_parser_t4_2", "suggestion-parser.py")
REDUCER = _load("suggestions_reducer_t4_2", "suggestions-reducer.py")

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
OCCUPIED = f"{ASSET_FOLDER}karte.png"

COMPUTED = "karte (2).png"
TYPED = "karte-dresden-1938.png"
FORBIDDEN = "karte|1938.png"  # '|' is Obsidian-forbidden, legal on macOS


def _conflict(proposed_name: str | None) -> dict:
    """One `attachment_conflicts[]` record, the shape T1.5 writes."""
    return {
        "source": SOURCE,
        "destination": OCCUPIED,
        "same_file": False,
        "owner_source_items": ["100 Inbox/Dresden.md"],
        "proposed_name": proposed_name,
    }


def _doc(proposed_name: str | None) -> dict:
    return {"attachment_conflicts": [_conflict(proposed_name)]}


def _rendered(proposed_name: str | None) -> str:
    """The markdown Pass 1 actually ships, from the renderer itself."""
    return REDUCER.render_attachment_conflicts_block(
        [_conflict(proposed_name)], ASSET_FOLDER
    )


def _retype(rendered: str, old_line_contains: str, new_line: str) -> str:
    """Replace the single line containing `old_line_contains` with `new_line`
    — an owner editing one remedy line and leaving the rest of the document
    exactly as rendered."""
    lines = rendered.splitlines()
    matches = [i for i, line in enumerate(lines) if old_line_contains in line]
    assert len(matches) == 1, (old_line_contains, lines)
    lines[matches[0]] = new_line
    return "\n".join(lines) + "\n"


def _record(markdown: str, doc: dict) -> dict:
    """The one joined remedy record the parser hands Pass 2."""
    records = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(markdown), doc
    )
    assert len(records) == 1, records
    return records[0]


def _outcome(record: dict) -> tuple[list[dict], list[dict]]:
    """Run the record through the Pass 2 builder that owns the typed-name
    guard, so a refusal is asserted where the owner would actually see it."""
    manifest = [{
        "id": "S01",
        "action": None,
        "title": "Dresden",
        "source_path": "Dresden.md",
        "rendered_file": "2026-01-01_0900_dresden.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "attachments": [SOURCE],
    }]
    return _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=[record]
    )


# ---------------------------------------------------------------------------
# 1. The untouched default — the regression floor
# ---------------------------------------------------------------------------

def test_the_untouched_default_is_byte_identical_to_the_computed_name():
    """An owner who touches nothing files under the name Pass 1 computed, and
    the record is byte-for-byte what the pre-T4.2 doc-read produced.

    This is the criterion that forbids the obvious shortcut: flagging every
    markdown name `name_is_owner_supplied: True`.

    Two mutations break it, by different mechanisms, and an earlier draft of
    this docstring credited the wrong one to the wrong mutation (found in code
    review, 2026-10-02):

    - Set the flag `True` unconditionally. Caught by the dict equality below
      and **not** by `check_typed_name` — `proposed_name` here is the
      post-strip bare name, which holds no separator, so the guard would pass
      it. The flag value alone is what differs.
    - Compare the **pre-strip** extracted text against the doc's bare name,
      which is what this task's brief originally specified. That flags the
      untouched default owner-supplied *and* hands the guard the full rendered
      path, so it refuses `separator_present`. This is the one where the
      backticks holding a path is the operative fact."""
    record = _record(_rendered(COMPUTED), _doc(COMPUTED))
    assert record == {
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": COMPUTED,
        "name_is_owner_supplied": False,
    }, record
    actions, skipped = _outcome(record)
    assert skipped == [], skipped
    assert [a["destination"] for a in actions] == [f"{ASSET_FOLDER}{COMPUTED}"], actions


# ---------------------------------------------------------------------------
# 2. The un-render table — every row is its own case (plan T4.2 step 3b(d))
# ---------------------------------------------------------------------------

def test_an_overtyped_name_with_the_folder_left_in_place_is_honoured():
    """Row 1: the natural edit — the owner retypes the filename and leaves the
    folder the document showed them. `rename`, carrying the BARE typed name.

    Mutation: drop the structured-doc read's replacement (the computed name
    comes back); or drop the prefix strip (`Atlas/…/karte-dresden-1938.png`
    reaches the guard and is refused `separator_present`)."""
    markdown = _retype(
        _rendered(COMPUTED),
        "] Rename to ",
        f"- [x] Rename to `{ASSET_FOLDER}{TYPED}`",
    )
    record = _record(markdown, _doc(COMPUTED))
    assert record["remedy"] == "rename", record
    assert record["proposed_name"] == TYPED, record
    assert record["name_is_owner_supplied"] is True, record
    actions, skipped = _outcome(record)
    assert skipped == [], skipped
    assert [a["destination"] for a in actions] == [f"{ASSET_FOLDER}{TYPED}"], actions


def test_an_overtyped_name_with_the_folder_deleted_too_is_the_same_name():
    """Row 2: the owner deletes the folder as well and types a bare name. The
    SAME `proposed_name` as row 1 — that equality is what proves the strip is
    an exact prefix match rather than a `basename()`.

    Mutation: strip unconditionally with `rsplit("/", 1)[-1]` — this case
    stays green, which is why it is asserted together with
    `test_a_different_folder_typed_is_refused` below."""
    markdown = _retype(
        _rendered(COMPUTED), "] Rename to ", f"- [x] Rename to `{TYPED}`"
    )
    record = _record(markdown, _doc(COMPUTED))
    assert record["remedy"] == "rename", record
    assert record["proposed_name"] == TYPED, record
    assert record["name_is_owner_supplied"] is True, record

    in_place = _record(
        _retype(
            _rendered(COMPUTED),
            "] Rename to ",
            f"- [x] Rename to `{ASSET_FOLDER}{TYPED}`",
        ),
        _doc(COMPUTED),
    )
    assert record["proposed_name"] == in_place["proposed_name"], (record, in_place)


def test_a_different_folder_typed_is_refused_separator_present():
    """Row 3: the owner types a folder of their OWN. That separator is not one
    Tomo printed, so F3-AC1 still refuses it — the name is never truncated to
    its last segment (ADR-5: rejected, never rewritten).

    Mutation: implement the un-render as `rsplit("/", 1)[-1]` — `Archive/` is
    silently discarded and the attachment is filed in the asset folder under a
    name the owner did not choose. The refusal `reason` is named because a
    missing strip refuses this same case for the same code, while the rows
    above would be the ones to break."""
    typed = f"Archive/{TYPED}"
    markdown = _retype(
        _rendered(COMPUTED), "] Rename to ", f"- [x] Rename to `{typed}`"
    )
    record = _record(markdown, _doc(COMPUTED))
    assert record["remedy"] == "rename", record
    assert record["proposed_name"] == typed, record
    assert record["name_is_owner_supplied"] is True, record
    actions, skipped = _outcome(record)
    assert actions == [], actions
    assert len(skipped) == 1, skipped
    assert skipped[0]["kind"] == "typed_name_refused", skipped[0]
    assert skipped[0]["refusal_reason"] == "separator_present", skipped[0]


def test_a_forbidden_character_with_the_folder_left_is_refused():
    """Row 4: the strip succeeds, and the remainder is still unusable. Proves
    the un-render feeds the guard rather than bypassing it.

    Mutation: skip `check_typed_name` for a name whose prefix matched (an
    "it was ours, so it must be fine" shortcut) — `karte|1938.png` would reach
    `_asset_dest_join` and Obsidian would hold a file it cannot address."""
    markdown = _retype(
        _rendered(COMPUTED),
        "] Rename to ",
        f"- [x] Rename to `{ASSET_FOLDER}{FORBIDDEN}`",
    )
    record = _record(markdown, _doc(COMPUTED))
    assert record["proposed_name"] == FORBIDDEN, record
    assert record["name_is_owner_supplied"] is True, record
    actions, skipped = _outcome(record)
    assert actions == [], actions
    assert len(skipped) == 1, skipped
    assert skipped[0]["kind"] == "typed_name_refused", skipped[0]
    assert skipped[0]["refusal_reason"] == "forbidden_character", skipped[0]


def test_an_emptied_ordinary_conflict_is_a_blank_refusal_not_a_null_rename():
    """Row 5: the owner clears the backticks (or deletes the filename and
    leaves the folder, which strips to the same empty remainder) on an
    ORDINARY conflict — no marker on the line. The record must carry `""`
    with the flag True, which `check_typed_name` verdicts `blank`: NOT
    `rename` with a null `proposed_name`, which would hand Pass 2
    `_asset_dest_join(folder, None)` — the destination-less move Rule 6
    forbids and the 2026-09-23 docstring names.

    `blank` is named rather than "a refusal": a broken prefix strip refuses
    this line too, as `separator_present`.

    Mutation: fall back to the doc's `proposed_name` when the remainder is
    empty — the attachment is then filed under the computed name the owner
    just deleted, in silence.

    MEASURED 2026-10-02 and reported to the coordinator: the guard is not
    what Pass 2 reaches first for a FALSY name. `_build_move_asset_actions`
    degrades `remedy == "rename" and not proposed_name` to keep-in-inbox
    before `name_is_owner_supplied` is consulted, so the surfaced entry is
    `vault_collision_held`, not `typed_name_refused`. Both withhold the move
    and leave the attachment in the inbox; they differ in the sentence the
    owner reads. Pinned here as today's answer — this task owns the parser,
    not that ordering (`render_actions.py`, Phase 3's T3.2)."""
    for cleared in ("", ASSET_FOLDER):
        markdown = _retype(
            _rendered(COMPUTED), "] Rename to ", f"- [x] Rename to `{cleared}`"
        )
        record = _record(markdown, _doc(COMPUTED))
        assert record["remedy"] == "rename", record
        assert record["proposed_name"] == "", record
        assert record["proposed_name"] is not None, record
        assert record["name_is_owner_supplied"] is True, record
        assert check_typed_name(record["proposed_name"]).reason == "blank", record

        actions, skipped = _outcome(record)
        assert actions == [], actions
        assert len(skipped) == 1, skipped
        assert skipped[0]["kind"] == "vault_collision_held", skipped[0]


def test_a_half_edited_line_with_no_closing_backtick_is_refused():
    """A line left mid-edit: the opening backtick is there, the closing one is
    gone. Nothing usable can be read, so the entry refuses `blank` — it does
    not fall back to the doc's name and it does not become a different remedy
    (the `Rename` label prefix still matches, so the line is never
    mis-routed).

    HAND-BUILT on purpose: no renderer produces this. It is what an owner's
    document looks like halfway through typing.

    Mutation: make `RE_RENAME_TARGET` tolerant of a missing closing backtick
    (`` `([^`]*) ``) — the trailing text is then read as a name, which for
    this line means the owner's half-typed stem is filed as if finished."""
    markdown = _retype(
        _rendered(COMPUTED), "] Rename to ", f"- [x] Rename to `{ASSET_FOLDER}karte-"
    )
    record = _record(markdown, _doc(COMPUTED))
    assert record["remedy"] == "rename", record
    assert record["proposed_name"] == "", record
    assert record["name_is_owner_supplied"] is True, record
    assert check_typed_name(record["proposed_name"]).reason == "blank", record


# ---------------------------------------------------------------------------
# 3. The no-free-name line — the three cases of the 2026-10-02 ruling
# ---------------------------------------------------------------------------

def test_the_no_free_name_line_honours_a_typed_name():
    """Case (a), **the case that fails today**: Pass 1 found no free name, so
    the renderer ships ``- [ ] Rename to `` — no free name available`` with
    empty backticks (T4.1). The owner ticks it and types a name. That name
    must reach Pass 2.

    Mutation: restore `rename_impossible = RENAME_IMPOSSIBLE_MARKER in label`
    — `_resolve_attachment_remedy` then overrides the tick to `ignore` and the
    typed name is discarded, which is the defect the ruling closes. The
    narrowed condition is faithful rather than a reversal: the override's
    stated reason is a `rename` with no name, and here there is one."""
    rendered = _rendered(None)
    assert "] Rename to `` — no free name available" in rendered, rendered
    # The marker prose STAYS: an owner types between the backticks, they do not
    # rewrite the line. A fixture that drops the marker makes `rename_impossible`
    # False whatever the condition is, and the mutation named above then survives
    # — measured 2026-10-02, with this fixture written the other way.
    markdown = _retype(
        rendered,
        "] Rename to ",
        f"- [x] Rename to `{TYPED}` — no free name available",
    )
    markdown = _retype(markdown, "] Keep in inbox", "- [ ] Keep in inbox")
    record = _record(markdown, _doc(None))
    assert record["remedy"] == "rename", record
    assert record["proposed_name"] == TYPED, record
    assert record["name_is_owner_supplied"] is True, record
    actions, skipped = _outcome(record)
    assert skipped == [], skipped
    assert [a["destination"] for a in actions] == [f"{ASSET_FOLDER}{TYPED}"], actions


def test_the_no_free_name_line_ticked_but_still_empty_stays_ignore():
    """Case (b), unchanged from today, and the one that fails SILENTLY if the
    override is dropped or evaluated after the guard: the owner ticks the
    no-free-name line and types nothing.

    `ignore` — and `name_is_owner_supplied` False with `proposed_name` None,
    so `check_typed_name` is never consulted and NO `typed_name_refused`
    entry can be produced. The empty backticks are Tomo's own rendering, not
    owner input; a refusal here would have T3.4 render a refusal bullet for a
    name the owner never typed.

    Mutations: drop the override (the entry becomes `rename` with an
    owner-supplied `""`); or settle the typed-name flag before the override
    (the record claims an owner-supplied blank, and the refusal assertion
    below fires)."""
    rendered = _rendered(None)
    markdown = _retype(
        rendered, "] Rename to ", "- [x] Rename to `` — no free name available"
    )
    markdown = _retype(markdown, "] Keep in inbox", "- [ ] Keep in inbox")
    record = _record(markdown, _doc(None))
    assert record == {
        "source": SOURCE,
        "remedy": "ignore",
        "proposed_name": None,
        "name_is_owner_supplied": False,
    }, record
    _actions, skipped = _outcome(record)
    assert [s["kind"] for s in skipped if s["kind"] == "typed_name_refused"] == [], (
        skipped
    )


def test_the_no_free_name_line_left_alone_keeps_the_attachment_in_the_inbox():
    """Case (c), unchanged from today: the owner touches nothing, so the
    pre-ticked `Keep in inbox` settles it.

    Mutation: treat the rendered empty backticks as a typed name — the
    pre-ticked keep-in-inbox would be the only thing left holding this entry,
    and any later change to the tick logic would file the attachment under a
    blank name instead."""
    record = _record(_rendered(None), _doc(None))
    assert record == {
        "source": SOURCE,
        "remedy": "keep_in_inbox",
        "proposed_name": None,
        "name_is_owner_supplied": False,
    }, record


# ---------------------------------------------------------------------------
# 4. The doc is no longer the source of the name
# ---------------------------------------------------------------------------

def test_a_stale_doc_does_not_win_over_the_typed_name():
    """The doc's computed name disagrees with the markdown's — a re-run of
    Pass 1 between render and parse, or a hand-edited doc. The owner's
    keystrokes win (SDD/Implementation Gotchas).

    Mutation: keep the structured-doc read alongside the markdown read and
    prefer the doc when the two differ."""
    markdown = _retype(
        _rendered(COMPUTED),
        "] Rename to ",
        f"- [x] Rename to `{ASSET_FOLDER}{TYPED}`",
    )
    record = _record(markdown, _doc("karte (7).png"))
    assert record["proposed_name"] == TYPED, record


def test_a_source_absent_from_the_doc_still_degrades_rather_than_raising():
    """037's stale-doc contract, unchanged: without the doc record there is no
    `destination` to recover the folder from, so the extracted text cannot be
    told apart from a typed one. The entry degrades to `proposed_name: None`
    (the documented "rename that lost its name" route) instead of being
    refused for a separator Tomo itself printed.

    Mutation: carry the extracted text through when the doc record is missing
    — every entry of a stale doc would then be refused `separator_present`,
    turning a degradation into a report about the owner's typing."""
    record = _record(_rendered(COMPUTED), {"attachment_conflicts": []})
    assert record == {
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": None,
        "name_is_owner_supplied": False,
    }, record


def test_the_asset_folder_is_un_rendered_in_either_slash_form():
    """`_asset_dest_join` normalises a trailing slash, so the folder form the
    doc happens to carry must not change the answer — the 037 fixture uses the
    trailing-slash variant.

    Mutation: build the prefix without re-normalising (`destination.rsplit(
    "/", 1)[0]` used as-is, no trailing slash) — the strip then leaves a
    leading `/` on every remainder and the guard refuses `separator_present`."""
    for folder in (ASSET_FOLDER, ASSET_FOLDER.rstrip("/")):
        rendered = REDUCER.render_attachment_conflicts_block(
            [{**_conflict(COMPUTED), "destination": _asset_dest_join(folder, SOURCE)}],
            folder,
        )
        markdown = _retype(
            rendered, "] Rename to ", f"- [x] Rename to `{ASSET_FOLDER}{TYPED}`"
        )
        doc = {"attachment_conflicts": [
            {**_conflict(COMPUTED), "destination": _asset_dest_join(folder, SOURCE)}
        ]}
        record = _record(markdown, doc)
        assert record["proposed_name"] == TYPED, (folder, record)
        assert record["name_is_owner_supplied"] is True, (folder, record)
