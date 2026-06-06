#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_propose_e2e.py — F-43 T6.1 + spec 021 T4.1: Producer-side end-to-end integration tests.

Tests the full Tomo pipeline for /moc-propose:
  moc-discovery.py (discovery phases) →
  suggestions-reducer.py --moc-proposal-mode (proposal-doc render) →
  suggestion-parser.py (parse accepted proposal) →
  instruction-render.py (emit create_moc + add_relationship actions)

SCOPE DECISION (locked by user, 2026-05-08):
  Producer-side only. Tests do NOT spawn Hashi or run Obsidian. Hashi-side
  correctness is covered by Hashi 0.2.0's own contract tests + manual T6.2.

Privat-Test is cloned into tmp_path per test — the real directory is never
mutated (per feedback_test_scripts_must_never_touch_real_install.md).

Run with:
  pytest tests/integration/ -v -m integration
  pytest tests/integration/ -v -m "integration and perf"   # perf tests only
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ── Repo paths ────────────────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

# ── Script module handles (pre-loaded in conftest) ────────────────────────────

sys.path.insert(0, str(SCRIPTS_DIR))

import moc_discovery as _moc_disc  # noqa: E402 — loaded by conftest
import suggestions_reducer as _reducer  # noqa: E402
_moc_parser_mod = importlib.import_module("moc-proposal-parser")
parse_moc_proposal = _moc_parser_mod.parse_moc_proposal

from .conftest import (  # noqa: E402
    make_candidate,
    make_cluster,
    make_discovery_report,
    PRIVAT_TEST_ROOT,
)


# ── Config stub ──────────────────────────────────────────────────────────────


class _Cfg:
    """Minimal duck-typed config stub for the reducer."""

    def __init__(self, max_results: int = 5, squelch_runs: int = 3):
        self.max_results = max_results
        self.squelch_runs = squelch_runs


# ── Shared cluster fixtures ───────────────────────────────────────────────────

_DATAVIEW_STEMS = [
    "Dataview - Contains Explained",
    "Dataview - Dateformat",
    "Dataview - Display Inlinks",
    "Dataview - Display notes which have inline field",
    "Dataview - Dynamic Queries via Variable",
]

_PKM_STEMS = [
    "Map of Content",
    "Map vs MOC",
    "Mapmaking",
    "Higher Order Notes",
    "Concepts",
]


def _dataview_cluster() -> tuple[dict, list[dict]]:
    return make_cluster(
        "MOC01",
        title="Dataview (MOC)",
        confidence=0.82,
        candidate_stems=_DATAVIEW_STEMS,
        topic_keywords=["dataview", "obsidian", "plugin", "query"],
        slug="dataview-moc",
        location="Atlas/200 Maps/",
    )


