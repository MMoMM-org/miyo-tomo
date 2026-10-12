#!/usr/bin/env python3
"""test_039_t5_1_reporting.py — spec 039 T5.1.

What the owner reads about the attachment plan's new outcomes: the instruction
document (K8, `lib/render_md.py`), the run-level shell relay
(`tomo-tmp/withheld-attachments.md`, K7) and the sentences behind both (K16,
`lib/refusal_sentences.py`).

One end-to-end fixture drives `instruction-render.py` `main()` the way the
synthesis conductor calls it, over a fake vault in which every outcome happens
exactly once: a folder that will be created, a target the vault did not answer
for, an occupied target, a refused typed folder, a blank / unreadable folder
line, an ambiguous basename, an unanswered basename search, and an Ignore.

Mechanism each test falsifies:
- `test_occupied_bullet_names_attachment_target_and_occupier` (F3-AC5): the
  skipped-asset notice having no `vault_occupied` branch (it falls to the
  loud "No remedy defined" fallback), or note wording leaking in.
- `test_unchecked_target_notices_follow_the_final_actions`: the relay filter
  reading reports instead of the final actions, so a move a guard withdrew is
  still reported as an unchecked target.
- `test_refused_folder_bullet_names_attachment_and_rule` (F2-AC5): no
  `typed_folder_refused` branch in the notice.
- `test_each_folder_reason_has_its_own_sentence_in_the_notice` (F2-AC5):
  two reasons sharing one sentence, or a reason dropped by the notice.
- `test_unreadable_folder_line_is_not_reported_as_left_blank`: the `blank`
  folder sentence claiming the owner left it blank — a malformed or
  disagreeing folder line reaches the plan as `""` too.
- `test_unchecked_target_is_reported_not_checked_and_never_free` (F3-AC6):
  the move block carrying no unchecked line, or a sentence calling it free.
- `test_folder_to_be_created_is_listed` (F2-AC8): no line for an absent
  target folder, or one on a move whose folder exists.
- `test_qualified_embeds_are_reported_with_their_reason` (tracking table):
  no line for a qualified embed, the two reasons sharing one sentence, or a
  line on a move whose embed is bare.
- `test_ignore_disclosure_says_the_origin_is_kept` (F6-AC8): the old
  "filed either way" sentence surviving.
- `test_relay_carries_one_line_per_withheld_and_per_unchecked` (038 C1): the
  relay omitting unchecked targets, counting, or drifting from the document.
- `test_no_executor_internals_in_any_new_sentence`: an internal term in an
  owner-facing line (owner paths stripped first, so a file literally named
  `move_asset.png` cannot trip it).
- `test_conductor_relays_unchecked_lines_and_passes_cost_history` and
  `test_conductor_mirror_records_the_unchecked_relay_decision`: the runtime
  prompt and its WHY mirror.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import KadoError  # noqa: E402
from lib.render_md import (  # noqa: E402
    _render_skipped_asset_notice,
    unchecked_target_notices,
)
from lib.typed_name_check import FOLDER_REFUSAL_REASONS  # noqa: E402
from test_039_t4_5_wire_plan_into_pass_2 import (  # noqa: E402
    ASSET,
    INBOX,
    NOTES,
    CountingKado,
    _item,
    _run_main,
    _suggestions,
    _typed,
)

refusal_sentences = importlib.import_module("lib.refusal_sentences")

NEW_FOLDER = "Atlas/296 Maps"
DOWN_FOLDER = "Atlas/297 Down"

FOLDER_NEW = f"{INBOX}neu.png"
UNCHECKED = f"{INBOX}offen.png"
OCCUPIED = f"{INBOX}belegt.png"
FOLDER_REFUSED = f"{INBOX}karte.png"
BLANK_FOLDER = f"{INBOX}leer.png"
AMBIGUOUS = f"{INBOX}doppelt.png"
UNANSWERED = f"{INBOX}stumm.png"
IGNORED = f"{INBOX}egal.png"

WITHHELD = [OCCUPIED, FOLDER_REFUSED, BLANK_FOLDER]

# Executor and pipeline internals no owner-facing sentence may contain.
FORBIDDEN = [
    r"\bHashi\b", r"\bplanner\b", r"depends_on", r"\bcascade\b",
    r"\baction id\b", r"move_asset", r"delete_source", r"move_note",
    r"\bexecutor\b", r"skipped_assets", r"vault_occupied",
    r"typed_folder_refused", r"folder_created", r"qualified_reason",
    r"\bunchecked\b", r"\bunanswered\b", r"\bambiguous\b", r"\bcensus\b",
    r"render_md", r"render_actions", r"\bPass [AB]\b", r"\bK\d+\b",
    r"\bbyName\b", r"\blistDir\b", r"\blist_dir\b",
]


class FailingKado(CountingKado):
    """CountingKado whose listing of `DOWN_FOLDER` and name search for
    `stumm` fail — Kado answering with an error, not `Path not found`."""

    def list_dir(self, folder, depth=1):
        if folder.rstrip("/") == DOWN_FOLDER:
            self._record("list_dir", folder, depth)
            raise KadoError("Kado timed out")
        return super().list_dir(folder, depth)

    def _call_tool(self, tool, args):
        if tool == "kado-search" and "stumm" in (args.get("query") or ""):
            self._record("_call_tool", tool, args.get("operation"), args.get("query"))
            raise KadoError("Kado timed out")
        return super()._call_tool(tool, args)


def _blank_folder(source):
    return {
        "source": source, "remedy": "rename", "proposed_name": "leer.png",
        "name_is_owner_supplied": True,
        "proposed_dir": "", "dir_is_owner_supplied": True,
    }


@pytest.fixture
def every_kind(monkeypatch, tmp_path):
    """Render once over a vault where every new outcome happens once."""
    return render_every_kind(monkeypatch, tmp_path)


def render_every_kind(monkeypatch, tmp_path):
    """`(instructions.md, relay lines)` for the every-outcome fixture — a plain
    function so spec 039 T5.4's tests render the same document."""
    vault = [
        FOLDER_NEW, UNCHECKED, OCCUPIED, FOLDER_REFUSED, BLANK_FOLDER,
        AMBIGUOUS, UNANSWERED, IGNORED,
        f"{ASSET}/Belegt.png",          # occupies OCCUPIED's target, spelled differently in case
        "Elsewhere/doppelt.png",        # makes AMBIGUOUS's basename non-unique
        f"{ASSET}/egal.png",            # the occupier the owner chose to Ignore
    ]
    client = FailingKado(vault, existing_folders=[ASSET, NOTES])
    sources = [FOLDER_NEW, UNCHECKED, OCCUPIED, FOLDER_REFUSED, BLANK_FOLDER,
               AMBIGUOUS, UNANSWERED, IGNORED]
    items = [
        _item(f"S{i:02d}", f"Note{i}", attachments=[src])
        for i, src in enumerate(sources, start=1)
    ]
    remedies = [
        _typed(FOLDER_NEW, folder=NEW_FOLDER, name="neu.png"),
        _typed(UNCHECKED, folder=DOWN_FOLDER, name="offen.png"),
        _typed(FOLDER_REFUSED, folder="../Ausserhalb", name="karte.png"),
        _blank_folder(BLANK_FOLDER),
        {"source": IGNORED, "remedy": "ignore", "proposed_name": None},
    ]
    rc, out_dir = _run_main(monkeypatch, tmp_path, _suggestions(items, remedies), client)
    assert rc == 0
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")
    relay_path = out_dir.parent / "withheld-attachments.md"
    relay = relay_path.read_text(encoding="utf-8").splitlines() if relay_path.exists() else []
    return md, relay


