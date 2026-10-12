#!/usr/bin/env python3
"""test_039_t5_4_owner_wording.py — spec 039 T5.4 follow-up.

An end-to-end read of the rendered Pass-2 instruction document found
owner-facing wording problems; the owner ruled (2026-10-12) one report per
item and one remedy per withheld kind. Each test below pins one finding, over
the same `every_kind` fixture T5.1 renders (one of every attachment outcome).

Mechanism each test falsifies:
- `test_one_remedy_per_withheld_kind_in_every_surface` (finding 1): the
  "Not filed" section and the "Attachments still in the inbox" bullet / shell
  relay carrying two different remedies for the same withheld attachment.
- `test_remedy_sentences_are_exact` (findings 1, 2): a remedy whose
  before/after-apply antecedents are unclear, or that names a command the
  triage routing does not honour for that moment (`re-run Pass 2`, or a bare
  `/inbox` for a held note whose source is already captured).
- `test_ignore_is_reported_once_at_its_move` (finding 3): an Ignore whose move
  is emitted ALSO listed under "Skipped" as an unresolved conflict.
- `test_case_only_occupied_sentence_does_not_put_the_occupier_at_the_target`
  (finding 4): the case-only sentence saying the occupier is AT the target.
- `test_each_withheld_delete_is_reported_once` (finding 5): the "Delete
  withdrawn" catch-all repeating the Source Deletions notice for the same note.
- `test_withdrawal_with_no_inline_guard_is_still_reported_once` (finding 5):
  dropping the catch-all also dropping the only report of an undeclared or
  unattributed withdrawal.
- `test_unchecked_target_gives_an_owner_action` (finding 6): the unchecked
  notice ending without telling the owner what they can do.

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib.render_md import render_instructions_md  # noqa: E402
from test_039_t4_5_wire_plan_into_pass_2 import ASSET  # noqa: E402
from test_039_t5_1_reporting import (  # noqa: E402
    BLANK_FOLDER,
    DOWN_FOLDER,
    FOLDER_REFUSED,
    IGNORED,
    OCCUPIED,
    UNCHECKED,
    _withheld_bullets,
    render_every_kind,
)

refusal_sentences = importlib.import_module("lib.refusal_sentences")


@pytest.fixture
def every_kind(monkeypatch, tmp_path):
    """T5.1's every-outcome render: one of every attachment outcome."""
    return render_every_kind(monkeypatch, tmp_path)

HELD_AFTER_APPLY = (
    "If you have already applied, the attachment is still in the inbox, and "
    "so is every note that embeds it: run `/inbox --recover` and "
)
EXPECTED_REMEDY = {
    "typed_folder_refused": (
        "To fix: correct the folder in the suggestions document and run "
        "`/inbox --pass2 --force` before you apply. " + HELD_AFTER_APPLY
        + "choose the attachment's folder again"
    ),
    "typed_name_refused": (
        "To fix: correct the name in the suggestions document and run "
        "`/inbox --pass2 --force` before you apply. " + HELD_AFTER_APPLY
        + "name the attachment again"
    ),
    "vault_occupied": (
        "To fix: free that target in the vault, then run "
        "`/inbox --pass2 --force` before you apply. " + HELD_AFTER_APPLY
        + "choose another name for the attachment, or free the target first"
    ),
}
KIND_OF = {
    OCCUPIED: "vault_occupied",
    FOLDER_REFUSED: "typed_folder_refused",
    BLANK_FOLDER: "typed_folder_refused",
}


def _remedy(kind, destination=None):
    fn = getattr(refusal_sentences, "withheld_attachment_remedy", None)
    assert fn is not None, "lib.refusal_sentences has no withheld_attachment_remedy"
    return fn(kind, destination)


def _not_filed_lines(md: str) -> list[str]:
    section = md.split("## Not filed — an attachment could not be filed with it", 1)[1]
    section = section.split("\n## ", 1)[0]
    return [ln for ln in section.splitlines() if ln.startswith("- `")]


# ---------------------------------------------------------------------------
# Findings 1 + 2 — one remedy per withheld kind, from one source
# ---------------------------------------------------------------------------

def test_one_remedy_per_withheld_kind_in_every_surface(every_kind):
    md, relay = every_kind
    for source, kind in KIND_OF.items():
        remedy = _remedy(kind)
        (top,) = [ln for ln in _not_filed_lines(md) if ln.startswith(f"- `{source}`")]
        (bullet,) = [b for b in _withheld_bullets(md) if f"`{source}`" in b]
        (relayed,) = [ln for ln in relay if f"`{source}`" in ln]
        for line in (top, bullet, relayed):
            assert line.endswith(f" {remedy}."), (kind, line)
            assert "re-run Pass 2" not in line, line
        assert relayed == bullet


