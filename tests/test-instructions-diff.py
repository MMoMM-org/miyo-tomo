#!/usr/bin/env python3
# version: 0.4.0
"""test-instructions-diff.py — Unit tests for instructions-diff.

Covers:
  - Happy path: matching parsed-suggestions.json + instructions.json → exit 0
  - Count mismatch: missing instruction → exit 1
  - Link mismatch: wrong parent_mocs coverage → exit 1
  - Orphan create_moc observation (warning, not fail)
  - Daily-only delete-source inference reconciles on both sides
  - edit_frontmatter registration (spec 032 T4.2): the kind is counted in the
    ACTION_ORDER reconciliation table for non-garden run_diff (proven via
    summarize_actual directly, since run_diff's ACTION_ORDER loop is
    unreachable for edit_frontmatter — see the module comment below)
  - run_diff_garden's dynamic all_kinds never silently drops an unregistered
    action kind — a guard on the path spec 032's garden_action findings
    actually travel through

Each test builds in-memory dicts, invokes run_diff, and asserts exit code
+ observation count. We capture stdout so test output stays clean.
"""
from __future__ import annotations

import importlib.util
import io
import re
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
# run_diff dispatches on document shape (line ~610): garden-audit docs
# (confirmed_items all carrying garden_action) route to run_diff_garden and
# never reach derive_expected at all; non-garden docs call derive_expected
# then reconcile against a FIXED ACTION_ORDER list. The two paths have
# different silent-drop behaviour for a kind absent from their table:
#
#   - non-garden run_diff: iterates ACTION_ORDER only, so a kind missing from
#     that list is silently dropped from both the printed table and the
#     total — the audit can exit rc=0 while that kind's actions go completely
#     unreconciled (spec 031 hit this trap for move_asset).
#   - run_diff_garden: builds its kind list dynamically (GARDEN_ACTION_ORDER
#     plus whatever unknown kinds show up in actual_counts), so nothing is
#     silently dropped there. Its gap is different: _GARDEN_EXPECTED_KINDS
#     does not yet know a frontmatter-routed finding owes an edit_frontmatter
#     action — that routing rule is T4.3, deliberately held until Phase 3
#     defines it. Until then a frontmatter-routed finding legitimately shows
#     as [DIFF], which is correct-but-incomplete, not a bug to paper over.
#
# spec 032's broken_up findings are garden_action items, so they travel the
# run_diff_garden path — never the ACTION_ORDER path below. The tests here
# split accordingly: the ACTION_ORDER tests exercise summarize_actual
# directly (proving the registration itself, independent of dispatch), and
# the garden test guards run_diff_garden's already-correct dynamic-kind
# behaviour against regressing into the same silent-drop trap.
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


def test_garden_diff_never_drops_unregistered_kind():
    """Guard, not regression test: proves run_diff_garden's CURRENT, already
    correct behaviour — its all_kinds list is built dynamically
    (GARDEN_ACTION_ORDER plus any kind from actual_counts not already in it),
    so a kind absent from GARDEN_ACTION_ORDER still appears in the printed
    table and still contributes to the actual total. It is never silently
    dropped the way non-garden run_diff drops an unregistered kind.

    This test passes today and is expected to keep passing — it exists to
    catch a future refactor of run_diff_garden that reintroduces the
    ACTION_ORDER-style silent-drop bug for garden mode.

    It deliberately does NOT assert that edit_frontmatter's expected count
    reconciles with its actual count: making _GARDEN_EXPECTED_KINDS aware
    that a frontmatter-routed finding owes an edit_frontmatter action is
    T4.3, held pending Phase 3's routing rule. rc=1 here is the correct,
    incomplete-but-honest current state, not a bug.
    """
    confirmed = [{
        "id": "G1", "garden_action": "resolve_dead_link",
        "path": "Atlas/Japan.md", "target": "Old Note.md",
    }]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}

    n = 3
    actions = [
        {"id": "g1", "action": "resolve_dead_link",
         "path": "Atlas/Japan.md", "target": "Old Note.md"},
    ] + [_edit_frontmatter_action(str(i), f"Atlas/Note{i}.md") for i in range(n)]
    instrs = {"schema_version": "1", "type": "tomo-instructions",
              "action_count": len(actions), "actions": actions}

    rc, _obs, out = _run(parsed, instrs)

    # edit_frontmatter is not in GARDEN_ACTION_ORDER (expected=0) but still
    # gets its own row with the real actual count — never absorbed or hidden.
    kind_line = f"  {'edit_frontmatter':<20s} {0:>9d} {n:>9d}  [DIFF]"
    _must(kind_line in out, f"edit_frontmatter row missing/wrong in output:\n{out}")

    # TOTAL actual must include those n actions: resolve_dead_link (1/1, [OK])
    # plus edit_frontmatter (0 expected / n actual) = 1 expected, 1+n actual.
    total_line = f"  {'TOTAL':<20s} {1:>9d} {1 + n:>9d}  [DIFF]"
    _must(total_line in out, f"TOTAL row does not reflect the unregistered kind:\n{out}")

    _must(rc == 1, f"expected/actual mismatch on edit_frontmatter must fail today, got rc={rc}")
    print("[PASS] run_diff_garden: unregistered kind is shown and counted, never dropped")


