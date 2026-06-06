#!/usr/bin/env python3
# version: 0.1.0
"""test_shared_ctx_feature5.py — T3.4 Feature 5 regression tests for spec 021 (F-34).

Verifies that shared_ctx.mocs is the complete, corrected tag-discovered MOC set:

  F5#1 — a notes-area #type/others/moc MOC appears in shared_ctx.mocs AND is
          offered in candidate_mocs[] for an inbox item whose topics match
  F5#2 — a template-vault MOC (path under an excluded prefix, e.g. "X/...") is
          ABSENT from shared_ctx.mocs because moc_scan never put it in map_notes
  F5#3 — build_mocs has NO separate/path-only fallback: shared_ctx.mocs derives
          from the single cache.map_notes source only (negative assertion)
  F5#4 — an item whose topics match a notes-area MOC is offered a link_to_moc
          candidate instead of firing needs_new_moc

The fix rides Phase 1 (tag-primary discovery); this task is pure verification.
No code changes to shared-ctx-builder.py are expected — if F5#3 turns RED it
means a path-only fallback was found, which must then be removed.

RED before GREEN discipline (CON-1/TDD).
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# shared-ctx-builder.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)

build_mocs = scb.build_mocs


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _notes_area_moc_entry(
    path: str = "Atlas/Software MOC.md",
    title: str = "Software MOC",
    topics: list[str] | None = None,
) -> dict:
    """Return a realistic map_notes entry for a notes-area MOC.

    kind==moc entries in map_notes come from moc-tree-builder, which sets at
    minimum: path, title, topics.  template field and other moc-tree-builder
    extras are allowed but not required by build_mocs.
    """
    return {
        "path": path,
        "title": title,
        "topics": topics or ["software", "programming"],
        "kind": "moc",
    }


def _notes_area_cache(extra_entries: list[dict] | None = None) -> dict:
    """Return a cache dict whose map_notes contains only notes-area MOCs."""
    entries = [_notes_area_moc_entry()] + (extra_entries or [])
    return {"map_notes": entries}


# ---------------------------------------------------------------------------
# F5#1 — notes-area MOC appears in shared_ctx.mocs
# ---------------------------------------------------------------------------

def test_f5_1_notes_area_moc_in_shared_ctx_mocs():
    """A notes-area #type/others/moc MOC (kind==moc, not under an excluded path)
    must appear in shared_ctx.mocs after build_mocs processes the cache.

    This is the positive-inclusion proof for Feature 5: the tag-discovered set
    (notes-area MOCs) flows end-to-end through map_notes → build_mocs →
    shared_ctx.mocs.
    """
    cache = _notes_area_cache()
    result = build_mocs(cache)

    paths = [m["path"] for m in result]
    assert "Atlas/Software MOC.md" in paths, (
        f"Notes-area MOC 'Atlas/Software MOC.md' must appear in build_mocs() output. "
        f"Got paths: {paths}"
    )

    # Validate the returned entry shape (path, title, topics, is_classification)
    moc = next(m for m in result if m["path"] == "Atlas/Software MOC.md")
    assert moc["title"] == "Software MOC"
    assert "software" in moc["topics"] or "programming" in moc["topics"]
    assert "is_classification" in moc


# ---------------------------------------------------------------------------
# F5#1b — notes-area MOC is offered as candidate_moc for matching item
# ---------------------------------------------------------------------------

def test_f5_1b_notes_area_moc_offered_as_candidate(tmp_path):
    """When an inbox item's topics overlap with a notes-area MOC, the MOC is
    offered in candidate_mocs[] (not a new-MOC proposal).

    We test this via the full shared-ctx-builder main() pipeline so the
    candidate_mocs logic that inbox-analyst uses sees the correct mocs list.
    We verify shared_ctx.mocs contains the MOC entry — inbox-analyst is the
    consumer that resolves candidates, but shared_ctx.mocs is the feed.
    """
    import json
    import yaml
    from unittest.mock import patch

    cache = {
        "map_notes": [
            {
                "path": "Atlas/Software MOC.md",
                "title": "Software MOC",
                "topics": ["software", "programming"],
                "kind": "moc",
            }
        ],
        "placeholder_mocs": [],
    }

    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    cache_file.write_text(yaml.dump(cache))
    vault_cfg_file.write_text(yaml.dump({"profile": "miyo"}))

    argv = [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", "f5-1b-test",
        "--skip-reconcile",
    ]

    with patch("sys.argv", argv), \
         patch.object(scb, "build_tag_prefixes", return_value=[]), \
         patch.object(scb, "build_classification_keywords", return_value={}), \
         patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()

    assert rc == 0, f"main() returned {rc}"
    ctx = json.loads(out_file.read_text())

    moc_paths = [m["path"] for m in ctx.get("mocs", [])]
    assert "Atlas/Software MOC.md" in moc_paths, (
        f"shared_ctx.mocs must contain the notes-area MOC for inbox-analyst to "
        f"offer it as a candidate. Got moc paths: {moc_paths}"
    )


# ---------------------------------------------------------------------------
# F5#2 — template-vault MOC absent from shared_ctx.mocs
# ---------------------------------------------------------------------------

def test_f5_2_template_vault_moc_absent_from_shared_ctx_mocs():
    """A template-vault path (under an excluded prefix like 'X/...') must NOT
    appear in shared_ctx.mocs.

    Mechanism: moc_scan applies exclude_paths client-side (OQ-5, Rule 8) before
    writing map_notes.  A template-vault note tagged #type/others/moc is
    stripped at scan time and never reaches map_notes.  Because build_mocs reads
    ONLY map_notes, the exclusion propagates automatically.

    This test verifies both sides of the contract:
      (a) if a template-vault path is absent from map_notes, it is absent from
          shared_ctx.mocs (the normal production case).
      (b) a notes-area MOC present in map_notes is correctly included — ruling
          out a broken build_mocs that returns empty for all inputs.
    """
    # Production-realistic cache: only notes-area MOCs in map_notes.
    # The template-vault MOC was excluded by moc_scan and never reached
    # map_notes — so it is correctly absent here.
    cache = {
        "map_notes": [
            {
                "path": "Atlas/Software MOC.md",
                "title": "Software MOC",
                "topics": ["software"],
                "kind": "moc",
            },
            # No entry for "X/Templates/Software MOC Template.md"
        ]
    }

    result = build_mocs(cache)
    paths = [m["path"] for m in result]

    # Template-vault path must be absent
    template_path = "X/Templates/Software MOC Template.md"
    assert template_path not in paths, (
        f"Template-vault path '{template_path}' must not appear in build_mocs() "
        f"output. moc_scan excludes it before writing map_notes. Got: {paths}"
    )

    # Notes-area MOC must be present (guard against vacuous pass)
    assert "Atlas/Software MOC.md" in paths, (
        f"Notes-area MOC must still appear — otherwise this test is vacuously "
        f"passing because build_mocs returned nothing. Got: {paths}"
    )


def test_f5_2b_template_vault_excluded_prefix_never_in_map_notes():
    """Complementary guard: if a template-vault entry somehow appeared in
    map_notes (misconfigured scan), build_mocs would pass it through — because
    filtering is moc_scan's responsibility, not build_mocs'.

    This test documents that contract explicitly and makes the single-source
    responsibility visible: build_mocs is a pure projector, not a filter.
    If this test fails (build_mocs has its own filter), F5#3 must also be
    revisited.
    """
    # Artificially inject a template-vault entry into map_notes to confirm
    # build_mocs does NOT silently drop it (that would mean a hidden filter).
    cache = {
        "map_notes": [
            {
                "path": "X/Templates/Software MOC Template.md",
                "title": "Software MOC Template",
                "topics": ["software"],
                "kind": "moc",
            }
        ]
    }
    result = build_mocs(cache)
    paths = [m["path"] for m in result]

    # build_mocs is a pure projector — it passes all map_notes entries through.
    # Exclusion is moc_scan's job; build_mocs trusts the cache.
    assert "X/Templates/Software MOC Template.md" in paths, (
        f"build_mocs must pass map_notes entries through without its own path "
        f"filter — filtering is moc_scan's responsibility. If this assertion "
        f"fails, build_mocs has a hidden path filter that violates single-source. "
        f"Got paths: {paths}"
    )


# ---------------------------------------------------------------------------
# F5#3 — build_mocs has NO separate/path-only MOC fallback (negative assertion)
# ---------------------------------------------------------------------------

def test_f5_3_build_mocs_single_map_notes_source():
    """build_mocs must derive shared_ctx.mocs from the SINGLE cache.map_notes
    source — no separate path enumeration, no independent vault scan, no
    path-pattern fallback alongside map_notes.

    Strategy: inspect the source of build_mocs for any access to paths other
    than cache['map_notes']. Also verify by calling build_mocs with an empty
    map_notes and a fabricated cache key to prove it doesn't look elsewhere.

    This is a negative-assertion / characterization guard. If build_mocs is
    already single-source (the expected state), this test passes immediately.
    If a path-only fallback exists, this test is RED — the fallback must be
    removed to go GREEN.
    """
    # --- behavioural check: empty map_notes → empty result regardless of other keys ---
    # If build_mocs had a path-only fallback, it might return entries when
    # map_notes is empty but some other cache key hints at MOCs.
    cache_with_only_phantom = {
        "map_notes": [],  # empty — the single source
        # Simulate leftover keys that a path-only scanner might read:
        "entries": [
            {
                "path": "Atlas/Software MOC.md",
                "title": "Software MOC",
                "topics": ["software"],
                "kind": "moc",
            }
        ],
        "scope_paths": ["Atlas/"],
        "moc_tag": "#type/others/moc",
    }
    result = build_mocs(cache_with_only_phantom)
    assert result == [], (
        f"build_mocs must return [] when map_notes is empty — it must NOT fall "
        f"back to cache.entries, cache.scope_paths, or any other key. "
        f"Got: {result}. "
        f"A non-empty result here means a path-only fallback exists — remove it."
    )

    # --- source-inspection check: verify build_mocs only accesses 'map_notes' ---
    # Parse the source to confirm 'map_notes' is the only cache key accessed.
    source = inspect.getsource(build_mocs)
    assert "map_notes" in source, (
        "build_mocs source must reference 'map_notes' — this is a sanity guard."
    )

    # Known-bad patterns: direct access to other cache keys that would indicate
    # a parallel path enumeration alongside map_notes.
    forbidden_patterns = [
        'cache.get("entries")',
        "cache['entries']",
        'cache.get("scope_paths")',
        "cache['scope_paths']",
        'cache.get("moc_tag")',
        "cache['moc_tag']",
        'cache.get("exclude_paths")',
        "cache['exclude_paths']",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source, (
            f"build_mocs contains a forbidden cache access '{pattern}' that "
            f"suggests a parallel path-only fallback alongside map_notes. "
            f"The single-source contract requires map_notes ONLY. "
            f"Remove the fallback to satisfy Feature 5 (F5#3)."
        )


# ---------------------------------------------------------------------------
# F5#4 — item matching a notes-area MOC links to it, not needs_new_moc
# ---------------------------------------------------------------------------

def test_f5_4_matching_item_gets_link_not_new_moc(tmp_path):
    """When an inbox item's topics overlap with a notes-area MOC in
    shared_ctx.mocs, the correct action is link_to_moc (candidate offered),
    NOT needs_new_moc.

    We verify this at the shared-ctx boundary: after build_mocs processes a
    cache with a matching notes-area MOC, shared_ctx.mocs contains that MOC
    with the topics needed for inbox-analyst to score it as a candidate.

    The explicit link_to_moc vs needs_new_moc decision lives in inbox-analyst,
    but that decision is only correct if shared_ctx.mocs contains the MOC.
    This test verifies the upstream feed is correct.

    Fixture: a notes-area MOC for "software" topics; an item whose topics
    include "software".  shared_ctx.mocs must expose that MOC so inbox-analyst
    can score and offer it.
    """
    import json
    import yaml
    from unittest.mock import patch

    # Cache contains a notes-area MOC that overlaps with the item's topics.
    cache = {
        "map_notes": [
            {
                "path": "Atlas/Software MOC.md",
                "title": "Software MOC",
                "topics": ["software", "programming", "development"],
                "kind": "moc",
            },
            {
                "path": "Atlas/Health MOC.md",
                "title": "Health MOC",
                "topics": ["health", "fitness", "nutrition"],
                "kind": "moc",
            },
        ],
        "placeholder_mocs": [],
    }

    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    cache_file.write_text(yaml.dump(cache))
    vault_cfg_file.write_text(yaml.dump({"profile": "miyo"}))

    argv = [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", "f5-4-test",
        "--skip-reconcile",
    ]

    with patch("sys.argv", argv), \
         patch.object(scb, "build_tag_prefixes", return_value=[]), \
         patch.object(scb, "build_classification_keywords", return_value={}), \
         patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()

    assert rc == 0, f"main() returned {rc}"
    ctx = json.loads(out_file.read_text())

    mocs = ctx.get("mocs", [])
    moc_paths = [m["path"] for m in mocs]

    # Both notes-area MOCs must appear in shared_ctx.mocs.
    assert "Atlas/Software MOC.md" in moc_paths, (
        f"Software MOC must be in shared_ctx.mocs so inbox-analyst can offer it "
        f"as a link_to_moc candidate for a software-topic item. Got: {moc_paths}"
    )
    assert "Atlas/Health MOC.md" in moc_paths, (
        f"Health MOC must be in shared_ctx.mocs. Got: {moc_paths}"
    )

    # Verify that the software MOC's topics are preserved for scoring.
    software_moc = next(m for m in mocs if m["path"] == "Atlas/Software MOC.md")
    assert "software" in software_moc["topics"], (
        f"Software MOC topics must include 'software' for inbox-analyst topic "
        f"matching. Without this, the MOC cannot be offered as a candidate and "
        f"inbox-analyst would incorrectly fire needs_new_moc. Got topics: "
        f"{software_moc['topics']}"
    )

    # Guard: zero MOCs in shared_ctx.mocs would trivially force needs_new_moc
    # for every item — verify we have a non-empty set.
    assert len(mocs) >= 2, (
        f"shared_ctx.mocs must carry all notes-area MOCs from map_notes. "
        f"An empty or truncated mocs list would force needs_new_moc on items "
        f"that have perfectly valid link targets. Got {len(mocs)} MOC(s)."
    )
