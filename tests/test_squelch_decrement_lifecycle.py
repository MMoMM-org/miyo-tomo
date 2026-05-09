#!/usr/bin/env python3
# version: 0.1.1
"""test_squelch_decrement_lifecycle.py — T5.1: squelch decrement-and-persist at main() start.

Four tests verify that moc-discovery.py's main() loads the squelch registry,
decrements all entries at run start, persists the result atomically, and that
the post-decrement registry filters clusters from DiscoveryReport.topic_clusters
via phase6_dedupe.

Test map:
  test_decrement_on_run_start          — 2-entry registry → after run, 1 entry remains (0 removed)
  test_decrement_persisted_atomically  — save_registry_atomic raise leaves original intact
  test_active_signature_filters_cluster — signature in registry → cluster absent from kept list
  test_signature_is_stable_across_runs  — _compute_topic_signature is deterministic

Invocation strategy:
  Tests 1-2 invoke main() in the full-pipeline path (no --dry-run, valid cache).
  The full pipeline raises NotImplementedError because T2.5-T2.7 phases are not yet
  wired. The squelch load/decrement/save runs BEFORE that stub, so tests assert on
  the file state after catching the expected NotImplementedError.

F-43 Phase 5 T5.1. Stdlib + pytest only — no Kado, no LLM calls.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

from lib import squelch as squelch_mod  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_registry_json(entries: list[dict]) -> str:
    """Serialise a minimal squelch registry JSON from a list of entry dicts."""
    return json.dumps(
        {
            "schema_version": "1",
            "last_run_id": "",
            "rejections": entries,
        },
        indent=2,
    )


def _entry(signature: str, runs_remaining: int) -> dict:
    return {
        "topic_signature": signature,
        "topic_keywords": ["test"],
        "rejected_at_run_id": "run-abc",
        "runs_remaining": runs_remaining,
        "first_seen_at": "2026-05-08T00:00:00Z",
    }


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    """Create minimal vault-config.yaml and discovery-cache.yaml in tmp_path."""
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text("profile: miyo\n", encoding="utf-8")

    cache_path = tmp_path / "discovery-cache.yaml"
    # Non-empty map_notes so validate_cache_loaded() passes.
    cache_path.write_text(
        "map_notes:\n  - path: Atlas/Maps/Existing MOC.md\n    title: Existing MOC\n    topics: []\n",
        encoding="utf-8",
    )
    return config_path, cache_path


def _full_pipeline_argv(
    tmp_path: Path,
    squelch_state: Path,
    *,
    config: Path | None = None,
    cache: Path | None = None,
) -> list[str]:
    """Build argv for a full-pipeline run (no --dry-run, valid cache)."""
    if config is None or cache is None:
        config, cache = _write_config(tmp_path)
    return [
        "--config", str(config),
        "--cache", str(cache),
        "--squelch-state", str(squelch_state),
    ]


# ── tests ─────────────────────────────────────────────────────────────────────


def test_decrement_on_run_start(tmp_path: Path) -> None:
    """Registry with 2 entries (runs_remaining=2,1); after run: 1 entry (runs_remaining=1).

    Entry with runs_remaining=1 decrements to 0 and is removed.
    Entry with runs_remaining=2 decrements to 1 and is kept.

    The squelch load/decrement/save executes before Phase 1. The no-arg
    (scan) pipeline needs a live Kado connection which is unavailable in
    unit tests. We assert on the squelch file state after the run regardless
    of whether main() returns normally or raises (KadoError on scan mode,
    or exits 0/1/2 on title/free-text mode).
    """
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        _make_registry_json([
            _entry("sig-alpha", runs_remaining=2),
            _entry("sig-beta", runs_remaining=1),
        ]),
        encoding="utf-8",
    )

    argv = _full_pipeline_argv(tmp_path, squelch_path)
    try:
        moc_discovery.main(argv)
    except Exception:
        pass  # KadoError from scan-mode Phase 1 — expected in unit test env

    post_run = json.loads(squelch_path.read_text(encoding="utf-8"))
    sigs = {r["topic_signature"]: r["runs_remaining"] for r in post_run["rejections"]}

    assert "sig-alpha" in sigs, "sig-alpha (runs_remaining 2→1) must be kept"
    assert sigs["sig-alpha"] == 1, f"expected runs_remaining=1, got {sigs['sig-alpha']}"
    assert "sig-beta" not in sigs, "sig-beta (runs_remaining 1→0) must be removed"


def test_all_entries_expire_writes_empty_registry(tmp_path: Path) -> None:
    """Boundary case — sole entry with runs_remaining=1 expires; file remains valid empty registry.

    Verifies the ``rejections == []`` shape round-trips through load_registry
    so a subsequent run starts cleanly.
    """
    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        _make_registry_json([_entry("sig-only", runs_remaining=1)]),
        encoding="utf-8",
    )

    argv = _full_pipeline_argv(tmp_path, squelch_path)
    try:
        moc_discovery.main(argv)
    except Exception:
        pass  # KadoError from scan-mode Phase 1 — expected in unit test env

    post_run = json.loads(squelch_path.read_text(encoding="utf-8"))
    assert post_run["rejections"] == [], "all-expired registry should serialise empty rejections"
    # Re-load via the public API to confirm round-trip.
    reloaded = squelch_mod.load_registry(squelch_path)
    assert reloaded == {}, "load_registry on empty rejections should return empty dict"


def test_decrement_persisted_atomically(tmp_path: Path) -> None:
    """If save_registry_atomic raises, the original squelch file must be intact.

    Patching os.replace inside squelch_mod causes save_registry_atomic to raise
    mid-rename, simulating a disk-full or permission error. The tmp file is
    cleaned up by squelch.py and the original target must remain unmodified.
    """
    squelch_path = tmp_path / "moc-squelch.json"
    original_content = _make_registry_json([_entry("sig-gamma", runs_remaining=3)])
    squelch_path.write_text(original_content, encoding="utf-8")

    real_os = os  # capture before patching

    with mock.patch.object(squelch_mod, "os") as fake_os:
        fake_os.replace.side_effect = OSError("simulated disk full")
        fake_os.fdopen = real_os.fdopen
        fake_os.fsync = real_os.fsync

        with pytest.raises(OSError, match="simulated disk full"):
            argv = _full_pipeline_argv(tmp_path, squelch_path)
            moc_discovery.main(argv)

    after_content = squelch_path.read_text(encoding="utf-8")
    assert after_content == original_content, (
        "Squelch file must not be modified when save_registry_atomic raises"
    )
    # No tmp staging file should be left behind after rollback.
    leftover = list(squelch_path.parent.glob("*.tmp")) + list(
        squelch_path.parent.glob(".moc-squelch*")
    )
    assert leftover == [], f"staging file leaked after atomic-write rollback: {leftover}"


def test_active_signature_filters_cluster(tmp_path: Path) -> None:
    """A cluster whose topic signature is in the active registry must not appear in kept.

    Simulates what main() does (load → decrement → pass to phase6_dedupe) and
    verifies the cluster is suppressed when its signature remains active after
    decrement.
    """
    topic_keywords = ["shell", "zsh", "terminal"]
    candidate_stems = ["zsh-rc", "zsh-tools", "shell-utils"]
    cluster = {
        "topic": "shell",
        "topic_keywords": topic_keywords,
        "items": candidate_stems,
        "title": "Shell MOC",
        "parent": "",
        "tags": [],
    }
    signature = moc_discovery._compute_topic_signature(cluster)

    squelch_path = tmp_path / "moc-squelch.json"
    squelch_path.write_text(
        _make_registry_json([
            {
                "topic_signature": signature,
                "topic_keywords": topic_keywords,
                "rejected_at_run_id": "run-xyz",
                "runs_remaining": 2,  # 2 → 1 after decrement: still active
                "first_seen_at": "2026-05-08T00:00:00Z",
            }
        ]),
        encoding="utf-8",
    )

    # Mirror what main() does: load → decrement.
    registry = squelch_mod.load_registry(squelch_path)
    decremented = squelch_mod.decrement_all(registry)

    # Entry had runs_remaining=2 → decremented to 1 → still active.
    assert squelch_mod.is_active(decremented, signature), (
        "Entry with runs_remaining=2 must remain active after decrement (2→1)"
    )

    cache = {"map_notes": []}

    class _Cfg:
        pass

    kept, dups, squelched = moc_discovery.phase6_dedupe([cluster], cache, decremented, _Cfg())

    assert kept == [], (
        f"Cluster with active squelch signature must not appear in kept; got {kept!r}"
    )
    assert len(squelched) == 1, (
        f"Cluster must appear in squelched list; got {squelched!r}"
    )


def test_signature_is_stable_across_runs() -> None:
    """Same cluster + same top-K stems → identical hex digest on every invocation.

    Per SDD Example 2: sha1(sorted(lower(topics)) + "::" + sorted(stems)[:5])[:16].
    """
    cluster = {
        "topic": "shell",
        "topic_keywords": ["Shell", "ZSH", "terminal"],
        "items": ["zsh-rc", "zsh-tools", "shell-utils", "dotfiles", "terminal-config"],
        "title": "Shell MOC",
        "parent": "",
        "tags": [],
    }

    sig1 = moc_discovery._compute_topic_signature(cluster)
    sig2 = moc_discovery._compute_topic_signature(cluster)

    assert sig1 == sig2, "Signature must be deterministic"
    assert len(sig1) == 16, f"Signature must be 16-char hex; got {len(sig1)!r}"
    int(sig1, 16)  # raises ValueError if not valid hex
