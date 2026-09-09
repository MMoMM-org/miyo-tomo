#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t2_2_analyst_contract.py — inbox-analyst.md carries item_key end to end.

Covers T2.2 (XDD 034 Phase 2): T2.4 made `--item-key` a required argument of
state-update.py, but inbox-analyst.md (the LLM-loaded agent spec that invokes it)
never passed the flag — every analyst dispatch died at argparse on a live /inbox
run. This also carries the identity split (ADR-1/ADR-2) into the analyst's own
IO Contract and output-file naming: `stem` stays a bare, display-only filename;
`item_key` (the vault-relative path) becomes the join key and the source of the
per-item result filename (`lib.item_key.to_filename`), so two inbox items that
share a filename in different subfolders no longer collide on one result file.

`tomo/dot_claude/agents/inbox-analyst.md` is LLM-loaded markdown, not Python —
there is no function to call, so these tests operate on the markdown source
directly: parsing out the `state-update.py` invocation blocks (static scan,
CON-5), checking the IO Contract's declared input list, and checking that the
new output-path instruction still resolves to what `lib.item_key.to_filename`
would produce for the same key (the actual round-trip artifact both the
analyst and the reducer must agree on).

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
AGENT_PATH = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
DOC_PATH = REPO_ROOT / "docs" / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))
from lib.item_key import to_filename  # noqa: E402


def _agent_text() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.DOTALL)


def _state_update_invocation_blocks(text: str) -> list[str]:
    """Every fenced bash block that invokes state-update.py.

    Asserting against the whole file (`"--item-key" in text`) would pass even
    if the flag only appeared once, in an unrelated block, or in prose. We
    need every one of the four call sites (Step 0, Step 2b, Step 11 x2) to
    carry the flag in its own invocation.
    """
    blocks = [b for b in _bash_blocks(text) if "state-update.py" in b]
    assert blocks, "expected at least one state-update.py invocation block"
    return blocks


# ---------------------------------------------------------------------------
# The blocking bug: every state-update.py call site must pass --item-key
# ---------------------------------------------------------------------------


def test_every_state_update_invocation_passes_item_key():
    blocks = _state_update_invocation_blocks(_agent_text())
    assert len(blocks) == 4, (
        f"expected 4 state-update.py invocation blocks (Step 0, Step 2b, "
        f"Step 11 done, Step 11 failed), found {len(blocks)}"
    )
    for i, block in enumerate(blocks):
        assert "--item-key" in block, (
            f"state-update.py invocation #{i + 1} is missing --item-key:\n{block}"
        )


def test_item_key_flag_is_not_reconstructed_from_stem():
    """The task is explicit: item_key IS `path` (identity fn) — never derive it
    from `stem`. A naive fix might invent `--item-key "<stem>"`, which silently
    reintroduces the exact collision T2.4 closed (two items sharing a stem would
    share a state-file join key again).
    """
    for block in _state_update_invocation_blocks(_agent_text()):
        assert '--item-key "<stem>"' not in block
        assert "--item-key" not in block or re.search(
            r'--item-key\s+"<(item_key|path)>"', block
        ), f"--item-key must use <item_key> or <path> (identity), not stem:\n{block}"


def test_no_other_runtime_file_invokes_state_update_unflagged():
    """Sweep tomo/dot_claude and tomo/skills for other state-update.py callers.

    inbox-analyst.md is the only LLM-loaded caller; suggestion-conductor.md and
    the suggest-handling / force-atomic-handling skills dispatch analysts but
    never call state-update.py themselves.
    """
    runtime_roots = [REPO_ROOT / "tomo" / "dot_claude", REPO_ROOT / "tomo" / "skills"]
    callers = []
    for root in runtime_roots:
        if not root.exists():
            continue
        for f in root.rglob("*.md"):
            if "state-update.py" in f.read_text(encoding="utf-8"):
                callers.append(f)
    assert callers == [AGENT_PATH], (
        f"expected inbox-analyst.md as the sole runtime caller of state-update.py, "
        f"found: {callers}"
    )


