#!/usr/bin/env python3
# version: 0.1.0
"""Regression guard for #165 — Force Atomic on a suppressed per-item block.

#88 gave sub-0.5-worthiness items a light "kept in inbox" block with a
Force Atomic Note escape hatch. XDD 012 gave force-atomic'd items a
resolve subflow: Pass 2 proposes a full atomic in a companion fan doc, the
user approves it, and the next Pass 2 merges it back.

Those two features were never joined. The XDD 012 reconciliation loop is
driven exclusively by daily-note log entries, so a suppressed per-item
block never reaches its resolve-doc branch and is re-parked on every run —
a livelock the user cannot leave, reported as "you left its Approve box
unticked" while the box is ticked.

Also covers #161: `_promote_entry` built its entry field-by-field and
omitted `attachments` and `audio_peer`, both present in the canonical
confirmed-item shape. Wiring the resolve branch without that fix would
confirm the note while discarding its attachment — filing the note and
orphaning its image, the exact failure spec 031 exists to prevent.

The suppressed block is produced by the real renderer rather than
hand-written markdown, so the parser is fed what the reducer actually
emits.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER = REPO_ROOT / "tomo" / "scripts" / "suggestion-parser.py"
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer_165", "suggestions-reducer.py")


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

def _suppressed_block(stem: str, *, ticked: bool, date_suffix: bool = False) -> str:
    """The light block for a sub-0.5 item, rendered by the real reducer.

    `ticked` checks the Force Atomic box the way a user would; `date_suffix`
    additionally appends the completion date Obsidian's Tasks plugin writes,
    which is what the live document carried.
    """
    md = _reducer.render_suppressed_atomic(
        {
            "kind": "create_atomic_note",
            "suggested_title": stem,
            "atomic_note_worthiness": 0.4,
            "stem": stem,
            "suppressed": True,
        },
        stem,
    )
    if ticked:
        box = "- [x] Force Atomic Note (create a standalone note for this item)"
        if date_suffix:
            box += " ✅ 2026-09-05"
        md = md.replace(
            "- [ ] Force Atomic Note (create a standalone note for this item)", box
        )
    return md


def _primary_doc(stem: str, *, ticked: bool, date_suffix: bool = False) -> str:
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-05T14:45:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-09-05T14-41-53Z-test165",
        "---",
        "",
        "# Inbox Suggestions — 2026-09-05",
        "",
        "- [x] Approved — check this box when you have finished reviewing, "
        "then run `/inbox` for Pass 2",
        "",
        "## Summary",
        "",
        "- Items processed: 1",
        "- Sections: 1",
        "",
        "## Suggestions",
        "",
        f"### S01 — {stem}",
        _suppressed_block(stem, ticked=ticked, date_suffix=date_suffix),
        "",
    ])


def _resolve_doc(
    stem: str,
    *,
    approved: bool = True,
    attachments: str | None = None,
    audio_peer: str | None = None,
) -> str:
    source = f"[[{stem}]]" + (f" + [[{audio_peer}]]" if audio_peer else "")
    lines = [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-05T15:05:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-09-05T15-03-03Z-test165",
        "tomo:",
        "  doc_type: suggestions-fan",
        "---",
        "",
        "# Inbox Suggestions — Force-Atomic Resolve — 2026-09-05",
        "",
        "- [x] Approved",
        "",
        "## Summary",
        "",
        "- Items processed: 1",
        "",
        "## Suggestions",
        "",
        f"### S01 — {stem} resolved",
        "",
        f"**Source:** {source}",
        f"**Suggested name:** {stem} resolved",
        "**Template:** [[t_note_tomo]]",
        "**Location:** [[Atlas/202 Notes/]]",
    ]
    if attachments:
        lines.append(f"**Attachments:** `{attachments}`")
    lines += [
        "",
        f"**Summary:** Resolved atomic proposal for {stem}.",
        "",
        "**Decision (atomic note):**",
        f"- [{'x' if approved else ' '}] Approve",
        "- [ ] Keep source files",
        "",
    ]
    return "\n".join(lines)


def _run_parser(tmp_path: Path, primary: str, resolve: str | None) -> dict:
    ppath = tmp_path / "2026-09-05_1445_suggestions.md"
    ppath.write_text(primary, encoding="utf-8")
    cmd = [sys.executable, str(PARSER), "--file", str(ppath)]
    if resolve is not None:
        rpath = tmp_path / "2026-09-05_1505_suggestions-fan.md"
        rpath.write_text(resolve, encoding="utf-8")
        cmd += ["--fan-resolve-file", str(rpath)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"parser exit {proc.returncode}\n{proc.stderr}"
    return json.loads(proc.stdout)


def _stems(entries: list[dict]) -> list[str]:
    return [(e.get("source_path") or "").rsplit("/", 1)[-1] for e in entries]


# ──────────────────────────────────────────────────────────────────────
# #165 — the livelock
# ──────────────────────────────────────────────────────────────────────

def test_suppressed_force_atomic_promotes_from_resolve_doc(tmp_path):
    """The approved resolve-doc proposal must be consumed, not re-parked."""
    out = _run_parser(
        tmp_path,
        _primary_doc("Bautzen", ticked=True),
        _resolve_doc("Bautzen", attachments="100 Inbox/Images/bautzen-turm.jpg"),
    )
    assert _stems(out["confirmed_items"]) == ["Bautzen"], (
        "suppressed item with an approved resolve proposal was not confirmed"
    )
    assert out["pending_fan_resolutions"] == [], (
        "the stem was re-parked despite an approved resolve proposal — livelock"
    )


def test_completion_date_suffix_does_not_break_promotion(tmp_path):
    """Obsidian's Tasks plugin appends `✅ YYYY-MM-DD` to a ticked box."""
    out = _run_parser(
        tmp_path,
        _primary_doc("Bautzen", ticked=True, date_suffix=True),
        _resolve_doc("Bautzen", attachments="100 Inbox/Images/bautzen-turm.jpg"),
    )
    assert _stems(out["confirmed_items"]) == ["Bautzen"]
    assert out["pending_fan_resolutions"] == []


