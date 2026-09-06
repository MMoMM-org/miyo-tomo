#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t5_0_pass2_reads_item_key.py — Pass 2 addresses items by item_key.

Spec 034 (recursive inbox discovery), Phase 5 T5.0.

Phase 3 made discovery recursive; Phase 2 threaded `item_key` — the note's
vault-relative path, verbatim (ADR-1) — through Pass 1. The Pass-2 render
stage never adopted it: four files, seven sites, every one of them
reconstructing a path as `<inbox>/<display stem>.md`. That reconstruction
was correct while `depth=1` guaranteed every note sat at the inbox root.
Phase 3 removed the precondition, not the code.

What this file pins:

  * a subfolder note with a GLOBALLY UNIQUE filename survives Pass 2 and
    reaches the instruction set (this is not a collision problem — it is
    every subfolder note carrying a `template`);
  * a note nested two levels deep survives;
  * a root-level note is unchanged;
  * the #116 guard STILL drops an item whose source note is genuinely gone —
    the guard is right, it was only addressing the item wrongly;
  * a drop is never silent: it reaches an artefact with an accurate reason
    and the path that was actually probed;
  * no bare-stem composition survives in the Pass-2 render stage.

CASE 0 (`TestCase0DailyOnlyDeleteReachability`) is the reachability fixture
for `render_actions.py:967`, the one site that emits a `delete_source` with
no guard at all. It is asserted separately and first because it is the only
site in this task that can destroy user data.

BOTH PARSER PATHS. `build_from_wire` mints `item_key`; `main()` — the
markdown path `synthesis-conductor.md` actually invokes — does not, because
the rendered document carries only a bare display stem (that gap is T5.1).
Every behavioural case therefore runs through both, asserting the DEFINED
outcome for each: the wire path resolves the note, and the markdown path
degrades to the documented reconstruction *visibly* rather than silently.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import to_filename  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402


INBOX = "100 Inbox/"

# Three notes, three depths. Every filename is globally unique — nothing here
# collides, so a failure cannot be explained away as a namesake problem.
ROOT_NOTE = "100 Inbox/Kaffee.md"
DEEP_1 = "100 Inbox/Places/Bohnen.md"
DEEP_2 = "100 Inbox/Reise/2026/Sapporo.md"

ITEMS: list[tuple[str, str, str]] = [
    ("Kaffee", ROOT_NOTE, "Kaffee als Ritual"),
    ("Bohnen", DEEP_1, "Bohnen aus Äthiopien"),
    ("Sapporo", DEEP_2, "Sapporo im Februar"),
]

# The note the vault no longer holds — the #116 case. It must still be dropped.
GONE_STEM = "Verschwunden"
GONE_KEY = "100 Inbox/Archiv/Verschwunden.md"

RUN_ID = "t5-0-run"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{Path(cmd[1]).name} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _exact_path_client(present: set[str]) -> MagicMock:
    """A Kado fake that answers on the EXACT path, the way Kado does.

    The pre-existing #116 fake (`test_instruction_render_missing_source.py`)
    matches on the basename, so it answers True for a path the vault does not
    hold. That is precisely the blind spot this task exists to close, so this
    fake compares the full vault-relative path and nothing else.
    """
    client = MagicMock()
    client.note_exists.side_effect = lambda path: path in present
    return client


def _atomic_result(stem: str, item_key: str, title: str) -> dict:
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "issues": [],
        "force_atomic": False,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": stem,
                "suggested_title": title,
                "template": "t_note_tomo",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [
                    {"path": "Atlas/200 Maps/Kaffee (MOC).md",
                     "score": 0.8, "pre_check": True},
                ],
                "tags_to_add": ["topic/kaffee"],
                "atomic_note_worthiness": 0.85,
                "classification": None,
            },
        ],
    }


