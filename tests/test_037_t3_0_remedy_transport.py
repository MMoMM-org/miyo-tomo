#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t3_0_remedy_transport.py — spec 037 T3.0.

Before this file, `parse_attachment_conflict_remedies` (T2.4) had ZERO
production callers: `suggestion-parser.py`'s `main()` never called it, and
its output dict never carried the result. `_build_move_asset_actions`
(T3.1's target) is reached only through `instruction-render.py:600`'s
`build_actions` call. This is the missing edge — every later Phase 3 task
is dead code without it.

Covers, per `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-
decision/plan/phase-3.md` T3.0:

  1. `main()`'s JSON output carries one record per `## Attachment
     Conflicts` entry, each with `source`, `remedy` AND `proposed_name`
     joined from the structured suggestions-doc's `attachment_conflicts[]`
     by `source` (T1.5's grouping key) — mutation: drop the join and emit
     `{source, remedy}` only.
  2. A document with no `## Attachment Conflicts` section emits an EMPTY
     LIST under the new key, not a missing key — mutation: emit the key
     only when non-empty.
  3. A `source` present in the markdown but absent from the doc's
     `attachment_conflicts[]` joins to `proposed_name: None` rather than
     raising — mutation: index the JSON dict directly and let `KeyError`
     escape.
  4. `instruction-render.py` forwards the parsed records to `build_actions`
     — mutation: accept the argument and never pass it on. Invisible to
     every parser-side assertion (1-3), so this needs its own capture of
     what `build_actions` was actually called with.
  5. A conflict-free document parsed by `main()` produces an `output` dict
     equal by `==` to a captured literal (captured against the pre-T3.0
     parser, reproduced here as `_PRE_T3_0_OUTPUT` union the new key's
     empty-list value) — not merely non-erroring. Mutation: emit the new
     key with a fabricated entry on a conflict-free run, which bullet 2
     alone cannot catch (it only proves the key is present, not that its
     value is right on a run with nothing to join).
  6. Likewise for `instruction-render.py`'s output on the same shape of
     fixture (`instructions.json` minus the two live fields it stamps —
     `generated`, `md_peer` — and `manifest.json`) — same mutation,
     same reasoning, one hop downstream.

Follows `test_zero_conflict_run_still_emits_no_attachment_conflicts_key`
(`tests/test_037_t1_5_one_entry_one_file.py:428`) and
`test_no_withdrawals_source_deletions_byte_identical`
(`tests/test_036_t4_3_withdrawal_reporting.py:800`): capture the literal,
assert exact equality, rather than merely asserting the run does not raise.

Deliberately OUT of scope (T3.1/T3.3, not this file):
  - `_build_move_asset_actions` consulting `remedy` to choose a
    destination, withhold a move, or leave one unchanged.
  - Any embed rewrite.
`_build_move_asset_actions` is exercised here only to prove it ACCEPTS the
new argument without raising — its behaviour must be unchanged by it.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PARSER = _load_module("suggestion_parser_t037_t3_0", "suggestion-parser.py")
RENDER_ACTIONS = _load_module("render_actions_t037_t3_0", "lib/render_actions.py")
IR = _load_module("instruction_render_t037_t3_0", "instruction-render.py")


# ---------------------------------------------------------------------------
# Fixture: one Attachment-Conflicts entry, rendered exactly as T2.2/T2.3
# render it (mirrors tests/test_037_t2_4_parse_remedy.py's own fixture).
# ---------------------------------------------------------------------------

SOURCE = "100 Inbox/Scans/karte.png"
DESTINATION = "Atlas/290 Assets/295 Attachments/karte.png"
PROPOSED_NAME = "karte (2).png"
RENAME_TARGET = "Atlas/290 Assets/295 Attachments/karte (2).png"

_CONFLICT_MD = (
    "# Inbox Suggestions\n\n"
    "## Attachment Conflicts\n\n"
    f"### `{SOURCE}`\n\n"
    f"- **Destination:** `{DESTINATION}` (already occupied)\n"
    "- **Embedded by:**\n"
    "  - [[karte]]\n"
    "- **File comparison:** A different file already holds this name.\n\n"
    "**Remedy — choose one:**\n"
    f"- [x] Rename to `{RENAME_TARGET}`\n"
    "- [ ] Keep in inbox\n"
    "- [ ] Ignore (the move is sent as-is and will fail — "
    "the attachment stays in the inbox)\n"
)

_CONFLICT_FREE_MD = "# Inbox Suggestions\n\nNothing here.\n"


def _doc_with_conflict() -> dict:
    return {
        "attachment_conflicts": [{
            "source": SOURCE,
            "destination": DESTINATION,
            "same_file": False,
            "owner_source_items": ["Atlas/karte.md"],
            "proposed_name": PROPOSED_NAME,
        }],
    }


def _run_parser(text: str, doc_path, extra_argv: list[str] | None = None) -> dict:
    old_argv, old_stdin = sys.argv, sys.stdin
    argv = ["suggestion-parser.py"]
    if doc_path is not None:
        argv += ["--suggestions-doc", str(doc_path)]
    argv += extra_argv or []
    sys.argv = argv
    sys.stdin = io.StringIO(text)
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = PARSER.main()
    finally:
        sys.argv, sys.stdin, sys.stdout = old_argv, old_stdin, old_stdout
    assert rc == 0, buf.getvalue()
    return json.loads(buf.getvalue())


def _write_doc(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "suggestions-doc.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. The parser's output carries source + remedy + proposed_name, joined
#    from the structured doc by source.
# ---------------------------------------------------------------------------

def test_conflict_entry_joins_proposed_name_by_source(tmp_path):
    """Mutation: drop the join in `_join_attachment_conflict_remedies` and
    return the bare `{source, remedy}` pairs `parse_attachment_conflict_
    remedies` produces — `proposed_name` would be absent from each record,
    leaving T3.1 no name to rename to."""
    doc_path = _write_doc(tmp_path, _doc_with_conflict())
    output = _run_parser(_CONFLICT_MD, doc_path)
    assert output["attachment_conflict_remedies"] == [{
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": PROPOSED_NAME,
    }]


# ---------------------------------------------------------------------------
# 2. Absent section -> empty list, not a missing key.
# ---------------------------------------------------------------------------

def test_no_conflicts_section_emits_empty_list_not_missing_key(tmp_path):
    """Mutation: emit `attachment_conflict_remedies` only when the joined
    list is non-empty — a conflict-free run's output shape would then
    differ from a conflicted one (a downstream `.get(key, [])` masks this,
    but a strict `output["attachment_conflict_remedies"]` index does not)."""
    doc_path = _write_doc(tmp_path, {})
    output = _run_parser(_CONFLICT_FREE_MD, doc_path)
    assert "attachment_conflict_remedies" in output
    assert output["attachment_conflict_remedies"] == []


# ---------------------------------------------------------------------------
# 3. A source in the markdown but absent from the doc's attachment_conflicts
#    joins to proposed_name: None instead of raising.
# ---------------------------------------------------------------------------

def test_source_absent_from_doc_yields_null_proposed_name_not_keyerror(tmp_path):
    """Mutation: `_join_attachment_conflict_remedies` indexes a `{source:
    proposed_name}` dict directly (`by_source[r["source"]]`) instead of
    `.get` — a source the doc never recorded (hand-edited/stale doc) would
    raise `KeyError` and crash the whole parse instead of degrading to
    `None`."""
    # A doc with attachment_conflicts present, but for a DIFFERENT source —
    # the join must miss cleanly, not raise.
    other_doc = {
        "attachment_conflicts": [{
            "source": "100 Inbox/Scans/other.png",
            "destination": "Atlas/290 Assets/295 Attachments/other.png",
            "same_file": False,
            "owner_source_items": [],
            "proposed_name": "other (2).png",
        }],
    }
    doc_path = _write_doc(tmp_path, other_doc)
    output = _run_parser(_CONFLICT_MD, doc_path)
    assert output["attachment_conflict_remedies"] == [{
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": None,
    }]

    # --suggestions-doc points at a file that does not exist at all —
    # _load_json_doc returns {} on the OSError — same outcome.
    missing_doc_path = tmp_path / "does-not-exist.json"
    output_missing_doc = _run_parser(_CONFLICT_MD, missing_doc_path)
    assert output_missing_doc["attachment_conflict_remedies"] == [{
        "source": SOURCE,
        "remedy": "rename",
        "proposed_name": None,
    }]


# ---------------------------------------------------------------------------
# 5. Conflict-free run: output dict == a captured pre-T3.0 literal, union
#    the new key's empty-list value.
# ---------------------------------------------------------------------------

# Captured by running the UNMODIFIED (pre-T3.0) suggestion-parser.py main()
# against `_CONFLICT_FREE_MD` with no --suggestions-doc — see the T3.0
# implementer's report for the exact capture command. `total_sections` is 0
# because the fixture carries no `S##` section at all — parse_section is
# never reached.
_PRE_T3_0_OUTPUT = {
    "confirmed_items": [],
    "merged_moc_proposals": [],
    "daily_updates": [],
    "skipped": [],
    "pending_fan_resolutions": [],
    "approved_tag_handler_group_ids": [],
    "tag_handler_keep_source_group_ids": [],
    "total_sections": 0,
    "total_approved": 0,
    "total_skipped": 0,
}


def test_conflict_free_run_output_is_byte_identical_to_pre_change_literal(tmp_path):
    """Not merely non-erroring: the WHOLE output dict is asserted `==` a
    captured literal. Mutation: emit `attachment_conflict_remedies` with a
    fabricated entry on a conflict-free run (e.g. a stray `attachment_
    conflicts` record surviving from a leftover default doc-path read) —
    bullet 2 alone only proves the key is present, not that its value is
    exactly `[]` when the fixture has nothing to join."""
    missing_doc_path = tmp_path / "does-not-exist.json"
    output = _run_parser(_CONFLICT_FREE_MD, missing_doc_path)
    expected = {**_PRE_T3_0_OUTPUT, "attachment_conflict_remedies": []}
    assert output == expected


# ---------------------------------------------------------------------------
# 4 & 6. instruction-render.py forwards the key to build_actions, and a
#    conflict-free run's manifest.json / instructions.json are unchanged.
# ---------------------------------------------------------------------------

_IR_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}

# Captured against the UNMODIFIED (pre-T3.0) instruction-render.py, same
# fixture, real (unmocked) build_actions — `generated` and `md_peer` are
# stamped from the live clock/date and are stripped before comparison.
_PRE_T3_0_INSTRUCTIONS = {
    "schema_version": "3",
    "type": "tomo-instructions",
    "source_suggestions": "suggestions.json",
    "profile": "miyo",
    "tomo_version": None,
    "action_count": 0,
    "actions": [],
}
_PRE_T3_0_MANIFEST: list = []


def _run_instruction_render(monkeypatch, tmp_path, suggestions: dict):
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(IR, "load_config", lambda _path: dict(_IR_CFG))
    monkeypatch.setattr(IR, "KadoClient", lambda: MagicMock())

    captured_kwargs: dict = {}
    real_build_actions = IR.build_actions

    def _spy_build_actions(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return real_build_actions(*args, **kwargs)

    monkeypatch.setattr(IR, "build_actions", _spy_build_actions)

    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
        ],
    )
    rc = IR.main()
    assert rc == 0
    return out_dir, captured_kwargs


