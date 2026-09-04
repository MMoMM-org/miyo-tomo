#!/usr/bin/env python3
# version: 0.3.2
"""garden_exclusions.py — Load and apply the garden-audit exclusion config (spec 030 T1.2).

Loads config/garden-audit-exclusions.yaml, separates expired temporaries
(reporting which reappeared), and exposes is_excluded(note_entry, check_name) -> bool
applied as a filter before findings render.

Also owns the two garden-audit tuning knobs (optional top-level ``settings:`` in the
exclusions YAML — ``stale_moc_days``, ``advisory_pushback_days``) and the auto-managed
advisory-pushback ledger (config/garden-audit-pushback.yaml): acknowledged advisories
are stamped there by garden-audit-parser --stamp-pushback and merged into the active
rule set on load (from_paths), so a fresh scan suppresses them until their date lapses.

Fail-open: missing or malformed config/ledger returns an empty GardenExclusions
instance (nothing excluded, no crash) and default settings.

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
    [
        "unparented", "orphan", "broken_up", "dead_link", "duplicate_stem", "stale_moc",
        "parent_not_moc",
    ]
)

# Tuning defaults — used when the exclusions YAML has no settings block (fail-open).
DEFAULT_STALE_MOC_DAYS = 90
DEFAULT_ADVISORY_PUSHBACK_DAYS = 30


def _settings_int(settings: dict, key: str, default: int) -> int:
    """Read a positive-int setting; fall back to default on any bad value."""
    value = settings.get(key, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string (YYYY-MM-DD) into a date, or return None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _normalize_checks(checks: Any) -> frozenset[str]:
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
        checks = _normalize_checks(raw["checks"])
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
      active_rules(today=None) -> list[dict]  # active rules (stats read view)
      pushback_rules(today=None) -> list[dict]  # active temporaries only
    """

    def __init__(self, rules: list[_ExclusionRule], today: date,
                 settings: dict | None = None) -> None:
        self._active: list[_ExclusionRule] = [r for r in rules if r.is_active(today)]
        self._reappeared: list[dict] = [r.raw for r in rules if r.is_expired(today)]
        self._settings: dict = settings if isinstance(settings, dict) else {}
        # The date this instance was built against. Every query defaults to it, so a
        # caller that pinned a date at construction keeps that pin for the whole run
        # instead of silently falling back to the wall clock mid-scan.
        self._today: date = today

    # ------------------------------------------------------------------
    # Settings (optional top-level `settings:` block in the exclusions YAML)
    # ------------------------------------------------------------------

    @property
    def stale_moc_days(self) -> int:
        """Staleness threshold for the stale_moc check (days; default 90)."""
        return _settings_int(self._settings, "stale_moc_days", DEFAULT_STALE_MOC_DAYS)

    @property
    def advisory_pushback_days(self) -> int:
        """Rest window for an acknowledged advisory (days; default 30)."""
        return _settings_int(
            self._settings, "advisory_pushback_days", DEFAULT_ADVISORY_PUSHBACK_DAYS
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_excluded(self, entry: dict, check_name: str, *, today: date | None = None) -> bool:
        """Return True if entry should be suppressed for check_name.

        `today` is injectable for per-call date pinning; it defaults to the date this
        instance was constructed with, NOT the wall clock. The active/expired split
        already happened at construction (from_dict/from_paths), so defaulting to
        date.today() here would silently override a caller's pin and let a rule that
        was active at construction read as expired mid-scan.
        """
        effective_today = today if today is not None else self._today
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

    def active_rules(self, today: date | None = None) -> list[dict]:
        """Return a read view of the ACTIVE exclusion rules (spec 030 stats).

        Each entry: ``{target, checks (sorted list), mode, until}`` — a pure view
        for the stats overview; does not affect is_excluded. ``today`` re-checks
        activity inline so a caller that pinned a different date sees the same set
        (the active/expired split is made at construction, so this only ever
        narrows the already-active set); it defaults to the construction date, not
        the wall clock. ``until`` is the ISO string or None.
        """
        effective_today = today if today is not None else self._today
        out: list[dict] = []
        for rule in self._active:
            if not rule.is_active(effective_today):
                continue
            out.append({
                "target": dict(rule.target),
                "checks": sorted(rule.checks),
                "mode": rule.mode,
                "until": rule.until.isoformat() if rule.until else None,
            })
        return out

    def pushback_rules(self, today: date | None = None) -> list[dict]:
        """Return active TEMPORARY rules only (spec 030 stats — on-pushback view).

        Same shape as active_rules but filtered to ``mode == "temporary"``; these
        are the time-boxed push-backs the stats view lists with days-remaining.
        """
        return [r for r in self.active_rules(today) if r["mode"] == "temporary"]

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Any, *, today: date | None = None,
                  ledger_entries: list[dict] | None = None) -> "GardenExclusions":
        """Build from a parsed config dict. Returns empty on None or malformed input.

        ``ledger_entries`` (parsed pushback-ledger entries) are appended as
        temporary note-target rules — same active/expired lifecycle as
        wizard-written temporaries.
        """
        effective_today = today or date.today()
        if not isinstance(data, dict):
            data = {}
        settings = data.get("settings")
        raw_exclusions = data.get("exclusions") or []
        if not isinstance(raw_exclusions, list):
            raw_exclusions = []
        rules: list[_ExclusionRule] = []
        for raw in raw_exclusions:
            if not isinstance(raw, dict):
                continue
            rule = _parse_rule(raw)
            if rule is None:
                logger.debug("garden_exclusions: skipping malformed entry: %r", raw)
                continue
            rules.append(rule)
        for entry in ledger_entries or []:
            rule = _parse_rule(_ledger_entry_to_rule(entry))
            if rule is None:
                logger.debug("garden_exclusions: skipping malformed ledger entry: %r", entry)
                continue
            rules.append(rule)
        return cls(rules, effective_today, settings=settings)

    @classmethod
    def from_path(cls, path: Path, *, today: date | None = None) -> "GardenExclusions":
        """Load from a YAML file path. Returns empty on missing file or parse error."""
        effective_today = today or date.today()
        data = _load_yaml_dict(path)
        # C1: pass effective_today (already resolved) so both calls share the same date
        return cls.from_dict(data, today=effective_today)

    @classmethod
    def from_paths(cls, config_path: Path, ledger_path: Path, *,
                   today: date | None = None) -> "GardenExclusions":
        """Load the exclusions config AND the advisory-pushback ledger, merged.

        Ledger entries become temporary note-target rules, so acknowledged
        advisories are suppressed by the same is_excluded path as wizard
        push-backs until their date lapses. Either file may be missing (fail-open).
        """
        effective_today = today or date.today()
        return cls.from_dict(
            _load_yaml_dict(config_path),
            today=effective_today,
            ledger_entries=load_pushback_ledger(ledger_path),
        )


