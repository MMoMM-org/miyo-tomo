#!/usr/bin/env python3
# version: 0.1.0
"""test_vault_scan_concept_paths.py — concept path resolution in vault-scan.py.

Regression guard for the spec 021 M8 consumer-drift bug: the M8 canonical
atomic_note shape is a dict with a single `path` key
(`atomic_note: { path: "Atlas/202 Notes/" }`), read by lib/moc_scan. vault-scan
is the OTHER consumer of the same config and originally only handled `base_path`
and `paths` — so `path` resolved to None and /explore-vault reported the
atomic_note concept as unresolved (0 notes). These tests assert vault-scan now
accepts `path` alongside `base_path` and `paths`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "tomo" / "scripts" / "vault-scan.py"

_spec = importlib.util.spec_from_file_location("vault_scan", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extract_primary_path = _mod.extract_primary_path
extract_all_paths = _mod.extract_all_paths


# ── extract_primary_path ──────────────────────────────────────────────────────

def test_primary_path_single_path_key_m8_canonical():
    # The bug: this returned None before the fix.
    assert extract_primary_path("atomic_note", {"path": "Atlas/202 Notes/"}) == "Atlas/202 Notes/"


def test_primary_path_base_path_key_still_works():
    assert extract_primary_path("calendar", {"base_path": "Calendar/"}) == "Calendar/"


def test_primary_path_paths_list_still_works():
    assert extract_primary_path("map_note", {"paths": ["Atlas/200 Maps/"]}) == "Atlas/200 Maps/"


def test_primary_path_scalar_string():
    assert extract_primary_path("inbox", "+/") == "+/"


def test_primary_path_none_and_empty():
    assert extract_primary_path("x", None) is None
    assert extract_primary_path("x", {}) is None
    assert extract_primary_path("x", {"path": ""}) is None  # empty path is not a resolution


def test_primary_path_base_path_precedence_over_path():
    # calendar-style entries keep base_path precedence; a stray path doesn't override.
    assert extract_primary_path("calendar", {"base_path": "Calendar/", "path": "ignored/"}) == "Calendar/"


# ── extract_all_paths ─────────────────────────────────────────────────────────

def test_all_paths_includes_single_path_key():
    assert extract_all_paths({"path": "Atlas/202 Notes/"}) == ["Atlas/202 Notes/"]


def test_all_paths_collects_mixed_keys():
    out = extract_all_paths({"base_path": "Calendar/", "path": "Atlas/202 Notes/", "paths": ["Atlas/200 Maps/"]})
    assert "Calendar/" in out
    assert "Atlas/202 Notes/" in out
    assert "Atlas/200 Maps/" in out


def test_all_paths_empty_path_skipped():
    assert extract_all_paths({"path": ""}) == []
