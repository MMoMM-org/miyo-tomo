#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_main.py — main() orchestration for moc-discovery.py.

F-43 Phase 6 T6.0: covers the full discovery pipeline wired in main():
  Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 6.5 → emit.

These tests exercise main() end-to-end with minimal fakes — no live Kado,
no live LLM, no live vault. The test fixtures seed just enough state for the
pipeline to traverse all phases and emit a valid DiscoveryReport.

Test matrix:
  - test_main_title_mode_produces_discovery_report : happy path, title mode (cache-only Phase 1)
  - test_main_tag_mode_produces_discovery_report   : happy path, tag mode (Kado-fake via monkeypatch)
  - test_main_zero_candidates_emits_abort_reason   : zero-candidates abort
  - test_main_handles_squelched_cluster             : squelch read-only lookup
  - test_main_dry_run_path_unchanged               : --dry-run is still bit-identical
  - test_emit_phase1_writes_candidates_json        : --emit-phase1 round-trip (T6.5.1)
  - test_emit_phase1_marks_misses_as_null          : cache-miss candidates → topics: null
  - test_phase1_input_skips_phase1_no_llm_needed   : --phase1-input + pre-populated topics

TDD note: these tests were written BEFORE the orchestration code and
confirmed failing (NotImplementedError) at commit time.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

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
    """Write a FRESH moc-structure-cache.yaml under tmp_path (spec 021 T2.1).

    moc-discovery now reads the MOC-structure cache through moc_cache_loader,
    which projects `entries[kind=="moc"]` → `map_notes` (the shim). To keep these
    tests exercising the same Phase 1 title-match / Phase 2 topic-lookup / Phase 6
    paths (all of which read `map_notes`), the fixture entries are written as
    `kind: moc` so the shim surfaces them exactly as the old `map_notes` did.

    A recent `last_scan` keeps the cache FRESH so the loader loads it WITHOUT a
    rebuild (a rebuild would need Kado). `ttl_days` defaults to 1.

    `extra_map_notes` adds further MOC entries (Phase 6 duplicate-detection).
    """
    from datetime import datetime, timezone

    def _as_moc_entry(e: dict) -> dict:
        # Tag fixture entries as MOC so the loader shim surfaces them; preserve
        # whatever fields the test supplied (path/title/topics/...).
        return {**e, "kind": e.get("kind", "moc")}

    entries = [_as_moc_entry(e) for e in (list(extra_map_notes or []) + atomic_notes)]
    cache = {
        "moc_cache_version": 1,
        "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_days": 1,
        "scope_paths": [],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries,
        "placeholder_mocs": [],
    }
    p = tmp_path / "moc-structure-cache.yaml"
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


class _FakeKadoForTag:
    """Fake Kado client for search_by_tag and read_note.

    search_by_tag returns the shell notes; read_note returns empty content
    without `up::` marker so every child gets `state="absent"`.
    """

    def search_by_tag(self, query: str) -> list[dict]:
        return [{"path": note["path"]} for note in _SHELL_NOTES]

    def read_note(self, path: str) -> dict:
        return {"content": "# stub note\nNo up:: here.\n"}

    def list_dir(self, path: str, depth: int = 10) -> list[dict]:  # pragma: no cover
        return []


# ── Tests ────────────────────────────────────────────────────────────────────


