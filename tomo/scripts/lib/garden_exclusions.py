#!/usr/bin/env python3
# version: 0.1.0
"""garden_exclusions.py — Load and apply the garden-audit exclusion config (spec 030 T1.2).

Loads config/garden-audit-exclusions.yaml, separates expired temporaries
(reporting which reappeared), and exposes is_excluded(note_entry, check_name) -> bool
applied as a filter before findings render.

Fail-open: missing or malformed config returns an empty GardenExclusions instance
(nothing excluded, no crash).

Design notes: docs/tomo/scripts/lib/garden_exclusions.md
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# All check names recognised by garden-audit (for "checks: all" expansion).
ALL_CHECK_NAMES = frozenset(
    ["unparented", "orphan", "broken_up", "dead_link", "duplicate_stem", "stale_moc"]
)


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string (YYYY-MM-DD) into a date, or return None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _normalise_checks(checks: Any) -> frozenset[str]:
    """Return the effective set of check names from a checks value.

    Accepts the string "all" or a list of check name strings.
    Returns frozenset of ALL_CHECK_NAMES for "all", frozenset of the list otherwise.
    Returns empty frozenset for unrecognised shapes (fail-open).
    """
    if checks == "all":
        return ALL_CHECK_NAMES
    if isinstance(checks, list):
        return frozenset(str(c) for c in checks)
    return frozenset()


def _matches_target(entry: dict, target: dict) -> bool:
    """Return True if the note entry matches the exclusion target.

    target.type:
      path  — prefix match on entry["path"] (e.g. "Calendar/" matches "Calendar/2026-07-19.md")
      note  — exact match on entry["path"]
      tag   — membership in entry["tags"]
    """
    t_type = target.get("type")
    t_value = target.get("value", "")
    if t_type == "path":
        return entry.get("path", "").startswith(str(t_value))
    if t_type == "note":
        return entry.get("path", "") == str(t_value)
    if t_type == "tag":
        return str(t_value) in (entry.get("tags") or [])
    return False


class _ExclusionRule:
    """A single parsed, validated exclusion rule."""

    __slots__ = ("target", "checks", "mode", "until", "raw")

    def __init__(self, target: dict, checks: frozenset[str], mode: str,
                 until: date | None, raw: dict) -> None:
        self.target = target
        self.checks = checks
        self.mode = mode          # "permanent" | "temporary"
        self.until = until        # date | None (only for temporary)
        self.raw = raw            # original dict for reappeared reporting

    def is_active(self, today: date) -> bool:
        """Return True if this rule is currently active (not expired)."""
        if self.mode == "permanent":
            return True
        # temporary: active only before the until date
        if self.until is None:
            return True  # no until → never expires (conservative)
        return today < self.until

    def is_expired(self, today: date) -> bool:
        """Return True if this rule is a temporary that has expired."""
        return self.mode == "temporary" and self.until is not None and today >= self.until


def _parse_rule(raw: dict) -> _ExclusionRule | None:
    """Parse a raw exclusion dict into an _ExclusionRule; return None on error."""
    try:
        target = raw["target"]
        if not isinstance(target, dict) or "type" not in target or "value" not in target:
            return None
        checks = _normalise_checks(raw["checks"])
        mode = raw["mode"]
        if mode not in ("permanent", "temporary"):
            return None
        until = _parse_date(raw.get("until"))
        return _ExclusionRule(target=target, checks=checks, mode=mode, until=until, raw=raw)
    except (KeyError, TypeError):
        return None


class GardenExclusions:
    """Loaded and indexed exclusion config.

    Provides:
      is_excluded(note_entry, check_name, *, today=None) -> bool
      reappeared_exclusions() -> list[dict]   # expired temporary rules
    """

    def __init__(self, rules: list[_ExclusionRule], today: date) -> None:
        self._active: list[_ExclusionRule] = [r for r in rules if r.is_active(today)]
        self._reappeared: list[dict] = [r.raw for r in rules if r.is_expired(today)]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_excluded(self, entry: dict, check_name: str, *, today: date | None = None) -> bool:
        """Return True if entry should be suppressed for check_name.

        `today` is injectable for deterministic tests; defaults to date.today().
        Note: active/expired split happens at construction time (from_dict/from_path),
        so the today param here only matters for rules that are active at construction.
        Active rules are evaluated against their own mode/until logic; for the common
        usage pattern, today at construction time is what drives active/expired.
        This parameter is provided for is_excluded-level date pinning when the caller
        constructs GardenExclusions without a today override and needs per-call pinning.
        In that scenario we re-evaluate the rule's is_active status inline.
        """
        effective_today = today or date.today()
        for rule in self._active:
            # Re-check activity if the caller passed a different date
            if not rule.is_active(effective_today):
                continue
            if check_name in rule.checks and _matches_target(entry, rule.target):
                return True
        return False

    def reappeared_exclusions(self) -> list[dict]:
        """Return raw dicts for expired-temporary exclusions that have re-surfaced."""
        return list(self._reappeared)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Any, *, today: date | None = None) -> "GardenExclusions":
        """Build from a parsed config dict. Returns empty on None or malformed input."""
        effective_today = today or date.today()
        if not isinstance(data, dict):
            return cls([], effective_today)
        raw_exclusions = data.get("exclusions") or []
        if not isinstance(raw_exclusions, list):
            return cls([], effective_today)
        rules: list[_ExclusionRule] = []
        for raw in raw_exclusions:
            if not isinstance(raw, dict):
                continue
            rule = _parse_rule(raw)
            if rule is None:
                logger.debug("garden_exclusions: skipping malformed entry: %r", raw)
                continue
            rules.append(rule)
        return cls(rules, effective_today)

    @classmethod
    def from_path(cls, path: Path, *, today: date | None = None) -> "GardenExclusions":
        """Load from a YAML file path. Returns empty on missing file or parse error."""
        effective_today = today or date.today()
        if not path.exists():
            return cls([], effective_today)
        try:
            import yaml  # defer import — only needed for file loading
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("garden_exclusions: could not load %s: %s", path, exc)
            return cls([], effective_today)
        return cls.from_dict(data, today=today)
