#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t5_1_source_link_disambiguation.py — spec 034 T5.1.

Recursive discovery lets two inbox notes in different subfolders share a
filename. Both then render their source link as `[[Dresden]]`, so in the
document the user approves under CON-2 the two suggestions are
indistinguishable — and the vault resolves a bare wikilink by name, so
clicking either one opens whichever it picks.

This file pins the display half of the fix (ADR-2: `stem` is display text,
`item_key` is identity — nothing here may move a path into an identity
field):

  1. A filename unique in the run renders as the plain filename.
  2. Two items sharing a filename each render a link that resolves to
     exactly one note, and to a DIFFERENT one. Resolution is checked with
     `narrow_candidates` — the single narrowing rule Tomo itself uses to
     turn a wikilink reference into a path — not with a string shape.
  3. The suggested NAME of a subfolder note is still `Dresden`. Only the
     source LINK is qualified; a path-derived name would be a regression.
  4. A run with no collision renders a byte-identical document. That case
     is owned by `tests/test_034_t3_4_phase3_gate.py`, which asserts the
     whole document string against a golden rendered by the pipeline at
     `ee44cb3` (the commit before Phase 1). It is NOT re-implemented here:
     a fresh baseline taken after this change would be circular. The one
     assertion this file adds for it is the local half — a run whose
     filenames are unique carries no path-qualified link at all.

CON-7: fixtures only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.attachment_index import narrow_candidates  # noqa: E402
from lib.item_key import to_filename  # noqa: E402

INBOX = "100 Inbox/"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
DRESDEN_ROOT = "100 Inbox/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

# The inbox listing every reference is resolved against — basename -> paths.
# Mirrors `build_inbox_index`'s shape so `narrow_candidates` behaves exactly
# as it does at the Force-Atomic resolution site in inbox-triage.py.
FULL_INDEX = {
    "Dresden.md": [DRESDEN_PLACES, DRESDEN_REISE],
    "Root Note.md": [ROOT_NOTE],
}
FLAT_INDEX = {
    "Dresden.md": [DRESDEN_ROOT],
    "Root Note.md": [ROOT_NOTE],
}

RE_SOURCE_FIELD = re.compile(r"^\*\*Source:\*\* \[\[([^\]]+)\]\]", re.MULTILINE)
RE_SUGGESTED_NAME = re.compile(r"^\*\*Suggested name:\*\* (.+)$", re.MULTILINE)
RE_DELETE_LINE = re.compile(r"^- \[ \] Delete \[\[([^\]]+)\]\]$", re.MULTILINE)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _atomic_result(stem: str, item_key: str, title: str | None) -> dict:
    """An ordinary atomic-note proposal.

    `title=None` leaves `suggested_title` empty so the rendered
    `**Suggested name:**` falls back to the stem — the exact place a
    path-qualified value would leak into a name.
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
                "kind": "create_atomic_note",
                "source_stem": stem,
                "suggested_title": title or "",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [],
                "tags_to_add": [],
                "atomic_note_worthiness": 0.85,
                "classification": None,
            },
        ],
    }


def _daily_only_result(stem: str, item_key: str, content: str) -> dict:
    """An item fully captured in a daily note — no per-item section at all.

    It appears in the document only as a daily log entry plus a
    `- [ ] Delete [[…]]` line, so those two lines are its only source links.
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
                    "content": content,
                    "confidence": 0.8,
                    "reason": "noted",
                }],
            },
        ],
    }


def _drive(work: Path, results: dict[str, dict], run_id: str) -> str:
    """Run the real reducer + renderer over `results` and return the markdown."""
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

    doc_path = work / "suggestions-doc.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", run_id, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1", "--no-kado",
    ])

    md_path = work / "suggestions.md"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path), "--output", str(md_path),
        "--json-output", str(work / "suggestions-wire.json"),
    ])
    return md_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def unique_run(tmp_path_factory) -> str:
    """Every filename in the run is unique — the ordinary case."""
    return _drive(
        tmp_path_factory.mktemp("t5_1_unique"),
        {
            DRESDEN_ROOT: _atomic_result("Dresden", DRESDEN_ROOT, None),
            ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
        },
        "t5-1-unique",
    )


@pytest.fixture(scope="module")
def collision_run(tmp_path_factory) -> str:
    """Two namesakes in different subfolders, plus one unique note."""
    return _drive(
        tmp_path_factory.mktemp("t5_1_collision"),
        {
            DRESDEN_PLACES: _atomic_result(
                "Dresden", DRESDEN_PLACES, "Dresden - Frauenkirche"
            ),
            # No suggested_title: the name falls back to the stem, which is
            # where a path-derived value would surface if the link and the
            # name were rendered from the same value.
            DRESDEN_REISE: _atomic_result("Dresden", DRESDEN_REISE, None),
            ROOT_NOTE: _atomic_result("Root Note", ROOT_NOTE, "Root note takeaway"),
        },
        "t5-1-collision",
    )


