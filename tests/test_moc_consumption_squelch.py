#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_consumption_squelch.py — T5.3: squelch-unticked.py helper tests.

Four tests covering the `squelch-unticked.py` CLI helper:

  test_unticked_clusters_added_to_squelch
      — 2 unticked clusters → registry contains both with correct topic_signature
        and runs_remaining.

  test_ticked_clusters_not_added_to_squelch
      — empty unticked list → registry file NOT written (or empty rejections).

  test_squelch_signature_collision_replaces_no_duplicate
      — same topic_signature submitted twice → registry has ONE entry, not two.

  test_squelch_state_persistence_atomic
      — F-43 invariant: write goes through tmp-then-rename (os.replace).

All tests use tmp_path fixtures so no pollution to the real state/ directory.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest.mock
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load squelch-unticked.py as a module (hyphen in filename → importlib)
_HELPER_PATH = SCRIPTS_DIR / "squelch-unticked.py"
_spec = importlib.util.spec_from_file_location("squelch_unticked", _HELPER_PATH)
assert _spec is not None and _spec.loader is not None
_helper_mod = importlib.util.module_from_spec(_spec)
sys.modules["squelch_unticked"] = _helper_mod
_spec.loader.exec_module(_helper_mod)  # type: ignore[union-attr]

squelch_unticked_main = _helper_mod.main  # type: ignore[attr-defined]

from lib import squelch  # noqa: E402


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _make_unticked_cluster(
    signature: str,
    title: str = "Test MOC",
) -> dict:
    """Minimal unticked cluster dict matching T5.1 contract."""
    return {"topic_signature": signature, "title": title}


def _write_input_file(tmp_path: Path, clusters: list[dict]) -> Path:
    """Write an moc-parsed.json with unticked_clusters to tmp_path."""
    payload = {"ticked_clusters": [], "unticked_clusters": clusters}
    input_file = tmp_path / "moc-parsed.json"
    input_file.write_text(json.dumps(payload), encoding="utf-8")
    return input_file


# ── Tests ────────────────────────────────────────────────────────────────────


def test_unticked_clusters_added_to_squelch(tmp_path: Path) -> None:
    """2 unticked clusters → registry gains both entries with correct fields."""
    clusters = [
        _make_unticked_cluster("sig-aaa", title="Shell & Terminal (MOC)"),
        _make_unticked_cluster("sig-bbb", title="Python Tooling (MOC)"),
    ]
    input_file = _write_input_file(tmp_path, clusters)
    registry_path = tmp_path / "state" / "moc-squelch.json"

    # Patch the helper's _registry_path to point at our tmp location
    with unittest.mock.patch.object(
        _helper_mod,
        "_registry_path",
        return_value=registry_path,
    ):
        exit_code = squelch_unticked_main(["squelch-unticked.py", str(input_file)])

    assert exit_code == 0
    assert registry_path.exists(), "Registry file must be created after persist"

    registry = squelch.load_registry(registry_path)
    assert len(registry) == 2, f"Expected 2 entries, got {len(registry)}: {list(registry)}"

    assert "sig-aaa" in registry, "sig-aaa missing from registry"
    assert "sig-bbb" in registry, "sig-bbb missing from registry"

    entry_a = registry["sig-aaa"]
    assert entry_a.topic_signature == "sig-aaa"
    assert entry_a.runs_remaining > 0, "runs_remaining must be positive"
    assert entry_a.first_seen_at, "first_seen_at must be set"


def test_ticked_clusters_not_added_to_squelch(tmp_path: Path) -> None:
    """Empty unticked list → no registry entries written."""
    input_file = _write_input_file(tmp_path, clusters=[])
    registry_path = tmp_path / "state" / "moc-squelch.json"

    with unittest.mock.patch.object(
        _helper_mod,
        "_registry_path",
        return_value=registry_path,
    ):
        exit_code = squelch_unticked_main(["squelch-unticked.py", str(input_file)])

    assert exit_code == 0

    if registry_path.exists():
        # If the file was written, it must have zero rejections
        registry = squelch.load_registry(registry_path)
        assert len(registry) == 0, (
            f"Expected empty registry for no unticked clusters, got {len(registry)} entries"
        )


def test_squelch_signature_collision_replaces_no_duplicate(tmp_path: Path) -> None:
    """Same topic_signature submitted twice → registry has ONE entry, not two."""
    cluster = _make_unticked_cluster("sig-collision", title="Duplicate MOC")
    input_file = _write_input_file(tmp_path, clusters=[cluster])
    registry_path = tmp_path / "state" / "moc-squelch.json"

    with unittest.mock.patch.object(
        _helper_mod,
        "_registry_path",
        return_value=registry_path,
    ):
        # First call
        squelch_unticked_main(["squelch-unticked.py", str(input_file)])
        # Second call with the same signature
        squelch_unticked_main(["squelch-unticked.py", str(input_file)])

    registry = squelch.load_registry(registry_path)
    assert len(registry) == 1, (
        f"Collision must replace, not duplicate — expected 1, got {len(registry)}"
    )
    assert "sig-collision" in registry


def test_squelch_state_persistence_atomic(tmp_path: Path) -> None:
    """F-43 invariant: write goes through tmp-then-rename (os.replace called)."""
    cluster = _make_unticked_cluster("sig-atomic", title="Atomic Write Test (MOC)")
    input_file = _write_input_file(tmp_path, clusters=[cluster])
    registry_path = tmp_path / "state" / "moc-squelch.json"

    replace_calls: list[tuple[str, str]] = []

    original_replace = os.replace

    def _recording_replace(src: str, dst: str) -> None:
        replace_calls.append((str(src), str(dst)))
        original_replace(src, dst)

    with unittest.mock.patch.object(
        _helper_mod,
        "_registry_path",
        return_value=registry_path,
    ):
        with unittest.mock.patch("os.replace", side_effect=_recording_replace):
            exit_code = squelch_unticked_main(["squelch-unticked.py", str(input_file)])

    assert exit_code == 0
    assert len(replace_calls) >= 1, (
        "os.replace must be called at least once for atomic write (tmp-then-rename)"
    )

    # Destination of the rename must be the registry path
    dst_paths = [dst for _src, dst in replace_calls]
    assert any(str(registry_path) in dst for dst in dst_paths), (
        f"os.replace destination must include registry path {registry_path}; got {dst_paths}"
    )

    # No .tmp files left behind
    state_dir = registry_path.parent
    if state_dir.exists():
        leftovers = [p for p in state_dir.iterdir() if p.suffix == ".tmp"]
        assert leftovers == [], f"Stale .tmp file(s) left behind: {leftovers}"