def _daily_only_result(stem: str, item_key: str) -> dict:
    """An item whose content is fully captured in a daily note — no atomic.

    This is what makes an item `daily-only`: the reducer emits no per-item
    section for it, so it appears in the run ONLY as a daily-note entry
    carrying a bare `source_stem`. That is the input to `render_actions.py:967`.
    """
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "issues": [],
        "force_atomic": False,
        "actions": [
            {
                "kind": "update_daily",
                "date": "2026-06-11",
                "daily_note_path": "Calendar/301 Daily/2026-06-11.md",
                "updates": [{
                    "kind": "log_entry",
                    "time": "09:00",
                    "time_source": "frontmatter",
                    "position": "append",
                    "content": "drank the last of the Bohnen",
                    "confidence": 0.8,
                    "reason": "noted",
                }],
            },
        ],
    }


def _drive(work: Path, results: dict[str, dict], *, accept_all: bool) -> dict:
    """Run the real chain: state -> reducer -> render -> BOTH parser paths.

    `results` maps item_key -> the analyst's recorded result for that item.
    """
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for item_key, result in results.items():
        stem = result["stem"]
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", item_key,
                "--stem", stem,
                "--path", item_key,
                "--status", status,
                "--run-id", RUN_ID,
            ])
        (items_dir / to_filename(item_key)).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    doc_path = work / "suggestions-doc.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", RUN_ID,
        "--profile", "miyo",
        "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
        "--no-kado",
    ])

    md_path = work / "suggestions.md"
    wire_path = work / "suggestions-wire.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path),
        "--output", str(md_path),
        "--json-output", str(wire_path),
    ])

    # (a) markdown path — what synthesis-conductor.md invokes.
    text = md_path.read_text(encoding="utf-8")
    if accept_all:
        text = text.replace("- [ ] Accept", "- [x] Accept")
    approved_md = work / "suggestions-approved.md"
    approved_md.write_text(text, encoding="utf-8")
    parsed_md = json.loads(_run([
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(approved_md),
    ]).stdout)

    # (b) ADR-026 wire path — driven through the CLI exactly as production
    # does. Calling build_from_wire() directly would skip main()'s wire
    # handling, and an omitted step is precisely how a fix gets proven against
    # a path nothing runs.
    wire = json.loads(wire_path.read_text(encoding="utf-8"))
    if accept_all:
        for s in wire.get("suggestions", []) or []:
            s["decision"] = "approve"
        for day in wire.get("daily_updates", []) or []:
            for bucket in ("trackers", "log_entries", "log_links"):
                for entry in day.get(bucket, []) or []:
                    entry["accepted"] = True
    # An edit is what makes the wire authoritative (load_changed_wire compares
    # the recomputed digest against the embedded one), so stale it deliberately.
    wire["emit_digest"] = "edited-by-the-user"
    edited_wire = work / "suggestions-wire-edited.json"
    edited_wire.write_text(json.dumps(wire, ensure_ascii=False), encoding="utf-8")
    parsed_wire = json.loads(_run([
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(approved_md),
        "--suggestions-json", str(edited_wire),
        "--suggestions-doc", str(doc_path),
    ]).stdout)

    return {
        "work": work,
        "doc": json.loads(doc_path.read_text(encoding="utf-8")),
        "markdown": md_path.read_text(encoding="utf-8"),
        "wire": wire,
        "parsed_md": parsed_md,
        "parsed_wire": parsed_wire,
    }


# ===========================================================================
# CASE 0 — is render_actions.py:967 reachable?
# ===========================================================================

@pytest.fixture(scope="module")
def daily_only(tmp_path_factory) -> dict:
    """A subfolder note whose content is fully captured in a daily note."""
    work = tmp_path_factory.mktemp("t5_0_case0")
    return _drive(work, {DEEP_1: _daily_only_result("Bohnen", DEEP_1)}, accept_all=True)


def _delete_sources(parsed: dict) -> list[dict]:
    from lib.render_actions import build_actions  # noqa: PLC0415 — script-dir import

    actions, _ = build_actions(
        manifest=[],
        confirmed=parsed.get("confirmed_items", []),
        daily_updates=parsed.get("daily_updates", []),
        skipped=parsed.get("skipped", parsed.get("skipped_items", [])),
        cfg=CFG,
        kado_client=None,
    )
    return [a for a in actions if a.get("action") == "delete_source"]


