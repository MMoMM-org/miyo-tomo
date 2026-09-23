#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t2_2_render_conflicts.py — spec 037 T2.2.

`render_attachment_conflicts_block(conflicts, asset_folder) -> str` renders
`attachment_conflicts[]` (spec 037 T1.2/T1.5/T2.1) into the `## Attachment
Conflicts` section of the suggestions document — the decision the owner reads
and acts on, per PRD F2. This file pins that renderer, its `rendered_
attachment_conflicts_md` doc field, and `suggestions-render.py`'s verbatim
consumer of that field.

Every bullet below names the mutation it kills, per the T2.2 deviation block
in `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/
plan/phase-2.md`:

  1. `test_one_conflict_renders_section_zero_conflicts_render_nothing` — ONE
     red/green pair, not two bullets `[ref: PRD/F2-AC1, F2-AC4]`. A stub that
     unconditionally returns "" fails the positive half; a stub that
     unconditionally emits the header fails the negative half. The negative
     half ALONE is already true of pre-T2.2 code (nothing renders this
     section yet) and proves nothing without the positive half beside it.
  2. `test_exactly_three_remedies_with_rename_ticked` — mutation: render two
     remedies, or tick none `[ref: PRD/F2-AC2, SDD/ADR-4]`.
  3. `test_one_block_per_conflict_not_per_owner` — mutation: iterate
     `owner_source_items` and emit one decision block per owner, tested
     against an entry with THREE owners, asserting ONE block carrying three
     names `[ref: PRD/F2-AC3]`.
  4. `test_rename_remedy_names_fully_composed_destination` — mutation: render
     `proposed_name` alone (a bare basename, no folder) `[ref: PRD/C1]`.
  5. `test_null_proposed_name_pre_ticks_keep_in_inbox_not_rename` — mutation:
     keep rename ticked when `proposed_name` is null (the owner accepts a
     rename that cannot happen), or drop the rename line entirely (the owner
     cannot see why the usual default is absent) `[ref: SDD/ADR-4, exception]`.
  6. `test_zero_conflicts_run_is_byte_identical_to_pre_t2_2` — the committed
     golden file `tests/fixtures/037-t2-2/pre-change-no-conflicts-doc.json`,
     diffed byte-for-byte. Mutation: gate `rendered_attachment_conflicts_md`
     outside the `if attachment_conflicts:` block — the key would then be
     present (as `""`) even on a conflict-free run, and the equality fails.
  7. `test_full_reduce_wires_rendered_field_when_conflicts_present` — proves
     the reducer's `main()` actually calls the renderer and stores its output
     verbatim, not just that the renderer works in isolation.
  8. `test_render_script_reads_field_verbatim` — `suggestions-render.py`'s
     `render_attachment_conflicts` must read `rendered_attachment_conflicts_md`
     verbatim (the precedent set by `render_tag_handler_updates` /
     `render_daily_updates`), never re-derive or re-format it.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
