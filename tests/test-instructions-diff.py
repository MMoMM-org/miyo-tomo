#!/usr/bin/env python3
# version: 0.2.0
"""test-instructions-diff.py — Unit tests for instructions-diff.

Covers:
  - Happy path: matching parsed-suggestions.json + instructions.json → exit 0
  - Count mismatch: missing instruction → exit 1
  - Link mismatch: wrong parent_mocs coverage → exit 1
  - Orphan create_moc observation (warning, not fail)
  - Daily-only delete-source inference reconciles on both sides

Each test builds in-memory dicts, invokes run_diff, and asserts exit code
+ observation count. We capture stdout so test output stays clean.
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

# Also need access to instruction-render for realistic actions[] generation
_spec_diff = importlib.util.spec_from_file_location(
    "instructions_diff", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec_diff)
assert _spec_diff.loader is not None
_spec_diff.loader.exec_module(diff)

_spec_ir = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec_ir)
assert _spec_ir.loader is not None
_spec_ir.loader.exec_module(ir)


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _run(parsed: dict, instrs: dict) -> tuple[int, list[str], str]:
    """Run diff and capture output. Returns (rc, observations, stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs, buf.getvalue()


CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _build_instrs_from(manifest, confirmed, daily_updates, skipped):
    """Use instruction-render's build_actions so tests exercise the real producer."""
    actions = ir.build_actions(manifest, confirmed, daily_updates, skipped, CFG)
    return {
        "schema_version": "1",
        "type": "tomo-instructions",
        "action_count": len(actions),
        "actions": actions,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_happy_path_reconciles():
    confirmed = [
        {
            "id": "S01", "source_path": "Asahikawa.md", "action": None,
            "title": "Asahikawa — Snow city",
            "tags": [], "parent_moc": "Japan (MOC)",
            "parent_mocs": ["Japan (MOC)"],
        },
        {
            "id": "S02", "source_path": "Catan.md", "action": None,
            "title": "Catan Strategy", "tags": [],
            "parent_moc": "", "parent_mocs": [],
        },
    ]
    manifest = [
        {
            "id": "S01", "action": None,
            "title": "Asahikawa — Snow city",
            "source_path": "Asahikawa.md",
            "rendered_file": "2026-04-21_1200_asahikawa-snow-city.md",
            "destination": "Atlas/202 Notes/",
            "parent_moc": "Japan (MOC)",
            "parent_mocs": ["Japan (MOC)"],
            "tags": [],
        },
        {
            "id": "S02", "action": None,
            "title": "Catan Strategy",
            "source_path": "Catan.md",
            "rendered_file": "2026-04-21_1200_catan-strategy.md",
            "destination": "Atlas/202 Notes/",
            "parent_moc": "",
            "parent_mocs": [],
            "tags": [],
        },
    ]
    parsed = {
        "confirmed_items": confirmed,
        "daily_updates": [],
        "skipped": [],
    }
    instrs = _build_instrs_from(manifest, confirmed, [], [])

    rc, obs, _ = _run(parsed, instrs)
    _must(rc == 0, f"happy path must reconcile, got rc={rc}")
    _must(obs == [], f"no observations expected, got {obs}")
    print("[PASS] happy path: counts + per-item coverage reconcile → exit 0")


def test_missing_instruction_fails():
    """Drop an action from instructions — diff must flag hard fail."""
    confirmed = [
        {"id": "S01", "source_path": "A.md", "action": None,
         "title": "A", "tags": [], "parent_moc": "", "parent_mocs": []},
    ]
    manifest = [{
        "id": "S01", "action": None, "title": "A",
        "source_path": "A.md",
        "rendered_file": "2026-04-21_1200_a.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "", "parent_mocs": [], "tags": [],
    }]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    # Hand-build instructions.json WITHOUT the move_note action
    instrs = {
        "schema_version": "1",
        "type": "tomo-instructions",
        "action_count": 0,
        "actions": [],
    }
    rc, _, out = _run(parsed, instrs)
    _must(rc == 1, f"missing action must fail, got rc={rc}")
    _must("[DIFF]" in out, "output must contain [DIFF] marker")
    _must("[MISSING]" in out, "per-item line must flag file=[MISSING]")
    print("[PASS] missing instruction → rc=1, [DIFF] + [MISSING] in output")


def test_link_mismatch_fails():
    """Suggestion says parent_moc=X but instructions link to Y."""
    confirmed = [{
        "id": "S01", "source_path": "A.md", "action": None,
        "title": "A", "tags": [],
        "parent_moc": "Japan (MOC)", "parent_mocs": ["Japan (MOC)"],
    }]
    manifest = [{
        "id": "S01", "action": None, "title": "A",
        "source_path": "A.md",
        "rendered_file": "2026-04-21_1200_a.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "Japan (MOC)",
        "parent_mocs": ["Japan (MOC)"],
        "tags": [],
    }]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    # Build real actions, then tamper: swap the link target
    instrs = _build_instrs_from(manifest, confirmed, [], [])
    for a in instrs["actions"]:
        if a["action"] == "link_to_moc":
            a["target_moc"] = "Wrong (MOC)"  # tamper
    rc, _, out = _run(parsed, instrs)
    _must(rc == 1, f"link mismatch must fail, got rc={rc}")
    _must("want=['Japan (MOC)']" in out or "want=['Japan (MOC)']" in out,
          "diff must show want= with expected target")
    _must("got=['Wrong (MOC)']" in out, "diff must show got= with tampered target")
    print("[PASS] wrong link_to_moc target → rc=1 with want/got diagnostic")


def test_supporting_items_expansion_reconciles():
    """create_moc with supporting_items must produce link_to_moc actions from
    each supporting atomic note into the new MOC — and the diff must count
    those as expected, not flag them."""
    confirmed = [
        {
            "id": "A1", "source_path": "Catan.md", "action": None,
            "title": "Catan Strategy", "tags": [],
            "parent_moc": "", "parent_mocs": [],
        },
        {
            "id": "A2", "source_path": "Gloomhaven.md", "action": None,
            "title": "Gloomhaven Combat", "tags": [],
            "parent_moc": "", "parent_mocs": [],
        },
        {
            "id": "MOC01", "source_path": None, "action": "create_moc",
            "title": "Brettspiele (MOC)", "tags": [],
            "parent_moc": "2700", "parent_mocs": ["2700"],
            "supporting_items": "A1, A2",
        },
    ]
    manifest = [
        {"id": "A1", "action": None, "title": "Catan Strategy",
         "source_path": "Catan.md", "rendered_file": "2026-04-21_1200_catan.md",
         "destination": "Atlas/202 Notes/", "parent_moc": "",
         "parent_mocs": [], "tags": []},
        {"id": "A2", "action": None, "title": "Gloomhaven Combat",
         "source_path": "Gloomhaven.md", "rendered_file": "2026-04-21_1200_gloom.md",
         "destination": "Atlas/202 Notes/", "parent_moc": "",
         "parent_mocs": [], "tags": []},
        {"id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
         "source_path": None, "rendered_file": "2026-04-21_1200_brettspiele-moc.md",
         "destination": "Atlas/200 Maps/", "parent_moc": "2700",
         "parent_mocs": ["2700"], "supporting_items": "A1, A2", "tags": []},
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    instrs = _build_instrs_from(manifest, confirmed, [], [])
    rc, obs, out = _run(parsed, instrs)
    _must(rc == 0, f"supporting_items expansion must reconcile, got rc={rc}")
    _must(obs == [], f"no observation expected (MOC has supporting_items), got {obs}")
    # Count check: 1 MOC up-link (Brettspiele → 2700) + 2 supporting_items
    # down-links (Brettspiele ← Catan, Brettspiele ← Gloomhaven) = 3 links total
    _must("link_to_moc" in out, "link_to_moc row must exist in output")
    print("[PASS] supporting_items expansion: reconciles, no orphan warning")


def test_truly_empty_moc_warns():
    """Create_moc with no supporting_items AND no parent_mocs pointing to it
    → observation that the MOC will be created empty."""
    confirmed = [{
        "id": "MOC01", "source_path": None, "action": "create_moc",
        "title": "Brettspiele (MOC)", "tags": [],
        "parent_moc": "2700 - Art & Recreation",
        "parent_mocs": ["2700 - Art & Recreation"],
        "supporting_items": "",  # empty — nothing to pull in
    }]
    manifest = [{
        "id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
        "source_path": None,
        "rendered_file": "2026-04-21_1200_brettspiele-moc.md",
        "destination": "Atlas/200 Maps/",
        "parent_moc": "2700 - Art & Recreation",
        "parent_mocs": ["2700 - Art & Recreation"],
        "supporting_items": "",
        "tags": [],
    }]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    instrs = _build_instrs_from(manifest, confirmed, [], [])
    rc, obs, out = _run(parsed, instrs)
    _must(rc == 0, f"truly empty MOC is warn-only, got rc={rc}")
    _must(len(obs) == 1, f"expected 1 observation, got {len(obs)}: {obs}")
    _must("Brettspiele" in obs[0], f"observation must mention MOC title: {obs[0]}")
    _must("empty" in obs[0].lower(), f"observation must say 'empty': {obs[0]}")
    print("[PASS] truly empty create_moc (no supporting_items, no parent refs) → observation")


def test_daily_only_delete_inference_reconciles():
    """Source that appears only in daily_updates gets a delete_source action."""
    confirmed = []  # no atomic notes
    manifest = []
    daily_updates = [{
        "date": "2026-03-26",
        "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
        "trackers": [{
            "field": "Sport", "value": "true", "syntax": "inline_field",
            "source_stem": "Sport", "accepted": True,
        }],
        "log_entries": [],
        "log_links": [],
    }]
    skipped = []
    parsed = {
        "confirmed_items": confirmed,
        "daily_updates": daily_updates,
        "skipped": skipped,
    }
    instrs = _build_instrs_from(manifest, confirmed, daily_updates, skipped)
    rc, obs, out = _run(parsed, instrs)
    _must(rc == 0, f"daily-only delete inference should reconcile, rc={rc}")
    _must("delete_source coverage: expected=1 actual=1 [OK]" in out,
          "delete_source counts must match (1 inferred from Sport source_stem)")
    print("[PASS] daily-only delete inference reconciles on both sides")


def main() -> int:
    test_happy_path_reconciles()
    test_missing_instruction_fails()
    test_link_mismatch_fails()
    test_supporting_items_expansion_reconciles()
    test_truly_empty_moc_warns()
    test_daily_only_delete_inference_reconciles()
    print("\n\u2713 All instructions-diff tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
