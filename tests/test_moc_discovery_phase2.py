#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_phase2.py — Phase 2 cache lookup + LLM batching for moc-discovery.py.

F-43 Phase 2 T2.3: covers the cache-first hit path (zero LLM calls when every
candidate already has cached topics), the bounded LLM cache-miss path
(batches of ≤10 with cap), and the two cache-related abort branches:
`cache-miss-cap-exceeded` (Phase 2) and `cache-empty` (pre-Phase-1 startup
gate). Tests exercise the unit functions directly with a recording mock
LLM client; no real LLM is called.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PROFILES_DIR = REPO_ROOT / "tomo" / "profiles"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def small_config() -> object:
    """Spec-default-shaped config: cache_miss_max_batches=5 per SDD §10."""
    class _Cfg:
        candidate_cap = 200
        cache_miss_max_batches = 5
    return _Cfg()


class RecordingLLMClient:
    """Minimal recording fake for the LLMClient interface.

    The phase2 helper calls `.batch_extract(batch: list[Candidate]) -> list[dict]`
    once per batch (≤10 candidates each). The fake records every call so tests
    can assert on call count and per-batch sizes, and returns a deterministic
    `[{path, topics}]` shape mirroring the real LLM contract.
    """

    def __init__(self):
        self.calls: list[list[str]] = []

    def batch_extract(self, batch):
        # Record paths so tests can assert on batch sizes + ordering.
        self.calls.append([c.path for c in batch])
        return [
            {"path": c.path, "topics": [f"llm-topic-{c.stem}"]}
            for c in batch
        ]


def _mk_candidates(n: int, prefix: str = "Atlas/202 Notes/2611 Code Snippets") -> list:
    """Build n Candidates with deterministic paths/stems."""
    return [
        moc_discovery.Candidate(stem=f"n{i}", path=f"{prefix}/n{i}.md")
        for i in range(n)
    ]


# ── Cache-first hit path (no LLM calls) ─────────────────────────────────────


def test_cache_first_hit_no_llm(small_config):
    """All candidates already in cache → 0 LLM calls; topics copied from cache."""
    candidates = _mk_candidates(5)
    cache = {
        "map_notes": [
            {
                "path": c.path,
                "topics": [f"cached-topic-{c.stem}", "shared"],
            }
            for c in candidates
        ]
    }
    llm = RecordingLLMClient()

    enriched, abort = moc_discovery.phase2_extract_topics(
        candidates, cache, small_config, llm
    )

    assert abort is None
    assert llm.calls == [], "cache-first path must not invoke the LLM"
    assert len(enriched) == len(candidates)
    # Cached topics propagated 1:1 onto the Candidate.
    enriched_by_path = {c.path: c for c in enriched}
    for c in candidates:
        topics = enriched_by_path[c.path].topics
        assert f"cached-topic-{c.stem}" in topics
        assert "shared" in topics


# ── Cache-miss path: bounded LLM batching ──────────────────────────────────


def test_cache_miss_batched(small_config):
    """50 candidates entirely absent from cache → exactly 5 batches of 10."""
    candidates = _mk_candidates(50)
    cache = {"map_notes": []}  # no entries → every candidate is a miss
    llm = RecordingLLMClient()

    enriched, abort = moc_discovery.phase2_extract_topics(
        candidates, cache, small_config, llm
    )

    assert abort is None
    # 5 LLM calls, each with 10 candidates.
    assert len(llm.calls) == 5
    for batch in llm.calls:
        assert len(batch) == 10
    # Every candidate received its LLM topic.
    enriched_by_path = {c.path: c for c in enriched}
    assert len(enriched_by_path) == 50
    for c in candidates:
        assert f"llm-topic-{c.stem}" in enriched_by_path[c.path].topics


# ── Cache-miss cap exceeded (Phase 2 abort) ────────────────────────────────


def test_cache_miss_cap_exceeded_aborts(small_config):
    """60 cache-miss candidates with cap=5 (×10 per batch) → abort, no LLM call."""
    candidates = _mk_candidates(60)  # ⌈60/10⌉ = 6 batches > cap 5
    cache = {"map_notes": []}
    llm = RecordingLLMClient()

    enriched, abort = moc_discovery.phase2_extract_topics(
        candidates, cache, small_config, llm
    )

    assert abort == "cache-miss-cap-exceeded"
    assert enriched == []
    # Cap-check fires before any LLM call.
    assert llm.calls == []


# ── Cache-empty pre-check (BEFORE Phase 1) ─────────────────────────────────


def test_validate_cache_loaded_returns_cache_empty_for_none():
    """`None` cache → `cache-empty` sentinel."""
    assert moc_discovery.validate_cache_loaded(None) == "cache-empty"


def test_validate_cache_loaded_returns_cache_empty_for_missing_map_notes():
    """Cache dict without `map_notes` key → `cache-empty`."""
    assert moc_discovery.validate_cache_loaded({}) == "cache-empty"
    assert moc_discovery.validate_cache_loaded({"last_scan": "2026-04-23"}) == "cache-empty"


def test_validate_cache_loaded_returns_cache_empty_for_empty_map_notes():
    """`map_notes: []` → `cache-empty` (cache file written but never populated)."""
    assert moc_discovery.validate_cache_loaded({"map_notes": []}) == "cache-empty"


def test_validate_cache_loaded_returns_none_for_populated_cache():
    """Populated cache → no abort."""
    cache = {"map_notes": [{"path": "a.md", "topics": ["t"]}]}
    assert moc_discovery.validate_cache_loaded(cache) is None


def test_cache_empty_aborts_at_startup(tmp_path):
    """Missing/empty cache file → exit 0 with abort_reason=cache-empty BEFORE Phase 1.

    The pre-check fires at the top of `main()`, before mode routing reaches
    `phase1_select_candidates`. We assert against a JSON DiscoveryReport on
    stdout (per spec — abort paths emit a report and exit 0, not a fatal exit).
    """
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text("profile: miyo\n", encoding="utf-8")

    # Empty cache (file exists, `map_notes: []` — the most common "ran
    # explore-vault on an empty vault" failure mode).
    cache_path = tmp_path / "discovery-cache.yaml"
    cache_path.write_text("map_notes: []\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--tag",
            "topic/anything",
        ],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            # Pre-check must fire BEFORE Phase 1 → no Kado contact required.
            "KADO_API_BASE_URL": "http://127.0.0.1:1",
            "KADO_API_KEY": "must-not-be-used",
        },
        timeout=15,
    )

    assert result.returncode == 0, (
        f"cache-empty abort should be exit 0, got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    report = json.loads(result.stdout)
    assert report["abort_reason"] == "cache-empty"
    assert report["abort_message"], "cache-empty abort must include a user-facing message"
    # No Phase-1 work happened → no candidates produced.
    assert report["candidates"] == []
    # Sanity check: nothing leaked through to Phase 1's NotImplementedError or to Kado.
    assert "NotImplementedError" not in result.stderr
    assert "ConnectionRefused" not in result.stderr
