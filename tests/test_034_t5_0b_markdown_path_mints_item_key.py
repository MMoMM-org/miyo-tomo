#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t5_0b_markdown_path_mints_item_key.py — the path users actually take.

Spec 034 (recursive inbox discovery), Phase 5, follow-on to T5.0.

T5.0 made the Pass-2 render stage address items by `item_key`, which fixed the
ADR-026 wire path. The markdown path — `suggestion-parser.py main()`, which
`synthesis-conductor.md:105` invokes as the normal flow — minted no key at any
of its `confirmed_items.append` sites, so every subfolder note carrying a
template was still dropped there.

The premise that made that look unfixable was that the rendered document
carries only a bare display stem and a path cannot be recovered from one. That
is true of the markdown FILE and false of the markdown PATH: the same flow
passes `--suggestions-doc tomo-tmp/suggestions-doc.json`, and that document
carries `sections[].item_key` keyed by the exact id the markdown heading shows.

    markdown:  ### S01 — Bohnen aus Äthiopien      **Source:** [[Bohnen]]
    doc:       {"id": "S01", "stem": "Bohnen",
                "item_key": "100 Inbox/Places/Bohnen.md"}

So the key is joined back on the section id, cross-checked against the display
stem, exactly as T5.0 recovers daily-entry keys. Nothing about the rendered
document changes.

This also closes what T5.1 would NOT have: T5.1 path-qualifies source links
only for same-filename groups, so a globally unique subfolder note keeps its
bare `[[Bohnen]]` link and would still have been dropped after T5.1 landed.

WHAT MUST STILL HOLD: the doc is not passed on every invocation
(`synthesis-conductor.md:117` runs the parser bare), so the join has to fail
safe — no doc means the pre-existing behaviour, unchanged.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import test_034_t5_0_pass2_reads_item_key as T5  # noqa: E402


def _parse_markdown(work: Path, *, with_doc: bool, cwd: Path | None = None) -> dict:
    """Run the parser over the rendered markdown, with or without the doc.

    `cwd` matters when `with_doc` is False: `_default_doc_path` falls back to a
    cwd-relative `tomo-tmp/suggestions-doc.json`, so the no-doc case has to run
    somewhere that file cannot be found.
    """
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(work / "suggestions-approved.md"),
    ]
    if with_doc:
        cmd += ["--suggestions-doc", str(work / "suggestions-doc.json")]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None
    )
    assert result.returncode == 0, f"parser failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict:
    work = tmp_path_factory.mktemp("t5_0b")
    return T5._drive(
        work,
        {key: T5._atomic_result(stem, key, title) for stem, key, title in T5.ITEMS},
        accept_all=True,
    )


def _keys_by_title(parsed: dict) -> dict[str, str | None]:
    return {c["title"]: c.get("item_key") for c in parsed["confirmed_items"]}


class TestMarkdownPathMintsTheKey:
    def test_one_level_subfolder_note_gets_its_path(self, run):
        keys = _keys_by_title(_parse_markdown(run["work"], with_doc=True))
        assert keys["Bohnen aus Äthiopien"] == T5.DEEP_1

    def test_two_level_subfolder_note_gets_its_path(self, run):
        keys = _keys_by_title(_parse_markdown(run["work"], with_doc=True))
        assert keys["Sapporo im Februar"] == T5.DEEP_2

    def test_root_note_gets_its_path_too(self, run):
        keys = _keys_by_title(_parse_markdown(run["work"], with_doc=True))
        assert keys["Kaffee als Ritual"] == T5.ROOT_NOTE

    def test_display_stem_is_untouched(self, run):
        """ADR-2: item_key is identity, source_path stays display text. A path
        leaking into source_path would put a folder into a note title."""
        parsed = _parse_markdown(run["work"], with_doc=True)
        assert sorted(c["source_path"] for c in parsed["confirmed_items"]) == [
            "Bohnen", "Kaffee", "Sapporo",
        ]


