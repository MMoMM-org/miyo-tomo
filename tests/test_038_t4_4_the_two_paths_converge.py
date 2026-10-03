#!/usr/bin/env python3
"""test_038_t4_4_the_two_paths_converge.py — spec 038 T4.4, phase validation.

The load-bearing test of Phase 4 and Phase 2 together: the SAME attachment
decision, driven once through the **markdown** path and once through the
**wire** path, emits an identical `move_asset` destination. That is F1's and
F2's shared criterion stated as one assertion `[ref: PRD/F1, PRD/F2]`.

Both runs go through `suggestion-parser.py`'s `main` as a subprocess — the only
way the wire path can be reached at all — and each run's own
`attachment_conflict_remedies` are then driven through
`_build_move_asset_actions`, the Pass 2 builder that owns the destination and
the typed-name guard. So a divergence is asserted where the owner would see it,
not on an intermediate record.

Why this test can pass while proving nothing, and what stops it
---------------------------------------------------------------
ADR-026: `load_changed_wire` returns the wire **only** when it was edited (its
embedded `emit_digest` no longer matches a recomputation). An unedited wire
falls straight through to the markdown parse. So a convergence test that
publishes a wire and forgets to stale its digest **runs the markdown path twice
and passes** — and nothing about it looks wrong.

`load_changed_wire` returns `None` on three distinct routes, each of which
produces that same tautology:

  - the digest matches (an unedited wire);
  - the JSON is unparseable (`warning: suggestions-json ignored (…)`);
  - `schema_version` is not the schema's current version
    (`warning: suggestions-json schema_version X != Y — ignored, using
    markdown`). The accepted version is read from the schema itself, never a
    literal, so a hand-built wire that hard-codes one drifts the moment the
    schema moves — and spec 038 moved it. The wires here are therefore built
    through `build_wire_payload`, so the version comes from the same source
    the gate checks.

Three assertions close all three routes, and `_run_both` makes every case
carry them:

  1. the JSON-only announcement is a line of the wire run's stderr —
     `suggestions-json: edited wire is authoritative (JSON-only path)`;
  2. it is NOT a line of the markdown run's stderr, and neither run warns
     about the wire at all;
  3. `compute_payload_digest(wire) != wire["emit_digest"]` before the run —
     the staleness was genuine, not a line that appeared for another reason.

The digest is staled by ticking the candidate MOC in the wire
(`suggestions[0].candidate_mocs[0].selected`), the mutation
`test_changed_wire_overrides_moc_selection` already uses. It is deliberately
**orthogonal to the decision under test**: any mutation stales the digest, but
mutating the attachment remedy itself would mean the two paths no longer carry
the same decision, so an identical destination would prove nothing and a
differing one would be correct behaviour misread as a defect. Its visible
consequence is that the wire run's item carries `parent_mocs` and the markdown
run's does not — the wire being authoritative, exactly as designed — which is
why `_assert_same_subject` compares the fields `move_asset` is built from
(`attachments`, `item_key`) and not the whole manifest.

Provenance differs by design, so convergence is about guard-passing names
-------------------------------------------------------------------------
The wire path sets `name_is_owner_supplied: True` unconditionally (T2.3 — it
cannot know whether the consumer edited the field, so "could have been edited"
is the only honest claim); the markdown path sets it by comparison (T4.2 —
`remainder != doc_name`). So for an untouched **computed** name the wire runs
`check_typed_name` and the markdown does not. For any name that passes the
guard the destinations are identical, which is what the first two cases assert.

For a computed name the vault forbids but macOS permits, the wire refuses and
the markdown files it. That asymmetry is recorded (T3.2, and the deviations row
of 2026-10-02) and is pinned here as its own case rather than fixed — and it is
pinned as **whole records on both sides**, because "the wire refuses and the
markdown permits" would pass on any implementation that happened to diverge,
including a broken one.

Mutations, each of which turns a case here red
----------------------------------------------
Each was applied and run (2026-10-03); the assertion named is the one that
actually fires, which for several is upstream of the destination comparison.

  - Make `load_changed_wire` treat a stale digest as unedited (`if stored:
    return None`). **All three** cases fail on `_run_both`'s JSON-only stderr
    assertion, and the observed failure is `assert '…(JSON-only path)' in []`
    — the wire run printed nothing at all, because it was the markdown run
    again. That is the tautology this file exists to refuse.
  - Set `name_is_owner_supplied: False` in `build_from_wire`'s
    `attachment_conflict_remedies` (T2.3 reverted): all three cases fail on
    the wire's whole-remedy assertion. With that assertion removed,
    `test_an_unusable_computed_name_*` would still fail on `wire.actions == []`
    — the wire would file the name the vault forbids.
  - Set the markdown path's flag `True` unconditionally in
    `_join_attachment_conflict_remedies` (T4.2 reverted): the computed and
    asymmetry cases fail on the markdown's whole-remedy assertion — the typed
    case passes, correctly, since provenance already agrees there. With the
    record assertion removed, the asymmetry case would still fail on
    `markdown.actions` — the markdown would refuse a name Pass 1 computed.
  - Restore the pre-T4.2 `proposed_name = doc_name` doc lookup as the markdown
    path's answer: only `test_a_typed_accepted_name_converges` fails, on the
    markdown remedy — it carries `karte (2).png` where the wire carries
    `karte-dresden-1938.png`, so the two paths would file different names.
  - Drop the un-render prefix strip in `_join_attachment_conflict_remedies`:
    all three cases fail on the markdown remedy, whose `proposed_name` now
    carries the rendered folder. With that assertion removed the typed case
    would still fail on the destination, since `check_typed_name` refuses the
    path `separator_present` and no move is emitted.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker. The
markdown and the wire are both produced by the real renderers, never hand-built
— the one owner edit is applied by replacing a single rendered line.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_move_asset_actions  # noqa: E402
from lib.render_md import compute_payload_digest  # noqa: E402


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


RENDER = _load("suggestions_render_t4_4", "suggestions-render.py")
REDUCER = _load("suggestions_reducer_t4_4", "suggestions-reducer.py")

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
OWNER = "100 Inbox/Dresden.md"
TOPIC_MOC = "Atlas/200 Maps/Topic MOC"

# A guard-passing pair: the computed name Pass 1 would propose beside an
# occupied destination, and a name an owner might type in its place.
SOURCE = "100 Inbox/Scans/karte.png"
COMPUTED = "karte (2).png"
TYPED = "karte-dresden-1938.png"

# The asymmetry fixture: '*' is legal in a macOS filename and forbidden by the
# vault (`lib.obsidian_filename.FORBIDDEN_CHARS`), so Pass 1's
# `_propose_asset_name` — which sanitises nothing — can legally compute it from
# a source that already carries the character.
UNUSABLE_SOURCE = "100 Inbox/Scans/foo*bar.png"
UNUSABLE_COMPUTED = "foo*bar (2).png"

JSON_ONLY_LINE = "suggestions-json: edited wire is authoritative (JSON-only path)"

MD_NAME = "2026-07-03_1000_suggestions.md"
WIRE_NAME = "2026-07-03_1000_suggestions.json"


# ── Fixture: one approved atomic note that embeds one conflicting attachment ──

def _conflict(source: str, proposed_name: str | None) -> dict:
    """One `attachment_conflicts[]` record, the shape T1.5 writes."""
    return {
        "source": source,
        "destination": f"{ASSET_FOLDER}{source.rsplit('/', 1)[-1]}",
        "same_file": False,
        "owner_source_items": [OWNER],
        "proposed_name": proposed_name,
    }


def _atomic_action(source: str) -> dict:
    """One `create_atomic_note` action, rendered by the real reducer.

    The action carries its fields twice on purpose, because the two consumers
    read different halves: `render_create_atomic_note` reads the action's own
    keys, `_wire_note` reads `action["item"]`. That is how the reducer builds
    a real doc, so a fixture that set only one half would exercise one path.
    """
    action = {
        "kind": "create_atomic_note",
        "suggestion_id": "S01",
        "suggested_title": "Dresden",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "attachments": [source],
        "atomic_note_worthiness": 0.9,
        "candidate_mocs": [
            {
                "path": f"{TOPIC_MOC}.md",
                "pre_check": False,
                "score": 0.2,
                "anchor": {
                    "type": "heading",
                    "value": "Notes",
                    "placement": "inside",
                },
            }
        ],
        "item": {
            "title": "Dresden",
            "template": "t_note_tomo.md",
            "location": "Atlas/202 Notes/",
            "tags": [],
            "audio_peer": None,
            "attachments": [source],
            "worthiness": 0.9,
            "suppressed": False,
            "force_atomic": False,
        },
    }
    action["rendered_md"] = REDUCER.render_create_atomic_note(
        action, "Dresden", " MOC"
    )
    return action


def _doc(source: str, proposed_name: str | None) -> dict:
    conflict = _conflict(source, proposed_name)
    return {
        "schema_version": "1",
        "generated": "2026-07-03T10:00:00Z",
        "run_id": "2026-07-03-1000-t44",
        "profile": "miyo",
        "source_items": 1,
        "conventions": {
            "parent_marker": "up::",
            "peer_marker": "related::",
            "moc_suffix": " MOC",
        },
        "sections": [
            {
                "id": "S01",
                "stem": "Dresden",
                # ADR-1: the markdown path recovers identity from the doc by
                # section id, so without this both paths' `item_key` would
                # disagree for a reason that has nothing to do with this test.
                "item_key": OWNER,
                "actions": [_atomic_action(source)],
            }
        ],
        "proposed_mocs": [],
        "needs_attention": [],
        "attachment_conflicts": [conflict],
        "rendered_attachment_conflicts_md": (
            REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER)
        ),
    }


def _full_md(doc: dict) -> str:
    """The suggestions markdown Pass 1 ships, from the renderers themselves."""
    return "\n".join(
        [
            "---",
            "type: tomo-suggestions",
            "generated: 2026-07-03T10:00:00Z",
            'tomo_version: "0.1.0"',
            "profile: miyo",
            "source_items: 1",
            "run_id: 2026-07-03-1000-t44",
            "---",
            "",
            "# Inbox Suggestions — 2026-07-03",
            "",
            "- [x] Approved",
            "",
            "## Summary",
            "",
            "- Items processed: 1",
            "",
            "\n".join(RENDER.render_suggestions(doc)),
            "",
            "\n".join(RENDER.render_attachment_conflicts(doc)),
        ]
    )


def _retype(markdown: str, contains: str, new_line: str) -> str:
    """Replace the one rendered line containing `contains` — an owner editing
    a single remedy line and leaving the rest of the document as rendered."""
    lines = markdown.splitlines()
    hits = [i for i, line in enumerate(lines) if contains in line]
    assert len(hits) == 1, (contains, lines)
    lines[hits[0]] = new_line
    return "\n".join(lines) + "\n"


# ── Driving one decision down each path ──────────────────────────────────────

def _parse(tmp_path: Path, doc: dict, markdown: str, wire: dict | None):
    """Run the parser's own `main` over this markdown, with or without a wire.

    The structured doc is written as a sibling of the markdown because that is
    where `_default_doc_path` looks for it, and `cwd=tmp_path` keeps the run
    away from any repo-root `tomo-tmp/` cache.
    """
    md_path = tmp_path / MD_NAME
    md_path.write_text(markdown, encoding="utf-8")
    (tmp_path / "suggestions-doc.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8"
    )
    cmd = [sys.executable, str(PARSER), "--file", str(md_path)]
    if wire is not None:
        wire_path = tmp_path / WIRE_NAME
        wire_path.write_text(json.dumps(wire, ensure_ascii=False), encoding="utf-8")
        cmd += ["--suggestions-json", str(wire_path)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, cwd=str(tmp_path)
    )
    assert result.returncode == 0, f"exit {result.returncode}\n{result.stderr}"
    return json.loads(result.stdout), result.stderr.splitlines()


def _move_assets(parsed: dict) -> tuple[list[dict], list[dict], dict]:
    """Drive one parser output through the Pass 2 move builder.

    The manifest is built from **this run's own** confirmed item rather than
    from a shared literal, so a path that dropped the attachment or the
    item identity fails here instead of being papered over by the fixture.
    """
    items = [c for c in parsed["confirmed_items"] if c.get("action") != "create_moc"]
    assert len(items) == 1, items
    item = items[0]
    entry = {
        "id": item["id"],
        "action": None,
        "title": item["title"],
        "item_key": item.get("item_key"),
        "source_path": item.get("source_path"),
        "rendered_file": "2026-07-03_1000_dresden.md",
        "destination": item.get("destination"),
        "parent_moc": item.get("parent_moc"),
        "parent_mocs": item.get("parent_mocs") or [],
        "tags": item.get("tags") or [],
        "attachments": list(item.get("attachments") or []),
    }
    actions, skipped = _build_move_asset_actions(
        [entry],
        INBOX,
        ASSET_FOLDER,
        [0],
        attachment_conflict_remedies=parsed["attachment_conflict_remedies"],
    )
    return actions, skipped, entry


class _Outcome:
    """One path's whole outcome for one decision."""

    def __init__(self, parsed: dict, stderr_lines: list[str]):
        self.parsed = parsed
        self.stderr_lines = stderr_lines
        self.remedies = parsed["attachment_conflict_remedies"]
        self.actions, self.skipped, self.manifest_entry = _move_assets(parsed)

    @property
    def remedy(self) -> dict:
        assert len(self.remedies) == 1, self.remedies
        return self.remedies[0]

    @property
    def destinations(self) -> list[str]:
        return [a["destination"] for a in self.actions if a["action"] == "move_asset"]