# ---------------------------------------------------------------------------
# IO Contract gains item_key (ADR-2: stem stays display-only)
# ---------------------------------------------------------------------------


def test_io_contract_declares_item_key_input():
    text = _agent_text()
    contract_start = text.index("## IO Contract")
    contract_end = text.index("## Workflow")
    contract = text[contract_start:contract_end]
    assert "`item_key`" in contract, "IO Contract input list must declare item_key"
    # stem is retained as a distinct, still-declared input (ADR-2) — the fix
    # must not collapse the two concepts back into one.
    assert "`stem`" in contract


# ---------------------------------------------------------------------------
# Output path: the analyst must write under lib.item_key.to_filename(item_key)
# ---------------------------------------------------------------------------


def test_result_filename_helper_wraps_the_real_encoding():
    """item-result-filename.py (the CLI the analyst runs to name its own output
    file) must print exactly what lib.item_key.to_filename returns — not a
    reimplementation that could drift from the reducer's future lookup.
    """
    helper = SCRIPTS_DIR / "item-result-filename.py"
    assert helper.exists(), "expected tomo/scripts/item-result-filename.py"
    item_key = "100 Inbox/Places/Dresden.md"
    proc = subprocess.run(
        [sys.executable, str(helper), "--item-key", item_key],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == to_filename(item_key)


def test_step_10_writes_to_the_item_key_filename_not_bare_stem():
    text = _agent_text()
    step10 = text[text.index("### Step 10 —"): text.index("### Step 10b")]
    assert "item-result-filename.py" in step10, (
        "Step 10 must compute the output filename via the shared helper, not "
        "hand-assemble <stem>.result.json"
    )
    assert "<stem>.result.json" not in step10.replace("<items_dir>/<stem>.result.json", "")
    # The literal old instruction must be gone, not merely supplemented.
    assert "Write` tool to\n```\n<items_dir>/<stem>.result.json" not in step10


def test_template_carries_item_key_placeholder():
    template_path = REPO_ROOT / "tomo" / "templates" / "item-result.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template.get("item_key") == "<ITEM_KEY>"


# ---------------------------------------------------------------------------
# Round-trip: a fixture written under to_filename(item_key) is the artifact
# the reducer must key on. T2.3 wired the reducer's *lookup* to this filename;
# the second test below is the read-side half of the same round-trip.
# ---------------------------------------------------------------------------


def test_fixture_written_under_item_key_filename_is_self_discoverable(tmp_path):
    """Anyone holding the item_key (the reducer included) can deterministically
    reconstruct the filename the analyst wrote and find the file — no directory
    listing, no stem-based guess.
    """
    item_key = "100 Inbox/Places/Dresden.md"
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    fixture = {
        "schema_version": "1",
        "stem": "Dresden",
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.5,
        "actions": [],
    }
    result_path = items_dir / to_filename(item_key)
    result_path.write_text(json.dumps(fixture), encoding="utf-8")

    rediscovered_path = items_dir / to_filename(item_key)
    assert rediscovered_path.exists()
    assert json.loads(rediscovered_path.read_text(encoding="utf-8")) == fixture


def test_reducer_lookup_is_item_key_aware():
    """The read side of the round-trip above (T2.3, now landed).

    T2.2 left this as an `xfail(strict=True)` asserting the bare-stem lookup was
    still present, so that removing it would turn into a hard failure and force
    the test to be updated rather than silently going stale. T2.3 removed it, so
    this is now the positive assertion: the reducer names the result file the
    same way the analyst does, through `lib.item_key.to_filename`.
    """
    reducer_source = REDUCER_PATH.read_text(encoding="utf-8")
    stem_keyed_lookups = re.findall(r'items_dir / f"\{stem\}\.result\.json"', reducer_source)
    assert stem_keyed_lookups == [], (
        "suggestions-reducer.py is keying a result lookup on the bare stem again "
        "— two items sharing a filename would overwrite each other's result file"
    )
    assert "item_key_to_filename(item_key)" in reducer_source, (
        "the reducer must derive the result filename through lib.item_key.to_filename"
    )
