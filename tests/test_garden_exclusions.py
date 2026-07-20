#!/usr/bin/env python3
# version: 0.1.1
"""test_garden_exclusions.py — Behavioural tests for lib.garden_exclusions (spec 030 T1.2).

Tests cover:
- is_excluded honours target type (note/path/tag) × scope (per-check vs complete)
- permanent always excludes
- temporary excludes only before `until` date
- expired temporary → NOT excluded AND surfaced as "reappeared"
- malformed/missing config → empty (fail-open, no crash)
- schema validates the sample config (jsonschema)
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCHEMAS_DIR = Path(__file__).parent.parent / "tomo" / "schemas"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.garden_exclusions import GardenExclusions  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — note entries (path, stem, tags)
# ──────────────────────────────────────────────────────────────────────────────

def _note(path: str, *, tags: list[str] | None = None) -> dict:
    """Minimal note entry with path, stem, and tags."""
    stem = Path(path).stem
    return {"path": path, "stem": stem, "tags": tags or []}


# Sample config matching the SDD verbatim shape
SAMPLE_CONFIG = {
    "version": 1,
    "exclusions": [
        {
            "target": {"type": "path", "value": "Calendar/"},
            "checks": ["unparented", "orphan", "broken_up"],
            "mode": "permanent",
            "reason": "daily notes never get up::",
            "created": "2026-07-19",
        },
        {
            "target": {"type": "note", "value": "Projects/Big Refactor.md"},
            "checks": "all",
            "mode": "temporary",
            "until": "2026-10-17",
            "reason": "actively fixing",
            "created": "2026-07-19",
        },
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# Permanent exclusions
# ──────────────────────────────────────────────────────────────────────────────

def test_permanent_path_prefix_excludes_matching_note():
    """A permanent path exclusion suppresses all listed checks for notes under that path."""
    cfg = GardenExclusions.from_dict(SAMPLE_CONFIG)
    note = _note("Calendar/2026-07-19.md")
    assert cfg.is_excluded(note, "unparented") is True
    assert cfg.is_excluded(note, "orphan") is True
    assert cfg.is_excluded(note, "broken_up") is True


def test_permanent_path_prefix_does_not_exclude_unlisted_check():
    """Checks not in the exclusion's check list are not suppressed."""
    cfg = GardenExclusions.from_dict(SAMPLE_CONFIG)
    note = _note("Calendar/2026-07-19.md")
    assert cfg.is_excluded(note, "dead_link") is False


def test_permanent_path_prefix_does_not_exclude_nonmatching_path():
    """A note outside the excluded path prefix is not excluded."""
    cfg = GardenExclusions.from_dict(SAMPLE_CONFIG)
    note = _note("Projects/Planning.md")
    assert cfg.is_excluded(note, "unparented") is False


def test_permanent_note_exact_match_excludes():
    """Exact-note target type matches the note's path exactly."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Big Refactor.md"},
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Big Refactor.md")
    assert cfg.is_excluded(note, "orphan") is True


def test_permanent_note_exact_match_does_not_match_different_path():
    """Exact-note match does not affect notes with different paths."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Big Refactor.md"},
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Other.md")
    assert cfg.is_excluded(note, "orphan") is False


def test_permanent_tag_excludes_note_carrying_that_tag():
    """Tag-type target excludes a note that has the tag in its tags list."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "tag", "value": "wip"},
                "checks": ["stale_moc"],
                "mode": "permanent",
                "reason": "works in progress",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Draft.md", tags=["wip", "project"])
    assert cfg.is_excluded(note, "stale_moc") is True


def test_permanent_tag_does_not_exclude_note_without_that_tag():
    """Tag-type exclusion does not affect notes that lack the tag."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "tag", "value": "wip"},
                "checks": ["stale_moc"],
                "mode": "permanent",
                "reason": "works in progress",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Done.md", tags=["project"])
    assert cfg.is_excluded(note, "stale_moc") is False


# ──────────────────────────────────────────────────────────────────────────────
# checks: all (complete scope)
# ──────────────────────────────────────────────────────────────────────────────

def test_checks_all_excludes_every_named_check():
    """checks: all suppresses every known check name for the matched target."""
    all_checks = ["unparented", "orphan", "broken_up", "dead_link", "duplicate_stem", "stale_moc"]
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Big Refactor.md"},
                "checks": "all",
                "mode": "permanent",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Big Refactor.md")
    for check in all_checks:
        assert cfg.is_excluded(note, check) is True, f"checks:all must suppress {check!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Temporary exclusions — before and after `until`
