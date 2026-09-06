#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_7_diff_keys_on_item_key.py — instructions-diff.py's coverage
audit must key identity on item_key (the vault-relative path, ADR-1), not a
bare filename stem.

Spec 034 (recursive inbox discovery), Phase 2 T2.7. Before this fix,
`derive_expected` and `summarize_actual` both flattened identity to a bare
stem, so two confirmed items sharing a filename in different subfolders
collapsed onto the same dict/set entry on BOTH sides. That is a false
**pass** waiting to happen: a real defect (a duplicated or missing action
for one of the two items) can hide behind the other item's presence.

Fixtures are hand-built instructions.json actions rather than routed through
the real renderer (`lib/render_actions.py`) — that module has its own,
separately-scoped stem-based dedup for delete_source pairing (out of this
task's file ownership) and would confound a test of instructions-diff.py's
own identity handling. CON-7: fixtures/fakes only, no live vault run.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec_diff = importlib.util.spec_from_file_location(
    "instructions_diff", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec_diff)
assert _spec_diff.loader is not None
_spec_diff.loader.exec_module(diff)


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _run(parsed: dict, instrs: dict) -> tuple[int, list[str], str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs, buf.getvalue()


def _confirmed(item_id: str, source_path: str, title: str) -> dict:
    return {
        "id": item_id, "source_path": source_path, "action": None,
        "title": title, "tags": [], "parent_moc": "", "parent_mocs": [],
    }


def _move_note_action(action_id: str, source_inbox_item: str, title: str) -> dict:
    return {
        "id": action_id, "action": "move_note",
        "source": f"tomo-tmp/rendered/{action_id}.md",
        "destination": "Atlas/202 Notes/",
        "title": title,
        "rendered_file": f"{action_id}.md",
        "source_inbox_item": source_inbox_item,
        "audio_peer": None,
        "parent_mocs": [],
        "tags": [],
    }


def _delete_source_action(action_id: str, source_path: str) -> dict:
    return {
        "id": action_id, "action": "delete_source",
        "source_path": source_path,
        "reason": "Content moved to an atomic note.",
    }


def _instrs(actions: list[dict]) -> dict:
    return {
        "schema_version": "1", "type": "tomo-instructions",
        "action_count": len(actions), "actions": actions,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Case 1 — two same-named items produce a count of two on both sides
# ──────────────────────────────────────────────────────────────────────────────

def test_two_same_named_items_in_different_subfolders_produce_count_of_two():
    """Two confirmed items named 'Dresden.md' living in different subfolders
    (Places/, Other/) — a genuine, fully-correct render (2 move_note + 2
    delete_source actions, one pair per item) must reconcile as 2/2 on
    BOTH the move_note and delete_source rows, and both items must show
    file=[OK] individually [ref: PRD/AC Feature 2]."""
    confirmed = [
        _confirmed("S01", "Places/Dresden.md", "Dresden — Frauenkirche"),
        _confirmed("S02", "Other/Dresden.md", "Dresden — a different note"),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    actions = [
        _move_note_action("a1", "Places/Dresden.md", "Dresden — Frauenkirche"),
        _move_note_action("a2", "Other/Dresden.md", "Dresden — a different note"),
        _delete_source_action("d1", "Places/Dresden.md"),
        _delete_source_action("d2", "Other/Dresden.md"),
    ]
    instrs = _instrs(actions)

    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_note"] == 2,
          f"expected move_note count must be 2, got {expected['counts']['move_note']}")
    _must(expected["counts"]["delete_source"] == 2,
          f"expected delete_source count must be 2 (one per subfolder-distinct "
          f"item), got {expected['counts']['delete_source']} — a stem-keyed "
          f"dedup would collapse this to 1")

    rc, obs, out = _run(parsed, instrs)
    _must(rc == 0, f"two correctly-rendered same-named items must reconcile, got rc={rc}\n{out}")
    _must(obs == [], f"no observations expected, got {obs}")
    _must("  move_note           " in out and "2         2  [OK]" in out.replace("\n", " "),
          f"move_note row must show 2/2 [OK]:\n{out}")
    _must("  delete_source       " in out,
          f"delete_source row must be present:\n{out}")

    # Per-item coverage: BOTH items must show file=[OK] individually, proving
    # neither is silently riding on the other's presence.
    lines = [ln for ln in out.splitlines() if "S01" in ln or "S02" in ln]
    _must(len(lines) == 2, f"expected 2 per-item coverage lines, got: {lines}")
    for ln in lines:
        _must("file=[OK]" in ln, f"expected file=[OK] for both items, got: {ln}")
    print("[PASS] two same-named items (different subfolders) reconcile 2/2 on both sides")


# ──────────────────────────────────────────────────────────────────────────────
# Case 2 — a genuine mismatch is still caught (negative control)
# ──────────────────────────────────────────────────────────────────────────────

def test_genuine_missing_item_still_caught_among_same_named_items():
    """Same two same-named items as above, but this time only ONE of the two
    real move_note actions actually exists (S02's was never rendered — a
    genuine defect). The fix must not blunt the audit: S01 (present) shows
    [OK], S02 (missing) must show [MISSING], and the run must hard-fail.
    Before the fix, both would show [OK] because 'Dresden' as a bare stem
    resolves to whichever action last wrote the shared dict entry."""
    confirmed = [
        _confirmed("S01", "Places/Dresden.md", "Dresden — Frauenkirche"),
        _confirmed("S02", "Other/Dresden.md", "Dresden — a different note"),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    # Only S01's move_note is present; S02's was dropped by a renderer defect.
    actions = [
        _move_note_action("a1", "Places/Dresden.md", "Dresden — Frauenkirche"),
    ]
    instrs = _instrs(actions)

    rc, obs, out = _run(parsed, instrs)
    _must(rc == 1, f"a genuinely missing item must hard-fail, got rc={rc}\n{out}")

    lines = {ln.split()[0]: ln for ln in out.splitlines() if ln.strip().split(":")[:1] and (
        ln.strip().startswith("S01") or ln.strip().startswith("S02")
    )}
    _must("S01" in lines, f"S01 per-item line missing from output:\n{out}")
    _must("S02" in lines, f"S02 per-item line missing from output:\n{out}")
    _must("file=[OK]" in lines["S01"], f"S01 (present) must show file=[OK]: {lines['S01']}")
    _must("file=[MISSING]" in lines["S02"],
          f"S02 (never rendered) must show file=[MISSING], not silently pass "
          f"on S01's presence: {lines['S02']}")
    print("[PASS] a genuinely missing item among same-named items is still caught, not blunted")


# ──────────────────────────────────────────────────────────────────────────────
# Case 3 — existing single-item audits are unchanged
# ──────────────────────────────────────────────────────────────────────────────

def test_single_item_flat_inbox_audit_unchanged():
    """A single, ordinary flat-inbox item (bare filename, no subfolder) must
    keep reconciling exactly as before. The actual side's source_inbox_item
    carries the renderer's inbox-path prefix (e.g. '100 Inbox/A.md') while
    the confirmed item's source_path does not ('A.md') — the item_key match
    must still bridge that gap for the single-item, no-collision case."""
    confirmed = [_confirmed("S01", "A.md", "A")]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    actions = [
        _move_note_action("a1", "100 Inbox/A.md", "A"),
        _delete_source_action("d1", "100 Inbox/A.md"),
    ]
    instrs = _instrs(actions)

    rc, obs, out = _run(parsed, instrs)
    _must(rc == 0, f"single flat-inbox item must reconcile, got rc={rc}\n{out}")
    _must(obs == [], f"no observations expected, got {obs}")
    _must("file=[OK]" in out, f"single item must show file=[OK]:\n{out}")
    print("[PASS] single-item, flat-inbox audit is unchanged")


def main() -> int:
    test_two_same_named_items_in_different_subfolders_produce_count_of_two()
    test_genuine_missing_item_still_caught_among_same_named_items()
    test_single_item_flat_inbox_audit_unchanged()
    print("\n✓ All T2.7 item_key coverage-audit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