class TestCase0DailyOnlyDeleteReachability:
    """Reachability of the unguarded root composition at render_actions.py:967.

    Reported either way: if a `daily_updates` entry cannot in practice carry a
    subfolder note's stem, that is a finding, not a failure.
    """

    def test_the_daily_only_item_produces_a_delete_source(self, daily_only):
        """Establishes reachability before anything is asserted about the path."""
        for label in ("parsed_md", "parsed_wire"):
            dels = _delete_sources(daily_only[label])
            assert len(dels) == 1, (
                f"[{label}] expected exactly one daily-only delete_source, "
                f"got {json.dumps(dels, ensure_ascii=False)}"
            )
            assert dels[0]["reason"] == "Content fully captured in daily note.", (
                f"[{label}] a different delete rule produced this action: {dels[0]}"
            )

    def test_the_delete_names_the_note_not_the_inbox_root(self, daily_only):
        """The site composes `<inbox>/<stem>.md` unconditionally.

        For `100 Inbox/Places/Bohnen.md` that names `100 Inbox/Bohnen.md` — a
        path the run never saw. With a different note of that name at the inbox
        root, the emitted delete names THAT note.
        """
        for label in ("parsed_md", "parsed_wire"):
            dels = _delete_sources(daily_only[label])
            assert dels[0]["source_path"] == DEEP_1, (
                f"[{label}] delete_source names {dels[0]['source_path']!r}, "
                f"not the note it came from ({DEEP_1!r})"
            )


# ===========================================================================
# The three depths — one run, both parser paths
# ===========================================================================

@pytest.fixture(scope="module")
def three_depths(tmp_path_factory) -> dict:
    work = tmp_path_factory.mktemp("t5_0_depths")
    return _drive(
        work,
        {key: _atomic_result(stem, key, title) for stem, key, title in ITEMS},
        accept_all=True,
    )


def _confirmed(parsed: dict) -> list[dict]:
    return parsed.get("confirmed_items", [])


def _by_title(items: list[dict], title: str) -> dict:
    match = [i for i in items if i.get("title") == title]
    assert len(match) == 1, f"expected one item titled {title!r}, got {len(match)}"
    return match[0]


class TestSubfolderNotesSurvivePass2:
    """PRD Feature 1 AC: a subfolder note is triaged end to end.

    The vault holds all three notes. `filter_missing_source_notes` must keep
    all three — it currently probes `100 Inbox/Bohnen.md` and drops two.
    """

    def _filter(self, parsed: dict):
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        client = _exact_path_client({ROOT_NOTE, DEEP_1, DEEP_2})
        return filter_missing_source_notes(_confirmed(parsed), client, INBOX)

    def test_wire_path_keeps_the_one_level_subfolder_note(self, three_depths):
        kept, dropped = self._filter(three_depths["parsed_wire"])
        titles = {i.get("title") for i in kept}
        assert "Bohnen aus Äthiopien" in titles, (
            f"one-level subfolder note dropped; dropped="
            f"{json.dumps(dropped, ensure_ascii=False)}"
        )

    def test_wire_path_keeps_the_two_level_subfolder_note(self, three_depths):
        kept, dropped = self._filter(three_depths["parsed_wire"])
        titles = {i.get("title") for i in kept}
        assert "Sapporo im Februar" in titles, (
            f"two-level subfolder note dropped; dropped="
            f"{json.dumps(dropped, ensure_ascii=False)}"
        )

    def test_wire_path_keeps_the_root_note_unchanged(self, three_depths):
        kept, dropped = self._filter(three_depths["parsed_wire"])
        titles = {i.get("title") for i in kept}
        assert "Kaffee als Ritual" in titles
        assert dropped == [], (
            f"nothing should be dropped — the vault holds all three: {dropped}"
        )

    def test_markdown_path_keeps_every_note_too(self, three_depths):
        """The markdown path recovers each key from the `--suggestions-doc`
        sibling, so it no longer drops subfolder notes either. Its keyless
        fallback is exercised separately, in
        test_034_t5_0b_markdown_path_mints_item_key.py."""
        kept, dropped = self._filter(three_depths["parsed_md"])
        assert dropped == [], f"a note that exists was dropped: {dropped}"
        assert {i.get("title") for i in kept} == {
            "Kaffee als Ritual", "Bohnen aus Äthiopien", "Sapporo im Februar",
        }

    def test_a_keyless_drop_is_visible_and_accurately_worded(self):
        """Whatever causes a drop, it must never be silent: the record names
        the path that was probed and says why — and never calls a note that
        exists one folder down `missing`."""
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        confirmed = [{
            "id": "S01", "title": "Bohnen", "template": "t_note_tomo",
            "source_path": "Bohnen", "parent_mocs": [], "candidate_mocs": [],
            "tags": [],
        }]  # no item_key: a document minted before spec 034
        client = _exact_path_client({DEEP_1})
        _kept, dropped = self._filter_with(
            filter_missing_source_notes, confirmed, client
        )
        assert len(dropped) == 1
        assert dropped[0]["probed_path"] == "100 Inbox/Bohnen.md"
        assert dropped[0]["reason"]
        blob = json.dumps(dropped, ensure_ascii=False).lower()
        assert "missing" not in blob, (
            "'missing' misdiagnoses a note that exists one folder down — "
            f"the wording must say what really happened: {dropped}"
        )

    @staticmethod
    def _filter_with(fn, confirmed, client):
        return fn(confirmed, client, INBOX)