def _run_both(
    tmp_path: Path,
    doc: dict,
    markdown: str,
    wire_edit=None,
) -> tuple[_Outcome, _Outcome]:
    """Drive `doc`/`markdown` down the markdown path and the wire path.

    `wire_edit` applies the consumer's edit to the wire payload. The candidate
    MOC is ticked on top of it in every case, which is what stales the digest;
    see this module's docstring for why the staling mutation must not be the
    decision under test.

    Every anti-tautology assertion lives here, so no case can omit one.
    """
    md_parsed, md_stderr = _parse(tmp_path, doc, markdown, None)

    wire = RENDER.build_wire_payload(doc)
    if wire_edit is not None:
        wire_edit(wire)
    wire["suggestions"][0]["candidate_mocs"][0]["selected"] = True

    # (3) The staleness is genuine — the recomputation no longer matches the
    # digest the producer embedded. Asserted before the run, so a wire that
    # was never actually edited cannot reach the parser unnoticed.
    assert compute_payload_digest(wire) != wire["emit_digest"], (
        "the wire's emit_digest still matches its payload — this wire would "
        "fall through to the markdown path and the test would compare the "
        "markdown with itself"
    )

    wire_parsed, wire_stderr = _parse(tmp_path, doc, markdown, wire)

    # (1) The JSON-only branch was taken. Whole lines, not substrings.
    assert JSON_ONLY_LINE in wire_stderr, wire_stderr
    # (2) …and the markdown run did not take it, and neither run fell back.
    assert JSON_ONLY_LINE not in md_stderr, md_stderr
    for name, lines in (("markdown", md_stderr), ("wire", wire_stderr)):
        ignored = [ln for ln in lines if ln.startswith("warning: suggestions-json")]
        assert ignored == [], (name, ignored)

    return _Outcome(md_parsed, md_stderr), _Outcome(wire_parsed, wire_stderr)