# ──────────────────────────────────────────────────────────────────────────────
# move_asset registration (spec 031 T4.1)
#
# PRD Feature 5 / Risks row 1 (Likelihood High): run_diff's reconciliation loop
# iterates the FIXED ACTION_ORDER list (line ~653), not summarize_actual's
# dynamic per-kind counts (line ~365-366). A kind absent from ACTION_ORDER is
# counted by summarize_actual but never reconciled or printed — the audit
# exits 0 (OK) while those actions go completely unchecked. The only visible
# symptom is the header's action_count exceeding the printed TOTAL.
#
# Expectation derivation (how many move_asset actions SHOULD exist, from
# parsed-suggestions attachments) is spec 031 T4.2's job, not this one — these
# tests isolate the registration concern (counts initialiser + ACTION_ORDER)
# by patching derive_expected's returned counts directly where a matched
# expected/actual comparison is needed.
# ──────────────────────────────────────────────────────────────────────────────

def _move_asset_action(n: str) -> dict:
    return {
        "id": f"asset-{n}", "action": "move_asset",
        "source": f"100 Inbox/Attachments/photo-{n}.jpg",
        "destination": f"Atlas/900 Assets/photo-{n}.jpg",
    }


def _run_with_expected_move_asset(parsed, instrs, n_expected, monkeypatch):
    """Run the audit with derive_expected's move_asset count pinned to
    n_expected, isolating ACTION_ORDER/counts registration (T4.1) from
    expectation derivation (T4.2)."""
    real_derive = diff.derive_expected

    def _patched(parsed_arg, tag_handler_groups=None):
        expected = real_derive(parsed_arg, tag_handler_groups)
        expected["counts"]["move_asset"] = n_expected
        return expected

    monkeypatch.setattr(diff, "derive_expected", _patched)
    return _run(parsed, instrs)


def test_move_asset_action_count_reconciles_with_total():
    """Headline invariant (PRD Risks row 1): for ANY instruction set, the
    actual count summed over ACTION_ORDER must equal action_count —
    including a set carrying move_asset actions. Before registration,
    move_asset is excluded from ACTION_ORDER and this sum falls short —
    the exact symptom the PRD calls out ('action_count exceeding the
    printed TOTAL')."""
    actions = [_move_asset_action(str(i)) for i in range(4)]
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": len(actions), "actions": actions}

    actual = diff.summarize_actual(instrs)
    total_actual = sum(actual["counts"].get(k, 0) for k in diff.ACTION_ORDER)

    _must(
        total_actual == instrs["action_count"],
        f"action_count={instrs['action_count']} but ACTION_ORDER-summed "
        f"total={total_actual} — move_asset is uncounted in the table",
    )
    print("[PASS] move_asset: action_count reconciles with ACTION_ORDER total")


def test_move_asset_contributes_n_to_total():
    """N move_asset actions contribute exactly N to the ACTION_ORDER total —
    not zero, and not silently absorbed into another kind."""
    n = 5
    actions = [_move_asset_action(str(i)) for i in range(n)]
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n, "actions": actions}

    actual = diff.summarize_actual(instrs)
    total_actual = sum(actual["counts"].get(k, 0) for k in diff.ACTION_ORDER)

    _must(total_actual == n, f"expected {n} move_asset actions in TOTAL, got {total_actual}")
    print("[PASS] move_asset: N actions contribute N to TOTAL")


# Parses the two printed values the audit's own output claims should agree
# — the header's action_count=N and the TOTAL row's actual column — out of
# the REAL stdout run_diff produces. Unlike the two tests above (which
# re-derive the sum locally via summarize_actual + ACTION_ORDER), this is
# the canary for the whole blind-spot class: it fails on a bug in run_diff's
# own summation OR on a broken f-string (wrong variable, wrong column),
# neither of which the internal-invariant tests above can see.
_ACTION_COUNT_RE = re.compile(r"action_count=(\d+)")
_TOTAL_ROW_RE = re.compile(r"TOTAL\s+\d+\s+(\d+)\s+\[(?:OK|DIFF)\]")