# ──────────────────────────────────────────────────────────────────────────────

def test_temporary_excludes_before_until():
    """Temporary exclusion is active when today < until date."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Draft.md"},
                "checks": ["orphan"],
                "mode": "temporary",
                "until": "2026-10-17",
                "reason": "still drafting",
                "created": "2026-07-19",
            }
        ],
    }
    # W1: pin construction date so the rule is always active at build time
    cfg = GardenExclusions.from_dict(config, today=date(2026, 7, 19))
    note = _note("Projects/Draft.md")
    # today before until → excluded
    assert cfg.is_excluded(note, "orphan", today=date(2026, 7, 19)) is True
    assert cfg.is_excluded(note, "orphan", today=date(2026, 10, 16)) is True


def test_temporary_does_not_exclude_on_or_after_until():
    """Temporary exclusion is NOT active when today >= until date."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Draft.md"},
                "checks": ["orphan"],
                "mode": "temporary",
                "until": "2026-10-17",
                "reason": "still drafting",
                "created": "2026-07-19",
            }
        ],
    }
    # W2: pin construction date before until so the rule enters _active at build time;
    # the per-call today then exercises the inline re-check path intentionally
    cfg = GardenExclusions.from_dict(config, today=date(2026, 7, 19))
    note = _note("Projects/Draft.md")
    # today == until → expired, not excluded
    assert cfg.is_excluded(note, "orphan", today=date(2026, 10, 17)) is False
    # today > until → expired
    assert cfg.is_excluded(note, "orphan", today=date(2026, 11, 1)) is False


# ──────────────────────────────────────────────────────────────────────────────
# Expired temporary → reappeared list
# ──────────────────────────────────────────────────────────────────────────────

def test_expired_temporary_surfaces_in_reappeared():
    """An expired temporary exclusion is reported in the reappeared list."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Draft.md"},
                "checks": ["orphan"],
                "mode": "temporary",
                "until": "2026-07-01",
                "reason": "was drafting",
                "created": "2026-06-01",
            }
        ],
    }
    # today is after until → expired
    cfg = GardenExclusions.from_dict(config, today=date(2026, 7, 19))
    reappeared = cfg.reappeared_exclusions()
    assert len(reappeared) == 1
    assert reappeared[0]["target"]["value"] == "Projects/Draft.md"


def test_non_expired_temporary_not_in_reappeared():
    """An active (non-expired) temporary exclusion does NOT appear in reappeared."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Draft.md"},
                "checks": ["orphan"],
                "mode": "temporary",
                "until": "2026-12-31",
                "reason": "active push-back",
                "created": "2026-07-19",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config, today=date(2026, 7, 19))
    assert cfg.reappeared_exclusions() == []


def test_permanent_exclusion_never_in_reappeared():
    """Permanent exclusions are never surfaced in reappeared — they never expire."""
    cfg = GardenExclusions.from_dict(SAMPLE_CONFIG, today=date(2030, 1, 1))
    reappeared = cfg.reappeared_exclusions()
    # The SAMPLE_CONFIG has one permanent + one temporary-until-2026-10-17
    # With today=2030-01-01 the temporary is expired; the permanent is not
    assert all(e["mode"] == "temporary" for e in reappeared), (
        f"only temporary entries appear in reappeared; got {reappeared}"
    )


