#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_withheld_deletes_relay.py — the run-level withheld-
delete relay file (`sync_withheld_deletes_file`, `instruction-render.py`).

Follow-up to spec 036/035's Step-4 relay (`3c8170c`, "withheld delete no
longer fails coverage or stays silent to the user"). That commit taught
`synthesis-conductor.md` to grep the withdrawn-delete notice out of
`tomo-tmp/rendered/instructions.md` after each entry's 3b and hold it in the
conductor's own conversational memory until Step 4 — because
`instruction-render.py` is always invoked with the fixed
`--output-dir tomo-tmp/rendered`, that file is overwritten by the NEXT
entry's 3b. A Pass 2 run processing N approved docs therefore made entries
1..N-1's notices survive only in a haiku-tier agent's memory across an
arbitrary number of tool calls — exactly the "works in today's single-entry
run" fragility this repo has already learned about (deterministic rendering
over LLM assembly; an agent definition's rules are not what the LLM actually
does).

This file covers the deterministic replacement: `instruction-render.py` now
writes each entry's already-sanitized notices to a RUN-LEVEL file,
`tomo-tmp/withheld-deletes.md` (one directory above `--output-dir`, so the
per-entry overwrite never touches it), append-only across the several
`instruction-render.py` invocations one Pass 2 run makes and keyed on
`--run-id` to avoid leaking a previous `/inbox` run's notices into a later
one. Full rationale: docs/tomo/scripts/instruction-render.md,
"`sync_withheld_deletes_file` — a Run-Level Relay That Survives Being Called
N Times".

Tests are RED against `3c8170c` (no `sync_withheld_deletes_file`, no
`tomo-tmp/withheld-deletes.md` at all) and GREEN after this change.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render_withheld_relay", SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_withheld_relay"] = _ir
_ir_spec.loader.exec_module(_ir)


# ── Fixtures — mirrors tests/test_036_t4_3_withdrawal_reporting.py's harness,
#    kept self-contained rather than imported so this file's dependency on
#    that one is not a hidden coupling. ────────────────────────────────────


def _daily_action(id_="I05", date="2026-09-17"):
    return {
        "id": id_,
        "action": "update_log_entry",
        "daily_note_path": f"Calendar/301 Daily/{date}.md",
        "date": date,
        "content": "Logged in daily.",
        "applied": False,
    }


def _withdrawn_delete(id_="D1", source_path="100 Inbox/Origin.md", depends_on=("I05",)):
    return {
        "id": id_,
        "action": "delete_source",
        "source_path": source_path,
        "reason": "Content fully captured in daily note.",
        "depends_on": list(depends_on),
        "applied": False,
    }


def _suggestions_payload():
    return {
        "confirmed_items": [{"id": "C0"}],
        "daily_updates": [{"id": "dummy"}],
        "skipped": [],
    }


def _client(note_exists: bool) -> MagicMock:
    client = MagicMock()
    client.note_exists.return_value = note_exists
    return client


