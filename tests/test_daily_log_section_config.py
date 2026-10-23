#!/usr/bin/env python3
# version: 0.1.0
"""test_daily_log_section_config.py — the daily-log heading comes from the
documented `daily_log.section` key.

The tomo-daily-log-wizard and vault-example.yaml write `daily_log.section`;
instruction-render used to read only `daily_log.heading`, so a custom section
name was ignored and every log entry/link targeted the default "Daily Log".
`heading` stays readable as the older spelling when `section` is absent.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_renderer():
    spec = importlib.util.spec_from_file_location("instruction_render", SCRIPTS_DIR / "instruction-render.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["instruction_render"] = mod
    spec.loader.exec_module(mod)
    return mod


ir = _load_renderer()


def _config(tmp_path: Path, daily_log_yaml: str) -> dict:
    path = tmp_path / "vault-config.yaml"
    path.write_text("daily_log:\n" + daily_log_yaml, encoding="utf-8")
    return ir.load_config(str(path))


def test_section_sets_the_heading(tmp_path: Path) -> None:
    cfg = _config(tmp_path, '  section: "Log"\n  heading_level: 1\n')
    assert cfg["daily_log.heading"] == "Log"
    assert cfg["daily_log.heading_level"] == 1


def test_section_wins_over_legacy_heading(tmp_path: Path) -> None:
    cfg = _config(tmp_path, '  section: "Log"\n  heading: "Old"\n')
    assert cfg["daily_log.heading"] == "Log"


def test_legacy_heading_still_read_without_section(tmp_path: Path) -> None:
    cfg = _config(tmp_path, '  heading: "Journal"\n')
    assert cfg["daily_log.heading"] == "Journal"


def test_default_when_neither_key_is_set(tmp_path: Path) -> None:
    cfg = _config(tmp_path, "  heading_level: 2\n")
    assert cfg["daily_log.heading"] == "Daily Log"