def test_unapproved_resolve_section_still_parks(tmp_path):
    """An un-ticked Approve in the resolve doc is not consent — keep parking.

    This is the state the user is genuinely in before they approve, and the
    message about the unticked box is correct here.
    """
    out = _run_parser(
        tmp_path,
        _primary_doc("Bautzen", ticked=True),
        _resolve_doc("Bautzen", approved=False),
    )
    assert out["confirmed_items"] == []
    assert [p["stem"] for p in out["pending_fan_resolutions"]] == ["bautzen"]


def test_no_resolve_doc_still_parks(tmp_path):
    """First pass: no companion doc yet, so parking is the correct outcome."""
    out = _run_parser(tmp_path, _primary_doc("Bautzen", ticked=True), None)
    assert out["confirmed_items"] == []
    assert [p["stem"] for p in out["pending_fan_resolutions"]] == ["bautzen"]


def test_unticked_force_atomic_is_untouched(tmp_path):
    """A suppressed item nobody force-atomic'd stays skipped, resolve or not."""
    out = _run_parser(
        tmp_path,
        _primary_doc("Bautzen", ticked=False),
        _resolve_doc("Bautzen", attachments="100 Inbox/Images/bautzen-turm.jpg"),
    )
    assert out["confirmed_items"] == []
    assert out["pending_fan_resolutions"] == []


# ──────────────────────────────────────────────────────────────────────
# #161 — the field drop that makes the fix above safe
# ──────────────────────────────────────────────────────────────────────

def test_promoted_entry_carries_attachments(tmp_path):
    """Without this the note is filed and its image is orphaned in the inbox."""
    out = _run_parser(
        tmp_path,
        _primary_doc("Bautzen", ticked=True),
        _resolve_doc("Bautzen", attachments="100 Inbox/Images/bautzen-turm.jpg"),
    )
    assert out["confirmed_items"][0]["attachments"] == [
        "100 Inbox/Images/bautzen-turm.jpg"
    ]


def test_promoted_entry_carries_audio_peer(tmp_path):
    """`audio_peer` is dropped by the same omission — assert it survives too."""
    out = _run_parser(
        tmp_path,
        _primary_doc("Memo", ticked=True),
        _resolve_doc("Memo", audio_peer="memo.m4a"),
    )
    assert out["confirmed_items"][0]["audio_peer"] == "memo.m4a"


def test_promoted_entry_has_no_attachments_key_missing(tmp_path):
    """Absent attachments must be [] — the canonical shape, not a missing key.

    instruction-render reads `item.get("attachments", [])`, so a missing key
    would not crash; it would silently behave like an empty list and hide a
    regression in the two assertions above.
    """
    out = _run_parser(
        tmp_path, _primary_doc("Memo", ticked=True), _resolve_doc("Memo")
    )
    entry = out["confirmed_items"][0]
    assert "attachments" in entry and entry["attachments"] == []
    assert "audio_peer" in entry