def _lines_naming(md: str, source: str) -> list[str]:
    return [ln for ln in md.splitlines() if f"`{source}`" in ln]


def _move_block(md: str, source: str) -> list[str]:
    lines = md.splitlines()
    name = source.rsplit("/", 1)[-1]
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("### ") and ln.endswith(f"Move attachment: {name}"))
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("### ") or lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _withheld_bullets(md: str) -> list[str]:
    return [ln for ln in md.splitlines() if ln.startswith("- ⚠️ **Attachment not filed:**")]


def _unchecked_bullets(md: str) -> list[str]:
    return [ln for ln in md.splitlines() if ln.startswith("- ⚠️ **Target not checked:**")]


def _sentence_fn(name):
    fn = getattr(refusal_sentences, name, None)
    assert fn is not None, f"lib.refusal_sentences has no {name}"
    return fn


# ---------------------------------------------------------------------------
# F3-AC5 — the occupied target
# ---------------------------------------------------------------------------

def test_occupied_bullet_names_attachment_target_and_occupier(every_kind):
    md, _relay = every_kind
    (bullet,) = [b for b in _withheld_bullets(md) if f"`{OCCUPIED}`" in b]
    # spec 039 T5.4: the case-only occupier is not AT the target
    assert f"from the target `{ASSET}/belegt.png`" in bullet, bullet
    assert f"already holds `{ASSET}/Belegt.png`" in bullet, bullet
    assert "only in case" in bullet, bullet
    assert "attachment" in bullet, bullet
    assert "No remedy defined" not in bullet, bullet
    for line in _lines_naming(md, OCCUPIED):
        assert "a note already exists" not in line, line


