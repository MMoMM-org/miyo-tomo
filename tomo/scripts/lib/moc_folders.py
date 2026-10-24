# version: 0.1.0
"""moc_folders.py — the one answer to "is this MOC inside the configured MOC folders?".

The shared-ctx builder gives every MOC a delivered name: its title, or its
path when the title collides with another MOC's (spec 040 ADR-1). Which of the
colliding MOCs keeps the bare title depends on whether it lies inside
`concepts.map_note` — so that membership is decided here, once.

`lib.moc_scan.read_scope_paths` is not used for this: it merges the atomic-note
paths into the MOC scan scope, which is the right universe for scanning and the
wrong one for "the MOC folder". Rationale: docs/tomo/scripts/lib/moc_folders.md.
"""
from __future__ import annotations

from lib.vault_paths import path_key


def moc_folder_prefixes(vault_cfg: dict) -> tuple[str, ...]:
    """Folder prefixes from `concepts.map_note`, each ending in "/".

    Accepts the three shapes the config takes: `{paths: [...]}`, `{path: str}`
    or a bare string. Whitespace is stripped; empty entries are dropped.
    """
    concepts = (vault_cfg or {}).get("concepts") or {}
    value = concepts.get("map_note") if isinstance(concepts, dict) else None
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, dict):
        raw = list(value.get("paths") or [])
        if value.get("path"):
            raw.append(value["path"])
    else:
        raw = []
    out: list[str] = []
    for p in raw:
        if not isinstance(p, str) or not p.strip():
            continue
        prefix = p.strip().rstrip("/") + "/"
        if prefix not in out:
            out.append(prefix)
    return tuple(out)


def in_moc_folders(path: str, prefixes: tuple[str, ...]) -> bool:
    """True when `path` lies in (or below) one of `prefixes`, compared by `path_key`."""
    key = path_key(path)
    return any(key.startswith(path_key(p)) for p in prefixes)
