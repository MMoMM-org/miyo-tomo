#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_main.py — main() orchestration for moc-discovery.py.

F-43 Phase 6 T6.0: covers the full discovery pipeline wired in main():
  Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 6.5 → emit.

These tests exercise main() end-to-end with minimal fakes — no live Kado,
no live LLM, no live vault. The test fixtures seed just enough state for the
pipeline to traverse all phases and emit a valid DiscoveryReport.

Test matrix:
  - test_main_tag_mode_produces_discovery_report   : happy path, tag mode
  - test_main_zero_candidates_emits_abort_reason   : zero-candidates abort
  - test_main_handles_squelched_cluster             : squelch read-only lookup
  - test_main_dry_run_path_unchanged               : --dry-run is still bit-identical

TDD note: these tests were written BEFORE the orchestration code and
confirmed failing (NotImplementedError) at commit time.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PROFILES_DIR = REPO_ROOT / "tomo" / "profiles"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in name → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
_moc_disc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = _moc_disc
_spec.loader.exec_module(_moc_disc)


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _write_config(tmp_path: Path, *, profile: str = "miyo") -> Path:
    """Write a minimal vault-config.yaml under tmp_path."""
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


def _write_cache(
    tmp_path: Path,
    atomic_notes: list[dict],
    extra_map_notes: list[dict] | None = None,
) -> Path:
    """Write a minimal discovery-cache.yaml under tmp_path.

    `atomic_notes` are included in `map_notes` (matching the real discovery-cache
    structure where all notes, MOC and atomic alike, live under map_notes keyed
    by path). This is what Phase 1 title-match and Phase 2 topic-lookup read.

    `extra_map_notes` allows adding additional entries (e.g. existing MOC entries
    for Phase 6 duplicate-detection scenarios). If omitted, no extra entries are
    added, so Phase 6 Jaccard comparison only runs against the atomic notes whose
    multi-topic sets do not overlap the cluster topic at ≥ 0.80.
    """
    cache = {
        "cache_version": 1,
        "map_notes": list(extra_map_notes or []) + atomic_notes,
        "atomic_notes": atomic_notes,
    }
    p = tmp_path / "discovery-cache.yaml"
    p.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    return p


def _write_squelch(tmp_path: Path, rejections: list[dict] | None = None) -> Path:
    """Write a moc-squelch.json sidecar under tmp_path."""
    data = {
        "schema_version": "1",
        "last_run_id": "",
        "rejections": rejections or [],
    }
    p = tmp_path / "moc-squelch.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


# Canonical atomic-note paths used in the miyo profile's atomic_note.base_path.
_BASE_PATH = "Atlas/202 Notes/"

# Three notes that share the topic "shell" (above min_notes=2).
#
# Multi-topic entries are deliberate: Phase 6 Jaccard comparison runs against
# ALL map_notes entries including the atomic notes. Single-topic entries {shell}
# produce Jaccard = 1.0 against the cluster topic-set {shell}, which would
# falsely skip the cluster as a dup of itself.
#
# With UNIQUE secondary topics (unix, posix, interactive — each appears once),
# Phase 3 produces EXACTLY ONE cluster "shell" (3 items) — no secondary cluster
# forms because no secondary topic appears in ≥2 notes.
#
# Phase 6 Jaccard: cluster topic-set = {shell}; each note topic-set =
#   {shell, unix} → J = 1/2 = 0.50 < 0.80 ✓ no false-positive dup
# Phase 1 title-match: "shell" in topics → candidate selected ✓
# Phase 2 topic lookup: _build_topics_index reads topics list → cache-hit ✓
_SHELL_NOTES = [
    {"path": f"{_BASE_PATH}zsh.md", "title": "zsh", "topics": ["shell", "unix"], "tags": []},
    {"path": f"{_BASE_PATH}bash.md", "title": "bash", "topics": ["shell", "posix"], "tags": []},
    {"path": f"{_BASE_PATH}fish.md", "title": "fish", "topics": ["shell", "interactive"], "tags": []},
]