def test_unchecked_target_notices_follow_the_final_actions():
    target = f"{DOWN_FOLDER}/offen.png"
    reports = {UNCHECKED: {"unchecked": True, "target": target}}
    withdrawn = unchecked_target_notices([], reports)
    assert withdrawn == [], "a move no longer in the actions must not be reported"
    move = {"action": "move_asset", "source": UNCHECKED}
    (notice,) = unchecked_target_notices([move], reports)
    assert f"`{UNCHECKED}`" in notice and f"`{target}`" in notice, notice


# ---------------------------------------------------------------------------
# F2-AC5 — the refused folder
# ---------------------------------------------------------------------------

def test_refused_folder_bullet_names_attachment_and_rule(every_kind):
    md, _relay = every_kind
    (bullet,) = [b for b in _withheld_bullets(md) if f"`{FOLDER_REFUSED}`" in b]
    rule = refusal_sentences.folder_sentence("escapes_vault", "../Ausserhalb")
    assert rule in bullet, bullet
    assert "No remedy defined" not in bullet, bullet
    assert "folder" in bullet.split(rule, 1)[1], f"remedy must name the folder: {bullet}"


@pytest.mark.parametrize("reason", sorted(FOLDER_REFUSAL_REASONS))
def test_each_folder_reason_has_its_own_sentence_in_the_notice(reason):
    folder = "Atlas/x"
    sentence = refusal_sentences.folder_sentence(reason, folder)
    others = {refusal_sentences.folder_sentence(r, folder)
              for r in FOLDER_REFUSAL_REASONS if r != reason}
    assert sentence not in others
    notice = _render_skipped_asset_notice({
        "source": FOLDER_REFUSED, "destination": None, "reason": sentence,
        "refusal_reason": reason, "kind": "typed_folder_refused",
        "owner_source_items": [f"{INBOX}Note4.md"],
    })
    assert notice.startswith(f"- ⚠️ **Attachment not filed:** `{FOLDER_REFUSED}` — {sentence}. ")
    assert "No remedy defined" not in notice, notice


def test_unreadable_folder_line_is_not_reported_as_left_blank(every_kind):
    sentence = refusal_sentences.folder_sentence("blank", "")
    assert "could not be read" in sentence, sentence
    assert "the typed folder is blank" not in sentence, sentence
    md, _relay = every_kind
    (bullet,) = [b for b in _withheld_bullets(md) if f"`{BLANK_FOLDER}`" in b]
    assert sentence in bullet, bullet


# ---------------------------------------------------------------------------
# F3-AC6 — the target nobody could check
# ---------------------------------------------------------------------------

def test_unchecked_target_is_reported_not_checked_and_never_free(every_kind):
    md, _relay = every_kind
    target = f"{DOWN_FOLDER}/offen.png"
    block = _move_block(md, UNCHECKED)
    matches = [ln for ln in block if ln.startswith("- ⚠️ **Target not checked:**")]
    assert len(matches) == 1, block
    line = matches[0]
    assert f"`{UNCHECKED}`" in line and f"`{target}`" in line, line
    assert "not checked" in line, line
    assert not re.search(r"\bfree\b", line, re.IGNORECASE), line
    assert not any("will be created" in ln for ln in block), block
    assert _unchecked_bullets(md).count(line) == 1, "listed once, in its move's block"
    # every other move is not marked unchecked
    for src in (FOLDER_NEW, AMBIGUOUS, UNANSWERED, IGNORED):
        assert not any("Target not checked" in ln for ln in _move_block(md, src)), src


# ---------------------------------------------------------------------------
# F2-AC8 — the folder to be created
# ---------------------------------------------------------------------------

def test_folder_to_be_created_is_listed(every_kind):
    md, _relay = every_kind
    block = _move_block(md, FOLDER_NEW)
    expected = "- **New folder:** " + _sentence_fn("folder_created_sentence")(NEW_FOLDER)
    assert expected in block, block
    assert f"`{NEW_FOLDER}`" in expected and "will be created on apply" in expected
    for src in (AMBIGUOUS, UNANSWERED, IGNORED):
        assert not any("New folder" in ln for ln in _move_block(md, src)), src


