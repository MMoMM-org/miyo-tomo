#!/usr/bin/env python3
# version: 0.3.0
"""profile_conventions.py — single resolver for profile-agnostic vault conventions.

Threads a profile's relationship markers and MOC-title suffix into the pipeline
as one immutable value object, replacing scattered hardcoded `up::`/`related::`/
`" (MOC)"` literals. Profiles stay pure data; this lib carries no vault literals
of its own beyond the documented backward-compatibility defaults (ADR-3).

`profiles_dir` is always caller-supplied — the lib never derives it from its own
`__file__` (ADR-2), because the flattened instance runtime breaks deep
`parent.parent`-style path resolution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ADR-3 backward-compatibility defaults for absent profile keys.
_DEFAULT_PARENT_MARKER = "up::"
_DEFAULT_PEER_MARKER = "related::"
_DEFAULT_MOC_SUFFIX = ""


@dataclass(frozen=True)
class Conventions:
    """Resolved vault conventions for the active profile."""

    parent_marker: str  # e.g. "up::"
    peer_marker: str  # e.g. "related::"
    moc_suffix: str  # e.g. " (MOC)" or ""


def marker_word(suffix: str) -> str:
    """Alphanumeric core (the "marker word") of a MOC suffix.

    ' (MOC)' → 'MOC'; '' → ''. Shared by the MOC-marker regexes in
    lib.topic_clusters and shared-ctx-builder so the two never drift (F-55 S1).
    """
    return re.sub(r"\W", "", suffix or "")


def ensure_suffix(title: str, suffix: str) -> str:
    """Append `suffix` to `title` once. Empty suffix is a no-op; never double-apply."""
    if not suffix:
        return title
    return title if title.endswith(suffix) else f"{title}{suffix}"


def strip_suffix(title: str, suffix: str) -> str:
    """Remove a trailing `suffix` from `title`.

    Empty suffix strips nothing. Case-insensitive to match the legacy
    topic_clusters / shared-ctx regexes (parity, not new behaviour).
    """
    if not suffix:
        return title
    if title.lower().endswith(suffix.lower()):
        return title[: -len(suffix)]
    return title


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file → dict; empty / missing → {}."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _from_dict(profile: dict[str, Any]) -> Conventions:
    """Extract conventions from a loaded profile dict, with ADR-3 defaults."""
    rel = profile.get("relationship_defaults") or {}
    parent = rel.get("parent") or {}
    peer = rel.get("peer") or {}
    map_note = (profile.get("concept_defaults") or {}).get("map_note") or {}
    _raw_suffix = map_note.get("name_suffix")
    moc_suffix = _DEFAULT_MOC_SUFFIX if _raw_suffix is None else _raw_suffix
    return Conventions(
        parent_marker=parent.get("marker") or _DEFAULT_PARENT_MARKER,
        peer_marker=peer.get("marker") or _DEFAULT_PEER_MARKER,
        moc_suffix=moc_suffix,
    )


def resolve_conventions(
    *,
    profiles_dir: Path,
    profile_dict: dict[str, Any] | None = None,
    config_path: Path | None = None,
    profile_override: str | None = None,
) -> Conventions:
    """Resolve the active profile's Conventions.

    `profiles_dir` is required and caller-supplied (ADR-2). Resolution order
    mirrors moc-discovery.resolve_profile:
      1. explicit `profile_dict` (already loaded by the caller)
      2. `profile_override` name        → profiles_dir/<name>.yaml
      3. `config_path` `profile:` key   → profiles_dir/<name>.yaml (default "miyo")
      4. default name "miyo"            → profiles_dir/miyo.yaml
    """
    if profile_dict is not None:
        return _from_dict(profile_dict)

    if profile_override:
        name = profile_override
    elif config_path is not None:
        cfg = _load_yaml(config_path)
        name = str(cfg.get("profile") or "miyo")
    else:
        name = "miyo"

    return _from_dict(_load_yaml(profiles_dir / f"{name}.yaml"))