# ----------------------------------------------------------------------
# Advisory-pushback ledger (config/garden-audit-pushback.yaml)
# ----------------------------------------------------------------------
# Auto-managed by garden-audit-parser --stamp-pushback: one entry per
# acknowledged advisory finding {path, check, created, until}. Never edited
# by the configure wizard — kept separate so a wizard rewrite of the
# exclusions YAML can never clobber automatic state.

def _load_yaml_dict(path: Path) -> dict:
    """Read a YAML file into a dict; {} on missing file or any parse error."""
    if not path.exists():
        return {}
    try:
        import yaml  # defer import — only needed for file loading
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("garden_exclusions: could not load %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _ledger_entry_to_rule(entry: dict) -> dict:
    """Project a ledger entry to the exclusion-rule shape _parse_rule accepts."""
    if not isinstance(entry, dict):
        return {}
    return {
        "target": {"type": "note", "value": entry.get("path", "")},
        "checks": [entry.get("check", "")],
        "mode": "temporary",
        "until": entry.get("until"),
    }


def load_pushback_ledger(path: Path) -> list[dict]:
    """Return the ledger's entries list; [] on missing/malformed file."""
    entries = _load_yaml_dict(path).get("entries")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def stamp_pushback(path: Path, items: list[dict], days: int, *,
                   today: date | None = None) -> list[dict]:
    """Upsert acknowledged advisories into the ledger; prune expired entries.

    ``items``: [{path, check}] — each gets created=today, until=today+days.
    Existing entries are kept unless expired (until <= today) or re-stamped
    (same path+check → the new until wins). Writes the whole ledger YAML and
    returns the entries written.
    """
    from datetime import timedelta

    import yaml

    effective_today = today or date.today()
    kept: list[dict] = []
    stamped_keys = {(i.get("path"), i.get("check")) for i in items}
    for entry in load_pushback_ledger(path):
        until = _parse_date(entry.get("until"))
        if until is None or until <= effective_today:
            continue  # expired (or dateless) — prune
        if (entry.get("path"), entry.get("check")) in stamped_keys:
            continue  # re-acknowledged — replaced by the new stamp below
        kept.append(entry)
    until_str = (effective_today + timedelta(days=days)).isoformat()
    for item in items:
        kept.append({
            "path": item.get("path", ""),
            "check": item.get("check", ""),
            "created": effective_today.isoformat(),
            "until": until_str,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Managed by garden-audit-parser --stamp-pushback. Do not edit manually.\n"
        + yaml.safe_dump({"version": 1, "entries": kept}, sort_keys=False,
                         allow_unicode=True),
        encoding="utf-8",
    )
    return kept
