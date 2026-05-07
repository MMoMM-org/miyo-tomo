#!/usr/bin/env python3
# version: 0.1.0
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
    "candidate_cap": 200,
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
    assert out.cache_miss_max_batches == SPEC_DEFAULTS["cache_miss_max_batches"]
    assert out.squelch_runs == SPEC_DEFAULTS["squelch_runs"]


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