def test_move_asset_rendered_action_count_matches_rendered_total():
    """The printed action_count header and the printed TOTAL row's actual
    column must agree for a set carrying move_asset actions — asserted on
    the audit's real stdout, not on a value the test recomputes itself
    [ref: PRD/Risks; row 1]."""
    n = 4
    actions = [_move_asset_action(str(i)) for i in range(n)]
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n, "actions": actions}
    _rc, _obs, out = _run(parsed, instrs)

    header_match = _ACTION_COUNT_RE.search(out)
    total_match = _TOTAL_ROW_RE.search(out)
    _must(header_match is not None, f"action_count header not found in output:\n{out}")
    _must(total_match is not None, f"TOTAL row not found in output:\n{out}")

    header_count = int(header_match.group(1))
    total_actual = int(total_match.group(1))
    _must(
        header_count == total_actual,
        f"printed action_count={header_count} but printed TOTAL actual={total_actual}:\n{out}",
    )
    print("[PASS] rendered action_count header matches rendered TOTAL actual column")


def test_move_asset_appears_in_printed_table():
    """move_asset must get its own row in the printed count table via the
    full run_diff pipeline, not be silently merged or omitted."""
    n = 2
    actions = [_move_asset_action(str(i)) for i in range(n)]
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n, "actions": actions}
    _rc, _obs, out = _run(parsed, instrs)
    _must("move_asset" in out, f"move_asset row missing from printed table:\n{out}")
    print("[PASS] move_asset row appears in the printed count table")


def test_move_asset_matched_counts_reconcile(monkeypatch):
    """Expected N == actual N move_asset actions reconciles (rc=0)
    [ref: PRD/AC-F5.1]."""
    n = 3
    actions = [_move_asset_action(str(i)) for i in range(n)]
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n, "actions": actions}
    rc, _obs, out = _run_with_expected_move_asset(parsed, instrs, n, monkeypatch)
    row = f"  {'move_asset':<20s} {n:>9d} {n:>9d}  [OK]"
    _must(row in out, f"expected matched move_asset row not found:\n{out}")
    _must(rc == 0, f"matched move_asset counts must reconcile, got rc={rc}\n{out}")
    print("[PASS] move_asset expected==actual reconciles")


def test_move_asset_undercoverage_hard_fails(monkeypatch):
    """Expected N, actual N-1 move_asset actions -> per-kind mismatch, hard
    fail [ref: PRD/AC-F5.2]."""
    n_expected = 3
    n_actual = n_expected - 1
    actions = [_move_asset_action(str(i)) for i in range(n_actual)]
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n_actual, "actions": actions}
    rc, _obs, out = _run_with_expected_move_asset(parsed, instrs, n_expected, monkeypatch)
    row = f"  {'move_asset':<20s} {n_expected:>9d} {n_actual:>9d}  [DIFF]"
    _must(row in out, f"expected move_asset [DIFF] row not found:\n{out}")
    _must(rc == 1, f"undercoverage must hard-fail, got rc={rc}\n{out}")
    print("[PASS] move_asset undercoverage (N-1) → rc=1")


def test_move_asset_overcoverage_hard_fails(monkeypatch):
    """Expected N, actual N+1 move_asset actions -> hard fail."""
    n_expected = 3
    n_actual = n_expected + 1
    actions = [_move_asset_action(str(i)) for i in range(n_actual)]
    parsed = {"confirmed_items": [], "daily_updates": [], "skipped": []}
    instrs = {"schema_version": "2", "type": "tomo-instructions",
              "action_count": n_actual, "actions": actions}
    rc, _obs, out = _run_with_expected_move_asset(parsed, instrs, n_expected, monkeypatch)
    row = f"  {'move_asset':<20s} {n_expected:>9d} {n_actual:>9d}  [DIFF]"
    _must(row in out, f"expected move_asset [DIFF] row not found:\n{out}")
    _must(rc == 1, f"overcoverage must hard-fail, got rc={rc}\n{out}")
    print("[PASS] move_asset overcoverage (N+1) → rc=1")


# ──────────────────────────────────────────────────────────────────────────────
# move_asset expectation derivation (spec 031 T4.2)
#
# derive_expected must count how many move_asset actions confirmed items
# EXPECT, mirroring the renderer's global dedup (render_actions.py
# _build_move_asset_actions — the set spans the whole manifest, not a
# per-item loop) and keying on the resolved vault-relative path, not the
# basename — the audio_peer analogue's live asymmetry (basename on the diff
# side, inbox-joined path on the renderer side) must NOT be replicated here.
#
# ADR-6: an attachment move never implies a deletion — attachments must
# never be appended to expected_deletions (that is the audio_peer/deleted
# behaviour; filing is its exact inversion).
# ──────────────────────────────────────────────────────────────────────────────

def _confirmed_item(item_id, source_path, attachments=None, action=None, **over):
    item = {
        "id": item_id, "source_path": source_path, "action": action,
        "title": f"Item {item_id}", "tags": [],
        "parent_moc": "", "parent_mocs": [],
    }
    if attachments is not None:
        item["attachments"] = attachments
    item.update(over)
    return item


