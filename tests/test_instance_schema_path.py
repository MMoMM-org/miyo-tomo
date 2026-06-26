#!/usr/bin/env python3
# version: 1.0.0
"""Regression guard: tag-handler scripts must resolve their schema sibling-relative.

The bug (spec 025 live-walk, 2026-06-26): tag-handler-resolve.py and
tag-handler-writer.py computed the schema path as
``_SCRIPT_DIR.parent.parent / "tomo" / "schemas" / "tag-handler.schema.json"``.

In the REPO layout (``tomo/scripts`` + ``tomo/schemas``) that resolves to the same
location as the correct sibling path, so a unit test run in the repo cannot tell the
two apart. But the runtime InstanceLayout is FLATTENED — ``tomo-instance/scripts`` +
``tomo-instance/schemas`` with NO nested ``tomo/`` dir — so ``.parent.parent/"tomo"``
points at a missing path and the registry load crashes at runtime (the whole /inbox
tag-handler pipeline dies at triage).

The invariant: ``schemas/`` is a sibling of ``scripts/`` in BOTH layouts, so the path
MUST be ``_SCRIPT_DIR.parent / "schemas" / ...`` — never ``.parent.parent / "tomo" /
"schemas"``.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_SCRIPTS = ["tag-handler-resolve.py", "tag-handler-writer.py"]


def test_sibling_rule_resolves_in_flattened_instance_layout(tmp_path: Path) -> None:
    """The sibling rule finds the schema in a flattened layout; the nested rule does not."""
    # Simulate tomo-instance/{scripts,schemas} — no nested tomo/ dir.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "tag-handler.schema.json").write_text("{}", encoding="utf-8")
    script_dir = tmp_path / "scripts"  # stands in for _SCRIPT_DIR at runtime

    sibling_rule = script_dir.parent / "schemas" / "tag-handler.schema.json"
    nested_rule = script_dir.parent.parent / "tomo" / "schemas" / "tag-handler.schema.json"

    assert sibling_rule.exists(), "sibling-relative schema path must resolve in the instance layout"
    assert not nested_rule.exists(), "the .parent.parent/'tomo'/'schemas' rule must NOT resolve here"


def test_scripts_do_not_reintroduce_the_nested_schema_path() -> None:
    """Pin the source: the _SCHEMA_PATH ASSIGNMENT must not use parent.parent.

    Inspect only the assignment statement(s) — the warning comment intentionally
    names the bad pattern, so a whole-file grep would false-positive on it.
    """
    for name in SCHEMA_SCRIPTS:
        assignments = [
            ln for ln in (SCRIPTS_DIR / name).read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("_SCHEMA_PATH") and "=" in ln
        ]
        assert assignments, f"{name}: no _SCHEMA_PATH assignment found"
        for ln in assignments:
            assert "parent.parent" not in ln, (
                f"{name} reintroduced the instance-breaking schema path "
                f"(_SCRIPT_DIR.parent.parent / 'tomo' / 'schemas'). Use _SCRIPT_DIR.parent / 'schemas'."
            )


def test_live_schema_paths_are_sibling_relative_and_exist() -> None:
    """Each script's resolved _SCHEMA_PATH points at its sibling schemas/ dir and exists."""
    import importlib.util
    import sys

    for name in SCHEMA_SCRIPTS:
        mod_name = name.replace("-", "_").removesuffix(".py")
        spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / name)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(mod_name, mod)
        spec.loader.exec_module(mod)
        assert mod._SCHEMA_PATH == mod._SCRIPT_DIR.parent / "schemas" / "tag-handler.schema.json"
        assert mod._SCHEMA_PATH.exists()
