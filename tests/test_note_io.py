#!/usr/bin/env python3
# version: 0.1.0
"""test_note_io.py — Behavioural tests for lib.note_io (spec 044, #169).

Covers the config reader and the atomic text write the /note scripts share:
- load_vault_config: valid mapping; missing, unreadable, non-UTF-8 and invalid
  YAML raise ConfigUnreadable; empty and non-mapping raise ConfigNotMapping;
  messages carry the problem class only, never file text
- atomic_write_text: writes, replaces, leaves no temp; a failed write or
  replace removes the temp and leaves the old target untouched (no partial file)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_io  # noqa: E402
from lib.note_io import (  # noqa: E402
    ConfigError, ConfigNotMapping, ConfigUnreadable, atomic_write_text, load_vault_config,
)

MARKER = "SECRET_MARKER_9f3"


def _config(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "vault-config.yaml"
    path.write_bytes(raw)
    return path


# ── load_vault_config ────────────────────────────────────────────────────


def test_valid_config_returns_the_mapping(tmp_path):
    path = _config(tmp_path, b"concepts:\n  inbox: 100 Inbox/\nprofile: miyo\n")
    assert load_vault_config(path) == {"concepts": {"inbox": "100 Inbox/"}, "profile": "miyo"}


def test_valid_config_accepts_a_str_path(tmp_path):
    path = _config(tmp_path, b"profile: lyt\n")
    assert load_vault_config(str(path)) == {"profile": "lyt"}


def test_missing_config_is_unreadable_with_its_class(tmp_path):
    with pytest.raises(ConfigUnreadable) as info:
        load_vault_config(tmp_path / "absent.yaml")
    assert info.value.cause == "FileNotFoundError"
    assert str(info.value) == "vault-config.yaml unreadable (FileNotFoundError)"


def test_directory_in_place_of_the_config_is_unreadable(tmp_path):
    with pytest.raises(ConfigUnreadable) as info:
        load_vault_config(tmp_path)
    assert info.value.cause in ("IsADirectoryError", "PermissionError")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_unreadable_config_is_unreadable(tmp_path):
    path = _config(tmp_path, b"profile: miyo\n")
    path.chmod(0)
    try:
        with pytest.raises(ConfigUnreadable) as info:
            load_vault_config(path)
    finally:
        path.chmod(0o600)
    assert info.value.cause == "PermissionError"


def test_non_utf8_config_is_unreadable(tmp_path):
    path = _config(tmp_path, b"\xff\xfe\x00templates: \x9c")
    with pytest.raises(ConfigUnreadable) as info:
        load_vault_config(path)
    assert info.value.cause == "UnicodeDecodeError"


def test_invalid_yaml_is_unreadable_without_file_text(tmp_path):
    path = _config(tmp_path, f"a: [{MARKER}\nb: : :\n".encode())
    with pytest.raises(ConfigUnreadable) as info:
        load_vault_config(path)
    assert info.value.cause.endswith("Error")
    assert MARKER not in str(info.value) and MARKER not in info.value.cause


@pytest.mark.parametrize("raw, cause", [
    (b"", "NoneType"), (b"- a\n- b\n", "list"), (f"{MARKER}\n".encode(), "str"),
])
def test_non_mapping_config_is_not_a_mapping(tmp_path, raw, cause):
    path = _config(tmp_path, raw)
    with pytest.raises(ConfigNotMapping) as info:
        load_vault_config(path)
    assert str(info.value) == "vault-config.yaml is not a mapping"
    assert info.value.cause == cause


def test_both_errors_share_the_config_error_base():
    assert issubclass(ConfigUnreadable, ConfigError)
    assert issubclass(ConfigNotMapping, ConfigError)
    assert not issubclass(ConfigUnreadable, ConfigNotMapping)


# ── atomic_write_text ────────────────────────────────────────────────────


def _names(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def test_atomic_write_creates_the_file_without_a_temp(tmp_path):
    target = tmp_path / "meta.json"
    atomic_write_text(target, "Größe – ok\n")
    assert target.read_text(encoding="utf-8") == "Größe – ok\n"
    assert _names(tmp_path) == ["meta.json"]


def test_atomic_write_replaces_existing_text(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old text that is longer\n", encoding="utf-8")
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert _names(tmp_path) == ["note.md"]


def test_atomic_write_uses_the_tmp_sibling(tmp_path, monkeypatch):
    seen = []
    real = os.replace
    monkeypatch.setattr(note_io.os, "replace", lambda a, b: (seen.append((a, b)), real(a, b)))
    target = tmp_path / "meta.json"
    atomic_write_text(target, "x")
    assert seen == [(tmp_path / "meta.json.tmp", target)]


def test_atomic_write_does_not_create_the_parent(tmp_path):
    with pytest.raises(FileNotFoundError):
        atomic_write_text(tmp_path / "absent" / "note.md", "x")
    assert _names(tmp_path) == []


def test_failed_replace_removes_the_temp_and_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "note.md"
    target.write_text("old\n", encoding="utf-8")

    def refuse(_src, _dst):
        raise OSError("disk full")

    monkeypatch.setattr(note_io.os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert _names(tmp_path) == ["note.md"]


def test_failed_temp_write_leaves_no_partial_file(tmp_path, monkeypatch):
    target = tmp_path / "note.md"
    target.write_text("old\n", encoding="utf-8")
    real = Path.write_text

    def half_write(self, data, *args, **kwargs):
        real(self, data[:2], *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", half_write)
    with pytest.raises(OSError, match="disk full"):
        atomic_write_text(target, "new text\n")
    monkeypatch.undo()
    assert target.read_text(encoding="utf-8") == "old\n"
    assert _names(tmp_path) == ["note.md"]


def test_remove_temps_skips_missing_and_unremovable(tmp_path, monkeypatch):
    present = tmp_path / "a.tmp"
    present.write_text("x", encoding="utf-8")
    note_io.remove_temps([present, tmp_path / "gone.tmp"])
    assert _names(tmp_path) == []

    def refuse(self, missing_ok=False):
        raise OSError("busy")

    monkeypatch.setattr(Path, "unlink", refuse)
    note_io.remove_temps([tmp_path / "b.tmp"])  # an unremovable temp is left, no raise