# Regeneration recipe for `tests/fixtures/037-t2-2/pre-change-no-conflicts-doc.json`
# (the golden file bullet 6 diffs against): check out `04829d2` — the commit
# immediately before this task's changes — in a disposable worktree, copy a
# standalone capture harness (the `_reduce`/`_atomic_result`/`FakeKado` trio
# below, unchanged since T1.2 — they only drive `main()`) into it, and run it
# against the OLD `suggestions-reducer.py`:
#
#   git worktree add /tmp/tomo-04829d2 04829d2
#   cp tests/test_037_t2_2_render_conflicts.py \
#       /tmp/tomo-04829d2/tests/_fixture_capture.py   # (or any driver script
#       #   using this file's _reduce/_atomic_result/FakeKado + ITEM_KEY/
#       #   ASSET_SOURCE, with kado=FakeKado(occupied=set()))
#   cd /tmp/tomo-04829d2 && ./venv/bin/python -c "
#       import sys, json, tempfile
#       sys.path.insert(0, 'tests')
#       from pathlib import Path
#       from _fixture_capture import _reduce, _atomic_result, FakeKado, ITEM_KEY, ASSET_SOURCE
#       with tempfile.TemporaryDirectory() as tmp:
#           doc = _reduce(
#               Path(tmp),
#               {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, 'Karte')},
#               't037-t2-2-fixture',
#               {ITEM_KEY: {'attachments': [ASSET_SOURCE], 'unresolved_embeds': []}},
#               kado=FakeKado(occupied=set()),
#           )
#           print(json.dumps(doc, ensure_ascii=False, indent=2))
#   " > /tmp/tomo-04829d2-fixture.json
#   cp /tmp/tomo-04829d2-fixture.json tests/fixtures/037-t2-2/pre-change-no-conflicts-doc.json  # from repo root
#   git worktree remove /tmp/tomo-04829d2
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
FIXTURE_DIR = TESTS_DIR / "fixtures" / "037-t2-2"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_module("suggestions_reducer_t037_t2_2", "suggestions-reducer.py")
RENDER = _load_module("suggestions_render_t037_t2_2", "suggestions-render.py")

from lib.item_key import to_filename  # noqa: E402

ITEM_KEY = "100 Inbox/Scans/karte.md"
ASSET_SOURCE = "100 Inbox/Scans/karte.png"
NOTES = "Atlas/202 Notes/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER


