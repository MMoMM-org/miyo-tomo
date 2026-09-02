#!/usr/bin/env python3
# version: 0.3.0
"""test-instructions-diff.py — Unit tests for instructions-diff.

Covers:
  - Happy path: matching parsed-suggestions.json + instructions.json → exit 0
  - Count mismatch: missing instruction → exit 1
  - Link mismatch: wrong parent_mocs coverage → exit 1
  - Orphan create_moc observation (warning, not fail)
  - Daily-only delete-source inference reconciles on both sides
  - edit_frontmatter registration (spec 032 T4.2): the kind must be counted
    in the ACTION_ORDER reconciliation table, not just generically tallied

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


def test_batched_link_to_moc_reconciles():
    """#70: two notes merged under one (MOC, new_section) \u2192 ONE batched
    link_to_moc (source_note_title=None, multi-bullet) must still reconcile \u2014
    the audit credits each note via its bullets and counts coverage as pairs."""
    def _item(sid, title, src):
        anchor = {"type": "callout", "value": "[!blocks] Key Concepts",
                  "placement": "before", "new_section": "Japanische St\u00e4dte"}
        return {
            "id": sid, "source_path": src, "action": None, "title": title,
            "tags": [], "parent_moc": "Japan (MOC)",
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [{"path": "Atlas/200 Maps/Japan (MOC)", "anchor": anchor}],
        }

    def _man(sid, title, src, rendered):
        return {
            "id": sid, "action": None, "title": title, "source_path": src,
            "rendered_file": rendered, "destination": "Atlas/202 Notes/",
            "parent_moc": "Japan (MOC)", "parent_mocs": ["Japan (MOC)"], "tags": [],
        }

    confirmed = [_item("S01", "Asahikawa \u2014 Snow city", "Asahikawa.md"),
                 _item("S02", "Sapporo \u2014 Hokkaido capital", "Sapporo.md")]
    manifest = [_man("S01", "Asahikawa \u2014 Snow city", "Asahikawa.md", "2026-04-21_1200_asahikawa.md"),
                _man("S02", "Sapporo \u2014 Hokkaido capital", "Sapporo.md", "2026-04-21_1200_sapporo.md")]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    # Real producer path: build_actions, then the main() post-processing that
    # applies the #70 merge + serialize + internal-field strip.
    actions = ir.build_actions(manifest, confirmed, [], [], CFG)
    merged = ir._merge_new_section_links(actions)
    ir._serialize_new_sections(actions)
    ir._strip_internal_link_fields(actions)
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": len(actions), "actions": actions}

    links = [a for a in actions if a["action"] == "link_to_moc"]
    _must(merged == 1, f"expected 1 merge, got {merged}")
    _must(len(links) == 1, f"expected 1 batched link_to_moc, got {len(links)}")
    _must(links[0].get("source_note_title") is None, "batched link must have source_note_title=None")

    rc, _, out = _run(parsed, instrs)
    _must(rc == 0, f"batched link_to_moc must reconcile, got rc={rc}\n{out}")
    _must("link_to_moc" in out and "[DIFF]" not in out.split("per-item")[0],
          "count table must not flag link_to_moc as [DIFF]")
    print("[PASS] #70 batched link_to_moc reconciles \u2192 exit 0")


def test_batched_link_to_moc_coverage_gap_fails():
    """#70 failure case (review M13): a batched link_to_moc that drops one note's
    bullet leaves that note's (note, MOC) pair uncovered — the coverage audit
    must flag a hard fail (rc=1), not silently pass on the merged action count."""
    def _item(sid, title, src):
        anchor = {"type": "callout", "value": "[!blocks] Key Concepts",
                  "placement": "before", "new_section": "Japanische Städte"}
        return {
            "id": sid, "source_path": src, "action": None, "title": title,
            "tags": [], "parent_moc": "Japan (MOC)",
            "parent_mocs": ["Japan (MOC)"],
            "candidate_mocs": [{"path": "Atlas/200 Maps/Japan (MOC)", "anchor": anchor}],
        }

    def _man(sid, title, src, rendered):
        return {
            "id": sid, "action": None, "title": title, "source_path": src,
            "rendered_file": rendered, "destination": "Atlas/202 Notes/",
            "parent_moc": "Japan (MOC)", "parent_mocs": ["Japan (MOC)"], "tags": [],
        }

    confirmed = [_item("S01", "Asahikawa — Snow city", "Asahikawa.md"),
                 _item("S02", "Sapporo — Hokkaido capital", "Sapporo.md")]
    manifest = [_man("S01", "Asahikawa — Snow city", "Asahikawa.md", "2026-04-21_1200_asahikawa.md"),
                _man("S02", "Sapporo — Hokkaido capital", "Sapporo.md", "2026-04-21_1200_sapporo.md")]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    actions = ir.build_actions(manifest, confirmed, [], [], CFG)
    ir._merge_new_section_links(actions)
    ir._serialize_new_sections(actions)
    ir._strip_internal_link_fields(actions)
    # Tamper: drop the Sapporo (S02) bullet from the batched link_to_moc so its
    # (note, MOC) pair is no longer covered.
    for a in actions:
        if a["action"] == "link_to_moc" and "Sapporo" in a.get("line_to_add", ""):
            a["line_to_add"] = "\n".join(
                ln for ln in a["line_to_add"].split("\n") if "Sapporo" not in ln
            )
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": len(actions), "actions": actions}

    rc, _, out = _run(parsed, instrs)
    _must(rc == 1, f"dropped-bullet coverage gap must fail, got rc={rc}\n{out}")
    _must("[DIFF]" in out, "output must contain [DIFF] marker")
    print("[PASS] #70 batched link_to_moc coverage gap (dropped bullet) → rc=1")


# ──────────────────────────────────────────────────────────────────────────────
# edit_frontmatter registration (spec 032 T4.2)
#
# An unregistered action kind is counted generically by summarize_actual, but
# skipped by run_diff's ACTION_ORDER reconciliation loop — so the audit exits
# rc=0 while the kind's actions go completely unreconciled (spec 031 hit the
# identical trap for move_asset). These tests assert the invariant that must
# hold once a kind is registered, not the buggy pre-registration behaviour —
# they are written to stay true forever, not to be inverted after the fix.
# ──────────────────────────────────────────────────────────────────────────────

def _edit_frontmatter_action(n: str, path: str) -> dict:
    return {
        "id": f"edit-{n}", "action": "edit_frontmatter",
        "path": path, "property": "up", "operation": "remove",
        "expected": "[[Old Parent]]",
    }


def test_edit_frontmatter_action_count_reconciles_with_total():
    """Primary invariant: for ANY instruction set, the actual count summed
    over ACTION_ORDER must equal action_count — including a set carrying
    edit_frontmatter actions."""
    actions = [
        _edit_frontmatter_action("1", "Atlas/Japan.md"),
        _edit_frontmatter_action("2", "Atlas/Sapporo.md"),
        _edit_frontmatter_action("3", "Atlas/Asahikawa.md"),
    ]
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": len(actions), "actions": actions}

    actual = diff.summarize_actual(instrs)
    total_actual = sum(actual["counts"].get(k, 0) for k in diff.ACTION_ORDER)

    _must(
        total_actual == instrs["action_count"],
        f"action_count={instrs['action_count']} but ACTION_ORDER-summed "
        f"total={total_actual} — edit_frontmatter is uncounted in the table",
    )
    print("[PASS] edit_frontmatter: action_count reconciles with ACTION_ORDER total")


def test_edit_frontmatter_contributes_n_to_total():
    """N edit_frontmatter actions contribute exactly N to the ACTION_ORDER
    total — not zero, and not silently absorbed into another kind."""
    n = 5
    actions = [_edit_frontmatter_action(str(i), f"Atlas/Note{i}.md") for i in range(n)]
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": n, "actions": actions}

    actual = diff.summarize_actual(instrs)
    total_actual = sum(actual["counts"].get(k, 0) for k in diff.ACTION_ORDER)

    _must(total_actual == n, f"expected {n} edit_frontmatter actions in TOTAL, got {total_actual}")
    print("[PASS] edit_frontmatter: N actions contribute N to TOTAL")


def _patched_derive_expected(n: int):
    """Wrap the real derive_expected to also report an edit_frontmatter
    count of n. Deriving that count from parsed suggestions is T4.3's job
    (deliberately held pending Phase 3's routing rule) — this simulates an
    already-correct expected count so these tests can prove the ACTION_ORDER
    registration wires the kind into pass/fail, not just into the display."""
    original = diff.derive_expected

    def _patched(parsed, tag_handler_groups=None):
        expected = original(parsed, tag_handler_groups)
        expected["counts"]["edit_frontmatter"] = n
        return expected

    return original, _patched


def test_edit_frontmatter_expected_matches_actual_passes():
    """expected N, actual N → pass, and the kind is named in the printed
    table (not silently absorbed into the TOTAL row alone)."""
    n = 3
    actions = [_edit_frontmatter_action(str(i), f"Atlas/Note{i}.md") for i in range(n)]
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": n, "actions": actions}
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}

    original, patched = _patched_derive_expected(n)
    diff.derive_expected = patched
    try:
        rc, _obs, out = _run(parsed, instrs)
    finally:
        diff.derive_expected = original

    _must(rc == 0, f"expected N == actual N for edit_frontmatter must pass, got rc={rc}\n{out}")
    _must("edit_frontmatter" in out, "edit_frontmatter must appear in the printed table")
    print("[PASS] edit_frontmatter: expected N == actual N → pass, kind shown in table")


def test_edit_frontmatter_expected_mismatch_hard_fails():
    """expected N, actual N-1 → hard fail. An unreconciled edit_frontmatter
    action must not slip through as green."""
    n = 3
    actions = [_edit_frontmatter_action(str(i), f"Atlas/Note{i}.md") for i in range(n - 1)]
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": n - 1, "actions": actions}
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}

    original, patched = _patched_derive_expected(n)
    diff.derive_expected = patched
    try:
        rc, _obs, out = _run(parsed, instrs)
    finally:
        diff.derive_expected = original

    _must(rc == 1, f"expected N, actual N-1 for edit_frontmatter must hard-fail, got rc={rc}\n{out}")
    _must("[DIFF]" in out, "mismatch must be marked [DIFF] in the printed table")
    print("[PASS] edit_frontmatter: expected N, actual N-1 → hard fail")


def main() -> int:
    test_happy_path_reconciles()
    test_missing_instruction_fails()
    test_link_mismatch_fails()
    test_supporting_items_expansion_reconciles()
    test_truly_empty_moc_warns()
    test_daily_only_delete_inference_reconciles()
    test_batched_link_to_moc_reconciles()
    test_edit_frontmatter_action_count_reconciles_with_total()
    test_edit_frontmatter_contributes_n_to_total()
    test_edit_frontmatter_expected_matches_actual_passes()
    test_edit_frontmatter_expected_mismatch_hard_fails()
    print("\n\u2713 All instructions-diff tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
