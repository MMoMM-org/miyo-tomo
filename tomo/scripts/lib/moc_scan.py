# version: 0.1.0
"""moc_scan.py — Tag-primary MOC discovery with scope/exclude filtering.

Implements the tag-primary discovery strategy for the MOC-structure cache
(ADR-5): query Kado for all notes tagged #type/others/moc, then apply
client-side prefix filtering so that exclude wins over tag (OQ-5, Rule 8).
Also builds the in-scope note universe by listing each configured scope path.

Return shape (ScanResult):
    moc_paths            — frozenset[str]: vault-relative paths of discovered MOCs
    in_scope_note_paths  — frozenset[str]: all .md paths under the scope roots
                           (excluding excluded prefixes; consumed by T1.4 builder
                           as the placeholder denominator and up_state resolver)

Design decisions:
    - byTag has no server-side path filter → filter is applied client-side here.
    - Exclude prefix matching is a simple str.startswith check; trailing spaces in
      prefixes are respected exactly (Calendar/301 Daily/  is a real vault gotcha).
    - Errors from Kado on any single scope path are caught, logged to stderr, and
      skipped — the caller receives partial but honest results (AC-P2: no fabricated
      presence/absence).  Mirrors the try/except pattern in moc-tree-builder.py
      discover_via_paths().
    - M8: concepts.atomic_note can be a scalar string or a dict with 'path' or
      'paths' keys; read_scope_paths() normalises both shapes.

Spec: docs/XDD/specs/021-moc-propose-consolidation/
Refs: SDD/Runtime View; SDD/Error Handling (denial); ADR-5; OQ-1,5; H4.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.kado_client import KadoClient  # pragma: no cover

MOC_TAG = "#type/others/moc"


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScanResult:
    """Immutable result of a vault MOC scan.

    Consumed by T1.4 (moc-structure-cache builder).
    moc_paths            — vault-relative .md paths that carry #type/others/moc
                           AND are NOT under any exclude prefix.
    in_scope_note_paths  — all .md paths under the configured scope roots,
                           excluding paths under any exclude prefix.
    """
    moc_paths: frozenset = field(default_factory=frozenset)
    in_scope_note_paths: frozenset = field(default_factory=frozenset)


# ── Public API ────────────────────────────────────────────────────────────────

def scan(client: "KadoClient", config: dict) -> ScanResult:
    """Discover MOCs and in-scope notes from the vault.

    Parameters
    ----------
    client:
        A KadoClient (or fake) that implements search_by_tag and list_notes/list_dir.
    config:
        Parsed vault-config.yaml dict.  Reads:
          config["concepts"]["map_note"]["paths"]
          config["concepts"]["atomic_note"]            (scalar or dict, M8)
          config["tomo"]["moc_structure_cache"]["exclude_paths"]

    Returns
    -------
    ScanResult with moc_paths and in_scope_note_paths.
    """
    exclude_prefixes: list[str] = (
        config.get("tomo", {})
              .get("moc_structure_cache", {})
              .get("exclude_paths", [])
    )
    scope_paths = read_scope_paths(config)

    moc_paths = _discover_moc_paths(client, exclude_prefixes)
    in_scope_note_paths = _collect_in_scope_notes(client, scope_paths, exclude_prefixes)

    return ScanResult(
        moc_paths=frozenset(moc_paths),
        in_scope_note_paths=frozenset(in_scope_note_paths),
    )


def read_scope_paths(config: dict) -> list[str]:
    """Extract the ordered list of scope root paths from config.

    Handles both vault-example.yaml (scalar atomic_note) and the instance
    config (dict atomic_note with 'path' or 'paths' key).  M8.

    Returns
    -------
    list[str] — vault-relative folder paths that form the scan universe,
    drawn from concepts.map_note.paths and concepts.atomic_note.
    """
    concepts = config.get("concepts", {})
    scope: list[str] = []

    # map_note paths
    map_note = concepts.get("map_note", {})
    if isinstance(map_note, dict):
        for p in map_note.get("paths", []):
            if p and p not in scope:
                scope.append(p)

    # atomic_note — M8: scalar or dict
    atomic_note = concepts.get("atomic_note")
    if isinstance(atomic_note, str):
        if atomic_note and atomic_note not in scope:
            scope.append(atomic_note)
    elif isinstance(atomic_note, dict):
        # dict with a single 'path' key
        single = atomic_note.get("path")
        if single and single not in scope:
            scope.append(single)
        # dict with a 'paths' list
        for p in atomic_note.get("paths", []):
            if p and p not in scope:
                scope.append(p)

    return scope


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_excluded(path: str, exclude_prefixes: list[str]) -> bool:
    """Return True if path starts with any of the exclude prefixes.

    Trailing spaces in prefixes are respected exactly — a vault folder named
    'Calendar/301 Daily/ ' (trailing space) is a real-world gotcha (OQ-5).
    """
    return any(path.startswith(prefix) for prefix in exclude_prefixes)


def _discover_moc_paths(
    client: "KadoClient",
    exclude_prefixes: list[str],
) -> set[str]:
    """Query Kado for #type/others/moc, apply client-side exclude filter.

    byTag has no server-side path filter → filtering is done here.
    Exclude wins over tag (OQ-5): a note tagged #type/others/moc that lives
    under an excluded prefix is NOT treated as a MOC.
    """
    try:
        results = client.search_by_tag(MOC_TAG)
    except Exception as exc:
        print(f"[warn] moc_scan: could not search by tag {MOC_TAG!r}: {exc}", file=sys.stderr)
        return set()

    moc_paths: set[str] = set()
    for item in results:
        path = item.get("path", "")
        if not path or not path.endswith(".md"):
            continue
        if _is_excluded(path, exclude_prefixes):
            continue
        moc_paths.add(path)

    return moc_paths


def _collect_in_scope_notes(
    client: "KadoClient",
    scope_paths: list[str],
    exclude_prefixes: list[str],
) -> set[str]:
    """List all .md notes under each scope root, skipping excluded paths.

    Errors on any individual scope path are caught, logged to stderr, and
    skipped — other paths are still scanned.  Mirrors the try/except pattern
    in moc-tree-builder.py discover_via_paths() (denial-skip, AC-P2).
    No fabricated entries are added for failed paths.
    """
    in_scope: set[str] = set()

    for folder_path in scope_paths:
        print(f"[moc_scan] listing scope path: {folder_path!r}", file=sys.stderr)
        try:
            items = client.list_notes(folder_path)
        except Exception as exc:
            print(
                f"[warn] moc_scan: skipping scope path {folder_path!r} — {exc}",
                file=sys.stderr,
            )
            continue

        for item in items:
            path = item.get("path", "")
            if not path.endswith(".md"):
                continue
            if _is_excluded(path, exclude_prefixes):
                continue
            in_scope.add(path)

    return in_scope