class TestGuard116StillFires:
    """The #116 guard must keep working, not be removed."""

    def test_a_genuinely_deleted_source_is_still_dropped(self):
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        confirmed = [{
            "id": "S01",
            "title": "Ghost",
            "template": "t_note_tomo",
            "source_path": GONE_STEM,
            "item_key": GONE_KEY,
            "parent_mocs": [],
            "candidate_mocs": [],
            "tags": [],
        }]
        client = _exact_path_client(set())  # the vault holds nothing
        kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
        assert kept == [], "an item whose source note is gone must not be rendered"
        assert [d.get("id") for d in dropped] == ["S01"]
        assert dropped[0].get("probed_path") == GONE_KEY, (
            "the guard must report the path it actually probed — the item_key"
        )

    def test_an_unverifiable_source_is_not_rendered_as_a_stub(self):
        """A Kado error used to KEEP the item, which then read an empty body and
        fabricated exactly the stub #116 exists to prevent. An unverifiable
        source must not be rendered, and must be reported as unverifiable —
        not as a deleted note."""
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        confirmed = [{
            "id": "S01",
            "title": "Unknown",
            "template": "t_note_tomo",
            "source_path": "Kaffee",
            "item_key": ROOT_NOTE,
            "parent_mocs": [],
            "candidate_mocs": [],
            "tags": [],
        }]
        client = MagicMock()
        client.note_exists.side_effect = KadoError("transport blew up")
        kept, dropped = filter_missing_source_notes(confirmed, client, INBOX)
        assert kept == [], (
            "keeping an unverifiable item is how the stub gets fabricated"
        )
        assert len(dropped) == 1
        assert "not found" not in (dropped[0].get("reason") or "").lower(), (
            f"a Kado failure is not a deleted note: {dropped[0]}"
        )


