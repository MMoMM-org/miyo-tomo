#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_proposal_config.py — Loader tests for vault-config tomo.moc_proposal block.

F-43 Phase 1 T1.2: schema additions + loader for the MOC-creation skill's
tunables. The block lives at `vault-config.yaml::tomo.moc_proposal` and is
optional — when absent, the loader returns spec defaults from
`docs/XDD/specs/013-moc-creation-skill/solution.md` §10 (Data Storage).

Coverage:
  - test_defaults_when_block_missing: absent block → spec defaults
    (PRD/AC-7.2 — discovery uses safe defaults without user setup).
  - test_user_overrides_take_precedence: user-set values win
    (PRD/AC-7.1 — user can tune candidate_cap, confidence_threshold, etc).
  - test_unknown_keys_logged_and_ignored: unknown keys produce a warning
    on stderr but do not crash (forward-compat).
  - test_non_dict_block_returns_defaults_with_warn: scalar block (e.g.
    `moc_proposal: true`) emits stderr WARN and falls back to defaults
    rather than crashing (defensive guard at shared-ctx-builder.py:98-104).
  - test_quoted_int_passes_through_as_string: documents the loader's
    contract — YAML types pass through as-is. Quoted scalars like
    `min_notes: "5"` land as `str` on the frozen dataclass; downstream
    arithmetic surfaces the type mismatch cleanly. The loader is
    intentionally not a coercion layer (keeps it minimal; coercion would
    hide user typos behind silent str→int conversion).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Register in sys.modules before exec — Python 3.14's dataclass machinery
# inspects the owning module's __dict__ during @dataclass class processing
# (dataclasses._is_type → sys.modules[cls.__module__].__dict__). Without
# registration, the module is `None` in sys.modules and class processing
# raises AttributeError.
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)


# Spec defaults from solution.md §10 / Data Storage Changes (lines 470-475).
SPEC_DEFAULTS = {
    "min_notes": 3,
    "confidence_threshold": 0.15,
    "max_results": 5,
    "candidate_cap": 500,
    "orphan_display_cap": 50,
    "cache_miss_max_batches": 5,
    "squelch_runs": 3,
}


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_when_block_missing(tmp_path: Path) -> None:
    """Loader returns spec defaults when tomo.moc_proposal block is absent."""
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        "schema_version: 1\nprofile: miyo\n",
    )
    out = scb.load_moc_proposal_config(cfg)
    assert out.min_notes == SPEC_DEFAULTS["min_notes"]
    assert out.confidence_threshold == SPEC_DEFAULTS["confidence_threshold"]
    assert out.max_results == SPEC_DEFAULTS["max_results"]
    assert out.candidate_cap == SPEC_DEFAULTS["candidate_cap"]
    assert out.orphan_display_cap == SPEC_DEFAULTS["orphan_display_cap"]
    assert out.cache_miss_max_batches == SPEC_DEFAULTS["cache_miss_max_batches"]
    assert out.squelch_runs == SPEC_DEFAULTS["squelch_runs"]


def test_orphan_display_cap_override(tmp_path: Path) -> None:
    """orphan_display_cap is user-overridable (ADR-12, T6.3)."""
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        (
            "schema_version: 1\n"
            "tomo:\n"
            "  moc_proposal:\n"
            "    orphan_display_cap: 25\n"
        ),
    )
    out = scb.load_moc_proposal_config(cfg)
    assert out.orphan_display_cap == 25
    # Unset keys keep defaults
    assert out.candidate_cap == SPEC_DEFAULTS["candidate_cap"]


def test_user_overrides_take_precedence(tmp_path: Path) -> None:
    """User-provided values override defaults; unset keys keep defaults."""
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        (
            "schema_version: 1\n"
            "tomo:\n"
            "  moc_proposal:\n"
            "    min_notes: 5\n"
            "    confidence_threshold: 0.25\n"
            "    candidate_cap: 500\n"
        ),
    )
    out = scb.load_moc_proposal_config(cfg)
    # Overridden values
    assert out.min_notes == 5
    assert out.confidence_threshold == 0.25
    assert out.candidate_cap == 500
    # Unset keys retain spec defaults
    assert out.max_results == SPEC_DEFAULTS["max_results"]
    assert out.cache_miss_max_batches == SPEC_DEFAULTS["cache_miss_max_batches"]
    assert out.squelch_runs == SPEC_DEFAULTS["squelch_runs"]


def test_unknown_keys_logged_and_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unknown keys emit a stderr warning but do not crash; known keys still apply."""
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        (
            "schema_version: 1\n"
            "tomo:\n"
            "  moc_proposal:\n"
            "    min_notes: 7\n"
            "    bogus_field: 42\n"
            "    another_unknown: hello\n"
        ),
    )
    out = scb.load_moc_proposal_config(cfg)
    # Known field still applied
    assert out.min_notes == 7
    # Unknown fields not present on the dataclass
    assert not hasattr(out, "bogus_field")
    # Warnings hit stderr
    err = capsys.readouterr().err
    assert "bogus_field" in err
    assert "another_unknown" in err
    assert "WARN" in err or "warn" in err.lower()


def test_non_dict_block_returns_defaults_with_warn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scalar `moc_proposal` (e.g. `true`) → defaults + stderr WARN, no crash.

    Guards the defensive branch at shared-ctx-builder.py:98-104. A user who
    writes `moc_proposal: true` (or any non-mapping scalar) gets the full
    spec-defaults `MocProposalConfig` plus a WARN on stderr naming the
    offending type — same contract as a missing block, just noisier so the
    misconfiguration shows up in the run log.
    """
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        (
            "schema_version: 1\n"
            "tomo:\n"
            "  moc_proposal: true\n"
        ),
    )
    out = scb.load_moc_proposal_config(cfg)
    # Falls back to a fresh defaults instance — every field equals the spec.
    assert out == scb.MocProposalConfig()
    assert out.min_notes == SPEC_DEFAULTS["min_notes"]
    assert out.confidence_threshold == SPEC_DEFAULTS["confidence_threshold"]
    # WARN hits stderr and names the wrong type so the user can find the typo.
    err = capsys.readouterr().err
    assert "WARN" in err
    assert "moc_proposal" in err
    assert "bool" in err  # type(block).__name__ for `true`


def test_quoted_int_passes_through_as_string(tmp_path: Path) -> None:
    """Document loader contract: YAML types pass through as-is, no coercion.

    A quoted scalar (`min_notes: "5"`) is a YAML string, and the loader
    stores it verbatim on the frozen dataclass. Downstream code that does
    arithmetic on `cfg.min_notes` will then raise `TypeError` cleanly,
    surfacing the user's quoting mistake instead of papering over it with a
    silent str→int conversion. This regression test pins that behaviour so
    a future "helpful" coercion layer cannot land without an explicit
    contract change.
    """
    cfg = _write_yaml(
        tmp_path / "vault-config.yaml",
        (
            "schema_version: 1\n"
            "tomo:\n"
            "  moc_proposal:\n"
            '    min_notes: "5"\n'
        ),
    )
    out = scb.load_moc_proposal_config(cfg)
    # The quoted value is a str, NOT coerced to int.
    assert out.min_notes == "5"
    assert isinstance(out.min_notes, str)
    # Other fields keep their typed defaults — no cross-contamination.
    assert out.confidence_threshold == SPEC_DEFAULTS["confidence_threshold"]
    assert isinstance(out.confidence_threshold, float)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