@pytest.mark.parametrize("kind", sorted(EXPECTED_REMEDY))
def test_remedy_sentences_are_exact(kind):
    assert _remedy(kind) == EXPECTED_REMEDY[kind]


def test_not_filed_intro_names_no_pass_number(every_kind):
    md, _relay = every_kind
    section = md.split("## Not filed — an attachment could not be filed with it", 1)[1]
    intro = section.split("\n## ", 1)[0].strip().splitlines()[0]
    assert "Pass 2" not in intro and "Pass 1" not in intro, intro


def test_remedy_rejects_an_unknown_kind():
    with pytest.raises(ValueError):
        _remedy("something_else")


# ---------------------------------------------------------------------------
# Finding 3 — an Ignore is reported once, at its own move
# ---------------------------------------------------------------------------

def test_ignore_is_reported_once_at_its_move(every_kind):
    md, relay = every_kind
    naming = [ln for ln in md.splitlines() if f"`{IGNORED}`" in ln]
    assert naming == [f"- **From:** `{IGNORED}`"], naming
    assert "Destination was occupied" in md
    assert "Conflict remains" not in md, md
    assert "since been freed" not in md, md
    assert not any(f"`{IGNORED}`" in ln for ln in relay), relay


# ---------------------------------------------------------------------------
# Finding 4 — the case-only occupier is not AT the target
# ---------------------------------------------------------------------------

def test_case_only_occupied_sentence_does_not_put_the_occupier_at_the_target(every_kind):
    target, occupier = f"{ASSET}/belegt.png", f"{ASSET}/Belegt.png"
    expected = (
        f"target occupied: the vault already holds `{occupier}`, which differs "
        f"from the target `{target}` only in case — the filesystem may treat "
        f"them as one file — so the attachment is not filed over it"
    )
    assert refusal_sentences.occupied_target_sentence(target, occupier) == expected
    md, _relay = every_kind
    (bullet,) = [b for b in _withheld_bullets(md) if f"`{OCCUPIED}`" in b]
    assert expected in bullet, bullet
    # the exact-spelling and folder variants keep their wording
    assert refusal_sentences.occupied_target_sentence(target, target) == (
        f"target occupied: the vault already holds a file at the target "
        f"`{target}`, so the attachment is not filed over it"
    )
    assert refusal_sentences.occupied_target_sentence(
        target, None, occupier_is_folder=True
    ).startswith("target occupied: the vault already has a folder at")


# ---------------------------------------------------------------------------
# Finding 5 — each withheld delete is reported once
# ---------------------------------------------------------------------------

def test_each_withheld_delete_is_reported_once(every_kind):
    md, _relay = every_kind
    for note in ("Note3", "Note4", "Note5"):
        reports = [ln for ln in md.splitlines()
                   if f"[[{note}]]" in ln
                   and ("Not deleted" in ln or "Delete withheld" in ln)]
        assert reports == [
            f"- ⚠️ **Not deleted:** [[{note}]] — an attachment it carries could not be filed"
        ], reports
    assert "Delete withdrawn" not in md, md
    assert "justification" not in md, md


def test_withdrawal_with_no_inline_guard_is_still_reported_once():
    md = render_instructions_md([], {
        "generated": "2026-10-12T00:00:00Z",
        "delete_withdrawals": [{
            "id": "D2", "action": "delete_source",
            "source_path": "100 Inbox/Other.md",
            "reason": "Origin consumed by 1 atomic.",
            "causes": [{"missing_id": None, "guard": None}],
        }],
    }, {})
    reports = [ln for ln in md.splitlines() if "[[Other]]" in ln]
    assert reports == [
        "- ⚠️ **Not deleted:** [[Other]] — no reason was ever recorded for this delete"
    ], md
    assert "## Skipped" not in md, md


# ---------------------------------------------------------------------------
# Finding 6 — the unchecked target tells the owner what to do
# ---------------------------------------------------------------------------

def test_unchecked_target_gives_an_owner_action(every_kind):
    target = f"{DOWN_FOLDER}/offen.png"
    sentence = refusal_sentences.unchecked_target_sentence(target)
    assert sentence.endswith(
        f"stay in the inbox. You can apply this move as it is; to be sure "
        f"first, check in the vault that nothing is at `{target}`"
    ), sentence
    md, relay = every_kind
    (line,) = [ln for ln in md.splitlines()
               if ln.startswith("- ⚠️ **Target not checked:**")]
    assert line.endswith(f"nothing is at `{target}`."), line
    assert f"`{UNCHECKED}`" in line
    assert line in relay