def _conflict_free_suggestions() -> dict:
    return {
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [],
        "skipped": [],
    }


def test_build_actions_receives_the_parsed_remedies(monkeypatch, tmp_path):
    """Mutation: `main()` reads `attachment_conflict_remedies` off the
    parsed suggestions JSON but never passes it to `build_actions` —
    invisible to every parser-side assertion above, since the parser's own
    output is correct either way."""
    suggestions = _conflict_free_suggestions()
    suggestions["attachment_conflict_remedies"] = [{
        "source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME,
    }]
    _out_dir, captured_kwargs = _run_instruction_render(
        monkeypatch, tmp_path, suggestions
    )
    assert captured_kwargs.get("attachment_conflict_remedies") == [{
        "source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME,
    }]


def test_parser_output_reaches_build_actions_end_to_end(monkeypatch, tmp_path):
    """The chain the two halves of this task are supposed to close: a REAL
    `suggestion-parser.py` `main()` run's own output, fed straight into a
    REAL `instruction-render.py` `main()` run, reaches `build_actions`
    unchanged. Mutation: revert the parser's `output` line alone (drop
    `"attachment_conflict_remedies": attachment_conflict_remedies,` from the
    `output` dict) — `suggestion-parser.py`'s own tests (bullets 1-3, 5
    above) catch that directly, but this is the test that proves the two
    scripts were actually wired to each other, not just independently
    correct in isolation."""
    doc_path = _write_doc(tmp_path, _doc_with_conflict())
    parsed = _run_parser(_CONFLICT_MD, doc_path)
    # The fixture markdown carries no `S##` section, so `confirmed_items` is
    # empty — instruction-render.py's "nothing to do" short-circuit needs at
    # least one entry to reach the build_actions call at all.
    parsed["confirmed_items"] = [{
        "id": "S01", "action": None, "title": "placeholder",
        "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
    }]
    _out_dir, captured_kwargs = _run_instruction_render(monkeypatch, tmp_path, parsed)
    assert captured_kwargs.get("attachment_conflict_remedies") == [{
        "source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME,
    }]