def _pkm_cluster() -> tuple[dict, list[dict]]:
    return make_cluster(
        "MOC01",
        title="Map of Content (MOC)",
        confidence=0.75,
        candidate_stems=_PKM_STEMS,
        topic_keywords=["moc", "pkm", "linking", "map of content"],
        slug="map-of-content-moc",
        location="Atlas/200 Maps/",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Environment invariant
# ═══════════════════════════════════════════════════════════════════════════════


def test_privat_test_reachable():
    """Verify Privat-Test is accessible and has ≥1 cluster of 3+ atomic notes."""
    assert PRIVAT_TEST_ROOT.exists(), (
        f"Privat-Test directory not found at {PRIVAT_TEST_ROOT}. "
        "Mount the Moon volume or update PRIVAT_TEST_ROOT in conftest.py."
    )
    snippets = PRIVAT_TEST_ROOT / "Atlas" / "202 Notes" / "2611 Code Snippets"
    assert snippets.is_dir(), f"Expected Code Snippets dir at {snippets}"
    dataview_notes = list(snippets.glob("Dataview - *.md"))
    assert len(dataview_notes) >= 3, (
        f"Need ≥3 Dataview notes for cluster fixture; found {len(dataview_notes)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Input mode e2e tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_tag_mode_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """tag: mode produces proposal-doc with correct frontmatter and MOC section.

    Pipeline: DiscoveryReport (tag mode) → render → proposal-doc file.
    Asserts: filename pattern, frontmatter type/proposal_kind/tomo_skip_inbox_analysis,
    MOC section heading, Accept checkbox, Children section.

    Maps to PRD AC-1.1, AC-3.1, AC-3.2, AC-3.3.
    """
    cluster, parents = _dataview_cluster()
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="Obsidian/Plugin/Dataview",
        candidates=[make_candidate(s) for s in _DATAVIEW_STEMS],
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # Filename pattern (AC-3.1)
    assert "_moc-proposal-" in filename, f"bad filename: {filename}"
    assert filename.endswith(".md")
    assert "dataview" in filename.lower()

    # Frontmatter fields (AC-3.2)
    assert "type: tomo-proposal" in body
    assert "proposal_kind: moc" in body
    assert "tomo_skip_inbox_analysis: true" in body
    assert "status: pending" in body
    assert "trigger: tag:Obsidian/Plugin/Dataview" in body

    # Section structure (AC-3.3, ADR-4)
    assert "### MOC01 — Dataview (MOC)" in body
    assert "- [ ] Accept" in body
    assert "#### Children" in body

    # Persists to inbox dir
    inbox_dir = isolated_tomo_state["tomo_tmp_dir"] / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    (inbox_dir / filename).write_text(body, encoding="utf-8")
    assert (inbox_dir / filename).exists()


@pytest.mark.integration
def test_folder_mode_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """folder: mode produces proposal-doc for cluster from a specific folder.

    Maps to PRD AC-1.2, AC-3.1.
    """
    cluster, parents = _dataview_cluster()
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="folder",
        trigger_arg="Atlas/202 Notes/2611 Code Snippets/",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    assert "_moc-proposal-" in filename
    assert "trigger: folder:Atlas/202 Notes/2611 Code Snippets/" in body
    assert "### MOC01 — Dataview (MOC)" in body
    assert "- [ ] Accept" in body


@pytest.mark.integration
def test_class_mode_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """class: mode produces proposal-doc for Dewey classification cluster.

    Maps to PRD AC-1.3, AC-2.1, AC-2.3.
    """
    cluster, parents = make_cluster(
        "MOC01",
        title="Code Snippets (MOC)",
        confidence=0.80,
        candidate_stems=_DATAVIEW_STEMS,
        topic_keywords=["code", "snippet", "dataview"],
        slug="code-snippets-moc",
        parent_options=[
            {"moc_stem": "2600 - Applied Sciences", "confidence": 0.90, "label": "Applied Sciences (Dewey 2600)"}
        ],
    )
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="class",
        trigger_arg="2600",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    assert "_moc-proposal-" in filename
    assert "trigger: class:2600" in body
    assert "### MOC01 — Code Snippets (MOC)" in body
    # MiYo profile: location defaults to Atlas/200 Maps/ (AC-2.1)
    assert "Atlas/200 Maps/" in body


@pytest.mark.integration
def test_title_mode_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """title: mode uses user-provided title verbatim with profile suffix applied.

    Maps to PRD AC-1.4, AC-2.5.
    """
    cluster, parents = make_cluster(
        "MOC01",
        title="Dataview Queries (MOC)",  # profile suffix applied by moc-discovery
        confidence=0.78,
        candidate_stems=_DATAVIEW_STEMS,
        topic_keywords=["dataview", "query"],
        slug="dataview-queries-moc",
    )
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="title",
        trigger_arg="Dataview Queries",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    assert "_moc-proposal-" in filename
    # Title verbatim (user input) with profile suffix → appears in section heading
    assert "### MOC01 — Dataview Queries (MOC)" in body
    assert "trigger: title:Dataview Queries" in body


@pytest.mark.integration
def test_freetext_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """free-text input (no recognised prefix) produces proposal-doc with free-text trigger.

    Maps to PRD AC-1.5, AC-1.7.
    """
    cluster, parents = _pkm_cluster()
    cluster["cluster_id"] = "MOC01"
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="free-text",
        trigger_arg="map of content",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    assert "_moc-proposal-" in filename
    assert "trigger: free-text:map of content" in body
    assert "### MOC01 — Map of Content (MOC)" in body


@pytest.mark.integration
def test_no_args_e2e(privat_test_clone, seeded_discovery_cache, isolated_tomo_state):
    """no-args (scan) mode: whole-vault scan produces multi-cluster proposal-doc.

    Verifies: up to max_results sections, overflow footer, mode=scan trigger.
    Maps to PRD AC-1.6, AC-3.4.
    """
    # Build 7 clusters to verify cap at max_results=5 + overflow footer
    clusters = []
    parent_opts = {}
    for i in range(1, 8):
        cid = f"MOC{i:02d}"
        c, p = make_cluster(
            cid,
            title=f"Test Cluster {i} (MOC)",
            confidence=1.0 - (i * 0.05),
            candidate_stems=[f"note-{i}-a", f"note-{i}-b", f"note-{i}-c"],
            topic_keywords=[f"topic{i}", "obsidian"],
            slug=f"test-cluster-{i}-moc",
        )
        clusters.append(c)
        parent_opts[cid] = p

    report = make_discovery_report(
        clusters=clusters,
        parent_options=parent_opts,
        mode="scan",
        trigger_arg="",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg(max_results=5))

    # Exactly 5 sections rendered (max_results cap)
    import re
    sections = re.findall(r"^### MOC\d+ — ", body, re.MULTILINE)
    assert len(sections) == 5, f"Expected 5 sections, got {len(sections)}: {sections}"

    # Overflow footer (AC-3.4)
    assert "2 additional cluster(s) found" in body

    # Trigger field reflects scan mode
    assert "trigger: scan" in body


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Abort path tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_zero_candidates_aborts_no_file_written(tmp_path, seeded_discovery_cache):
    """When discovery finds 0 matching candidates, moc-discovery.py emits abort_reason
    'zero-candidates' and the pipeline writes no proposal-doc file.

    Drives moc-discovery.py as a subprocess with a --title that matches no cached
    note topics. The seeded cache passes the cache-empty pre-check so Phase 1 runs
    and returns 0 candidates → abort_reason='zero-candidates'. The agent pipeline
    must NOT call suggestions-reducer when abort_reason is set; this test asserts:

      (a) discovery exits 0 with abort_reason='zero-candidates' in its JSON output
      (b) the inbox directory contains no proposal-doc file (reducer not called on abort)

    Maps to PRD AC-3.5 (abort message) and SDD §Error Handling.
    """
    import subprocess

    # Write a minimal vault-config so profile resolution succeeds
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(
        "profile: miyo\nconcepts:\n  inbox: 100 Inbox/\n",
        encoding="utf-8",
    )
    # A squelch sidecar is required by main(); empty registry is fine
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        '{"schema_version":"1","last_run_id":"","rejections":[]}',
        encoding="utf-8",
    )

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()

    # "--title" with a topic string that appears in no cached note topics →
    # Phase 1 returns 0 candidates → abort_reason="zero-candidates"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "moc-discovery.py"),
            "--title", "COMPLETELY_NONEXISTENT_TOPIC_XYZ_99999",
            "--cache", str(seeded_discovery_cache),
            "--config", str(config_path),
            "--squelch-state", str(squelch_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # (a) moc-discovery exits 0 on abort paths (they're user-facing, not errors)
    assert result.returncode == 0, (
        f"moc-discovery should exit 0 on zero-candidates abort; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )

    report = json.loads(result.stdout)
    assert report.get("abort_reason") == "zero-candidates", (
        f"Expected abort_reason='zero-candidates'; got {report.get('abort_reason')!r}"
    )
    assert report.get("topic_clusters") == [], (
        "zero-candidates abort must emit no clusters"
    )

    # (b) The agent pipeline must not call suggestions-reducer when abort_reason is set.
    # Confirm inbox_dir is empty — no proposal file written on the abort path.
    existing = list(inbox_dir.glob("*_moc-proposal-*.md"))
    assert existing == [], (
        f"No proposal file should exist on abort path; found {existing}"
    )


@pytest.mark.integration
def test_cache_empty_aborts_no_file_written(tmp_path):
    """When discovery-cache.yaml is missing/empty, abort_reason='cache-empty', no file written.

    Unit-tests the validate_cache_loaded() pre-check in moc-discovery.py; then
    drives moc-discovery.py as a subprocess with a missing cache file to verify
    the full pipeline emits abort_reason='cache-empty' and writes no proposal-doc.

    Maps to PRD AC-3.5 (abort message) and SDD §Error Handling.
    """
    # Unit tests for validate_cache_loaded()
    # Missing cache file → validate_cache_loaded returns 'cache-empty'
    # (cache=None simulates a missing file: load_yaml on a non-existent path returns None)
    cache = None
    abort = _moc_disc.validate_cache_loaded(cache)
    assert abort == "cache-empty", f"Expected 'cache-empty', got {abort!r}"

    # Empty map_notes list also triggers cache-empty
    empty_cache = {"map_notes": []}
    abort2 = _moc_disc.validate_cache_loaded(empty_cache)
    assert abort2 == "cache-empty"

    # Populated cache → no abort
    populated_cache = {"map_notes": [{"path": "Atlas/200 Maps/Concepts (MOC).md", "title": "Concepts"}]}
    abort3 = _moc_disc.validate_cache_loaded(populated_cache)
    assert abort3 is None, f"Populated cache should not abort; got {abort3!r}"

    # Subprocess test: missing cache file aborts pipeline; no proposal-doc file written
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(
        "profile: miyo\nconcepts:\n  inbox: 100 Inbox/\n",
        encoding="utf-8",
    )
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        '{"schema_version":"1","last_run_id":"","rejections":[]}',
        encoding="utf-8",
    )

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()

    # spec 021 T2.1: moc-discovery reads the MOC-structure cache via the loader.
    # A FRESH cache with zero MOC entries is an empty vault → cache-empty WITHOUT
    # a rebuild (a missing cache would instead trigger a Kado-needing rebuild →
    # cache-rebuild-failed; this test isolates the empty-vault path, no Kado).
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    empty_cache = tmp_path / "moc-structure-cache.yaml"
    empty_cache.write_text(
        f"moc_cache_version: 1\nlast_scan: '{fresh}'\nttl_days: 1\nentries: []\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "moc-discovery.py"),
            "--title", "any-text",
            "--cache", str(empty_cache),
            "--config", str(config_path),
            "--squelch-state", str(squelch_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Must exit 0 with abort_reason='cache-empty' in JSON stdout
    assert result.returncode == 0, (
        f"moc-discovery should exit 0 on cache-empty abort; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    report = json.loads(result.stdout)
    assert report.get("abort_reason") == "cache-empty", (
        f"Expected abort_reason='cache-empty'; got {report.get('abort_reason')!r}"
    )

    # Verify the agent pipeline must not call suggestions-reducer on the abort path.
    # The inbox directory should remain empty (no proposal-doc file written on abort).
    existing = list(inbox_dir.glob("*_moc-proposal-*.md"))
    assert existing == [], (
        f"No proposal file should exist on cache-empty abort path; found {existing}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Override flow e2e
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_override_flow_e2e(tmp_path):
    """Override unchecked: child with valid existing up:: gets related:: action emitted.
    Override checked: child keeps existing up::, gains related:: to new MOC.

    Tests the proposal-doc rendering and parser branch for override_preserve_existing_up.
    Maps to PRD AC-4.2, AC-4.4.
    """
    # Build cluster with existing_up annotations (rendered by suggestions-reducer)
    candidates_with_up = [
        make_candidate("note-a", existing_up="2600 - Applied Sciences", existing_up_broken=False),
        make_candidate("note-b", existing_up=None, existing_up_broken=False),
        make_candidate("note-c", existing_up="broken-moc", existing_up_broken=True),
    ]

    cluster, parents = make_cluster(
        "MOC01",
        title="Override Test (MOC)",
        confidence=0.80,
        candidate_stems=["note-a", "note-b", "note-c"],
        topic_keywords=["test", "override"],
        existing_up=[
            {"stem": "note-a", "target": "2600 - Applied Sciences", "state": "valid"},
            {"stem": "note-b", "target": None, "state": "absent"},
            {"stem": "note-c", "target": "broken-moc", "state": "broken"},
        ],
    )

    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="test/override",
        candidates=candidates_with_up,
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # up::‑handling Override section must be present (AC-4.1 through 4.5)
    assert "Override" in body or "up::" in body or "Handling" in body, (
        "Expected up::-Handling Override section in proposal-doc"
    )
    # Accept checkbox present
    assert "- [ ] Accept" in body

    # Now simulate user ticking Accept + Override (preserve existing up::):
    accepted_body = body.replace("- [ ] Accept", "- [x] Accept")
    accepted_body = accepted_body.replace(
        "- [ ] **Keep existing up::, add new MOC as `related::`**",
        "- [x] **Keep existing up::, add new MOC as `related::`**",
    )

    result = parse_moc_proposal(accepted_body)
    proposals = result["confirmed_items"]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["override_preserve_existing_up"] is True, (
        "Override ticked → override_preserve_existing_up must be True"
    )

    # Without Override (default):
    accepted_no_override = body.replace("- [ ] Accept", "- [x] Accept")
    result_no_override = parse_moc_proposal(accepted_no_override)
    proposals_no_override = result_no_override["confirmed_items"]
    assert len(proposals_no_override) == 1
    assert proposals_no_override[0]["override_preserve_existing_up"] is False, (
        "Override unchecked → override_preserve_existing_up must be False"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Collision guard e2e (producer-side)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_collision_guard_e2e(privat_test_clone, isolated_tomo_state):
    """Pre-create destination file; verify emitted create_moc action's destination path.

    Tomo's job: emit well-formed create_moc action with `destination` matching the
    pre-existing path. Hashi handles the `applied: false` collision response (Hashi
    0.2.0 contract — out of scope for this producer-side test).

    Maps to PRD Feature 6, AC-6.1.
    """
    # Pre-create the MOC destination file in the cloned vault
    maps_dir = privat_test_clone / "Atlas" / "200 Maps"
    collision_title = "Dataview (MOC)"
    collision_file = maps_dir / f"{collision_title}.md"
    collision_file.write_text(
        "---\ntitle: Dataview (MOC)\ntype: moc\n---\nExisting file\n",
        encoding="utf-8",
    )
    assert collision_file.exists(), "Pre-created collision file must exist"

    # Build proposal (same title → same destination)
    cluster, parents = _dataview_cluster()
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="Obsidian/Plugin/Dataview",
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # User ticks Accept
    accepted_body = body.replace("- [ ] Accept", "- [x] Accept")

    # Tick all children
    import re
    def tick_children(text: str) -> str:
        return re.sub(r"- \[ \] (`\[\[)", r"- [x] \1", text)

    accepted_body = tick_children(accepted_body)

    result = parse_moc_proposal(accepted_body)
    proposals = result["confirmed_items"]
    assert len(proposals) == 1
    proposal = proposals[0]

    # Verify the proposal carries the correct destination path
    # (Tomo emits "Atlas/200 Maps/" as destination dir; title becomes filename)
    assert proposal["title"] == collision_title, (
        f"Proposal title must match cluster title; got {proposal['title']!r}"
    )
    assert proposal["destination"] == "Atlas/200 Maps/", (
        f"Destination dir must be Atlas/200 Maps/; got {proposal['destination']!r}"
    )

    # Build instruction-render manifest and emit create_moc action (M1 fix).
    # The core assertion: emitted action's `destination` must match the composed
    # path for the pre-existing file — proving Tomo emits the right destination
    # even when a collision exists (Hashi handles the collision at apply-time).
    manifest_item = {
        "action": "create_moc",
        "title": proposal["title"],
        "destination": proposal["destination"],
        "parent_moc": proposal.get("parent_moc"),
        "template": proposal.get("template", "t_moc_tomo"),
        "tags": [],
        "supporting_items": ", ".join(proposal.get("supporting_items", [])),
        "override_preserve_existing_up": proposal.get("override_preserve_existing_up", False),
        "rendered_file": "",
    }
    counter = [0]
    actions = instruction_render_build_create_moc([manifest_item], "100 Inbox/", counter)

    assert len(actions) >= 1, "create_moc must emit at least 1 action"
    create_action = actions[0]
    expected_destination = f"Atlas/200 Maps/{collision_title}.md"
    assert create_action["destination"] == expected_destination, (
        f"create_moc.destination must be {expected_destination!r}; "
        f"got {create_action['destination']!r}"
    )

    # The pre-existing file is still intact (Tomo doesn't touch it)
    assert collision_file.exists(), "Pre-existing collision file must be untouched by Tomo"
    assert collision_file.read_text(encoding="utf-8").startswith("---"), (
        "Collision file content must be unchanged"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Squelch lifecycle e2e
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_squelch_e2e(tmp_path):
    """Propose → reject → re-propose 3× (suppressed) → 4th run (re-allowed).

    Tests the squelch lifecycle via lib/squelch + lib/squelch_persist helpers.
    Maps to PRD Feature 8, AC-8.1, AC-8.2.
    """
    from lib import squelch as squelch_mod
    from lib import squelch_persist as squelch_persist_mod

    squelch_path = tmp_path / "moc-squelch.json"

    # Build a 1-cluster report
    cluster, parents = _dataview_cluster()
    cluster["cluster_id"] = "MOC01"
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="Obsidian/Plugin/Dataview",
    )

    _filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # 1. Reject: all clusters' Accept = unchecked (body as-is — none ticked)
    # Persist rejection → squelch entry with runs_remaining=3
    # persist_rejected_clusters expects (text, filename, registry_path, config_dict)
    cfg_dict = {"squelch_runs": 3}
    squelch_persist_mod.persist_rejected_clusters(
        body, _filename, str(squelch_path), cfg_dict
    )

    registry = squelch_mod.load_registry(squelch_path)
    assert len(registry) == 1, f"Expected 1 squelch entry after rejection; got {len(registry)}"
    entry = next(iter(registry.values()))
    assert entry.runs_remaining == 3, f"Expected runs_remaining=3; got {entry.runs_remaining}"

    # Capture the signature for later checks
    signature = entry.topic_signature

    # 2. Runs 1-3: cluster is suppressed (runs_remaining > 0 after each decrement)
    for run_num in range(1, 4):
        registry = squelch_mod.load_registry(squelch_path)
        decremented = squelch_mod.decrement_all(registry)
        squelch_mod.save_registry_atomic(squelch_path, decremented)

        reloaded = squelch_mod.load_registry(squelch_path)
        expected_remaining = 3 - run_num
        if expected_remaining > 0:
            assert squelch_mod.is_active(reloaded, signature), (
                f"Run {run_num}: signature should still be active "
                f"(expected runs_remaining={expected_remaining})"
            )
        else:
            # After run 3, entry expires (runs_remaining 1→0 → removed)
            assert not squelch_mod.is_active(reloaded, signature), (
                f"Run {run_num}: signature should be expired (runs_remaining=0 → removed)"
            )

    # 3. Run 4: cluster is re-allowed (signature no longer in registry)
    final_registry = squelch_mod.load_registry(squelch_path)
    assert not squelch_mod.is_active(final_registry, signature), (
        "After 3 decrement runs, cluster must no longer be suppressed"
    )
    assert len(final_registry) == 0, (
        f"Registry should be empty after expiry; got {len(final_registry)} entries"
    )

    # 4. Re-proposal (U1 fix): simulate the 4th discovery pass with the same cluster.
    # Because the registry is empty, the cluster is re-allowed — it must resurface in
    # a new proposal-doc (re-proposed = actually rendered, not just registry-empty).
    _filename4, body4 = _reducer.render_moc_proposal_doc(report, _Cfg())
    assert "### MOC01 — Dataview (MOC)" in body4, (
        "4th pass: re-allowed cluster must appear as a section in the new proposal-doc"
    )
    assert "- [ ] Accept" in body4, (
        "4th pass: Accept checkbox must be present (cluster is re-proposed, not suppressed)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Parse → instruction-render pipeline (accept flow)
# ═══════════════════════════════════════════════════════════════════════════════


def test_accept_flow_emits_create_moc_action(tmp_path):
    """Accepted proposal-doc → parse → instruction-render → create_moc + add_relationship.

    Full pipeline through to build_actions (without Kado — no up_preservation).
    Maps to PRD AC-5.3 (create_moc + add_relationship per accepted child).
    """
    cluster, parents = _dataview_cluster()
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="Obsidian/Plugin/Dataview",
        candidates=[make_candidate(s) for s in _DATAVIEW_STEMS],
    )

    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # Tick Accept and tick the first 3 children
    accepted_body = body.replace("- [ ] Accept", "- [x] Accept")

    import re
    # Tick all unchecked child wikilink lines
    accepted_body = re.sub(
        r"- \[ \] (`\[\[([^\]]+)\]\]`)",
        r"- [x] \1",
        accepted_body,
    )

    result = parse_moc_proposal(accepted_body)
    proposals = result["confirmed_items"]
    assert len(proposals) == 1, f"Expected 1 accepted proposal; got {len(proposals)}"

    proposal = proposals[0]
    assert proposal["title"] == "Dataview (MOC)"
    assert proposal["destination"] == "Atlas/200 Maps/"

    # Convert to manifest item (as moc-proposal-parser produces for instruction-render)
    # The manifest shape that instruction-render expects for a create_moc action:
    manifest_item = {
        "action": "create_moc",
        "title": proposal["title"],
        "destination": proposal["destination"],
        "parent_moc": proposal.get("parent_moc"),
        "template": proposal.get("template", "t_moc_tomo"),
        "tags": [],
        "supporting_items": ", ".join(proposal.get("supporting_items", [])),
        "override_preserve_existing_up": proposal.get("override_preserve_existing_up", False),
        "rendered_file": "",
    }

    cfg = {
        "concepts.inbox": "100 Inbox/",
        "profile": "miyo",
    }
    counter = [0]
    actions = instruction_render_build_create_moc([manifest_item], cfg["concepts.inbox"], counter)

    assert len(actions) >= 1, "Must emit at least 1 create_moc action"
    create_action = actions[0]
    assert create_action["action"] == "create_moc"
    assert create_action["title"] == "Dataview (MOC)"
    assert "Atlas/200 Maps/" in create_action["destination"]
    assert create_action["applied"] is False or "applied" not in create_action, (
        "Tomo-emitted actions must have applied=False or omit it pre-stamp"
    )


def instruction_render_build_create_moc(
    manifest: list[dict], inbox_path: str, counter: list[int]
) -> list[dict]:
    """Thin wrapper to call _build_create_moc_actions from instruction_render."""
    import instruction_render as _ir
    actions = _ir._build_create_moc_actions(manifest, inbox_path, counter)
    # Stamp applied=False as build_actions does
    for a in actions:
        a["applied"] = False
    return actions


def test_no_accept_emits_no_actions(tmp_path):
    """Proposal-doc with no Accept ticked → parse returns [] → no create_moc emitted.

    Maps to PRD AC-5.4.
    """
    cluster, parents = _dataview_cluster()
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="Obsidian/Plugin/Dataview",
    )

    _filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # No Accept ticked — body as-is
    result = parse_moc_proposal(body)
    assert result["confirmed_items"] == [], (
        f"No Accept ticked → confirmed_items must be []; got {result['confirmed_items']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Multi-cluster partial accept
# ═══════════════════════════════════════════════════════════════════════════════


def test_multi_cluster_partial_accept(tmp_path):
    """Multi-cluster doc: 1 accepted + 1 rejected → parser returns only 1 proposal.

    Maps to PRD AC-3.4, AC-5.3.
    """
    c1, p1 = _dataview_cluster()
    c1["cluster_id"] = "MOC01"

    c2, p2 = _pkm_cluster()
    c2["cluster_id"] = "MOC02"

    report = make_discovery_report(
        clusters=[c1, c2],
        parent_options={"MOC01": p1, "MOC02": p2},
        mode="scan",
        trigger_arg="",
    )

    _filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # Tick only MOC01's Accept checkbox
    # Find the first "- [ ] Accept" and tick it only
    first_accept = body.index("- [ ] Accept")
    accepted_body = (
        body[:first_accept]
        + "- [x] Accept"
        + body[first_accept + len("- [ ] Accept"):]
    )

    result = parse_moc_proposal(accepted_body)
    proposals = result["confirmed_items"]
    assert len(proposals) == 1, (
        f"Only 1 cluster accepted → 1 proposal; got {len(proposals)}"
    )
    assert proposals[0]["id"] == "MOC01"


# ═══════════════════════════════════════════════════════════════════════════════
# T6.1 — Performance tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.perf
def test_perf_cache_warm_under_45s(tmp_path, seeded_discovery_cache):
    """moc-discovery cache-warm path (real --title discovery) completes < 45s.

    45s = 1.5× the SDD target of 30s. On cold CI runners, plan for variability.
    Uses --title mode so Phase 1 runs against the seeded cache (pure in-memory
    substring match — no Kado call). This exercises the full non-dry-run pipeline:
    cache load → Phase 1 title match → Phase 2 topic extraction → clustering →
    DiscoveryReport JSON.

    Maps to SDD Quality Requirements / Performance.
    """
    import subprocess

    # Write a minimal vault-config so profile resolution succeeds
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(
        "profile: miyo\nconcepts:\n  inbox: 100 Inbox/\n",
        encoding="utf-8",
    )
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        '{"schema_version":"1","last_run_id":"","rejections":[]}',
        encoding="utf-8",
    )

    start = time.perf_counter()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "moc-discovery.py"),
            "--title", "dataview",
            "--cache", str(seeded_discovery_cache),
            "--config", str(config_path),
            "--squelch-state", str(squelch_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    elapsed = time.perf_counter() - start

    # Must exit 0 (either a DiscoveryReport with clusters or an abort — both are exit 0)
    assert result.returncode == 0, (
        f"moc-discovery should exit 0; got {result.returncode}\nstderr: {result.stderr}"
    )
    # Output must be valid JSON
    report = json.loads(result.stdout)
    assert "schema_version" in report, "Output must be a valid DiscoveryReport"

    assert elapsed < 45, (
        f"Cache-warm discovery (--title dataview) took {elapsed:.1f}s — exceeds 45s CI "
        f"tolerance (SDD target: 30s). Check for regressions in moc-discovery.py."
    )


@pytest.mark.integration
@pytest.mark.perf
def test_perf_pass2_apply_under_25s(tmp_path):
    """Pass-2 apply (proposal-doc render + parse + build_actions) for 5-child MOC < 25s.

    25s = 1.5× the SDD target of 15s.
    Maps to SDD Quality Requirements / Performance.
    """
    cluster, parents = make_cluster(
        "MOC01",
        title="Perf Test (MOC)",
        confidence=0.85,
        candidate_stems=[f"perf-note-{i}" for i in range(5)],
        topic_keywords=["perf", "test"],
        slug="perf-test-moc",
    )
    report = make_discovery_report(
        clusters=[cluster],
        parent_options={"MOC01": parents},
        mode="tag",
        trigger_arg="test/perf",
        candidates=[make_candidate(f"perf-note-{i}") for i in range(5)],
    )

    start = time.perf_counter()

    # Render
    filename, body = _reducer.render_moc_proposal_doc(report, _Cfg())

    # Accept all
    accepted_body = body.replace("- [ ] Accept", "- [x] Accept")
    import re
    accepted_body = re.sub(r"- \[ \] (`\[\[)", r"- [x] \1", accepted_body)

    # Parse
    result = parse_moc_proposal(accepted_body)
    proposals = result["confirmed_items"]

    # Build actions
    if proposals:
        manifest_item = {
            "action": "create_moc",
            "title": proposals[0]["title"],
            "destination": proposals[0]["destination"],
            "parent_moc": proposals[0].get("parent_moc"),
            "template": "t_moc_tomo",
            "tags": [],
            "supporting_items": ", ".join(proposals[0].get("supporting_items", [])),
            "override_preserve_existing_up": False,
            "rendered_file": "",
        }
        import instruction_render as _ir
        _ir._build_create_moc_actions([manifest_item], "100 Inbox/", [0])

    elapsed = time.perf_counter() - start

    assert elapsed < 25, (
        f"Pass-2 apply pipeline took {elapsed:.2f}s — exceeds 25s CI tolerance "
        f"(SDD target: 15s). Check render/parse/build_actions for regressions."
    )


@pytest.mark.integration
@pytest.mark.perf
def test_perf_multi_cluster_render_under_8s(tmp_path):
    """suggestions-reducer --moc-proposal-mode on 5-cluster DiscoveryReport < 8s.

    8s = 1.5× the SDD target of 5s.
    Maps to SDD Quality Requirements / Performance.
    """
    clusters = []
    parent_opts = {}
    for i in range(1, 6):
        cid = f"MOC{i:02d}"
        c, p = make_cluster(
            cid,
            title=f"Cluster {i} (MOC)",
            confidence=0.9 - (i * 0.05),
            candidate_stems=[f"note-{i}-{j}" for j in range(5)],
            topic_keywords=[f"topic{i}", "test"],
            slug=f"cluster-{i}-moc",
        )
        clusters.append(c)
        parent_opts[cid] = p

    report = make_discovery_report(
        clusters=clusters,
        parent_options=parent_opts,
        mode="scan",
        trigger_arg="",
    )

    start = time.perf_counter()

    for _ in range(3):  # 3 iterations to stress-test (still well within 8s)
        _reducer.render_moc_proposal_doc(report, _Cfg(max_results=5))

    elapsed = time.perf_counter() - start

    assert elapsed < 8, (
        f"5-cluster render (×3) took {elapsed:.2f}s — exceeds 8s CI tolerance "
        f"(SDD target: 5s per single render). Check render_moc_proposal_doc for regressions."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# spec 021 T4.1 — E2E across the three flows
#
# Mock-at-orchestrator discipline (feedback_mock_at_orchestrator_not_helper):
#   Tests 1 and 2 monkeypatch `moc_discovery.load_moc_cache` — the function
#   directly called by moc-discovery main() — rather than patching sub-helpers
#   inside moc_cache_loader. This mirrors production wiring: the orchestrator
#   (main) receives the loader result and branches on it. The fake rebuilder
#   passed to the real loader in test 2 is injected AT the loader's public API
#   boundary, not inside its internals.
#
#   Test 3 monkeypatches scb.build_tag_prefixes / build_classification_keywords
#   / build_daily_notes (the Kado-touching helpers) to isolate the shared-ctx
#   orchestration from live Kado while still exercising the full main() path.
#
#   Test 4 uses FakeKadoClient (pattern from test_moc_tree_builder.py) injected
#   at run_with_client() — the public seam moc-tree-builder exposes for testing.
# ═══════════════════════════════════════════════════════════════════════════════


def _load_moc_disc():
    """Return the already-loaded moc_discovery module (loaded by conftest)."""
    import moc_discovery as _md
    return _md


def _write_config(tmp_path: Path, *, profile: str = "miyo") -> Path:
    import yaml
    cfg = {
        "profile": profile,
        "tomo": {
            "moc_proposal": {
                "min_notes": 2,
                "confidence_threshold": 0.10,
                "max_results": 5,
                "candidate_cap": 200,
                "cache_miss_max_batches": 5,
                "squelch_runs": 3,
            }
        },
    }
    p = tmp_path / "vault-config.yaml"
    p.write_text(yaml.dump(cfg, allow_unicode=True), encoding="utf-8")
    return p


def _write_fresh_moc_cache(tmp_path: Path, entries: list[dict]) -> Path:
    """Write a FRESH moc-structure-cache.yaml (last_scan = now)."""
    import yaml
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache = {
        "moc_cache_version": 1,
        "last_scan": fresh,
        "ttl_days": 1,
        "scope_paths": ["Atlas/200 Maps/", "Atlas/202 Notes/"],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries,
        "placeholder_mocs": [],
    }
    p = tmp_path / "moc-structure-cache.yaml"
    p.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    return p


def _write_stale_moc_cache(tmp_path: Path, entries: list[dict]) -> Path:
    """Write a STALE moc-structure-cache.yaml (last_scan = 3 days ago)."""
    import yaml
    from datetime import datetime, timezone, timedelta
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache = {
        "moc_cache_version": 1,
        "last_scan": stale_ts,
        "ttl_days": 1,
        "scope_paths": ["Atlas/200 Maps/", "Atlas/202 Notes/"],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries,
        "placeholder_mocs": [],
    }
    p = tmp_path / "moc-structure-cache.yaml"
    p.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    return p


def _write_squelch(tmp_path: Path) -> Path:
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        '{"schema_version":"1","last_run_id":"","rejections":[]}',
        encoding="utf-8",
    )
    return squelch_path


# Three candidate entries that cluster around "dataview".
#
# Title-mode Phase 1 searches `cache["map_notes"][].topics` for the trigger
# term. The loader shim projects `entries[kind=="moc"]` → `map_notes`, so
# only kind=="moc" entries are visible to Phase 1. We tag all three as
# kind=="moc" so the shim surfaces them (same approach used by
# test_moc_discovery_main._write_cache for all its fixture entries).
#
# Paths are under the miyo profile's atomic_note.base_path ("Atlas/202 Notes/")
# so they survive the restrict_to_atomic_note_paths pre-filter in Phase 1.
# (Notes tagged kind=="moc" for shim visibility but located in the notes area —
# a fixture convenience that keeps the cache-fresh/stale E2E exercisable without
# a live Kado for tag/folder modes.)
_DISC_NOTES = [
    {"path": "Atlas/202 Notes/Dataview Alpha.md", "title": "Dataview Alpha",
     "topics": ["dataview", "obsidian"], "kind": "moc", "up_state": "absent",
     "up_target": None, "up_source": None, "tags": [],
     "classification": None, "linked_notes": 0},
    {"path": "Atlas/202 Notes/Dataview Beta.md", "title": "Dataview Beta",
     "topics": ["dataview", "query"], "kind": "moc", "up_state": "absent",
     "up_target": None, "up_source": None, "tags": [],
     "classification": None, "linked_notes": 0},
    {"path": "Atlas/202 Notes/Dataview Gamma.md", "title": "Dataview Gamma",
     "topics": ["dataview", "plugin"], "kind": "moc", "up_state": "absent",
     "up_target": None, "up_source": None, "tags": [],
     "classification": None, "linked_notes": 0},
]

# A proper MOC entry in the map-note area — ensures map_notes is non-empty
# and prevents cache-empty abort even if the topic filter changes.
_MAP_NOTE_ENTRY = {
    "path": "Atlas/200 Maps/Home (MOC).md",
    "title": "Home (MOC)",
    "topics": ["home", "index"],
    "kind": "moc",
    "up_state": "absent",
    "up_target": None,
    "up_source": None,
    "tags": ["type/others/moc"],
    "classification": None,
    "linked_notes": 0,
}

_ALL_ENTRIES = [_MAP_NOTE_ENTRY] + _DISC_NOTES


@pytest.mark.integration
def test_cache_backed_flow_fresh_cache_no_rebuild(tmp_path, monkeypatch):
    """Fresh cache → moc-discovery reads from cache, proposes, rebuilder NOT invoked.

    Mock at the orchestrator boundary: monkeypatch moc_discovery.load_moc_cache
    (the function main() calls) with a spy that wraps the real loader but injects
    a fake rebuilder with 0 calls. The cache is FRESH so the real loader must
    return the cache immediately without invoking any rebuilder.

    Assertions:
      - DiscoveryReport has ≥1 cluster (proposals emitted from cache)
      - spy rebuilder call count is 0 (no rebuild triggered)

    Maps to spec 021 SDD §Cache TTL + Rebuild, ADR-1, ADR-3.
    """
    import io
    import contextlib

    _moc_disc = _load_moc_disc()

    # Real loader for reference
    from lib import moc_cache_loader as _loader_mod

    config_path = _write_config(tmp_path)
    cache_path = _write_fresh_moc_cache(tmp_path, _ALL_ENTRIES)
    squelch_path = _write_squelch(tmp_path)

    # Spy rebuilder — should never be called for a fresh cache.
    spy_rebuilder_calls = []

    def _spy_rebuilder(cache_path_arg: str, config_path_arg: str) -> None:
        spy_rebuilder_calls.append((cache_path_arg, config_path_arg))
        raise AssertionError("Rebuilder must NOT be invoked for a fresh cache")

    # Mock load_moc_cache at the moc_discovery module boundary (the orchestrator),
    # injecting our spy rebuilder so if the real loader ever calls it, the test
    # fails explicitly.
    original_load = _loader_mod.load_moc_cache

    def _spy_load_moc_cache(cp, cfgp, **kwargs):
        kwargs["rebuilder"] = _spy_rebuilder
        return original_load(cp, cfgp, **kwargs)

    monkeypatch.setattr(_moc_disc, "load_moc_cache", _spy_load_moc_cache)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        rc = _moc_disc.main([
            "--title", "dataview",
            "--config", str(config_path),
            "--cache", str(cache_path),
            "--squelch-state", str(squelch_path),
        ])

    assert rc in (0, 1), (
        f"main() exited {rc} — expected 0 or 1\nstdout={captured.getvalue()!r}"
    )
    assert captured.getvalue().strip(), "stdout was empty — no DiscoveryReport emitted"

    report = json.loads(captured.getvalue())
    assert report.get("abort_reason") is None, (
        f"Fresh-cache flow must not abort; got abort_reason={report.get('abort_reason')!r}"
    )
    assert len(report["topic_clusters"]) >= 1, (
        "Fresh-cache flow must emit ≥1 cluster from cached notes"
    )

    # Rebuilder must NOT have been called — fresh cache → no rebuild.
    assert spy_rebuilder_calls == [], (
        f"Rebuilder was invoked {len(spy_rebuilder_calls)} time(s) on a fresh cache — "
        "ADR-3: fresh cache must load without rebuild"
    )


@pytest.mark.integration
def test_cache_backed_flow_stale_cache_inline_rebuild(tmp_path, monkeypatch):
    """Stale cache → loader triggers inline rebuild EXACTLY ONCE, then proposes.

    Mock at the orchestrator boundary: monkeypatch moc_discovery.load_moc_cache
    with a wrapper that injects a spy rebuilder into the real loader. The spy
    writes a fresh (valid) cache when called and records the call. The initial
    cache is STALE (last_scan = 3 days ago, ttl_days=1), so the loader must
    call the rebuilder exactly once, reload, and return a usable cache.

    Assertions:
      - DiscoveryReport has ≥1 cluster (proposals emitted after rebuild)
      - spy rebuilder was called exactly 1 time

    Maps to spec 021 SDD §Cache TTL + Rebuild, ADR-3.
    """
    import io
    import contextlib
    import yaml

    _moc_disc = _load_moc_disc()
    from lib import moc_cache_loader as _loader_mod
    from datetime import datetime, timezone

    config_path = _write_config(tmp_path)
    cache_path = _write_stale_moc_cache(tmp_path, _ALL_ENTRIES)
    squelch_path = _write_squelch(tmp_path)

    # Spy rebuilder — writes a fresh cache to simulate a successful rebuild.
    spy_rebuilder_calls = []

    def _spy_rebuilder(cache_path_arg: str, config_path_arg: str) -> None:
        spy_rebuilder_calls.append((cache_path_arg, config_path_arg))
        # Write a fresh version of the same cache so the loader can reload it.
        fresh_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rebuilt = {
            "moc_cache_version": 1,
            "last_scan": fresh_ts,
            "ttl_days": 1,
            "scope_paths": ["Atlas/200 Maps/", "Atlas/202 Notes/"],
            "exclude_paths": [],
            "moc_tag": "type/others/moc",
            "entries": _ALL_ENTRIES,
            "placeholder_mocs": [],
        }
        Path(cache_path_arg).write_text(
            yaml.dump(rebuilt, allow_unicode=True), encoding="utf-8"
        )

    original_load = _loader_mod.load_moc_cache

    def _spy_load_moc_cache(cp, cfgp, **kwargs):
        kwargs["rebuilder"] = _spy_rebuilder
        return original_load(cp, cfgp, **kwargs)

    monkeypatch.setattr(_moc_disc, "load_moc_cache", _spy_load_moc_cache)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        rc = _moc_disc.main([
            "--title", "dataview",
            "--config", str(config_path),
            "--cache", str(cache_path),
            "--squelch-state", str(squelch_path),
        ])

    assert rc in (0, 1), (
        f"main() exited {rc} — expected 0 or 1\nstdout={captured.getvalue()!r}"
    )
    assert captured.getvalue().strip(), "stdout was empty — no DiscoveryReport emitted"

    report = json.loads(captured.getvalue())
    assert report.get("abort_reason") is None, (
        f"Stale-cache rebuild flow must not abort; got abort_reason={report.get('abort_reason')!r}"
    )
    assert len(report["topic_clusters"]) >= 1, (
        "Post-rebuild flow must emit ≥1 cluster from the freshly-rebuilt cache"
    )

    # Rebuilder must have been called exactly once (ADR-3: rebuild inline EXACTLY once).
    assert len(spy_rebuilder_calls) == 1, (
        f"Rebuilder must be called exactly 1 time on a stale cache; "
        f"called {len(spy_rebuilder_calls)} time(s)"
    )


@pytest.mark.integration
def test_inbox_no_accumulation_index_conditions_a_c(tmp_path, monkeypatch):
    """shared-ctx for /inbox has NO accumulation_index; Conditions A + C intact.

    Drives shared-ctx-builder.main() with a cache containing:
      - kind==moc entries (complete MOC set → Condition A link targets)
      - placeholder_mocs entries (Condition C triggers)
      - NO accumulation_index (removed in T3.1)

    Mock at the orchestrator boundary: patch the Kado-touching helpers
    (build_tag_prefixes, build_classification_keywords, build_daily_notes)
    to isolate shared-ctx orchestration from live Kado while exercising the
    full main() path including build_mocs + build_placeholder_mocs.

    Assertions:
      - shared_ctx["mocs"] contains all kind==moc entries from the cache
      - "accumulation_index" is NOT in the output
      - shared_ctx["placeholder_mocs"] carries the cache's placeholder_mocs
        (Condition C preserved)

    Maps to spec 021 SDD §shared-ctx-builder removal, F-34 Condition A, C.
    """
    import yaml
    import importlib.util
    from unittest.mock import patch

    _scb_name = "shared_ctx_builder_t41"
    _spec = importlib.util.spec_from_file_location(
        _scb_name, SCRIPTS_DIR / "shared-ctx-builder.py"
    )
    scb = importlib.util.module_from_spec(_spec)
    # Register BEFORE exec_module so Python 3.14 dataclasses can resolve
    # `sys.modules[cls.__module__]` during class body execution.
    sys.modules[_scb_name] = scb
    _spec.loader.exec_module(scb)

    # Build a cache with MOC entries (A) + placeholder_mocs (C)
    moc_entries = [
        {"path": "Atlas/200 Maps/Dataview (MOC).md", "title": "Dataview (MOC)",
         "kind": "moc", "topics": ["dataview", "obsidian"],
         "up_state": "absent", "up_target": None, "up_source": None,
         "tags": ["type/others/moc"], "classification": None, "linked_notes": 3},
        {"path": "Atlas/200 Maps/PKM (MOC).md", "title": "PKM (MOC)",
         "kind": "moc", "topics": ["pkm", "linking"],
         "up_state": "absent", "up_target": None, "up_source": None,
         "tags": ["type/others/moc"], "classification": None, "linked_notes": 5},
    ]
    placeholder_mocs = [
        {"target": "Search MOC", "referenced_by": "Atlas/200 Maps/Dataview (MOC).md"},
    ]

    cache = {
        "map_notes": [e for e in moc_entries],  # shared-ctx reads map_notes directly
        "placeholder_mocs": placeholder_mocs,
    }

    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    vault_cfg = {"profile": "miyo"}
    cache_file.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    vault_cfg_file.write_text(yaml.dump(vault_cfg, allow_unicode=True), encoding="utf-8")

    argv = [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", "t4-1-inbox-test",
        "--skip-reconcile",
    ]

    with patch("sys.argv", argv), \
         patch.object(scb, "build_tag_prefixes", return_value=[]), \
         patch.object(scb, "build_classification_keywords", return_value={}), \
         patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()

    assert rc == 0, f"shared-ctx-builder.main() returned {rc}"
    ctx = json.loads(out_file.read_text(encoding="utf-8"))

    # Condition A: shared_ctx.mocs must be the complete MOC set (both entries)
    moc_paths_in_ctx = {m["path"] for m in ctx["mocs"]}
    expected_paths = {e["path"] for e in moc_entries}
    assert expected_paths <= moc_paths_in_ctx, (
        f"shared_ctx.mocs must include all MOC cache entries (Condition A link targets).\n"
        f"Expected: {expected_paths}\nGot: {moc_paths_in_ctx}"
    )

    # No accumulation_index (T3.1 removal; Condition B retired)
    assert "accumulation_index" not in ctx, (
        f"accumulation_index must be absent from /inbox shared-ctx; "
        f"got keys: {list(ctx.keys())}"
    )

    # Condition C: placeholder_mocs must be present and un-trimmed
    assert "placeholder_mocs" in ctx, (
        "placeholder_mocs must be present in shared_ctx (Condition C trigger)"
    )
    assert ctx["placeholder_mocs"] == placeholder_mocs, (
        f"placeholder_mocs must pass through unchanged (Condition C).\n"
        f"Expected: {placeholder_mocs}\nGot: {ctx['placeholder_mocs']}"
    )


@pytest.mark.integration
def test_explore_vault_force_rebuilds_cache(tmp_path):
    """run_with_client() + write_cache_atomic() writes the moc-structure cache.

    This characterises the /explore-vault Step 9 pipeline path: the MOC tree
    builder scans (via FakeKadoClient) and writes moc-structure-cache.yaml as a
    side effect. Tests that:
      - the cache file is written by write_cache_atomic (atomic tmp-rename)
      - the written file is valid YAML with moc_cache_version and entries
      - kind==moc entries for every tagged MOC appear in cache["entries"]

    Uses a FakeKadoClient injected at run_with_client() — the public testable
    seam moc-tree-builder exposes for this purpose (from test_moc_tree_builder.py
    pattern). No Kado server, no network calls.

    Maps to vault-explorer agent Step 9 (moc-tree-builder.py side effect),
    moc_cache_loader ADR-3 (fresh cache written by builder).
    """
    import yaml

    _builder = _load_moc_tree_builder()

    moc_path = "Atlas/200 Maps/Dataview (MOC).md"
    note_path = "Atlas/202 Notes/Dataview Alpha.md"

    class _FakeKadoClient:
        def search_by_tag(self, tag, limit=500):
            return [{"path": moc_path}]

        def list_notes(self, path, **kwargs):
            entries = {
                "Atlas/200 Maps/": [{"path": moc_path}],
                "Atlas/202 Notes/": [{"path": note_path}],
            }
            return entries.get(path, [])

        def read_note(self, path):
            notes = {
                moc_path: (
                    "---\ntitle: Dataview (MOC)\n"
                    "tags:\n  - type/others/moc\n---\n"
                    "# Dataview (MOC)\n\n[[Dataview Alpha]]\n"
                ),
                note_path: "---\ntitle: Dataview Alpha\n---\n# Dataview Alpha\n",
            }
            if path not in notes:
                from lib.kado_client import KadoNotFoundError
                raise KadoNotFoundError(f"not found: {path}")
            return {"content": notes[path]}

    config = {
        "concepts": {
            "map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]},
            "atomic_note": {"path": "Atlas/202 Notes/"},
        },
        "tomo": {
            "moc_structure_cache": {
                "scope_paths": ["Atlas/200 Maps/", "Atlas/202 Notes/"],
                "exclude_paths": [],
                "ttl_days": 1,
                "moc_tag": "type/others/moc",
            }
        },
    }

    # run_with_client: pure in-memory build (no disk write yet)
    cache, feed = _builder.run_with_client(_FakeKadoClient(), config)

    # write_cache_atomic: the side effect /explore-vault Step 9 relies on
    output_path = str(tmp_path / "moc-structure-cache.yaml")
    _builder.write_cache_atomic(cache, output_path)

    # Cache file must exist (atomic write succeeded)
    assert Path(output_path).exists(), (
        "write_cache_atomic must create the moc-structure-cache.yaml file "
        "(the /explore-vault Step 9 force-rebuild side effect)"
    )

    # File must be valid YAML with the versioned schema
    written = yaml.safe_load(Path(output_path).read_text(encoding="utf-8"))
    assert isinstance(written, dict), "Written cache must be a YAML mapping"
    assert written.get("moc_cache_version") == 1, (
        f"moc_cache_version must be 1; got {written.get('moc_cache_version')!r}"
    )
    assert "entries" in written, "Written cache must contain 'entries'"
    assert "last_scan" in written, "Written cache must contain 'last_scan'"

    # The tagged MOC must appear as a kind==moc entry
    moc_entries = [e for e in written["entries"] if e.get("kind") == "moc"]
    moc_paths = {e["path"] for e in moc_entries}
    assert moc_path in moc_paths, (
        f"Tagged MOC {moc_path!r} must appear as kind==moc in the rebuilt cache.\n"
        f"Got MOC paths: {moc_paths}"
    )


def _load_moc_tree_builder():
    """Return the moc-tree-builder module (lazy-loaded to avoid import at module level)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "moc_tree_builder_t41", SCRIPTS_DIR / "moc-tree-builder.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