def test_expired_temporary_not_excluded_but_reappeared():
    """Expired temporary: is_excluded → False AND reappeared_exclusions() non-empty."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Archive/Old.md"},
                "checks": "all",
                "mode": "temporary",
                "until": "2026-01-01",
                "reason": "old push-back",
                "created": "2025-10-01",
            }
        ],
    }
    today = date(2026, 7, 19)
    cfg = GardenExclusions.from_dict(config, today=today)
    note = _note("Archive/Old.md")
    assert cfg.is_excluded(note, "orphan", today=today) is False
    assert len(cfg.reappeared_exclusions()) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Fail-open: missing or malformed config
# ──────────────────────────────────────────────────────────────────────────────

def test_load_from_nonexistent_path_returns_empty():
    """Loading from a path that does not exist → empty config, no crash."""
    cfg = GardenExclusions.from_path(Path("/nonexistent/garden-audit-exclusions.yaml"))
    note = _note("Anywhere/Note.md")
    assert cfg.is_excluded(note, "orphan") is False
    assert cfg.reappeared_exclusions() == []


def test_load_from_invalid_yaml_returns_empty():
    """A YAML file with non-dict content → empty config, no crash."""
    cfg = GardenExclusions.from_dict(None)  # type: ignore[arg-type]
    note = _note("Anywhere/Note.md")
    assert cfg.is_excluded(note, "orphan") is False


def test_load_with_missing_exclusions_key_returns_empty():
    """Config dict missing the 'exclusions' key → treated as empty list."""
    cfg = GardenExclusions.from_dict({"version": 1})
    note = _note("Anywhere/Note.md")
    assert cfg.is_excluded(note, "orphan") is False


def test_malformed_exclusion_entry_skipped():
    """A malformed entry (missing required fields) is silently skipped."""
    config = {
        "version": 1,
        "exclusions": [
            {"bad": "entry"},  # missing target, checks, mode
            {
                "target": {"type": "note", "value": "Projects/OK.md"},
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "valid entry",
                "created": "2026-07-19",
            },
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/OK.md")
    # The valid entry must still work
    assert cfg.is_excluded(note, "orphan") is True
    # And no crash occurred processing the bad entry


# ──────────────────────────────────────────────────────────────────────────────
# Schema validation — sample config must be schema-valid
# ──────────────────────────────────────────────────────────────────────────────

def test_schema_validates_sample_config():
    """The sample config from the SDD is valid against garden-audit-exclusions.schema.json."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    assert schema_path.exists(), f"schema not found: {schema_path}"

    schema = json.loads(schema_path.read_text())
    # Should not raise
    jsonschema.validate(instance=SAMPLE_CONFIG, schema=schema)


def test_schema_rejects_invalid_target_type():
    """Schema must reject unknown target type values."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    bad_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "directory", "value": "Foo/"},  # not path|note|tag
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_config, schema=schema)


def test_schema_rejects_invalid_mode():
    """Schema must reject unknown mode values."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    bad_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Foo.md"},
                "checks": ["orphan"],
                "mode": "indefinite",  # not permanent|temporary
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_config, schema=schema)