@pytest.fixture(scope="module")
def daily_only_collision_run(tmp_path_factory) -> str:
    """Two namesakes whose content is fully captured in the same daily note."""
    return _drive(
        tmp_path_factory.mktemp("t5_1_daily"),
        {
            DRESDEN_PLACES: _daily_only_result(
                "Dresden", DRESDEN_PLACES, "walked past the Frauenkirche"
            ),
            DRESDEN_REISE: _daily_only_result(
                "Dresden", DRESDEN_REISE, "booked the sleeper to Dresden"
            ),
        },
        "t5-1-daily",
    )


# ---------------------------------------------------------------------------
# 1. A unique filename renders as the plain filename
# ---------------------------------------------------------------------------

class TestUniqueFilenameStaysBare:
    def test_the_source_link_is_the_plain_filename(self, unique_run):
        links = RE_SOURCE_FIELD.findall(unique_run)
        assert sorted(links) == ["Dresden", "Root Note"], (
            f"a run with no filename collision qualified a link: {links}"
        )

    def test_no_source_link_carries_a_path_or_an_alias(self, unique_run):
        for link in RE_SOURCE_FIELD.findall(unique_run):
            assert "/" not in link and "|" not in link, (
                f"path-qualification leaked into a no-collision run: [[{link}]]"
            )

    def test_the_bare_link_still_resolves_to_its_one_note(self, unique_run):
        for link in RE_SOURCE_FIELD.findall(unique_run):
            assert len(narrow_candidates(link, FLAT_INDEX,
                                         default_extension=".md")) == 1


# ---------------------------------------------------------------------------
# 2. Two items sharing a filename each resolve to their own note
# ---------------------------------------------------------------------------

class TestCollidingFilenamesAreDistinguishable:
    def test_the_two_source_links_differ(self, collision_run):
        links = RE_SOURCE_FIELD.findall(collision_run)
        dresden = [ln for ln in links if ln.endswith("Dresden")
                   or "Dresden|" in ln]
        assert len(dresden) == 2, f"expected two Dresden source links: {links}"
        assert dresden[0] != dresden[1], (
            "both namesakes rendered the same source link — the user cannot "
            f"tell the two suggestions apart: {dresden}"
        )

    def test_each_link_resolves_to_exactly_one_note(self, collision_run):
        resolved = []
        for link in RE_SOURCE_FIELD.findall(collision_run):
            candidates = narrow_candidates(link, FULL_INDEX,
                                           default_extension=".md")
            assert len(candidates) == 1, (
                f"[[{link}]] resolves to {len(candidates)} notes "
                f"{candidates} — the link does not say which note is meant"
            )
            resolved.append(candidates[0])
        assert set(resolved) == {DRESDEN_PLACES, DRESDEN_REISE, ROOT_NOTE}

    def test_the_two_links_resolve_to_different_notes(self, collision_run):
        resolved = [
            narrow_candidates(link, FULL_INDEX, default_extension=".md")[0]
            for link in RE_SOURCE_FIELD.findall(collision_run)
        ]
        assert len(set(resolved)) == len(resolved), (
            f"two source links opened the same note: {resolved}"
        )

    def test_the_unique_note_in_the_same_run_stays_bare(self, collision_run):
        links = RE_SOURCE_FIELD.findall(collision_run)
        assert "Root Note" in links, (
            "a filename with no namesake was qualified anyway — "
            f"qualification must be collision-only: {links}"
        )

    def test_each_daily_only_namesake_gets_its_own_delete_line(
        self, daily_only_collision_run
    ):
        deletes = RE_DELETE_LINE.findall(daily_only_collision_run)
        assert len(deletes) == 2, (
            "two daily-only namesakes collapsed onto one delete offer: "
            f"{deletes}"
        )
        resolved = [
            narrow_candidates(d, FULL_INDEX, default_extension=".md")
            for d in deletes
        ]
        assert all(len(c) == 1 for c in resolved), (
            f"a delete offer names an ambiguous note: {deletes} -> {resolved}"
        )
        assert {c[0] for c in resolved} == {DRESDEN_PLACES, DRESDEN_REISE}

    def test_each_daily_log_entry_names_its_own_source(
        self, daily_only_collision_run
    ):
        sources = re.findall(r"^  - Source: \[\[([^\]]+)\]\]$",
                             daily_only_collision_run, re.MULTILINE)
        assert len(sources) == 2, f"expected two log-entry sources: {sources}"
        resolved = [
            narrow_candidates(s, FULL_INDEX, default_extension=".md")
            for s in sources
        ]
        assert {c[0] for c in resolved if len(c) == 1} == {
            DRESDEN_PLACES, DRESDEN_REISE
        }, f"log-entry sources do not name their own notes: {sources}"


# ---------------------------------------------------------------------------
# 3. The suggested NAME is never path-derived
# ---------------------------------------------------------------------------

class TestSuggestedNameStaysABareFilename:
    def test_the_subfolder_note_is_still_named_dresden(self, collision_run):
        names = RE_SUGGESTED_NAME.findall(collision_run)
        assert "Dresden" in names, (
            "the note whose title falls back to its stem is no longer named "
            f"`Dresden`: {names}"
        )

    def test_no_suggested_name_contains_a_path_or_an_alias(self, collision_run):
        for name in RE_SUGGESTED_NAME.findall(collision_run):
            assert "/" not in name and "|" not in name, (
                f"a path-derived string reached a suggested name: {name!r}"
            )
