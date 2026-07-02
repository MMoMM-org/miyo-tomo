#!/usr/bin/env python3
# version: 0.1.0
"""test_shared_ctx_moc_detection.py — placeholder-MOC detection from suffix (028 T2.4).

shared-ctx-builder's `_is_missing_moc_target` must derive its detection regex
from the active profile's MOC suffix, not a hardcoded literal:
  - miyo (" (MOC)")  → detects "(MOC)" / " MOC" (parity, byte-identical behaviour)
  - lyt ("")         → detects nothing (no spurious matches)

This is internal detection only — shared-ctx JSON output / schema is unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)


# ── _moc_name_re: built from the suffix ───────────────────────────────────────


def test_miyo_suffix_regex_matches_both_forms() -> None:
    rx = scb._moc_name_re(" (MOC)")
    assert rx is not None
    assert rx.search("Efforts (MOC)")
    assert rx.search("AI MOC")
    assert rx.search("stoicism moc")  # case-insensitive
    assert not rx.search("COMMOC")  # mid-word → no boundary
    assert not rx.search("011 Index")


def test_empty_suffix_regex_is_none() -> None:
    assert scb._moc_name_re("") is None


def test_is_missing_moc_target_empty_suffix_detects_nothing() -> None:
    rx = scb._moc_name_re("")
    assert scb._is_missing_moc_target("Efforts (MOC)", rx) is False
    assert scb._is_missing_moc_target("AI MOC", rx) is False


def test_is_missing_moc_target_miyo_parity() -> None:
    rx = scb._moc_name_re(" (MOC)")
    assert scb._is_missing_moc_target("Efforts (MOC)", rx) is True
    assert scb._is_missing_moc_target("Körperliche Fitness 2024", rx) is False


# ── build_placeholder_links: threaded regex ───────────────────────────────────

_CACHE = {
    "placeholder_links": [
        {"target": "AI MOC", "referenced_by": "Atlas/Home.md"},
        {"target": "Efforts (MOC)", "referenced_by": "Atlas/Home.md"},
        {"target": "Körperliche Fitness 2024", "referenced_by": "Atlas/Home.md"},
    ]
}


def test_build_placeholder_links_default_is_miyo_parity() -> None:
    out = scb.build_placeholder_links(_CACHE)
    targets = {e["target"] for e in out}
    assert targets == {"AI MOC", "Efforts (MOC)"}


def test_build_placeholder_links_empty_suffix_detects_nothing() -> None:
    out = scb.build_placeholder_links(_CACHE, scb._moc_name_re(""))
    assert out == []
