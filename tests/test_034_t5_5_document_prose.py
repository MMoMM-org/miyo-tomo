#!/usr/bin/env python3
# version: 1.0.0
"""test_034_t5_5_document_prose.py — spec 034 T5.5.

Two sentences in the rendered instruction document that contradict either the
line beneath them or the vault the user is about to act on. Both passed 3596
tests and six review gates; reading the document as prose found them.

  1. Every `delete_source` heading claimed the same cause. `render_md`
     hardcoded "(content captured in daily note)" while the body underneath
     read "Origin consumed by 1 atomic." Five emission sites give `reason`
     five causes, so four in five deletes were headed wrongly. Under CON-2 the
     user approves deletions on this document, so a heading may not contradict
     the line beneath it. Pre-existing — introduced by the #113 refactor
     (`6d15fa9`), same class as the heading defect T5.3 corrected in `76ae8be`.
  2. The vault-collision sentence named one path twice. The two-path phrasing
     informs only when the two differ (the case-only collision); on an exact
     match — the common case — it reads like a rendering bug.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    make_folder_listing,
    validate_destinations,
)
from lib.render_md import render_instructions_md  # noqa: E402

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
ASSETS = "Atlas/290 Assets/295 Attachments/"

ROOT_NOTE = "100 Inbox/Root Note.md"
ELBE = "100 Inbox/Elbe.md"


CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSETS,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


class FakeKado:
    """`list_dir` only — the one call the vault half of the guard makes."""

    def __init__(self, occupied: set[str] | None = None):
        self.occupied = occupied or set()

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500):
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _atomic(item_key: str, title: str, *, idx: int, parents: list[str] | None = None,
            attachments: list[str] | None = None,
            location: str = NOTES) -> tuple[dict, dict]:
    """One manifest entry + its confirmed item, as instruction-render pairs them."""
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-07_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "tags": [],
        "attachments": list(attachments or []),
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "attachments": list(attachments or []),
    }
    return manifest, confirmed


def _build(pairs: list[tuple[dict, dict]], **kw) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _render(actions, clashes=None, suppressions=None, **kw) -> str:
    return render_instructions_md(
        actions,
        {
            "run_id": "t5-5",
            "generated": "2026-09-07T14:04:49Z",
            "profile": "miyo",
            "sources": [{"path": "100 Inbox/_suggestions.md"}],
            "destination_clashes": clashes or [],
            "attachment_suppressions": suppressions or [],
            **kw,
        },
        CFG,
    )


# ---------------------------------------------------------------------------
# 1. A delete heading may not claim a cause the body contradicts
# ---------------------------------------------------------------------------

def _delete_headings(md: str) -> list[str]:
    return [ln for ln in md.splitlines() if ln.startswith("### ") and "Delete" in ln]


def test_an_origin_consumed_delete_is_not_headed_as_a_daily_capture():
    actions, _ = _build([_atomic(ROOT_NOTE, "Root note takeaway", idx=1)])
    md = _render(actions)
    body = [ln for ln in md.splitlines() if ln.startswith("- **Action:**")]
    assert any("Origin consumed by 1 atomic" in ln for ln in body), body
    headings = _delete_headings(md)
    assert len(headings) == 1, headings
    assert "content captured in daily note" not in headings[0], (
        "the heading claimed a cause the line beneath it contradicts: "
        f"{headings[0]!r} over {body!r}"
    )


def test_the_delete_heading_names_the_note_being_deleted():
    actions, _ = _build([_atomic(ROOT_NOTE, "Root note takeaway", idx=1)])
    headings = _delete_headings(_render(actions))
    assert headings[0].endswith("Delete source note: Root Note"), (
        "every other section heading names its subject (`Move note: …`, "
        f"`Skip — …`); the delete section is the index of what leaves: {headings}"
    )


def test_a_daily_capture_delete_states_its_cause_once():
    """The cause belongs on the Action line only — one statement cannot
    contradict itself, two can."""
    daily = [{
        "date": "2026-09-07",
        "log_entries": [{
            "accepted": True, "source_stem": "Notiz",
            "source_item_key": "100 Inbox/Notiz.md",
            "content": "ring the dentist", "time": "09:00",
        }],
    }]
    actions, _ = _build([], daily_updates=daily)
    md = _render(actions)
    headings = _delete_headings(md)
    assert len(headings) == 1, headings
    assert "content captured in daily note" not in headings[0], headings
    assert "Content fully captured in daily note." in md, md


# ---------------------------------------------------------------------------
# 2. The vault-collision sentence names two paths only when they differ
# ---------------------------------------------------------------------------

def _clash_reason(occupied: set[str], title: str = "Elbe") -> str:
    pairs = [_atomic(ELBE, title, idx=1)]
    _kept, clashes = validate_destinations(
        _build(pairs)[0], make_folder_listing(FakeKado(occupied))
    )
    assert len(clashes) == 1, clashes
    return clashes[0]["reason"]


def test_an_exact_vault_collision_names_the_path_once():
    reason = _clash_reason({f"{NOTES}Elbe.md"})
    assert reason.count(f"`{NOTES}Elbe.md`") == 1, (
        "the same path twice in one sentence reads like a rendering bug: "
        f"{reason!r}"
    )
    assert reason == (
        f"a note already exists at `{NOTES}Elbe.md` — this item is not filed."
    ), reason


def test_a_case_only_vault_collision_still_names_both_spellings():
    reason = _clash_reason({f"{NOTES}elbe.md"})
    assert f"`{NOTES}elbe.md`" in reason and f"`{NOTES}Elbe.md`" in reason, (
        "here the two paths differ, and the user must see both to know which "
        f"name the vault holds: {reason!r}"
    )
    assert "differ only in case" in reason, reason