# ---------------------------------------------------------------------------
# Tracking table — the qualified embed
# ---------------------------------------------------------------------------

def test_qualified_embeds_are_reported_with_their_reason(every_kind):
    md, _relay = every_kind
    qualified = _sentence_fn("qualified_embed_sentence")
    ambiguous = qualified(f"{ASSET}/doppelt.png", "ambiguous")
    unanswered = qualified(f"{ASSET}/stumm.png", "unanswered")
    assert ambiguous != unanswered.replace("stumm", "doppelt")
    assert f"- **Embed written with path:** {ambiguous}" in _move_block(md, AMBIGUOUS)
    assert f"- **Embed written with path:** {unanswered}" in _move_block(md, UNANSWERED)
    assert "same name" in ambiguous, ambiguous
    assert "did not answer" in unanswered, unanswered
    # a bare embed (unique basename) carries no such line
    assert not any("Embed written with path" in ln for ln in _move_block(md, FOLDER_NEW))
    with pytest.raises(ValueError):
        qualified("a/b.png", "something_else")


# ---------------------------------------------------------------------------
# F6-AC8 — the Ignore disclosure
# ---------------------------------------------------------------------------

def test_ignore_disclosure_says_the_origin_is_kept(every_kind):
    md, _relay = every_kind
    block = "\n".join(_move_block(md, IGNORED))
    assert "you chose Ignore" in block, block
    assert "If the move fails, the source note that embeds it is kept in the inbox" in block, block
    assert "filed either way" not in block, block
    assert "left behind in the inbox" not in block, block


# ---------------------------------------------------------------------------
# 038 C1 — the shell relay
# ---------------------------------------------------------------------------

def test_relay_carries_one_line_per_withheld_and_per_unchecked(every_kind):
    md, relay = every_kind
    expected = _withheld_bullets(md) + _unchecked_bullets(md)
    assert relay == expected, relay
    for src in WITHHELD:
        assert sum(f"`{src}`" in ln for ln in relay) == 1, (src, relay)
    assert sum(f"`{UNCHECKED}`" in ln for ln in relay) == 1, relay
    assert len(relay) == len(WITHHELD) + 1
    for ln in relay:
        assert not re.search(r"\b\d+ (attachments?|targets?)\b", ln), ln


# ---------------------------------------------------------------------------
# No executor internals
# ---------------------------------------------------------------------------

def _new_sentences(md: str) -> list[str]:
    picked = _withheld_bullets(md) + _unchecked_bullets(md)
    picked += [ln for ln in md.splitlines()
               if ln.startswith(("- **New folder:**", "- **Embed written with path:**",
                                 "- ⚠️ **Destination was occupied:**"))]
    return picked


def test_no_executor_internals_in_any_new_sentence(every_kind):
    md, relay = every_kind
    lines = _new_sentences(md) + relay
    assert len(_new_sentences(md)) >= 8, _new_sentences(md)
    for line in lines:
        text = re.sub(r"`[^`]*`", "``", line)
        for pattern in FORBIDDEN:
            assert not re.search(pattern, text), (pattern, line)


# ---------------------------------------------------------------------------
# The conductor (runtime prompt) and its WHY mirror
# ---------------------------------------------------------------------------

CONDUCTOR = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "synthesis-conductor.md"
CONDUCTOR_WHY = REPO_ROOT / "docs" / "tomo" / "dot_claude" / "agents" / "synthesis-conductor.md"


def test_conductor_relays_unchecked_lines_and_passes_cost_history():
    text = CONDUCTOR.read_text(encoding="utf-8")
    render_call = text.split("python3 scripts/instruction-render.py", 1)[1].split("```", 1)[0]
    assert "--cost-history state/inbox-cost-history.jsonl" in render_call, render_call
    step4 = text.split("### Step 4", 1)[1].split("## What you never do", 1)[0]
    assert "could not be checked" in step4, step4
    version = re.search(r"^# version: (\d+)\.(\d+)\.(\d+)$", text, re.MULTILINE)
    assert version and tuple(int(v) for v in version.groups()) > (0, 21, 0)


def test_conductor_mirror_records_the_unchecked_relay_decision():
    text = CONDUCTOR_WHY.read_text(encoding="utf-8")
    marker = "## Step 4 Also Relays Attachment Targets That Could Not Be Checked (spec 039 T5.1"
    assert marker in text, "WHY section for the unchecked relay is missing"
    section = text.split(marker, 1)[1].split("\n## ", 1)[0]
    assert "free" in section and "--cost-history" in section, section