def _assert_same_subject(markdown: _Outcome, wire: _Outcome) -> None:
    """The two paths are acting on the same attachment and the same note.

    Only the fields `_build_move_asset_actions` reads: a full manifest equality
    would fail on `parent_mocs`, which diverges because ticking the candidate
    MOC is what stales the digest — the wire being authoritative, by design.
    """
    assert markdown.manifest_entry["attachments"] == [
        *wire.manifest_entry["attachments"]
    ], (markdown.manifest_entry, wire.manifest_entry)
    assert (
        markdown.manifest_entry["item_key"] == wire.manifest_entry["item_key"] == OWNER
    ), (markdown.manifest_entry, wire.manifest_entry)


# ── Case 1: a computed name converges ────────────────────────────────────────

def test_a_computed_name_converges_on_one_destination(tmp_path):
    """The owner touches nothing. Pass 1's computed name reaches the same
    `move_asset` destination down both paths.

    This is the case where the provenance asymmetry is live and harmless: the
    wire calls the name owner-supplied and runs `check_typed_name` over it, the
    markdown calls it computed and does not — and `karte (2).png` passes the
    guard, so the two destinations are the same string.

    Both halves of that are asserted. Without the provenance assertion the
    convergence could hold because both paths took the SAME branch, which is
    the state this file's docstring describes as passing while proving nothing.
    """
    doc = _doc(SOURCE, COMPUTED)
    markdown, wire = _run_both(tmp_path, doc, _full_md(doc))
    _assert_same_subject(markdown, wire)

    # The provenance differs — by design (T2.3 vs T4.2).
    assert markdown.remedy == {
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": COMPUTED,
        "name_is_owner_supplied": False,
    }, markdown.remedy
    assert wire.remedy == {
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": COMPUTED,
        "name_is_owner_supplied": True,
    }, wire.remedy

    # The destination does not.
    assert markdown.destinations == [f"{ASSET_FOLDER}{COMPUTED}"], markdown.actions
    assert wire.destinations == markdown.destinations, (
        markdown.actions,
        wire.actions,
    )
    assert markdown.skipped == [], markdown.skipped
    assert wire.skipped == [], wire.skipped