class FakeKado:
    """Same shape as spec 037 T1.2's own FakeKado."""

    def __init__(self, occupied: set[str] | None = None, raises: bool = False):
        self.occupied = occupied or set()
        self.raises = raises
        self.probed: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500) -> list:
        self.probed.append(path)
        if self.raises:
            raise RuntimeError("kado unreachable")
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _atomic_result(item_key: str, source: str, title: str) -> dict:
    return {
        "schema_version": "1",
        "stem": Path(item_key).stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "issues": [],
        "force_atomic": False,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": Path(item_key).stem,
                "suggested_title": title,
                "template": "Atomic Note.md",
                "location": NOTES,
                "candidate_mocs": [],
                "tags_to_add": [],
                "atomic_note_worthiness": 0.85,
                "classification": None,
                "force_atomic": False,
            },
        ],
    }


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _reduce(
    work: Path,
    results: dict[str, dict],
    run_id: str,
    resolved_attachments: dict[str, dict],
    *,
    kado: FakeKado | None = None,
) -> dict:
    """Drive the real reducer in-process (so `KadoClient` can be swapped for a
    fake) and return the parsed suggestions-doc JSON. `kado=None` means
    `--no-kado`, the degraded run."""
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for item_key, result in results.items():
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", item_key,
                "--stem", result["stem"],
                "--path", item_key,
                "--status", status,
                "--run-id", run_id,
            ])
        (items_dir / to_filename(item_key)).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    resolved_path = work / "resolved-attachments.json"
    resolved_path.write_text(
        json.dumps(resolved_attachments, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    doc_path = work / "suggestions-doc.json"
    argv = [
        "suggestions-reducer.py",
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", run_id, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(resolved_path),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
    ]
    if kado is None:
        argv.append("--no-kado")

    real_client = REDUCER.KadoClient
    real_argv = sys.argv
    try:
        sys.argv = argv
        if kado is not None:
            REDUCER.KadoClient = lambda *a, **k: kado
        assert REDUCER.main() == 0
    finally:
        REDUCER.KadoClient = real_client
        sys.argv = real_argv

    return json.loads(doc_path.read_text(encoding="utf-8"))


def _conflict(**overrides) -> dict:
    base = {
        "source": ASSET_SOURCE,
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": None,
        "owner_source_items": [ITEM_KEY],
        "proposed_name": "karte (2).png",
    }
    base.update(overrides)
    return base


def _checkbox_lines(md: str) -> list[str]:
    return [
        ln.strip() for ln in md.splitlines()
        if ln.strip().startswith(("- [ ]", "- [x]"))
    ]


# ---------------------------------------------------------------------------
# 1. Positive + negative as ONE pair (F2-AC1, F2-AC4)
# ---------------------------------------------------------------------------

def test_one_conflict_renders_section_zero_conflicts_render_nothing():
    md = REDUCER.render_attachment_conflicts_block([_conflict()], ASSET_FOLDER)
    assert md.startswith("## Attachment Conflicts")
    assert ASSET_SOURCE in md, "the incoming source path must be named"
    assert f"{ASSET_FOLDER}karte.png" in md, "the occupied destination must be named"
    assert "[[karte]]" in md, "the owning note must be named as a link"

    empty = REDUCER.render_attachment_conflicts_block([], ASSET_FOLDER)
    assert empty == "", "a run with no conflicts must render no section at all"


# ---------------------------------------------------------------------------
# 2. Exactly three remedies, rename ticked (F2-AC2, ADR-4)
# ---------------------------------------------------------------------------

def test_exactly_three_remedies_with_rename_ticked():
    md = REDUCER.render_attachment_conflicts_block([_conflict()], ASSET_FOLDER)
    checkboxes = _checkbox_lines(md)
    assert len(checkboxes) == 3, checkboxes
    assert checkboxes[0].startswith("- [x] Rename"), checkboxes[0]
    assert checkboxes[1] == "- [ ] Keep in inbox", checkboxes[1]
    assert checkboxes[2].startswith("- [ ] Ignore"), checkboxes[2]


# ---------------------------------------------------------------------------
# 3. One block per CONFLICT, not per owner (F2-AC3)
# ---------------------------------------------------------------------------

def test_one_block_per_conflict_not_per_owner():
    entry = _conflict(owner_source_items=[
        "100 Inbox/A/note-a.md",
        "100 Inbox/B/note-b.md",
        "100 Inbox/C/note-c.md",
    ])
    md = REDUCER.render_attachment_conflicts_block([entry], ASSET_FOLDER)
    assert md.count("## Attachment Conflicts") == 1
    assert md.count("### `") == 1, "three owners must still be ONE decision block"
    assert md.count("**Remedy") == 1
    assert "[[note-a]]" in md
    assert "[[note-b]]" in md
    assert "[[note-c]]" in md


# ---------------------------------------------------------------------------
# 3b. Owner link agrees with the SAME note's own per-item section (fix/037)
# ---------------------------------------------------------------------------

def test_owner_link_matches_same_notes_own_section_link():
    """Mutation: revert the owner loop to the inline `owner[:-3] if
    owner.endswith(".md") else owner` slice, bypassing `source_links`. Two
    items share the stem "karte" (different subfolders), so
    `source_link_targets` qualifies both as `<path>|karte` (spec 034 collision
    rule, `lib/source_link.py`). The inline slice ignores `source_links`
    entirely and renders the owner as its raw, unqualified item_key path —
    disagreeing with the SAME note's own per-item `**Source:**` line, which
    always resolves through `resolve_source_link`. This is the exact drift
    fix/037 exists to kill (reviewer-measured live on a real fixture).
    """
    other_key = "100 Inbox/Other/karte.md"
    done_items = [
        ("karte", ITEM_KEY, {}),
        ("karte", other_key, {}),
    ]
    source_links = REDUCER.source_link_targets(done_items)

    conflict = _conflict(owner_source_items=[ITEM_KEY])
    md = REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER, source_links)
    owner_line = next(ln for ln in md.splitlines() if ln.strip().startswith("- [["))
    owner_link_text = owner_line.strip()[len("- [["):-len("]]")]

    own_section_link_text = REDUCER.resolve_source_link(source_links, ITEM_KEY, "karte")

    assert owner_link_text == own_section_link_text, (owner_link_text, own_section_link_text)
    assert "|karte" in owner_link_text, "the collision must actually qualify the link"


# ---------------------------------------------------------------------------
# 4. The rename target is the FULLY COMPOSED destination (C1)
# ---------------------------------------------------------------------------

def test_rename_remedy_names_fully_composed_destination():
    md = REDUCER.render_attachment_conflicts_block([_conflict()], ASSET_FOLDER)
    expected_target = f"{ASSET_FOLDER}karte (2).png"
    rename_line = next(ln for ln in _checkbox_lines(md) if "Rename" in ln)
    assert expected_target in rename_line, rename_line
    # Guard the exact regression named by the task: a bare basename with no
    # folder must not be what the rename line renders.
    assert rename_line != "- [x] Rename to `karte (2).png`", rename_line


# ---------------------------------------------------------------------------
# 5. `proposed_name: null` pre-ticks *keep in inbox*, not rename (ADR-4 exception)
# ---------------------------------------------------------------------------

def test_null_proposed_name_pre_ticks_keep_in_inbox_not_rename():
    entry = _conflict(proposed_name=None)
    md = REDUCER.render_attachment_conflicts_block([entry], ASSET_FOLDER)
    checkboxes = _checkbox_lines(md)
    rename_line = next(ln for ln in checkboxes if "Rename" in ln)
    keep_line = next(ln for ln in checkboxes if "Keep in inbox" in ln)
    assert rename_line.startswith("- [ ]"), rename_line
    assert "no free name" in rename_line.lower(), rename_line
    assert keep_line.startswith("- [x]"), keep_line
    assert len(checkboxes) == 3, checkboxes


# ---------------------------------------------------------------------------
# 5b. No executor-internal name leaks into the reader-facing block (fix/037)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("same_file", [True, False, None])
def test_no_executor_internals_in_rendered_block(same_file):
    """Mutation: restore either original spec-037 T2.2 string this fix
    replaced — `- [ ] Rename — no free name found within 99 attempts` (names
    the reducer's internal retry budget) or `- [ ] Ignore (the move goes out
    unchanged; Hashi refuses it and reports it)` (names the executor). The
    reader of a suggestions document is doing PKM, not debugging a pipeline —
    tell them the effect, never the mechanism (owner ruling 2026-06-13).

    Scans the WHOLE block for digits, not just the remedy checkboxes: a
    checkbox-only scan has an uncovered reintroduction path — the reviewer
    demonstrated it live by planting "The reducer already tried up to 99
    candidate names before giving up." as prose under the `### <source>`
    heading, which a checkbox-only scan never visits. The `**Destination:**`
    line is the one exclusion — it legitimately carries Johnny-Decimal folder
    numbers (e.g. `290 Assets`); this fixture's source/owner are deliberately
    digit-free (unlike the module-level `ASSET_SOURCE`/`ITEM_KEY`) so the rest
    of the block is a clean surface and the test does not have to special-case
    any other line.

    Parametrized over all three `same_file` values (spec 037 T2.3 coverage
    gap): the `**File comparison:**` bullet has three mutually-exclusive
    sentences, one per `same_file` branch, and only the `null` sentence was
    ever scanned before this fix — `same_file` defaulted to `None` in every
    call and was never overridden. Mutation: introduce an executor name or a
    digit into the `true`- or `false`-branch sentence in
    `render_attachment_conflicts_block` — undetected before this fix, because
    no parametrized case exercised those branches.
    """
    entry = _conflict(
        proposed_name=None,
        source="Inbox/Scans/karte.png",
        owner_source_items=["Inbox/Scans/karte.md"],
        same_file=same_file,
    )
    md = REDUCER.render_attachment_conflicts_block([entry], ASSET_FOLDER)
    assert "hashi" not in md.lower(), md
    for line in md.splitlines():
        if line.strip().startswith("- **Destination:**"):
            continue
        assert not re.search(r"\d", line), line


# ---------------------------------------------------------------------------
# 6. Zero-conflict golden file (byte-for-byte)
# ---------------------------------------------------------------------------

def test_zero_conflicts_run_is_byte_identical_to_pre_t2_2(tmp_path):
    """Anchored against `tests/fixtures/037-t2-2/pre-change-no-conflicts-doc.json`,
    captured by running the reducer at `04829d2` (the commit before this task)
    against this exact fixture input. `rendered_attachment_conflicts_md` must
    be ABSENT, not an empty string, or this equality fails by construction —
    same reasoning as T1.2's `attachment_conflicts` guarantee.
    """
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t2-2-free",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=FakeKado(occupied=set()),
    )
    doc.pop("generated", None)
    doc.pop("run_id", None)
    cost_fields = {
        k: doc.pop(k) for k in ("folder_listing_calls", "distinct_destination_folders")
    }

    expected = json.loads(
        (FIXTURE_DIR / "pre-change-no-conflicts-doc.json").read_text(encoding="utf-8")
    )
    expected.pop("generated", None)
    expected.pop("run_id", None)
    expected_cost_fields = {
        k: expected.pop(k) for k in ("folder_listing_calls", "distinct_destination_folders")
    }

    assert doc == expected, (
        "a run with a free attachment destination must render the SAME "
        "document as the pre-T2.2 reducer — rendered_attachment_conflicts_md "
        "must be ABSENT, or this equality fails by construction"
    )
    assert "attachment_conflicts" not in doc
    assert "rendered_attachment_conflicts_md" not in doc
    assert cost_fields == expected_cost_fields


