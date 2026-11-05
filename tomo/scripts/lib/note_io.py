# note_io.py — the config reader and atomic text write shared by the /note scripts.
# version: 0.1.0
"""Read ``config/vault-config.yaml`` and replace local files atomically for /note.

``note-session.py``, ``template-outline.py`` and ``note-instructions.py`` all
read the vault config, and those three plus lib/note_meta.py and
lib/note_process.py all replace a local file in place. The hyphenated scripts
cannot import each other, so the one reader and the one write live here.

``load_vault_config`` raises ConfigUnreadable (missing, unreadable, not UTF-8,
not YAML) or ConfigNotMapping (empty or not a key/value mapping); both subclass
ConfigError and carry no file text. Each caller decides what an error means
(empty config, a stderr line, exit 2) — this module never prints.

``atomic_write_text`` writes ``<name>.tmp`` beside the target and moves it into
place with os.replace, so a reader sees the old or the new text, never a part.
It does not create the parent folder; on failure the temp is removed and the
OSError re-raised.

Stdlib only at import time; PyYAML is imported when the config is read.

Design notes: docs/tomo/scripts/lib/note_io.md
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

TEMP_SUFFIX = ".tmp"


class ConfigError(Exception):
    """vault-config.yaml cannot be used; ``cause`` names the problem class only."""

    def __init__(self, message: str, cause: str):
        super().__init__(message)
        self.cause = cause


class ConfigUnreadable(ConfigError):
    """The file is missing, unreadable, not UTF-8 or not valid YAML."""


class ConfigNotMapping(ConfigError):
    """The file parses but is not a key/value mapping (an empty file included)."""


def load_vault_config(path: str | Path) -> dict:
    """Return the config mapping; ConfigUnreadable or ConfigNotMapping when unusable."""
    import yaml

    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        cause = type(exc).__name__
        raise ConfigUnreadable(f"vault-config.yaml unreadable ({cause})", cause) from exc
    if not isinstance(data, dict):
        raise ConfigNotMapping("vault-config.yaml is not a mapping", type(data).__name__)
    return data


def temp_sibling(path: Path) -> Path:
    """Return ``<path>.tmp``, the temp file an atomic write of path uses."""
    return path.with_name(path.name + TEMP_SUFFIX)


def remove_temps(temps: Iterable[Path]) -> None:
    """Remove leftover temp files; one that cannot be removed is left."""
    for temp in temps:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    """Replace path with text (UTF-8) via a temp sibling; the temp never outlives a failure."""
    target = Path(path)
    temp = temp_sibling(target)
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, target)
    except OSError:
        remove_temps([temp])
        raise