def test_schema_accepts_checks_as_list_or_all_string():
    """Schema accepts checks as a list of strings OR the literal string 'all'."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    # checks as list
    cfg_list = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Calendar/"},
                "checks": ["unparented", "orphan"],
                "mode": "permanent",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    jsonschema.validate(instance=cfg_list, schema=schema)

    # checks as "all"
    cfg_all = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Big Refactor.md"},
                "checks": "all",
                "mode": "temporary",
                "until": "2026-10-17",
                "reason": "test",
                "created": "2026-07-19",
            }
        ],
    }
    jsonschema.validate(instance=cfg_all, schema=schema)


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_exclusions_list_never_excludes():
    """An empty exclusions list never suppresses anything."""
    cfg = GardenExclusions.from_dict({"version": 1, "exclusions": []})
    note = _note("Anywhere/Note.md")
    assert cfg.is_excluded(note, "orphan") is False
    assert cfg.reappeared_exclusions() == []


def test_multiple_exclusions_any_match_excludes():
    """A note excluded by ANY matching rule is excluded (OR semantics)."""
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Calendar/"},
                "checks": ["unparented"],
                "mode": "permanent",
                "reason": "r1",
                "created": "2026-07-19",
            },
            {
                "target": {"type": "tag", "value": "skip-audit"},
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "r2",
                "created": "2026-07-19",
            },
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    calendar_note = _note("Calendar/2026-07-19.md")
    assert cfg.is_excluded(calendar_note, "unparented") is True
    assert cfg.is_excluded(calendar_note, "orphan") is False  # not in first rule's checks

    tagged_note = _note("Projects/Tagged.md", tags=["skip-audit"])
    assert cfg.is_excluded(tagged_note, "orphan") is True
    assert cfg.is_excluded(tagged_note, "unparented") is False  # not in second rule's checks


def test_temporary_without_until_is_conservative_never_expires():
    """W3: temporary rule with no `until` field is treated as never-expiring (conservative).

    Built via from_dict to bypass the schema's if/then requirement for `until`.
    Contracts: is_excluded returns True for a matching note AND reappeared_exclusions() returns [].
    Locks the is_active ~line 91 conservative branch.
    """
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/NoUntil.md"},
                "checks": ["orphan"],
                "mode": "temporary",
                # deliberately no `until` field
                "reason": "push-back with no deadline",
                "created": "2026-07-19",
            }
        ],
    }
    # Construct at a far-future date to confirm it still behaves as active
    cfg = GardenExclusions.from_dict(config, today=date(2099, 1, 1))
    note = _note("Projects/NoUntil.md")
    assert cfg.is_excluded(note, "orphan") is True, (
        "temporary with no until must still exclude (conservative never-expires)"
    )
    assert cfg.reappeared_exclusions() == [], (
        "temporary with no until must NOT appear in reappeared"
    )


def test_unrecognised_checks_shape_does_not_exclude():
    """W4: a rule whose checks is an unrecognised shape (e.g. integer 42) is silently no-oped.

    _normalize_checks returns frozenset() for unknown shapes; _parse_rule treats it as
    a zero-check rule that never matches any check name.
    """
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Projects/Draft.md"},
                "checks": 42,  # unrecognised — not "all" and not a list
                "mode": "permanent",
                "reason": "bad checks value",
                "created": "2026-07-19",
            }
        ],
    }
    # Must not crash
    cfg = GardenExclusions.from_dict(config)
    note = _note("Projects/Draft.md")
    # The rule's normalised checks is empty → never matches any check name
    assert cfg.is_excluded(note, "orphan") is False, (
        "unrecognised checks shape must not exclude anything"
    )


# ──────────────────────────────────────────────────────────────────────────────
# configured marker — loader must ignore it; schema must accept it
# ──────────────────────────────────────────────────────────────────────────────

def test_loader_ignores_configured_false_marker():
    """A config with configured:false still loads its exclusions correctly.

    The `configured` key is a first-run marker for the agent wizard; the loader
    must treat it as opaque metadata and still apply the exclusion rules.
    """
    config = {
        "version": 1,
        "configured": False,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Calendar/"},
                "checks": ["unparented"],
                "mode": "permanent",
                "reason": "daily notes",
                "created": "2026-07-20",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Calendar/2026-07-20.md")
    assert cfg.is_excluded(note, "unparented") is True, (
        "configured:false must not prevent exclusion rules from loading"
    )


def test_loader_ignores_configured_true_marker():
    """A config with configured:true also loads its exclusions correctly.

    After the wizard runs it writes configured:true; the loader must continue
    to evaluate rules regardless of the marker's value.
    """
    config = {
        "version": 1,
        "configured": True,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Archive/"},
                "checks": ["orphan"],
                "mode": "permanent",
                "reason": "archived notes",
                "created": "2026-07-20",
            }
        ],
    }
    cfg = GardenExclusions.from_dict(config)
    note = _note("Archive/Old.md")
    assert cfg.is_excluded(note, "orphan") is True, (
        "configured:true must not prevent exclusion rules from loading"
    )


def test_schema_accepts_configured_false():
    """Schema must accept a config with configured:false (the seeded value)."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    cfg = {"version": 1, "configured": False, "exclusions": []}
    jsonschema.validate(instance=cfg, schema=schema)  # must not raise


def test_schema_accepts_configured_true():
    """Schema must accept a config with configured:true (post-wizard value)."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    cfg = {"version": 1, "configured": True, "exclusions": []}
    jsonschema.validate(instance=cfg, schema=schema)  # must not raise


def test_schema_accepts_config_without_configured():
    """Schema must accept a user config that omits the configured key (not required)."""
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    cfg = {"version": 1, "exclusions": []}
    jsonschema.validate(instance=cfg, schema=schema)  # must not raise


def test_schema_rejects_non_boolean_configured():
    """Schema must reject configured with a non-boolean value (e.g. string 'yes').

    Guards against schema typos (e.g. type:string) that would silently accept
    the marker with wrong type, bypassing the grep-based agent detection.
    """
    import jsonschema

    schema_path = SCHEMAS_DIR / "garden-audit-exclusions.schema.json"
    schema = json.loads(schema_path.read_text())

    bad_cfg = {"version": 1, "configured": "yes", "exclusions": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_cfg, schema=schema)