def test_main_title_mode_produces_discovery_report(tmp_path: Path) -> None:
    """Happy path: title mode with a cache-covered cluster emits a DiscoveryReport.

    The cache contains three notes sharing the topic "shell" (above min_notes=2).
    Phase 1 resolves via cache (title mode is cache-only in Phase 1 — no Kado
    needed). The DiscoveryReport must have schema_version="1", non-empty
    topic_clusters, abort_reason=None.

    Covers PRD AC-1.x (mode routing, title branch), AC-3 (report shape),
    SDD DiscoveryReport schema.
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


def test_main_tag_mode_produces_discovery_report(tmp_path: Path, monkeypatch) -> None:
    """Happy path: tag mode with a Kado-fake returns a full DiscoveryReport.

    Phase 1 (tag mode) calls kado_client.search_by_tag() — a live Kado server
    is not available in CI. We inject a fake by monkeypatching _build_kado_client
    on the already-loaded moc_discovery module. The fake's search_by_tag returns
    the same three shell-note paths that live in the cache, so Phase 2 gets
    cache-hits and the full pipeline (Phase 1 → Phase 6.5) completes.

    Covers PRD AC-1.x (mode routing, tag branch), AC-3 (report shape),
    SDD §Phase 1 tag handler.
    """
    config_path = _write_config(tmp_path)
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)
    squelch_path = _write_squelch(tmp_path)

    # Inject the module-scope _FakeKadoForTag by monkeypatching _build_kado_client.
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: _FakeKadoForTag())

    # Drive main() directly so the monkeypatch applies (subprocess would spawn
    # a fresh interpreter that doesn't share this process's monkeypatch).
    import io
    import contextlib

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        exit_code = _moc_disc.main(
            [
                "--tag",
                "shell",
                "--config",
                str(config_path),
                "--cache",
                str(cache_path),
                "--squelch-state",
                str(squelch_path),
            ]
        )

    assert exit_code in (0, 1), (
        f"main() returned exit_code={exit_code} — expected 0 or 1\n"
        f"stdout={captured.getvalue()!r}"
    )

    stdout_text = captured.getvalue().strip()
    assert stdout_text, "stdout was empty — main() emitted no JSON"

    report = json.loads(stdout_text)

    # SDD schema_version + mode fields
    assert report["schema_version"] == "1"
    assert report["mode"] == "tag"
    assert report["trigger_arg"] == "shell"
    assert report["profile"] == "miyo"
    assert report["abort_reason"] is None
    # Must have produced at least one cluster from the 3 shell notes
    assert len(report["topic_clusters"]) >= 1, (
        "Expected ≥1 cluster; got empty topic_clusters"
    )
    # Cluster shape
    cluster = report["topic_clusters"][0]
    assert "cluster_id" in cluster, "cluster missing cluster_id"
    assert "title" in cluster, "cluster missing title"
    assert "confidence" in cluster, "cluster missing confidence"
    assert "candidate_stems" in cluster, "cluster missing candidate_stems"
    assert "topic_keywords" in cluster, "cluster missing topic_keywords"
    # Structural fields
    assert "parent_options_per_cluster" in report
    assert isinstance(report["parent_options_per_cluster"], dict)
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


# ── T6.5: two-pass topic-extraction (agent-side LLM) ─────────────────────────


def test_emit_phase1_writes_candidates_json(tmp_path: Path) -> None:
    """--emit-phase1 writes Phase-1 candidates to JSON with topics-from-cache.

    Title mode with cache covering all three shell notes → each candidate's
    topics list is populated from cache.map_notes. No phase 2-6.5 runs.
    Exit 0, stdout empty (JSON goes to file, not stdout).

    Covers T6.5.1 emit-phase1 contract.
    """
    config_path = _write_config(tmp_path)
    cache_path = _write_cache(tmp_path, atomic_notes=_SHELL_NOTES)
    squelch_path = _write_squelch(tmp_path)
    out_path = tmp_path / "phase1-out.json"

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
            "--emit-phase1",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "TOMO_INSTANCE": str(tmp_path)},
        timeout=30,
    )

    assert result.returncode == 0, (
        f"--emit-phase1 exited {result.returncode}\nstderr={result.stderr}"
    )
    assert out_path.exists(), f"--emit-phase1 did not write {out_path}"

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload["mode"] == "title"
    assert payload["trigger_arg"] == "shell"
    assert payload["profile"] == "miyo"
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 3, f"expected 3 candidates, got {len(candidates)}"

    paths = {c["path"] for c in candidates}
    assert paths == {n["path"] for n in _SHELL_NOTES}

    # All three are in cache → topics non-null + list-shaped
    for c in candidates:
        assert isinstance(c.get("topics"), list), (
            f"expected list topics for cache-hit candidate {c['path']}; got {c.get('topics')!r}"
        )
        assert c["topics"], f"expected non-empty topics for {c['path']}"


def test_emit_phase1_marks_misses_as_null(tmp_path: Path, monkeypatch) -> None:
    """Tag-mode: Kado returns paths NOT in cache → candidates emit topics: null.

    Phase 1 (tag mode) discovers candidates via Kado; phase 2 normally hits
    cache.map_notes for topics. When cache has no entry for the candidate path,
    the emit-phase1 JSON should mark topics as null so the agent knows which
    candidates need LLM-side extraction before --phase1-input.

    Covers T6.5.1 miss-marking contract.
    """
    config_path = _write_config(tmp_path)
    squelch_path = _write_squelch(tmp_path)
    out_path = tmp_path / "phase1-out.json"

    # Cache has NO entries for the shell-note paths → all misses. Seed an
    # unrelated MOC entry so the cache is non-empty (loader loads it fresh, no
    # rebuild) but contains no atomic-note paths. Written via _write_cache so it
    # carries the fresh MOC-structure-cache shape (kind: moc + last_scan).
    cache_path = _write_cache(
        tmp_path,
        atomic_notes=[],
        extra_map_notes=[
            {"path": "Atlas/200 Maps/2600 Tools.md", "title": "Tools",
             "topics": ["tools"], "tags": []}
        ],
    )

    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: _FakeKadoForTag())

    exit_code = _moc_disc.main(
        [
            "--tag",
            "shell",
            "--config",
            str(config_path),
            "--cache",
            str(cache_path),
            "--squelch-state",
            str(squelch_path),
            "--emit-phase1",
            str(out_path),
        ]
    )
    assert exit_code == 0, f"--emit-phase1 returned {exit_code}"
    assert out_path.exists()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    candidates = payload["candidates"]
    assert len(candidates) == 3
    assert payload.get("abort_reason") is None
    # All candidates are misses (cache had no atomic-note entries)
    for c in candidates:
        assert c.get("topics") is None, (
            f"expected topics=null for miss {c['path']}; got {c.get('topics')!r}"
        )
        # body_excerpt populated from FakeKadoForTag.read_note
        assert "body_excerpt" in c, f"miss {c['path']} missing body_excerpt"
        assert c["body_excerpt"], f"miss {c['path']} body_excerpt is empty"
        assert c["body_excerpt"].startswith("# stub note"), (
            f"unexpected body_excerpt: {c['body_excerpt']!r}"
        )


def test_phase1_input_skips_phase1_no_llm_needed(tmp_path: Path) -> None:
    """--phase1-input loads pre-populated candidates → phase 2 short-circuits.

    Agent has pre-populated topics for every candidate (in real flow, via a
    topic-extract subagent). Phase 2 must NOT raise RuntimeError about missing
    llm_client — it should treat all candidates as hits and run phases 2-6.5
    normally to emit a DiscoveryReport.

    Covers T6.5.2 phase1-input contract + phase 2 topics short-circuit.
    """
    config_path = _write_config(tmp_path)
    # Cache has no atomic-note entries — proves phase 2 doesn't fall back to
    # cache lookup when topics are pre-populated. Written via _write_cache so the
    # loader sees a FRESH MOC-structure cache (no rebuild) with one MOC entry.
    cache_path = _write_cache(
        tmp_path,
        atomic_notes=[],
        extra_map_notes=[
            {"path": "Atlas/200 Maps/2600 Tools.md", "title": "Tools",
             "topics": ["tools"], "tags": []}
        ],
    )
    squelch_path = _write_squelch(tmp_path)

    # Pre-populated phase-1 payload — topics filled in for all candidates.
    phase1_payload = {
        "mode": "tag",
        "trigger_arg": "shell",
        "profile": "miyo",
        "candidates": [
            {"stem": "zsh", "path": f"{_BASE_PATH}zsh.md", "topics": ["shell", "unix"]},
            {"stem": "bash", "path": f"{_BASE_PATH}bash.md", "topics": ["shell", "posix"]},
            {"stem": "fish", "path": f"{_BASE_PATH}fish.md", "topics": ["shell", "interactive"]},
        ],
    }
    phase1_path = tmp_path / "phase1-in.json"
    phase1_path.write_text(json.dumps(phase1_payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--phase1-input",
            str(phase1_path),
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
            "KADO_API_BASE_URL": "http://127.0.0.1:1",
            "KADO_API_KEY": "no-kado-for-phase1-input-test",
            "TOMO_INSTANCE": str(tmp_path),
        },
        timeout=30,
    )

    assert result.returncode in (0, 1), (
        f"--phase1-input exited {result.returncode}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    # No RuntimeError about llm_client must surface in stderr
    assert "llm_client is required" not in result.stderr, (
        f"phase 2 must short-circuit on pre-populated topics — but raised:\n{result.stderr}"
    )

    report = json.loads(result.stdout)
    assert report["schema_version"] == "1"
    assert report["mode"] == "tag"
    assert report["trigger_arg"] == "shell"
    assert report["abort_reason"] is None
    assert len(report["topic_clusters"]) >= 1, "expected ≥1 cluster from pre-populated topics"