# ---------------------------------------------------------------------------
# 7. main() actually wires the renderer's output into the doc
# ---------------------------------------------------------------------------

def test_full_reduce_wires_rendered_field_when_conflicts_present(tmp_path):
    doc = _reduce(
        tmp_path,
        {ITEM_KEY: _atomic_result(ITEM_KEY, ASSET_SOURCE, "Karte")},
        "t037-t2-2-occupied",
        {ITEM_KEY: {"attachments": [ASSET_SOURCE], "unresolved_embeds": []}},
        kado=FakeKado(occupied={f"{ASSET_FOLDER}karte.png"}),
    )
    assert "attachment_conflicts" in doc
    assert doc["rendered_attachment_conflicts_md"] == REDUCER.render_attachment_conflicts_block(
        doc["attachment_conflicts"], ASSET_FOLDER
    )


# ---------------------------------------------------------------------------
# 8. suggestions-render.py reads the field verbatim
# ---------------------------------------------------------------------------

def test_render_script_reads_field_verbatim():
    md_block = "## Attachment Conflicts\n\nsome content\n"
    lines = RENDER.render_attachment_conflicts({"rendered_attachment_conflicts_md": md_block})
    assert lines == [md_block.strip(), ""]
    assert RENDER.render_attachment_conflicts({}) == []
    assert RENDER.render_attachment_conflicts({"rendered_attachment_conflicts_md": ""}) == []


# ---------------------------------------------------------------------------
# 9. Schema declares the new doc field (additionalProperties: false at root)
# ---------------------------------------------------------------------------

def test_schema_declares_rendered_attachment_conflicts_md():
    """Mutation: skip the schema edit — the root object's
    `additionalProperties: false` then rejects a real document carrying
    `rendered_attachment_conflicts_md`."""
    _DEPS = "/tmp/claude/py_deps"
    if Path(_DEPS).is_dir() and _DEPS not in sys.path:
        sys.path.insert(0, _DEPS)
    from jsonschema import validate  # noqa: PLC0415

    schema = json.loads(
        (REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json").read_text(
            encoding="utf-8"
        )
    )
    doc = {
        "schema_version": "1",
        "generated": "2026-09-23T00:00:00Z",
        "run_id": "t037-t2-2-schema",
        "profile": "miyo",
        "source_items": 1,
        "sections": [],
        "attachment_conflicts": [_conflict()],
        "rendered_attachment_conflicts_md": REDUCER.render_attachment_conflicts_block(
            [_conflict()], ASSET_FOLDER
        ),
    }
    validate(instance=doc, schema=schema)
