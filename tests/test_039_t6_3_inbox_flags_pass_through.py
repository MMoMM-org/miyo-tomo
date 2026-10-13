"""Spec 039 T6.3 -- /inbox hands the owner's flags to triage unchanged.

Live run 2026-10-13: ``/inbox --pass2 --force`` was translated by the model
into ``--force-pass2`` (``--force`` dropped), so a covered doc routed to idle
and the before-apply remedy printed in every withheld-attachment line did
nothing. The fix: triage accepts the user-facing flag names itself and the
command runs ``inbox-triage.py $ARGUMENTS`` with no translation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
INBOX_MD = REPO_ROOT / "tomo" / "dot_claude" / "commands" / "inbox.md"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from test_inbox_triage import (  # noqa: E402
    INBOX_PATH,
    FakeKadoClient,
    _fm_hit,
    _listdir_item,
    _load_module,
    _suggestions_body,
)

SUGG = INBOX_PATH + "2026-05-22_1432_suggestions.md"
INSTR = INBOX_PATH + "2026-05-24_0900_instructions.md"


def _body_checksum() -> str:
    """The checksum triage computes, so the doc is covered AND undrifted."""
    return _load_module()._compute_checksum(_suggestions_body(approved=True))


def _covered_client() -> FakeKadoClient:
    """Approved suggestions doc already covered by an instructions doc."""
    return FakeKadoClient(
        listdir_items=[_listdir_item(SUGG), _listdir_item(INSTR)],
        frontmatter_responses={
            "tomo.state=pending-approval": [],
            "tomo.state=pending-accept": [],
            "tomo.state=captured": [],
            "tomo.doc_type=instructions": [
                {"path": INSTR, "modified": 1716300000000, "frontmatter": {}},
            ],
            "tomo.state=approved": [_fm_hit(SUGG, "suggestions", "approved")],
            "tomo.state=accepted": [],
        },
        read_note_responses={
            SUGG: {"content": _suggestions_body(approved=True), "modified": 0},
        },
        read_frontmatter_responses={
            INSTR: {"content": {"tomo": {
                "doc_type": "instructions",
                "sources": [{"path": SUGG, "checksum": _body_checksum()}],
            }}},
        },
    )


def _route(tmp_path: Path, flags: list[str]) -> dict:
    mod = _load_module()
    rc = mod.main(
        [
            "--inbox-path", INBOX_PATH,
            "--output-dir", str(tmp_path),
            "--cost-history", str(tmp_path / "cost-history.jsonl"),
            *flags,
        ],
        client_factory=_covered_client,
    )
    assert rc == 0
    return json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))


def test_triage_accepts_the_user_facing_pass_flags():
    parser = _load_module()._build_arg_parser()

    one = parser.parse_args(["--pass1"])
    two = parser.parse_args(["--pass2"])

    assert (one.force_pass1, one.force_pass2) == (True, False)
    assert (two.force_pass1, two.force_pass2) == (False, True)


def test_pass2_force_resynthesizes_a_covered_doc(tmp_path):
    plan = _route(tmp_path, ["--pass2", "--force"])

    assert plan["action"] == "synthesize"
    assert [d["path"] for d in plan["approved_suggestions"]] == [SUGG]


@pytest.mark.parametrize("flags", [["--pass2"], ["--force-pass2"]])
def test_pass2_without_force_leaves_a_covered_doc_idle(tmp_path, flags):
    assert _route(tmp_path, flags)["action"] == "idle"


def test_inbox_command_passes_arguments_through_unchanged():
    text = INBOX_MD.read_text(encoding="utf-8")
    step1 = re.search(r"### 1\. Run triage(.*?)### 2\.", text, re.S).group(1)

    assert "python3 scripts/inbox-triage.py $ARGUMENTS" in step1
    assert "force-pass" not in step1
    assert "→" not in step1


def test_inbox_step_1_stops_when_triage_fails():
    text = INBOX_MD.read_text(encoding="utf-8")
    step1 = re.search(r"### 1\. Run triage(.*?)### 2\.", text, re.S).group(1)

    assert "exits non-zero" in step1
    assert "stderr" in step1
    assert "never read" in step1.lower() and "routing-plan.json" in step1


def test_pass1_help_does_not_promise_a_force():
    parser = _load_module()._build_arg_parser()

    action = next(a for a in parser._actions if "--pass1" in a.option_strings)
    help_text = " ".join(action.help.split())

    assert "Run Pass 1" in help_text
    assert "Force" not in help_text
