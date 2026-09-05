#!/usr/bin/env python3
# version: 0.1.0
"""test-instructions-dryrun.py — Unit tests for instructions-dryrun.

Covers spec 032 T4.4: registering `edit_frontmatter` in the dry-run validator.

  - a dry run over a set containing edit_frontmatter exits 0 and describes
    each action (no "unknown kind" failure)
  - an action missing BOTH expected/expected_absent is reported invalid
    (the schema's mutual-exclusion guard, mirrored here as a presence check)
  - describe() names the note, the property and the operation/change
  - expected/value are rendered faithfully — a list stays a list, a scalar
    stays a scalar, None stays None; never normalised, unwrapped or str()'d
  - the string "unknown kind" never appears for a well-formed edit_frontmatter
    action

Module-under-test has a hyphenated filename, loaded via importlib like its
instructions-diff.py sibling.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "instructions_dryrun", SCRIPTS_DIR / "instructions-dryrun.py"
)
dryrun = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(dryrun)


def _set_action(**over) -> dict:
    action = {
        "id": "I01",
        "action": "edit_frontmatter",
        "path": "100 Inbox/foo.md",
        "property": "status",
        "operation": "set",
        "value": "active",
        "expected_absent": True,
    }
    action.update(over)
    return action


def _remove_action(**over) -> dict:
    action = {
        "id": "I02",
        "action": "edit_frontmatter",
        "path": "Atlas/202 Notes/bar.md",
        "property": "up",
        "operation": "remove",
        "expected": ["Old MOC"],
    }
    action.update(over)
    return action


def _run(actions: list[dict], tmp_path: Path) -> tuple[int, str, str]:
    """Write an instructions.json fixture and invoke main(); capture output."""
    import contextlib
    import io
    import json

    doc = {
        "schema_version": 2,
        "generated": "2026-09-02T00:00:00Z",
        "profile": "miyo",
        "action_count": len(actions),
        "actions": actions,
    }
    fixture = tmp_path / "instructions.json"
    fixture.write_text(json.dumps(doc), encoding="utf-8")

    argv = sys.argv
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        sys.argv = ["instructions-dryrun.py", str(fixture)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = dryrun.main()
    finally:
        sys.argv = argv
    return code, stdout.getvalue(), stderr.getvalue()


def test_dry_run_exits_0_and_describes_each_action(tmp_path):
    actions = [_set_action(), _remove_action()]
    code, out, err = _run(actions, tmp_path)
    assert code == 0, err
    assert "I01" in out
    assert "I02" in out
    assert "unknown kind" not in out
    assert "unknown kind" not in err


def test_action_missing_expected_guard_is_invalid(tmp_path):
    bad = _set_action(id="I03")
    del bad["expected_absent"]
    assert "expected" not in bad and "expected_absent" not in bad

    code, out, err = _run([bad], tmp_path)
    assert code == 1
    assert "I03" in err
    assert "unknown kind" not in err


def test_action_missing_value_for_set_is_invalid(tmp_path):
    bad = _set_action(id="I04")
    del bad["value"]

    code, out, err = _run([bad], tmp_path)
    assert code == 1
    assert "I04" in err


def test_describe_names_note_property_and_change():
    text = dryrun.describe(_set_action())
    assert "100 Inbox/foo.md" in text
    assert "status" in text
    assert "active" in text


def test_describe_faithfully_renders_list_expected_no_normalisation():
    action = _remove_action(expected=["Old MOC", "Other MOC"])
    text = dryrun.describe(action)
    # The raw list, in JSON vocabulary, must appear verbatim — no unwrap, no str() flattening.
    assert json.dumps(["Old MOC", "Other MOC"]) in text


def test_describe_faithfully_renders_null_expected():
    action = _remove_action(expected=None)
    del action["expected"]
    action["expected"] = None
    text = dryrun.describe(action)
    assert "null" in text


def test_edit_frontmatter_registered_in_required_fields():
    assert "edit_frontmatter" in dryrun.REQUIRED_FIELDS_BY_KIND


# ──────────────────────────────────────────────────────────────────────────────
# move_asset (spec 031 T4.3) — REQUIRED is a whitelist keyed by action kind;
# an unlisted kind reports "unknown kind" and exits 1 regardless of how
# well-formed the action otherwise is. describe() has its own separate
# if/elif chain that must also gain a move_asset branch, or a well-formed
# action still prints "UNKNOWN ACTION" in the per-action listing.
# ──────────────────────────────────────────────────────────────────────────────

def _move_asset_action(**over) -> dict:
    action = {
        "id": "I05",
        "action": "move_asset",
        "source": "100 Inbox/Attachments/photo.jpg",
        "destination": "Atlas/900 Assets/photo.jpg",
    }
    action.update(over)
    return action


def test_move_asset_dry_run_exits_0_and_describes_each_action(tmp_path):
    actions = [_move_asset_action()]
    code, out, err = _run(actions, tmp_path)
    assert code == 0, err
    assert "I05" in out
    assert "unknown kind" not in out
    assert "unknown kind" not in err


def test_move_asset_missing_destination_is_invalid(tmp_path):
    bad = _move_asset_action(id="I06")
    del bad["destination"]

    code, out, err = _run([bad], tmp_path)
    assert code == 1
    assert "I06" in err
    assert "unknown kind" not in err


def test_move_asset_registered_in_required_fields():
    assert "move_asset" in dryrun.REQUIRED_FIELDS_BY_KIND


def test_describe_names_move_asset_source_and_destination():
    text = dryrun.describe(_move_asset_action())
    assert "100 Inbox/Attachments/photo.jpg" in text
    assert "Atlas/900 Assets/photo.jpg" in text
    assert "UNKNOWN ACTION" not in text