class TestDropReachesAnArtefactTheUserReads:
    """A drop reached stderr and nothing else — no artefact, exit code 0.

    Whatever the addressing does, the user has to be able to SEE that an
    approved item produced no note, and the two causes must not be confused:
    "the note is gone" and "Kado did not answer" call for different actions.
    """

    def _md(self, dropped: list[dict]) -> str:
        from lib.render_md import render_instructions_md  # noqa: PLC0415

        return render_instructions_md([], {
            "upstream_type": "suggestions", "upstream_path": "x.md",
            "upstream_body_path": None, "run_id": RUN_ID,
            "generated": "2026-09-06T00:00:00Z", "profile": "miyo",
            "tomo_version": "0.1.0", "dropped_sources": dropped,
        }, CFG)

    def test_a_keyless_drop_says_only_the_inbox_root_was_tried(self):
        md = self._md([{
            "id": "S01", "title": "Bohnen", "source_path": "Bohnen",
            "item_key": "", "probed_path": "100 Inbox/Bohnen.md",
            "kind": "not-found", "reason": "no note at this path",
        }])
        assert "100 Inbox/Bohnen.md" in md
        assert "subfolder" in md, f"the real cause is not stated: {md}"

    def test_an_unverifiable_drop_is_not_reported_as_a_deleted_note(self):
        md = self._md([{
            "id": "S01", "title": "Kaffee", "source_path": "Kaffee",
            "item_key": ROOT_NOTE, "probed_path": ROOT_NOTE,
            "kind": "unverifiable", "reason": "Kado could not confirm this path",
        }])
        assert "deleted" not in md, (
            f"a Kado failure must not be reported as a deleted note: {md}"
        )
        assert "Kado" in md

    def test_an_unrecognised_kind_inherits_no_remedy(self):
        md = self._md([{
            "id": "S01", "title": "X", "source_path": "X", "item_key": "",
            "probed_path": "100 Inbox/X.md", "kind": "something-new",
            "reason": "?",
        }])
        assert "no remedy defined" in md, (
            "a new drop kind must not silently inherit another kind's diagnosis"
        )


class TestActionsAddressTheRealNote:
    """The five sites in render_actions.py that compose an inbox path."""

    def _actions(self, parsed: dict) -> list[dict]:
        from lib.render_actions import build_actions  # noqa: PLC0415

        confirmed = _confirmed(parsed)
        manifest = [
            {
                "id": c["id"],
                "action": "create_note",
                "title": c["title"],
                "source_path": c.get("source_path"),
                "item_key": c.get("item_key"),
                "audio_peer": c.get("audio_peer"),
                "template": c.get("template"),
                "rendered_file": f"2026-06-11_1200_{c['id']}.md",
                "destination": c.get("destination") or "Atlas/202 Notes/",
                "parent_moc": c.get("parent_moc"),
                "parent_mocs": c.get("parent_mocs") or [],
                "attachments": [],
                "tags": c.get("tags") or [],
            }
            for c in confirmed
        ]
        actions, _ = build_actions(
            manifest, confirmed, parsed.get("daily_updates", []),
            parsed.get("skipped", []), CFG, kado_client=None,
        )
        return actions

    def test_move_note_origin_is_the_real_subfolder_path(self, three_depths):
        actions = self._actions(three_depths["parsed_wire"])
        origins = {
            a.get("source_inbox_item") for a in actions if a.get("action") == "move_note"
        }
        assert DEEP_1 in origins, f"move_note origin was reconstructed: {origins}"
        assert DEEP_2 in origins, f"move_note origin was reconstructed: {origins}"
        assert ROOT_NOTE in origins

    def test_delete_source_for_a_move_origin_names_the_real_path(self, three_depths):
        actions = self._actions(three_depths["parsed_wire"])
        deleted = {
            a.get("source_path") for a in actions if a.get("action") == "delete_source"
        }
        assert {ROOT_NOTE, DEEP_1, DEEP_2} <= deleted, (
            f"a delete_source names a path the run never saw: {sorted(deleted)}"
        )

    def test_skip_action_names_the_real_path(self):
        from lib.render_actions import build_actions  # noqa: PLC0415

        skipped = [{"id": "S01", "source_path": "Bohnen",
                    "item_key": DEEP_1, "disposition": "skip"}]
        actions, _ = build_actions([], [], [], skipped, CFG, kado_client=None)
        skips = [a for a in actions if a.get("action") == "skip"]
        assert [s["source_path"] for s in skips] == [DEEP_1]

    def test_user_delete_on_a_skipped_item_names_the_real_path(self):
        from lib.render_actions import build_actions  # noqa: PLC0415

        skipped = [{"id": "S01", "source_path": "Bohnen",
                    "item_key": DEEP_1, "disposition": "delete_source"}]
        actions, _ = build_actions([], [], [], skipped, CFG, kado_client=None)
        dels = [a for a in actions if a.get("action") == "delete_source"]
        assert [d["source_path"] for d in dels] == [DEEP_1], (
            "a user-requested delete on a subfolder note named the inbox root"
        )

    def test_audio_peer_resolves_beside_its_note_not_at_the_inbox_root(self):
        """Triage pairs audio to a note by containing folder plus stem
        (`inbox-triage.check_audio`), so a transcript's peer sits in the
        transcript's own folder — never at the inbox root."""
        from lib.render_actions import build_actions  # noqa: PLC0415

        manifest = [{
            "id": "S01",
            "action": "create_note",
            "title": "Bohnen aus Äthiopien",
            "source_path": "Bohnen",
            "item_key": DEEP_1,
            "audio_peer": "Bohnen.m4a",
            "template": "t_note_tomo",
            "rendered_file": "2026-06-11_1200_bohnen.md",
            "destination": "Atlas/202 Notes/",
            "parent_mocs": [],
            "attachments": [],
            "tags": [],
        }]
        actions, _ = build_actions(manifest, [], [], [], CFG, kado_client=None)
        deleted = {
            a.get("source_path") for a in actions if a.get("action") == "delete_source"
        }
        assert "100 Inbox/Places/Bohnen.m4a" in deleted, (
            f"the audio peer was addressed at the inbox root: {sorted(deleted)}"
        )