# ── Case 2: a typed, accepted name converges ─────────────────────────────────

def test_a_typed_accepted_name_converges_on_one_destination(tmp_path):
    """The owner types a new name. Both paths file the attachment under it.

    The same decision is expressed the way each surface expresses it: the
    markdown's rename line is retyped (keeping the folder the document showed,
    which is the natural edit), and the wire's `attachment_conflicts[0]
    .proposed_name` is replaced, which is what a consumer editor writes. The
    markdown's folder is un-rendered back off before the guard sees the name
    (T4.2), which is why both arrive at the bare `karte-dresden-1938.png`.

    Here the provenance agrees — both paths call the name owner-supplied, so
    both run `check_typed_name`, and it accepts.
    """
    doc = _doc(SOURCE, COMPUTED)
    markdown_text = _retype(
        _full_md(doc),
        "] Rename to ",
        f"- [x] Rename to `{ASSET_FOLDER}{TYPED}`",
    )

    def _consumer_types_a_name(wire: dict) -> None:
        wire["attachment_conflicts"][0]["proposed_name"] = TYPED

    markdown, wire = _run_both(
        tmp_path, doc, markdown_text, wire_edit=_consumer_types_a_name
    )
    _assert_same_subject(markdown, wire)

    expected_remedy = {
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": TYPED,
        "name_is_owner_supplied": True,
    }
    assert markdown.remedy == expected_remedy, markdown.remedy
    assert wire.remedy == expected_remedy, wire.remedy

    assert markdown.destinations == [f"{ASSET_FOLDER}{TYPED}"], markdown.actions
    assert wire.destinations == markdown.destinations, (
        markdown.actions,
        wire.actions,
    )
    assert markdown.skipped == [], markdown.skipped
    assert wire.skipped == [], wire.skipped


