#!/usr/bin/env python3
# version: 0.1.0
"""test_profile_conventions.py — Behavioural tests for lib.profile_conventions.

Covers the Conventions value object + resolve_conventions() resolver (028 T1.1):
  - resolve from an already-loaded profile_dict
  - resolve from a profile_override name (real bundled profiles)
  - resolve from a config_path carrying a top-level `profile:` key
  - missing relationship_defaults.*.marker  -> up:: / related:: defaults (ADR-3)
  - missing map_note.name_suffix            -> "" default (ADR-3)
  - profiles_dir is a REQUIRED keyword-only arg (ADR-2) -> TypeError without it

Plus T1.2: the actual bundled profiles carry the expected name_suffix
(miyo -> " (MOC)", lyt -> "").
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import profile_conventions  # noqa: E402
from lib.profile_conventions import (  # noqa: E402
    Conventions,
    ensure_suffix,
    resolve_conventions,
    strip_suffix,
)

BUNDLED_PROFILES_DIR = SCRIPTS_DIR.parent / "profiles"


# ──────────────────────────────────────────────────────────────────────────────
# (a) resolve from an already-loaded profile_dict
# ──────────────────────────────────────────────────────────────────────────────


def test_resolve_from_profile_dict(tmp_path: Path) -> None:
    profile = {
        "relationship_defaults": {
            "parent": {"marker": "parent::"},
            "peer": {"marker": "sibling::"},
        },
        "concept_defaults": {"map_note": {"name_suffix": " (Map)"}},
    }
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict=profile)
    assert conv == Conventions(
        parent_marker="parent::", peer_marker="sibling::", moc_suffix=" (Map)"
    )


def test_conventions_is_frozen(tmp_path: Path) -> None:
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict={})
    with pytest.raises((AttributeError, TypeError)):
        conv.parent_marker = "x::"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────────
# (b) resolve from a profile_override name (real bundled profiles)
# ──────────────────────────────────────────────────────────────────────────────


def test_resolve_from_profile_override_miyo() -> None:
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR, profile_override="miyo"
    )
    assert conv.parent_marker == "up::"
    assert conv.peer_marker == "related::"


def test_profile_dict_wins_over_profile_override(tmp_path: Path) -> None:
    # S1: resolution priority — an explicit profile_dict must take precedence
    # over profile_override; an accidental swap would surface as "top::" here.
    profile = {"relationship_defaults": {"parent": {"marker": "dict::"}}}
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR,
        profile_dict=profile,
        profile_override="miyo",
    )
    assert conv.parent_marker == "dict::"


# ──────────────────────────────────────────────────────────────────────────────
# (c) resolve from a config_path carrying a top-level `profile:` key
# ──────────────────────────────────────────────────────────────────────────────


def test_resolve_from_config_path(tmp_path: Path) -> None:
    config = tmp_path / "vault-config.yaml"
    config.write_text("profile: lyt\n", encoding="utf-8")
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR, config_path=config
    )
    assert conv.parent_marker == "up::"
    assert conv.moc_suffix == ""


def test_config_path_missing_profile_key_defaults_to_miyo(tmp_path: Path) -> None:
    config = tmp_path / "vault-config.yaml"
    config.write_text("something_else: true\n", encoding="utf-8")
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR, config_path=config
    )
    assert conv.moc_suffix == " (MOC)"


# ──────────────────────────────────────────────────────────────────────────────
# (d) missing relationship_defaults.*.marker -> up:: / related:: defaults (ADR-3)
# ──────────────────────────────────────────────────────────────────────────────


def test_missing_markers_fall_back_to_defaults(tmp_path: Path) -> None:
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict={})
    assert conv.parent_marker == "up::"
    assert conv.peer_marker == "related::"


def test_partial_markers_fall_back_per_key(tmp_path: Path) -> None:
    profile = {"relationship_defaults": {"parent": {"marker": "top::"}}}
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict=profile)
    assert conv.parent_marker == "top::"
    assert conv.peer_marker == "related::"


# ──────────────────────────────────────────────────────────────────────────────
# (e) missing map_note.name_suffix -> "" default (ADR-3)
# ──────────────────────────────────────────────────────────────────────────────


def test_missing_suffix_defaults_to_empty(tmp_path: Path) -> None:
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict={})
    assert conv.moc_suffix == ""


def test_null_suffix_defaults_to_empty(tmp_path: Path) -> None:
    # W2: YAML `name_suffix: null` -> {"name_suffix": None}; None must fall back
    # to the default, not leak into the str-typed field.
    profile = {"concept_defaults": {"map_note": {"name_suffix": None}}}
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict=profile)
    assert conv.moc_suffix == ""


def test_empty_string_suffix_is_preserved(tmp_path: Path) -> None:
    # A present empty string is a valid suffix (lyt) and must be kept as-is.
    profile = {"concept_defaults": {"map_note": {"name_suffix": ""}}}
    conv = resolve_conventions(profiles_dir=tmp_path, profile_dict=profile)
    assert conv.moc_suffix == ""


# ──────────────────────────────────────────────────────────────────────────────
# (f) profiles_dir is a REQUIRED keyword-only arg (ADR-2)
# ──────────────────────────────────────────────────────────────────────────────


def test_profiles_dir_is_required_kwarg() -> None:
    with pytest.raises(TypeError):
        resolve_conventions(profile_dict={})  # type: ignore[call-arg]


def test_lib_does_not_expose_default_profiles_dir() -> None:
    # ADR-2: the lib must never compute the profiles directory from __file__.
    assert not hasattr(profile_conventions, "DEFAULT_PROFILES_DIR")


# ──────────────────────────────────────────────────────────────────────────────
# T1.2 — actual bundled profiles carry the expected name_suffix
# ──────────────────────────────────────────────────────────────────────────────


def test_bundled_miyo_suffix() -> None:
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR, profile_override="miyo"
    )
    assert conv.moc_suffix == " (MOC)"


def test_bundled_lyt_suffix() -> None:
    conv = resolve_conventions(
        profiles_dir=BUNDLED_PROFILES_DIR, profile_override="lyt"
    )
    assert conv.moc_suffix == ""


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — shared suffix apply-once / strip rules (F-55)
# SDD/Implementation Examples: ensure_suffix / strip_suffix.
# ──────────────────────────────────────────────────────────────────────────────


def test_ensure_suffix_appends_miyo() -> None:
    assert ensure_suffix("Shell", " (MOC)") == "Shell (MOC)"


def test_ensure_suffix_apply_once_no_double() -> None:
    # Already ends with the suffix -> never double-apply.
    assert ensure_suffix("Shell (MOC)", " (MOC)") == "Shell (MOC)"


def test_ensure_suffix_empty_is_noop() -> None:
    assert ensure_suffix("Shell", "") == "Shell"


def test_strip_suffix_removes_miyo() -> None:
    assert strip_suffix("Shell (MOC)", " (MOC)") == "Shell"


def test_strip_suffix_case_insensitive() -> None:
    # Parity with the legacy case-insensitive regexes.
    assert strip_suffix("Shell (moc)", " (MOC)") == "Shell"


def test_strip_suffix_empty_is_noop() -> None:
    assert strip_suffix("Shell (MOC)", "") == "Shell (MOC)"


def test_strip_suffix_non_matching_left_intact() -> None:
    assert strip_suffix("Shell", " (MOC)") == "Shell"


def test_bundled_profiles_versions_bumped() -> None:
    # CON-5: a `# version:` bump is what makes update-tomo ship the change.
    for name, floor in (("miyo", 1.0), ("lyt", 1.0)):
        text = (BUNDLED_PROFILES_DIR / f"{name}.yaml").read_text(encoding="utf-8")
        first = text.splitlines()[0]
        assert first.startswith("# version:")
        assert float(first.split(":", 1)[1].strip()) > floor
        # sanity: the profile still parses and has the suffix key
        data = yaml.safe_load(text)
        assert "name_suffix" in data["concept_defaults"]["map_note"]