# ── Fake KadoClient ──────────────────────────────────────────────────────────


class _FakeKadoRead:
    """Fake for Kado read_note — returns empty content for any path.

    Phase 6.5 calls read_note per candidate; we return a body without any
    `up::` marker so every child gets `state="absent"`.
    """

    def read_note(self, path: str) -> dict:
        return {"content": "# stub note\nNo up:: here.\n"}

    def search_by_tag(self, query: str) -> list[dict]:  # pragma: no cover
        return []

    def list_dir(self, path: str, depth: int = 10) -> list[dict]:  # pragma: no cover
        return []


# ── Tests ────────────────────────────────────────────────────────────────────


def test_main_tag_mode_produces_discovery_report(tmp_path: Path) -> None:
    """Happy path: tag mode with a cache-covered cluster emits a DiscoveryReport.

    The cache contains three notes sharing the topic "shell" (above min_notes=2).
    Phase 1 resolves via free-text/cache (title mode is cache-only in Phase 1;
    we use title mode here to avoid needing a real Kado server). The DiscoveryReport
    must have schema_version="1", non-empty topic_clusters, abort_reason=None.

    Covers PRD AC-1.x (mode routing), AC-3 (report shape), SDD DiscoveryReport schema.
    """
    config_path = _write_config(tmp_path)
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)
    squelch_path = _write_squelch(tmp_path)

    # Invoke main() directly via subprocess so we can capture stdout cleanly
    # and get the complete JSON output.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--title",
            "shell",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--squelch-state",
            str(squelch_path),
        ],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            # Point at an unreachable Kado — Phase 1 title mode is cache-only
            # and Phase 6.5 read_note should not be called for title mode
            # with all-cache candidates.
            "KADO_API_BASE_URL": "http://127.0.0.1:1",
            "KADO_API_KEY": "no-kado-needed",
            "TOMO_INSTANCE": str(tmp_path),
        },
        timeout=30,
    )

    assert result.returncode in (0, 1), (
        f"main() exited {result.returncode} — expected 0 or 1\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )

    assert result.stdout.strip(), f"stdout was empty\nstderr={result.stderr}"

    report = json.loads(result.stdout)

    # SDD schema_version field
    assert report["schema_version"] == "1"
    assert report["mode"] == "title"
    assert report["trigger_arg"] == "shell"
    assert report["profile"] == "miyo"
    assert report["abort_reason"] is None
    # Must have produced at least one cluster
    assert len(report["topic_clusters"]) >= 1, (
        f"Expected ≥1 cluster; got empty topic_clusters\nstderr={result.stderr}"
    )
    # Cluster shape
    cluster = report["topic_clusters"][0]
    assert "cluster_id" in cluster, "cluster missing cluster_id"
    assert "title" in cluster, "cluster missing title"
    assert "confidence" in cluster, "cluster missing confidence"
    assert "candidate_stems" in cluster, "cluster missing candidate_stems"
    assert "topic_keywords" in cluster, "cluster missing topic_keywords"
    # parent_options_per_cluster must be present (may be empty for miyo without matching categories)
    assert "parent_options_per_cluster" in report
    assert isinstance(report["parent_options_per_cluster"], dict)
    # Structural fields
    assert "candidates_total" in report
    assert "candidates_after_prefilter" in report
    assert isinstance(report["candidates_capped"], bool)


def test_main_zero_candidates_emits_abort_reason(tmp_path: Path) -> None:
    """Phase 1 zero-candidates path emits abort_reason without crashing.

    The cache has notes, but none match the title trigger → Phase 1 produces
    zero candidates → the pipeline emits abort_reason="zero-candidates" with
    exit 0 and a user-facing abort_message.

    Covers PRD AC-3 abort paths, SDD §Error Handling.
    """
    config_path = _write_config(tmp_path)
    # Notes whose topics don't match the trigger "xyzzy-nonexistent"
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)
    squelch_path = _write_squelch(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--title",
            "xyzzy-nonexistent-topic",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--squelch-state",
            str(squelch_path),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "TOMO_INSTANCE": str(tmp_path)},
        timeout=30,
    )

    assert result.returncode == 0, (
        f"expected exit 0 for abort-reason path; got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    report = json.loads(result.stdout)
    assert report["abort_reason"] == "zero-candidates", (
        f"expected abort_reason='zero-candidates'; got {report.get('abort_reason')!r}"
    )
    assert report["abort_message"] is not None
    assert report["topic_clusters"] == []


def test_main_handles_squelched_cluster(tmp_path: Path) -> None:
    """A cluster whose signature is in the squelch registry appears in report.squelched.

    We pre-populate moc-squelch.json with a signature computed from the
    expected "shell" cluster. After main() runs, the kept clusters should be
    empty (the only cluster is squelched) and report.squelched should have
    one entry.

    Covers SDD §Phase 6 squelch read-only lookup, T5.1 contract.
    """
    from lib.topic_signature import compute_topic_signature as _sig

    config_path = _write_config(tmp_path)
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)

    # Compute the expected signature. Phase 3 produces items = stems.
    # The signature covers the normalised topic + sorted top-5 stems.
    shell_cluster_dict = {
        "topic": "shell",
        "items": ["zsh", "bash", "fish"],
        "parent": "",
        "tags": [],
    }
    signature = _sig(shell_cluster_dict)

    # Seed the squelch registry with runs_remaining=2.
    squelch_path = _write_squelch(
        tmp_path,
        rejections=[
            {
                "topic_signature": signature,
                "topic_keywords": ["shell"],
                "rejected_at_run_id": "test-run-abc",
                "runs_remaining": 2,
                "first_seen_at": "2026-05-09T12:00:00Z",
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--title",
            "shell",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--squelch-state",
            str(squelch_path),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "TOMO_INSTANCE": str(tmp_path)},
        timeout=30,
    )

    assert result.returncode in (0, 1), (
        f"unexpected exit {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    report = json.loads(result.stdout)
    # The squelched cluster must appear in report.squelched (not topic_clusters)
    assert report["squelched"] != [], (
        f"expected squelched entry; report.squelched={report['squelched']}\n"
        f"report.topic_clusters={report['topic_clusters']}\nstderr={result.stderr}"
    )
    assert report["topic_clusters"] == [], (
        f"squelched cluster must not appear in topic_clusters; got {report['topic_clusters']}"
    )


def test_main_dry_run_path_unchanged(tmp_path: Path) -> None:
    """--dry-run still emits a minimal DiscoveryReport bit-identically.

    Replicates the T2.1 contract: the dry-run exit path returns early before
    any phase functions are called, so no squelch decrement, no cache load
    beyond the profile resolution, and no Kado contact.

    This test ensures the T6.0 orchestration code does NOT accidentally break
    the existing --dry-run branch.

    Covers SDD §Error Handling (dry-run = non-discovery exit), T2.1 regression.
    """
    config_path = _write_config(tmp_path)
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dry-run",
            "--tag",
            "topic/applied/zsh",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
        ],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "KADO_API_BASE_URL": "http://127.0.0.1:1",
            "KADO_API_KEY": "dry-run-must-not-call",
        },
        timeout=15,
    )

    assert result.returncode == 0, (
        f"dry-run exited {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    report = json.loads(result.stdout)
    # Bit-identical to T2.1 contract
    assert report["schema_version"] == "1"
    assert report["mode"] == "tag"
    assert report["trigger_arg"] == "topic/applied/zsh"
    assert report["profile"] == "miyo"
    assert report["candidates"] == []
    assert report["topic_clusters"] == []
    assert report["candidates_total"] == 0
    assert report["candidates_capped"] is False
    assert report["abort_reason"] is None
    # Dry-run must not touch Kado
    assert "ConnectionRefused" not in result.stderr
    assert "kado" not in result.stderr.lower()