def _stub_pipeline(
    monkeypatch, base_dir: Path, fixture_actions: list[dict], client, run_id: str | None
) -> Path:
    """Stub the I/O boundary (build_actions + Kado reads); every guard, the
    withdrawal join, and both renderers run for real. `--output-dir` is
    always `base_dir / "out"`, so the run-level file lands at
    `base_dir / "withheld-deletes.md"` — one directory above, matching the
    real pipeline's `tomo-tmp/rendered` -> `tomo-tmp/withheld-deletes.md`.
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    suggestions_file = base_dir / "suggestions.json"
    suggestions_file.write_text(
        __import__("json").dumps(_suggestions_payload()), encoding="utf-8"
    )
    cfg_file = base_dir / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        _ir, "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox",
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )
    monkeypatch.setattr(_ir, "KadoClient", lambda: client)
    monkeypatch.setattr(_ir, "build_actions", lambda *_a, **_kw: (fixture_actions, []))
    monkeypatch.setattr(_ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(_ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(_ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(_ir, "backfill_supporting_items_parents", lambda _items: None)

    out_dir = base_dir / "out"
    argv = [
        "instruction-render.py",
        "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir),
        "--config", str(cfg_file),
    ]
    if run_id is not None:
        argv += ["--run-id", run_id]
    monkeypatch.setattr(sys, "argv", argv)
    return out_dir


RUN_A = "2026-09-18T10-00-00Z-aaaaaa"
RUN_B = "2026-09-18T11-30-00Z-bbbbbb"


# ── 1. One withheld delete: sanitized sentence, no internals ──────────────


class TestSingleEntryWritesSanitizedSentence:
    def test_run_level_file_carries_the_sanitized_sentence_only(self, monkeypatch, tmp_path):
        actions = [_daily_action(), _withdrawn_delete()]
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, actions, _client(note_exists=False), RUN_A
        )
        assert _ir.main() == 0

        relay_path = out_dir.parent / "withheld-deletes.md"
        assert relay_path.exists()
        content = relay_path.read_text(encoding="utf-8")
        assert "[[Origin]] was **not** deleted — its daily note does not exist" in content
        # No executor internals (ADR-11) — same standard as instructions.md.
        assert "D1" not in content
        assert "delete_source" not in content
        assert "I05" not in content
        assert "filter_missing_daily_notes" not in content
        assert "100 Inbox/Origin.md" not in content


# ── 2. Two entries in sequence: append, never erase (the defect fixed) ────


class TestTwoEntriesAppendAcrossTheSameRun:
    def test_second_entrys_render_does_not_erase_the_firsts_notice(
        self, monkeypatch, tmp_path
    ):
        """This is the defect `3c8170c` shipped: `--output-dir` is
        overwritten by every entry's 3b, so a relay keyed to that directory
        loses entry 1's notice once entry 2 renders. Must fail against
        `3c8170c` (no run-level file exists at all there)."""
        entry1_actions = [_daily_action(id_="I05"), _withdrawn_delete(
            id_="D1", source_path="100 Inbox/Origin.md", depends_on=("I05",)
        )]
        _stub_pipeline(monkeypatch, tmp_path, entry1_actions, _client(note_exists=False), RUN_A)
        assert _ir.main() == 0

        entry2_actions = [_daily_action(id_="I06", date="2026-09-18"), _withdrawn_delete(
            id_="D2", source_path="100 Inbox/Second.md", depends_on=("I06",)
        )]
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, entry2_actions, _client(note_exists=False), RUN_A
        )
        assert _ir.main() == 0

        content = (out_dir.parent / "withheld-deletes.md").read_text(encoding="utf-8")
        assert "[[Origin]] was **not** deleted — its daily note does not exist" in content
        assert "[[Second]] was **not** deleted — its daily note does not exist" in content


# ── 3. Nothing withheld: no file, not an empty one ─────────────────────────


class TestNoWithdrawalLeavesNoFile:
    def test_no_withheld_delete_creates_no_relay_file(self, monkeypatch, tmp_path):
        actions = [_daily_action(), _withdrawn_delete()]
        # note_exists=True -> filter_missing_daily_notes drops nothing ->
        # withdraw_unjustified_deletes withdraws nothing.
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, actions, _client(note_exists=True), RUN_A
        )
        assert _ir.main() == 0
        assert not (out_dir.parent / "withheld-deletes.md").exists()


# ── 4. Staleness rule: a previous run's notice never survives into a new one


class TestStalenessRuleAcrossRuns:
    def test_new_run_with_a_notice_replaces_the_stale_one(self, monkeypatch, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        relay_path = tmp_path / "withheld-deletes.md"
        relay_path.write_text(
            "<!-- run_id: " + RUN_A + " -->\n"
            "- [[Stale Old Run Note]] was **not** deleted — its daily note does not exist\n",
            encoding="utf-8",
        )

        actions = [_daily_action(id_="I09"), _withdrawn_delete(
            id_="D9", source_path="100 Inbox/Fresh.md", depends_on=("I09",)
        )]
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, actions, _client(note_exists=False), RUN_B
        )
        assert _ir.main() == 0

        content = (out_dir.parent / "withheld-deletes.md").read_text(encoding="utf-8")
        assert "Stale Old Run Note" not in content
        assert RUN_A not in content
        assert "[[Fresh]] was **not** deleted — its daily note does not exist" in content

    def test_new_run_with_nothing_withheld_deletes_the_stale_file(self, monkeypatch, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        relay_path = tmp_path / "withheld-deletes.md"
        relay_path.write_text(
            "<!-- run_id: " + RUN_A + " -->\n"
            "- [[Stale Old Run Note]] was **not** deleted — its daily note does not exist\n",
            encoding="utf-8",
        )

        actions = [_daily_action(), _withdrawn_delete()]
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, actions, _client(note_exists=True), RUN_B
        )
        assert _ir.main() == 0

        assert not (out_dir.parent / "withheld-deletes.md").exists()


# ── 5. Identical to the instructions.md sentence — never re-derived ────────


class TestSentenceIdenticalToInstructionsMd:
    def test_relay_line_matches_the_instructions_md_line_exactly(self, monkeypatch, tmp_path):
        actions = [_daily_action(), _withdrawn_delete()]
        out_dir = _stub_pipeline(
            monkeypatch, tmp_path, actions, _client(note_exists=False), RUN_A
        )
        assert _ir.main() == 0

        md_lines = (out_dir / "instructions.md").read_text(encoding="utf-8").splitlines()
        md_notice = next(
            line for line in md_lines if "was **not** deleted" in line
        )
        relay_lines = (out_dir.parent / "withheld-deletes.md").read_text(
            encoding="utf-8"
        ).splitlines()
        relay_notice = next(
            line for line in relay_lines if "was **not** deleted" in line
        )
        assert relay_notice == md_notice


# ── 6. sync_withheld_deletes_file unit coverage (direct, no pipeline) ──────


class TestSyncWithheldDeletesFileUnit:
    def test_no_run_id_is_a_no_op(self, tmp_path):
        path = tmp_path / "withheld-deletes.md"
        _ir.sync_withheld_deletes_file(path, None, ["- [[X]] was **not** deleted — reason"])
        assert not path.exists()

    def test_same_run_id_appends_without_rewriting_header_twice(self, tmp_path):
        path = tmp_path / "withheld-deletes.md"
        _ir.sync_withheld_deletes_file(path, RUN_A, ["- first notice"])
        _ir.sync_withheld_deletes_file(path, RUN_A, ["- second notice"])
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines.count(f"<!-- run_id: {RUN_A} -->") == 1
        assert "- first notice" in lines
        assert "- second notice" in lines

    def test_same_run_zero_notices_does_not_delete_prior_entries(self, tmp_path):
        path = tmp_path / "withheld-deletes.md"
        _ir.sync_withheld_deletes_file(path, RUN_A, ["- first notice"])
        _ir.sync_withheld_deletes_file(path, RUN_A, [])
        assert path.exists()
        assert "- first notice" in path.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