class TestSubfolderNotesSurvivePass2OnTheMarkdownPath:
    """The end this exists for: the note reaches the instruction set."""

    def _kept_and_actions(self, run):
        from lib.render_actions import build_actions  # noqa: PLC0415
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        parsed = _parse_markdown(run["work"], with_doc=True)
        client = T5._exact_path_client({T5.ROOT_NOTE, T5.DEEP_1, T5.DEEP_2})
        kept, dropped = filter_missing_source_notes(
            parsed["confirmed_items"], client, T5.INBOX
        )
        manifest = [
            {
                "id": c["id"], "action": "create_note", "title": c["title"],
                "source_path": c.get("source_path"), "item_key": c.get("item_key"),
                "audio_peer": None, "template": c.get("template"),
                "rendered_file": f"2026-06-11_1200_{c['id']}.md",
                "destination": c.get("destination") or "Atlas/202 Notes/",
                "parent_mocs": c.get("parent_mocs") or [], "attachments": [],
                "tags": c.get("tags") or [],
            }
            for c in kept
        ]
        actions, _ = build_actions(
            manifest, kept, parsed.get("daily_updates", []),
            parsed.get("skipped", []), T5.CFG, kado_client=None,
        )
        return kept, dropped, actions

    def test_nothing_is_dropped_when_the_vault_holds_all_three(self, run):
        kept, dropped, _ = self._kept_and_actions(run)
        assert dropped == [], f"a note that exists was still dropped: {dropped}"
        assert len(kept) == 3

    def test_the_move_origins_are_the_real_paths(self, run):
        _kept, _dropped, actions = self._kept_and_actions(run)
        origins = {
            a.get("source_inbox_item") for a in actions if a.get("action") == "move_note"
        }
        assert origins == {T5.ROOT_NOTE, T5.DEEP_1, T5.DEEP_2}


def _isolated_markdown(run: dict, tmp_path: Path) -> Path:
    """The markdown alone, with no doc anywhere the parser can reach it.

    `_default_doc_path` prefers a `suggestions-doc.json` SIBLING of the
    markdown before falling back to a cwd-relative `tomo-tmp/`, and the
    pipeline writes the two side by side — so omitting `--suggestions-doc` is
    not by itself enough to exercise the no-doc path. The markdown has to be
    somewhere the doc is not.
    """
    work = tmp_path / "markdown-only"
    work.mkdir()
    (work / "suggestions-approved.md").write_text(
        (run["work"] / "suggestions-approved.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return work


class TestNoDocFallsBackToTodaysBehaviour:
    """`synthesis-conductor.md:117` runs the parser without --suggestions-doc."""

    def test_parser_still_succeeds_and_mints_no_key(self, run, tmp_path):
        work = _isolated_markdown(run, tmp_path)
        parsed = _parse_markdown(work, with_doc=False, cwd=tmp_path)
        assert len(parsed["confirmed_items"]) == 3
        assert all(not c.get("item_key") for c in parsed["confirmed_items"]), (
            "a key was invented with no document to read it from"
        )

    def test_display_stems_are_unchanged_without_the_doc(self, run, tmp_path):
        work = _isolated_markdown(run, tmp_path)
        parsed = _parse_markdown(work, with_doc=False, cwd=tmp_path)
        assert sorted(c["source_path"] for c in parsed["confirmed_items"]) == [
            "Bohnen", "Kaffee", "Sapporo",
        ]

    def test_the_root_note_still_renders_without_the_doc(self, run, tmp_path):
        """The reconstruction fallback is what a pre-spec document relies on."""
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        work = _isolated_markdown(run, tmp_path)
        parsed = _parse_markdown(work, with_doc=False, cwd=tmp_path)
        client = T5._exact_path_client({T5.ROOT_NOTE, T5.DEEP_1, T5.DEEP_2})
        kept, _dropped = filter_missing_source_notes(
            parsed["confirmed_items"], client, T5.INBOX
        )
        assert "Kaffee als Ritual" in {c["title"] for c in kept}


class TestTheJoinRefusesToGuess:
    def test_an_edited_source_line_binds_no_key(self, run, tmp_path):
        """The user owns this document. If the Source line no longer names the
        note the doc recorded for that section, the id match alone is not
        evidence — binding on it would name a specific wrong note, which is
        worse than falling back to the reconstruction."""
        work = tmp_path / "edited"
        work.mkdir()
        (work / "suggestions-doc.json").write_text(
            (run["work"] / "suggestions-doc.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        md = (run["work"] / "suggestions-approved.md").read_text(encoding="utf-8")
        (work / "suggestions-approved.md").write_text(
            md.replace("**Source:** [[Bohnen]]", "**Source:** [[EtwasAnderes]]"),
            encoding="utf-8",
        )
        keys = _keys_by_title(_parse_markdown(work, with_doc=True))
        assert keys["Bohnen aus Äthiopien"] is None, (
            "the section id matched but the note did not — no key may be bound"
        )
        # The other two are untouched by one edited section.
        assert keys["Sapporo im Februar"] == T5.DEEP_2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