def test_move_asset_expected_counts_unique_attachments_on_one_item():
    """One confirmed item with 2 unique attachments -> expects 2
    [ref: PRD/AC-F5.1]."""
    confirmed = [_confirmed_item(
        "S01", "Trip.md",
        attachments=["100 Inbox/Attachments/a.jpg", "100 Inbox/Attachments/b.jpg"],
    )]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_asset"] == 2,
          f"expected 2 move_asset, got {expected['counts']['move_asset']}")
    print("[PASS] one item, 2 unique attachments -> expects 2")


def test_move_asset_expected_dedups_shared_attachment_globally():
    """Two confirmed items sharing one attachment path -> expects 1, matching
    the renderer's GLOBAL dedup (not per-item) [ref: PRD/AC-F4.2]."""
    shared = "100 Inbox/Attachments/shared.jpg"
    confirmed = [
        _confirmed_item("S01", "A.md", attachments=[shared]),
        _confirmed_item("S02", "B.md", attachments=[shared]),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_asset"] == 1,
          f"expected 1 (globally deduped), got {expected['counts']['move_asset']}")
    print("[PASS] two items sharing one attachment -> expects 1 (global dedup)")


def test_move_asset_expected_keys_on_full_path_not_basename():
    """Two items whose attachments share a BASENAME but live at different
    paths -> expects 2, proving the dedup key is the full resolved path, not
    the basename (the audio_peer asymmetry this design must not replicate)."""
    confirmed = [
        _confirmed_item("S01", "A.md", attachments=["100 Inbox/FolderA/photo.jpg"]),
        _confirmed_item("S02", "B.md", attachments=["100 Inbox/FolderB/photo.jpg"]),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_asset"] == 2,
          f"expected 2 (same basename, different path), got {expected['counts']['move_asset']}")
    print("[PASS] same-basename-different-path attachments -> expects 2 (keyed on full path)")


def test_move_asset_expected_skips_create_moc_items():
    """create_moc items are skipped, as in the existing passes — an
    attachments field on one (should never occur, but must not be trusted)
    contributes nothing [ref: PRD/AC-F5.1]."""
    confirmed = [
        _confirmed_item("A1", "Note.md", attachments=["100 Inbox/x.jpg"]),
        _confirmed_item("MOC01", None, action="create_moc",
                        attachments=["100 Inbox/should-not-count.jpg"]),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_asset"] == 1,
          f"create_moc attachments must not count, got {expected['counts']['move_asset']}")
    print("[PASS] create_moc item's attachments contribute nothing")


def test_move_asset_never_appended_to_expected_deletions():
    """ADR-6 guard, asserted on the deletions list itself: attachments must
    never appear in expected_deletions — filing means the file continues to
    exist at a new path, unlike the audio_peer's delete."""
    attachment = "100 Inbox/Attachments/keepsake.jpg"
    confirmed = [_confirmed_item("S01", "A.md", attachments=[attachment])]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    _must(attachment not in expected["expected_deletions"],
          f"attachment path leaked into expected_deletions: {expected['expected_deletions']}")
    print("[PASS] attachment path never appears in expected_deletions (ADR-6)")


def test_move_asset_skipped_items_contribute_nothing():
    """A skipped[] entry's attachments (if any survived onto that shape)
    contribute nothing — only confirmed_items feed the expectation
    [ref: PRD/AC-F4.5]."""
    confirmed = [_confirmed_item("S01", "A.md", attachments=["100 Inbox/x.jpg"])]
    skipped = [{
        "source_path": "B.md", "disposition": "skip",
        "attachments": ["100 Inbox/should-not-count.jpg"],
    }]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": skipped}
    expected = diff.derive_expected(parsed)
    _must(expected["counts"]["move_asset"] == 1,
          f"skipped item's attachments must not count, got {expected['counts']['move_asset']}")
    print("[PASS] skipped item's attachments contribute nothing")


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
    test_garden_diff_never_drops_unregistered_kind()
    test_move_asset_action_count_reconciles_with_total()
    test_move_asset_contributes_n_to_total()
    test_move_asset_rendered_action_count_matches_rendered_total()
    test_move_asset_appears_in_printed_table()
    # test_move_asset_matched_counts_reconcile, test_move_asset_undercoverage_hard_fails,
    # and test_move_asset_overcoverage_hard_fails require the pytest `monkeypatch`
    # fixture and are run only under pytest collection, not this script entrypoint.
    test_move_asset_expected_counts_unique_attachments_on_one_item()
    test_move_asset_expected_dedups_shared_attachment_globally()
    test_move_asset_expected_keys_on_full_path_not_basename()
    test_move_asset_expected_skips_create_moc_items()
    test_move_asset_never_appended_to_expected_deletions()
    test_move_asset_skipped_items_contribute_nothing()
    print("\n\u2713 All instructions-diff tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