# ── Case 3: the one deliberate divergence, pinned ────────────────────────────

def test_an_unusable_computed_name_is_refused_on_the_wire_and_filed_in_the_markdown(
    tmp_path,
):
    """A computed name the vault forbids diverges, and that is not a defect.

    `foo*bar (2).png` is a legal macOS filename and an illegal Obsidian one.
    Pass 1 computed it — `_propose_asset_name` sanitises nothing — and nobody
    typed it. The wire cannot know that (T2.3), calls it owner-supplied, and
    `check_typed_name` refuses it `forbidden_character`; the markdown knows the
    name is unchanged from the doc's, calls it computed, and files it. ADR-5
    confines rejection to names an owner could have typed, so refusing it on
    the markdown path would refuse a name Pass 1 itself generated — which F3's
    ninth acceptance criterion forbids.

    Recorded in T3.2 and in the deviations row of 2026-10-02, and pinned here
    as **both whole records** rather than as a direction. "The wire refuses and
    the markdown permits" would also pass on an implementation that diverged
    for the wrong reason, or on a broken one; naming the whole outcome on each
    side means the case fails if either changes.
    """
    doc = _doc(UNUSABLE_SOURCE, UNUSABLE_COMPUTED)
    markdown, wire = _run_both(tmp_path, doc, _full_md(doc))
    _assert_same_subject(markdown, wire)

    # Both paths agree the name is unchanged from Pass 1's; they disagree only
    # about whether it could have been typed.
    assert markdown.remedy == {
        "source": UNUSABLE_SOURCE,
        "remedy": "rename",
        "proposed_name": UNUSABLE_COMPUTED,
        "name_is_owner_supplied": False,
    }, markdown.remedy
    assert wire.remedy == {
        "source": UNUSABLE_SOURCE,
        "remedy": "rename",
        "proposed_name": UNUSABLE_COMPUTED,
        "name_is_owner_supplied": True,
    }, wire.remedy

    # The markdown path's whole outcome: it files the name.
    assert markdown.actions == [
        {
            "id": "I01",
            "action": "move_asset",
            "source": UNUSABLE_SOURCE,
            "destination": f"{ASSET_FOLDER}{UNUSABLE_COMPUTED}",
        }
    ], markdown.actions
    assert markdown.skipped == [], markdown.skipped

    # The wire path's whole outcome: no move, and one refusal record.
    # `destination` is None on purpose — the natural destination belongs to the
    # occupied name this rename was meant to avoid, not to the refused one.
    assert wire.actions == [], wire.actions
    assert wire.skipped == [
        {
            "source": UNUSABLE_SOURCE,
            "destination": None,
            "reason": (
                f"typed name refused: `{UNUSABLE_COMPUTED}` contains a "
                f"character Obsidian does not allow in a filename"
            ),
            "refusal_reason": "forbidden_character",
            "kind": "typed_name_refused",
            "owner_source_items": [OWNER],
        }
    ], wire.skipped