# ===========================================================================
# Static: no bare-stem composition survives in the Pass-2 render stage
# ===========================================================================

PASS2_FILES = {
    "instruction-render.py": SCRIPTS_DIR / "instruction-render.py",
    "render_resolve.py": LIB_DIR / "render_resolve.py",
    "render_io.py": LIB_DIR / "render_io.py",
    "render_actions.py": LIB_DIR / "render_actions.py",
}

# `f"{inbox}{...}"` and `f"{inbox_path.rstrip('/')}/{...}"` — the two literal
# spellings of the reconstruction, in every Pass-2 file that carries them.
INBOX_COMPOSITION = re.compile(
    r"""f"\{inbox\}\{|f"\{inbox_path\.rstrip\('/'\)\}/\{"""
)

# The "is this a bare stem" guard, named per variable so this asserts the
# specific sites rather than the shape of any `/` test anywhere.
BARE_STEM_GUARD = re.compile(
    r'"/"\s+(?:not\s+)?in\s+(full_path|origin_basename|audio_peer|sp)\b'
)


class TestNoBareStemCompositionSurvives:
    def test_no_inbox_root_composition_in_the_pass2_stage(self):
        offenders = {
            name: [
                f"{n}: {line.strip()}"
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                if INBOX_COMPOSITION.search(line)
            ]
            for name, path in PASS2_FILES.items()
        }
        offenders = {k: v for k, v in offenders.items() if v}
        assert not offenders, (
            "an inbox-root path is still composed from a display stem:\n"
            + json.dumps(offenders, indent=2, ensure_ascii=False)
        )

    def test_no_bare_stem_guard_on_a_source_path_in_the_pass2_stage(self):
        offenders = {
            name: [
                f"{n}: {line.strip()}"
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                if BARE_STEM_GUARD.search(line)
            ]
            for name, path in PASS2_FILES.items()
        }
        offenders = {k: v for k, v in offenders.items() if v}
        assert not offenders, (
            "a source path is still branched on 'is this a bare stem':\n"
            + json.dumps(offenders, indent=2, ensure_ascii=False)
        )

    @pytest.mark.parametrize(
        "name", ["instruction-render.py", "render_resolve.py", "render_actions.py"]
    )
    def test_the_item_addressing_files_read_the_key(self, name):
        src = PASS2_FILES[name].read_text(encoding="utf-8")
        assert "item_key" in src, (
            f"{name} addresses inbox items but never reads item_key"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