def test_conflict_free_run_manifest_and_instructions_are_byte_identical(
    monkeypatch, tmp_path
):
    """Same reasoning as the parser's byte-identical test, one hop
    downstream: `_build_move_asset_actions` accepting the new argument must
    not perturb a conflict-free run's actual output. Mutation: emit the new
    key with a fabricated entry on a conflict-free run — no other bullet in
    this file exercises the full `build_actions` -> `_build_move_asset_
    actions` chain end to end with a real (unmocked) `build_actions`."""
    suggestions = _conflict_free_suggestions()
    suggestions["attachment_conflict_remedies"] = []
    out_dir, _captured = _run_instruction_render(monkeypatch, tmp_path, suggestions)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == _PRE_T3_0_MANIFEST

    instructions = json.loads(
        (out_dir / "instructions.json").read_text(encoding="utf-8")
    )
    instructions.pop("generated", None)
    instructions.pop("md_peer", None)
    assert instructions == _PRE_T3_0_INSTRUCTIONS


# ---------------------------------------------------------------------------
# _build_move_asset_actions accepts the new keyword without raising or
# changing its output — T3.0's scope boundary made concrete: the argument
# is accepted and ignored here, never consulted.
# ---------------------------------------------------------------------------

def test_build_move_asset_actions_accepts_and_ignores_the_new_argument():
    manifest = [{
        "item_key": "100 Inbox/Scans/karte.md",
        "source_path": "100 Inbox/Scans/karte.md",
        "attachments": [SOURCE],
    }]
    remedies = [{"source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME}]

    without_arg, skipped_without = RENDER_ACTIONS._build_move_asset_actions(
        manifest, "100 Inbox/", "Atlas/290 Assets/295 Attachments/", [0]
    )
    with_arg, skipped_with = RENDER_ACTIONS._build_move_asset_actions(
        manifest, "100 Inbox/", "Atlas/290 Assets/295 Attachments/", [0],
        attachment_conflict_remedies=remedies,
    )
    assert with_arg == without_arg
    assert skipped_with == skipped_without
