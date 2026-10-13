#!/usr/bin/env python3
"""test_039_t6_3_unsafe_folder_does_not_abort_pass_2.py — spec 039 T6.3 close-out (F2-AC9).

PRD F2-AC9: a typed folder containing `{{`, `<%` or a control character is
refused with the reason F5-AC7 uses (`unsafe_sequence`), And the rest of the
run is produced. `test_039_t2_2_check_typed_folder.py` pins the reason on the
checker alone and `test_039_t2_1_…::test_unsafe_typed_name_does_not_abort_pass_2`
pins the second half for a typed NAME; no test drove an unsafe typed FOLDER
through Pass 2. The close-out's trace found that gap; this file closes it.

Each case runs the real `instruction-render.py main()` the way the synthesis
conductor calls it (`pass2_harness`), with a second item whose attachment has
no conflict: that item must still be filed and its attachment moved, and the
refused folder must be reported with the `unsafe_sequence` sentence.

Mechanism falsified: "an unsafe typed folder aborts Pass 2". Mutation proven
RED in an isolated `git archive` copy: delete the `unsafe_sequence` branch of
`check_typed_folder` (`lib/typed_name_check.py`). `{{` and the control
character then pass the checker, reach `_check_path_shape` in the target and
abort the whole run (exit 2); `<%` falls through to `forbidden_character`.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib.refusal_sentences import folder_sentence  # noqa: E402
from pass2_harness import (  # noqa: E402
    ASSET,
    INBOX,
    NOTES,
    CountingKado,
    _item,
    _run_main,
    _suggestions,
)

UNSAFE = f"{INBOX}karte.png"
GOOD = f"{INBOX}foto.png"


@pytest.mark.parametrize(
    "folder", ["Atlas/a{{b", "Atlas/a<%b", "Atlas/a\x01b"],
    ids=["double-brace", "template-tag", "control-char"],
)
def test_an_unsafe_typed_folder_is_refused_and_the_run_is_produced(
    monkeypatch, tmp_path, folder
):
    client = CountingKado([UNSAFE, GOOD], existing_folders=[ASSET, NOTES])
    rc, out_dir = _run_main(
        monkeypatch, tmp_path,
        _suggestions(
            [_item("S01", "Eins", attachments=[UNSAFE]),
             _item("S02", "Zwei", attachments=[GOOD])],
            [{"source": UNSAFE, "remedy": "rename", "proposed_name": "karte.png",
              "name_is_owner_supplied": True,
              "proposed_dir": folder, "dir_is_owner_supplied": True}],
        ),
        client,
    )
    assert rc == 0
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    actions = doc["actions"]
    assert [a["source"] for a in actions if a["action"] == "move_asset"] == [GOOD]
    assert [a["title"] for a in actions if a["action"] == "move_note"] == ["Zwei"]
    assert [(s["source"], s["kind"], s["reason"]) for s in doc["tomo"]["skipped_assets"]] == [
        (UNSAFE, "typed_folder_refused", folder_sentence("unsafe_sequence", folder)),
    ]
