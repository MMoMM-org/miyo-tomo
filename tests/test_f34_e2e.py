#!/usr/bin/env python3
# version: 0.1.0
"""test_f34_e2e.py — End-to-end integration tests for spec 015, Phase 5, T5.1.

Drives all four F-34 Condition B pipeline stages through a fake KadoClient
and asserts correct behaviour at each boundary:

  Stage 1  SCANNER     atomic-note-indexer.py :: build_accumulation_clusters()
  Stage 2  CACHE       cache-builder.py       :: assemble_cache()
  Stage 3  SHARED-CTX  shared-ctx-builder.py  :: build_accumulation_index() + enforce_budget()
  Stage 4  CONSUMER    inbox-analyst step 4 contract (pure Python transcription, test-only)

Test scenarios:
  test_f34_traced_walkthrough_clusters  — SDD traced walkthrough vault → full pipeline → consumer match
  test_f34_empty_vault                  — empty vault → accumulation_index OMITTED from shared-ctx
  test_f34_budget_stress_trimming       — many clusters → enforce_budget drops smallest first
  test_f34_conflict_vault_precedence    — placeholder + accumulation both match → placeholder wins (A7)

Spec: docs/XDD/specs/015-msp-condition-b-accumulation/
AC:   A3, A4, A6, A7
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Module loading — hyphenated filenames require importlib
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_script(name: str):
    """Load a tomo/scripts/<name>.py module via importlib.

    The module is registered in sys.modules under its canonical name before
    exec so that dataclass decorators (which call sys.modules.get(cls.__module__))
    resolve correctly — the same pattern used by test_shared_ctx_accumulation.py.
    """
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        module_name, SCRIPTS_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_indexer = _load_script("atomic-note-indexer")
_cache_mod = _load_script("cache-builder")
_scb = _load_script("shared-ctx-builder")

build_accumulation_clusters = _indexer.build_accumulation_clusters
assemble_cache = _cache_mod.assemble_cache
build_accumulation_index = _scb.build_accumulation_index
enforce_budget = _scb.enforce_budget
serialize = _scb.serialize


# ---------------------------------------------------------------------------
# Reuse: WALKTHROUGH_NOTES fixture from test_atomic_note_indexer.py
# (mirrored here rather than imported to keep tests self-contained and
# allow fixture evolution without cross-test coupling)
# ---------------------------------------------------------------------------

BASE_PATH = "Atlas/Atoms"


def _note(path: str, topics: list[str]) -> dict:
    """Build a minimal listNotes item.

    Topics embedded as plain tags — extract_topics_from_fields surfaces them
    via method 4 (plain tags).
    """
    return {
        "path": path,
        "name": Path(path).name,
        "tags": topics,
        "headings": [],
        "links": [],
    }


WALKTHROUGH_NOTES = [
    _note(f"{BASE_PATH}/monte-carlo-tree-search.md", ["mcts", "search", "games"]),
    _note(f"{BASE_PATH}/alpha-beta-pruning.md",      ["search", "games"]),
    _note(f"{BASE_PATH}/board-game-night.md",        ["games", "social"]),
    _note(f"{BASE_PATH}/minimax.md",                 ["search", "games"]),
]

WALKTHROUGH_CLASSIFIED = {"board-game-night"}

EXPECTED_CLUSTERS = {
    "games":  ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
    "search": ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
}


def _make_client(notes: list[dict], classified_stems: set[str]) -> MagicMock:
    """Return a fake KadoClient (mirrors _make_client from test_atomic_note_indexer.py)."""
    client = MagicMock()
    client.list_notes.return_value = notes

    def _read_inline(path: str) -> dict:
        stem = Path(path).stem
        if stem in classified_stems:
            return {"up": ["[[Hobbies MOC]]"]}
        return {}

    client.read_inline_fields.side_effect = _read_inline
    return client


# ---------------------------------------------------------------------------
# Minimal shared-ctx context builder (used by budget + conflict tests)
# ---------------------------------------------------------------------------

def _minimal_ctx(*, accumulation_index: dict | None = None) -> dict:
    """Return the minimum valid ctx dict accepted by enforce_budget."""
    ctx: dict = {
        "schema_version": "1",
        "run_id": "test-e2e-run",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }
    if accumulation_index is not None:
        ctx["accumulation_index"] = accumulation_index
    return ctx


# ---------------------------------------------------------------------------
# Step-4 contract helper (A3/A6/A7)
# Pure Python transcription of inbox-analyst Step 4 Accumulation cluster trigger.
# Lives in the TEST MODULE ONLY — not in product code.
# ---------------------------------------------------------------------------

def _step4_evaluate(shared_ctx: dict, item: dict) -> dict:
    """Faithful transcription of inbox-analyst Step 4 Accumulation cluster trigger.

    Rules (from spec 015 SDD §Secondary Flow / inbox-analyst.md):
      A6: if accumulation_index absent from shared_ctx → no-op (return trigger=False).
      A3: for each key K in accumulation_index:
            if any token in item['dominant_topic_tokens'] matches K
            (case-insensitive, whitespace-normalised) → set needs_new_moc=True,
            proposed_moc_topic=K, keep candidate_mocs unchanged.
      A7 (STRICT non-overwrite): if proposed_moc_topic was already set by an upstream
            check (Condition C / placeholder_mocs), do NOT overwrite it.

    Returns dict with keys:
      trigger_fired      bool
      needs_new_moc      bool
      proposed_moc_topic str | None
      source             "accumulation" | "placeholder" | None
    """
    result = {
        "trigger_fired": False,
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "source": None,
    }

    # --- Condition C (placeholder_mocs) runs BEFORE Condition B ---
    placeholder_mocs = shared_ctx.get("placeholder_mocs") or []
    topic_tokens = {t.lower().strip() for t in item.get("dominant_topic_tokens", [])}

    for ph in placeholder_mocs:
        target = ph.get("target", "")
        if target.lower().strip() in topic_tokens:
            result["needs_new_moc"] = True
            result["proposed_moc_topic"] = target  # preserve placeholder casing
            result["source"] = "placeholder_mocs"
            break  # first match wins

    # --- A6: skip if accumulation_index absent ---
    accumulation_index = shared_ctx.get("accumulation_index")
    if not accumulation_index:
        return result

    # --- A3: scan accumulation_index keys ---
    # A7 (STRICT): if proposed_moc_topic already set by placeholder, do NOT overwrite.
    if result["proposed_moc_topic"] is not None:
        return result

    for key in accumulation_index:
        if key.lower().strip() in topic_tokens:
            result["trigger_fired"] = True
            result["needs_new_moc"] = True
            result["proposed_moc_topic"] = key
            result["source"] = "accumulation"
            break  # first match wins

    return result


# ===========================================================================
# T5.1-1: Traced walkthrough vault — full pipeline smoke + consumer match
# ===========================================================================

def test_f34_traced_walkthrough_clusters():
    """Scanner → cache → shared-ctx pipeline; consumer matches accumulation cluster.

    Uses the SDD §Complex Logic traced walkthrough vault (search/games clusters,
    board-game-night classified). Asserts:
      - scanner output matches EXPECTED_CLUSTERS exactly
      - cache carries unclassified_topic_clusters unchanged
      - shared-ctx accumulation_index == scanner output (passthrough)
      - Step-4 contract with a matching item fires needs_new_moc=True and
        proposed_moc_topic equals the matched cluster key
    """
    # Stage 1: scanner
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    clusters = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    assert clusters == EXPECTED_CLUSTERS, (
        f"Stage 1 scanner: expected {EXPECTED_CLUSTERS}, got {clusters}"
    )

    # Stage 2: cache-builder
    cache = assemble_cache(
        structure_data=None,
        mocs_data=None,
        frontmatter_data=None,
        tags_data=None,
        orphans_data=None,
        accumulation_data=clusters,
        start_time=None,
    )

    assert cache.get("unclassified_topic_clusters") == clusters, (
        f"Stage 2 cache: expected unclassified_topic_clusters={clusters}, "
        f"got {cache.get('unclassified_topic_clusters')!r}"
    )

    # Stage 3: shared-ctx passthrough
    accumulation_index = build_accumulation_index(cache)

    assert accumulation_index == clusters, (
        f"Stage 3 shared-ctx: expected accumulation_index={clusters}, "
        f"got {accumulation_index!r}"
    )
    # Confirm neither cluster key is missing
    assert "games" in accumulation_index
    assert "search" in accumulation_index
    assert sorted(accumulation_index["games"]) == sorted(EXPECTED_CLUSTERS["games"])
    assert sorted(accumulation_index["search"]) == sorted(EXPECTED_CLUSTERS["search"])

    # Stage 4: consumer contract — item with 'games' topic triggers Condition B
    shared_ctx: dict = {
        "schema_version": "1",
        "run_id": "test-e2e-walkthrough",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
        "accumulation_index": accumulation_index,
    }
    item = {
        "stem": "new-game-notes",
        "dominant_topic_tokens": ["games", "strategy"],
    }

    verdict = _step4_evaluate(shared_ctx, item)

    assert verdict["needs_new_moc"] is True, (
        f"Stage 4: expected needs_new_moc=True for item matching 'games' cluster, got {verdict}"
    )
    assert verdict["proposed_moc_topic"] == "games", (
        f"Stage 4: expected proposed_moc_topic='games', got {verdict['proposed_moc_topic']!r}"
    )
    assert verdict["source"] == "accumulation", (
        f"Stage 4: expected source='accumulation', got {verdict['source']!r}"
    )


# ===========================================================================
# T5.1-2: Empty vault — accumulation_index OMITTED from shared-ctx (A6)
# ===========================================================================

def test_f34_empty_vault():
    """Empty vault produces {} clusters → accumulation_index absent from shared-ctx.

    Asserts byte-identical 'today's behaviour': when unclassified_topic_clusters
    is empty the field is never added to shared-ctx, and the Step-4 contract
    helper is a no-op (A6 silent skip).
    """
    # Stage 1: scanner with zero notes
    client = MagicMock()
    client.list_notes.return_value = []
    clusters = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    assert clusters == {}, (
        f"Stage 1: empty vault must yield empty clusters, got {clusters!r}"
    )

    # Stage 2: cache-builder with empty accumulation
    cache = assemble_cache(
        structure_data=None,
        mocs_data=None,
        frontmatter_data=None,
        tags_data=None,
        orphans_data=None,
        accumulation_data=clusters,
        start_time=None,
    )

    assert cache.get("unclassified_topic_clusters") == {}, (
        f"Stage 2: expected empty unclassified_topic_clusters, got "
        f"{cache.get('unclassified_topic_clusters')!r}"
    )

    # Stage 3: build_accumulation_index returns {} → field must be omitted
    accumulation_index = build_accumulation_index(cache)

    assert accumulation_index == {}, (
        f"Stage 3: expected empty accumulation_index, got {accumulation_index!r}"
    )

    # Confirm the conditional-add rule: empty → field absent from ctx
    # (mirrors the `if accumulation_index:` guard in shared-ctx-builder main())
    ctx: dict = {
        "schema_version": "1",
        "run_id": "test-e2e-empty",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }
    if accumulation_index:  # the guard from shared-ctx-builder.py main()
        ctx["accumulation_index"] = accumulation_index

    assert "accumulation_index" not in ctx, (
        "Stage 3 A6: accumulation_index must be absent from ctx when empty"
    )

    # Stage 4: no accumulation_index → Step-4 contract is a no-op
    item = {
        "stem": "any-item",
        "dominant_topic_tokens": ["games", "strategy"],
    }
    verdict = _step4_evaluate(ctx, item)

    assert verdict["trigger_fired"] is False, (
        f"Stage 4 A6: trigger must not fire when accumulation_index absent, got {verdict}"
    )
    assert verdict["needs_new_moc"] is False, (
        f"Stage 4 A6: needs_new_moc must be False when accumulation_index absent, got {verdict}"
    )
    assert verdict["proposed_moc_topic"] is None, (
        f"Stage 4 A6: proposed_moc_topic must be None when accumulation_index absent, got {verdict}"
    )


# ===========================================================================
# T5.1-3: Budget stress — enforce_budget drops smallest clusters first (A4)
# ===========================================================================

def test_f34_budget_stress_trimming(capsys):
    """Many clusters exceeding max_bytes → enforce_budget drops smallest first.

    Cluster sizes: big=5, medium=3, small=2, tiny=1.
    With a 1-byte-under budget, the smallest clusters are dropped first and
    alphabetical tiebreak applies within same size. The count log
    `accumulation_clusters_total=N accumulation_clusters_kept=K` must appear
    on stderr.
    """
    # Build a set of clusters with different sizes to stress the trim logic
    accumulation = {
        "big":    ["a1", "a2", "a3", "a4", "a5"],  # 5 members — highest priority to keep
        "medium": ["b1", "b2", "b3"],               # 3 members
        "small":  ["c1", "c2"],                     # 2 members
        "tiny":   ["d1"],                           # 1 member — dropped first
    }
    ctx = _minimal_ctx(accumulation_index=accumulation)
    ctx_size = len(serialize(ctx))
    tight_budget = ctx_size - 1  # force at least one drop

    trimmed, _dropped_moc_topics, acc_total, acc_kept = enforce_budget(ctx, tight_budget)

    # acc_total must equal the original cluster count
    assert acc_total == 4, (
        f"Expected acc_total=4, got {acc_total}"
    )
    # At least one cluster must have been dropped
    assert acc_kept < acc_total, (
        f"Expected acc_kept < {acc_total} after trim, got acc_kept={acc_kept}"
    )

    ai = trimmed.get("accumulation_index", {})

    # "tiny" (1 member) must be the first victim
    assert "tiny" not in ai, (
        f"'tiny' (1 member) must be dropped first under budget pressure, "
        f"but accumulation_index={ai}"
    )
    # "big" (5 members) must survive — it is the largest cluster
    assert "big" in ai, (
        f"'big' (5 members) must survive budget trimming, but accumulation_index={ai}"
    )

    # Stderr log must contain the count fields
    captured = capsys.readouterr()
    assert "accumulation_clusters_total=" in captured.err, (
        f"Expected 'accumulation_clusters_total=' in stderr log, got: {captured.err!r}"
    )
    assert "accumulation_clusters_kept=" in captured.err, (
        f"Expected 'accumulation_clusters_kept=' in stderr log, got: {captured.err!r}"
    )

    # Verify the logged counts are self-consistent with the return values
    import re
    total_match = re.search(r"accumulation_clusters_total=(\d+)", captured.err)
    kept_match = re.search(r"accumulation_clusters_kept=(\d+)", captured.err)
    assert total_match and kept_match, (
        f"Could not parse count fields from stderr: {captured.err!r}"
    )
    assert int(total_match.group(1)) == acc_total, (
        f"Stderr total={total_match.group(1)} does not match return value acc_total={acc_total}"
    )
    assert int(kept_match.group(1)) == acc_kept, (
        f"Stderr kept={kept_match.group(1)} does not match return value acc_kept={acc_kept}"
    )


# ===========================================================================
# T5.1-4: Conflict vault precedence — placeholder wins over accumulation (A7)
# ===========================================================================

def test_f34_conflict_vault_precedence():
    """Item matches BOTH placeholder_mocs AND accumulation_index — placeholder wins (A7).

    Uses the fixture shape from scenario_c_placeholder_wins.json:
      - placeholder_mocs has target 'Boardgames'
      - accumulation_index has key 'boardgames'
      - item dominant_topic_tokens contains 'boardgames'

    Asserts:
      - proposed_moc_topic == 'Boardgames' (placeholder casing preserved)
      - source == 'placeholder_mocs'
      - accumulation key 'boardgames' did NOT overwrite the placeholder result
    """
    shared_ctx: dict = {
        "schema_version": "1",
        "run_id": "test-e2e-conflict",
        "mocs": [
            {
                "path": "Atlas/200 MOCs/Hobbies MOC.md",
                "title": "Hobbies MOC",
                "topics": ["hobbies", "games"],
                "is_classification": False,
            }
        ],
        "tag_prefixes": [],
        "classification_keywords": {},
        "placeholder_mocs": [
            {
                "target": "Boardgames",        # Condition C — casing from placeholder
                "referenced_by": "Atlas/200 MOCs/Hobbies MOC.md",
            }
        ],
        "accumulation_index": {
            "boardgames": [                    # Condition B — lowercase key
                "20260101-boardgame-review",
                "20260102-catan-notes",
                "20260103-wingspan-tips",
                "20260104-gloomhaven-session",
            ]
        },
    }

    item = {
        "stem": "20260201-boardgames-strategy",
        "path": "100 Inbox/20260201-boardgames-strategy.md",
        "dominant_topic_tokens": ["boardgames", "strategy", "games"],
        "body_content": "Collected strategies for various boardgames.",
    }

    verdict = _step4_evaluate(shared_ctx, item)

    # Both triggers would match — placeholder must win
    assert verdict["needs_new_moc"] is True, (
        f"Expected needs_new_moc=True (both conditions match), got {verdict}"
    )
    assert verdict["proposed_moc_topic"] == "Boardgames", (
        f"A7: placeholder casing 'Boardgames' must be preserved; "
        f"accumulation key 'boardgames' must NOT overwrite. Got {verdict['proposed_moc_topic']!r}"
    )
    assert verdict["source"] == "placeholder_mocs", (
        f"A7: source must be 'placeholder_mocs', got {verdict['source']!r}"
    )
    # Explicitly confirm the accumulation key did not win
    assert verdict["proposed_moc_topic"] != "boardgames", (
        "A7 violated: accumulation key 'boardgames' (lowercase) overwrote "
        "placeholder target 'Boardgames'"
    )
