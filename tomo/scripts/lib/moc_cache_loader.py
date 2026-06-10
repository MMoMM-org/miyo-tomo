# version: 0.1.0
"""moc_cache_loader.py — TTL-gated loader for the MOC-structure cache.

Sits between moc-discovery and config/moc-structure-cache.yaml (the T1.4
builder's output). Responsibilities (ADR-1, ADR-3, ADR-8):

  1. Staleness check — `now − last_scan > ttl_days` ⇒ stale. A missing,
     corrupt, or timestamp-less cache is also stale. A `last_scan` in the
     FUTURE (clock skew) is treated as fresh (SDD Error Handling).
  2. Rebuild-if-stale — when stale, invoke the builder INLINE exactly once,
     then reload. `/moc-propose` relies on this; `/explore-vault` force-rebuilds
     via the builder directly (not through this loader).
  3. Shim — project `entries[kind=="moc"]` onto `cache["map_notes"]` so
     moc-discovery Phases 1–6 (which read `map_notes`) run unchanged (ADR-1).

Failure handling (SDD Error Handling):
  - Persistently unwritable / empty AFTER one rebuild → abort
    "cache-rebuild-failed" (NOT a re-scan every run). The rebuild is attempted
    exactly once; if the reloaded cache is still stale or carries no usable
    map_notes, the loader returns an actionable abort instead of looping a full
    Kado scan on every invocation.
  - The atomic tmp-rename in the builder guards against torn/partial reads, so
    a half-written cache never reaches the staleness check.

Scan-mode candidate source (M2 decision — DOCUMENTED, not wired here):
  moc-discovery `_handle_scan` enumerates atomic-note candidates via a live
  `list_dir`. The cache's `entries[kind=="note"]` already holds that in-scope
  note universe (the T1.4 builder populates it from moc_scan.in_scope_note_paths
  excluding MOCs), so scan-mode COULD be sourced from the cache to make M1
  ("no full live pull") hold for scan-mode too. That rewire is a moc-discovery
  change (a separate task), not the loader's job. The loader exposes the full
  `entries` list on the returned cache so the rewire is a one-line projection
  when it lands; until then scan-mode stays a live `list_dir` and M1 holds for
  the MOC tree-build specifically (no full whole-vault MOC tree-build when the
  cache is fresh).

Spec: docs/XDD/specs/021-moc-propose-consolidation/ — plan/phase-2.md T2.1;
SDD Application Data Models (loader shim); ADR-1,3,8.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

# Type alias: a rebuilder takes (cache_path, config_path) and writes the cache
# file as a side effect. Injectable so tests run without Kado / the real builder.
Rebuilder = Callable[[str, str], None]

ABORT_REBUILD_FAILED = "cache-rebuild-failed"
# A FRESH cache that carries zero MOC entries — an empty vault, not a staleness
# problem. Preserves moc-discovery's original validate_cache_loaded contract.
ABORT_CACHE_EMPTY = "cache-empty"


# ──────────────────────────────────────────────────────────────────────────────
# Cache file I/O
# ──────────────────────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> Optional[dict]:
    """Read a YAML cache file → dict.

    Returns None when the file is missing, empty, corrupt, or not a mapping —
    all of which the staleness check treats as stale (⇒ rebuild).
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


# ──────────────────────────────────────────────────────────────────────────────
# Staleness
# ──────────────────────────────────────────────────────────────────────────────

def _parse_iso(value: object) -> Optional[datetime]:
    """Parse an ISO-8601 UTC timestamp (mirrors cache-builder's Z→+00:00).

    Returns None for missing / non-string / unparseable values.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_stale(cache: Optional[dict], *, now: Optional[datetime] = None) -> bool:
    """Return True when the cache must be rebuilt.

    Stale when: cache is None / not a dict, `last_scan` missing or unparseable,
    or `now − last_scan > ttl_days`. A `last_scan` in the FUTURE (clock skew) is
    treated as fresh (returns False) per SDD Error Handling.
    """
    if not isinstance(cache, dict):
        return True

    last_scan = _parse_iso(cache.get("last_scan"))
    if last_scan is None:
        return True
    if last_scan.tzinfo is None:
        last_scan = last_scan.replace(tzinfo=timezone.utc)

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    ttl_days = cache.get("ttl_days")
    if not isinstance(ttl_days, (int, float)) or ttl_days < 0:
        ttl_days = 1  # default TTL when config-less / malformed

    age_seconds = (now - last_scan).total_seconds()
    if age_seconds < 0:
        return False  # future last_scan → fresh (clock skew)
    return age_seconds > ttl_days * 86400


# ──────────────────────────────────────────────────────────────────────────────
# Shim
# ──────────────────────────────────────────────────────────────────────────────

def apply_shim(cache: dict) -> dict:
    """Project `entries[kind=="moc"]` onto `cache["map_notes"]` (ADR-1).

    Mutates and returns the same dict so moc-discovery Phases 1–6 — which read
    `map_notes` — run unchanged against the new entries list. The full `entries`
    list is left intact for the case-(a) orphan pass (T2.3) and the documented
    scan-mode rewire.
    """
    entries = cache.get("entries") or []
    cache["map_notes"] = [
        e for e in entries if isinstance(e, dict) and e.get("kind") == "moc"
    ]
    return cache


def _has_usable_map_notes(cache: Optional[dict]) -> bool:
    """True when the shimmed cache carries at least one kind==moc entry."""
    if not isinstance(cache, dict):
        return False
    return bool(cache.get("map_notes"))


# ──────────────────────────────────────────────────────────────────────────────
# Default rebuilder
# ──────────────────────────────────────────────────────────────────────────────

def _default_rebuilder(cache_path: str, config_path: str) -> None:
    """Invoke the real MOC-structure-cache builder inline.

    Lazily imports moc-tree-builder.py (hyphen-named → importlib) so the heavy
    Kado-touching path is only loaded when an actual rebuild is needed; tests
    inject a fake rebuilder and never reach this.
    """
    import importlib.util

    builder_path = Path(__file__).resolve().parent.parent / "moc-tree-builder.py"
    spec = importlib.util.spec_from_file_location("moc_tree_builder", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    # builder.run() writes the YAML cache atomically and prints the JSON feed to
    # stdout; the loader only needs the YAML side-effect.
    builder.run(config_path, cache_path)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def load_moc_cache(
    cache_path: str,
    config_path: str,
    *,
    now: Optional[datetime] = None,
    rebuilder: Optional[Rebuilder] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Load the MOC-structure cache, rebuilding inline if stale.

    Parameters
    ----------
    cache_path:
        Path to moc-structure-cache.yaml.
    config_path:
        Path to vault-config.yaml (passed to the builder on rebuild).
    now:
        Override for the current time (testing / determinism).
    rebuilder:
        Injectable builder invocation `(cache_path, config_path) -> None`.
        Defaults to the real inline builder.

    Returns
    -------
    (cache, abort_reason):
        On success — (shimmed cache dict with `map_notes`, None).
        On failure — (None, "cache-rebuild-failed"): the cache was stale/missing,
        a single inline rebuild was attempted, and the result is still
        stale/empty. The caller surfaces an actionable message; the loader does
        NOT re-scan on every invocation.
    """
    rebuilder = rebuilder or _default_rebuilder
    path = Path(cache_path)

    cache = _load_yaml(path)
    if not is_stale(cache, now=now):
        cache = apply_shim(cache)  # type: ignore[arg-type]
        if not _has_usable_map_notes(cache):
            # Fresh but zero MOCs — a real empty vault, not a staleness problem.
            # Preserve the original validate_cache_loaded contract: surface
            # "cache-empty" so the agent shows the "run /explore-vault" hint
            # instead of silently proceeding with no MOC index. (No rebuild —
            # the cache is fresh; rebuilding would not add MOCs.)
            return None, ABORT_CACHE_EMPTY
        return cache, None

    # Stale / missing / corrupt → rebuild inline EXACTLY ONCE.
    try:
        rebuilder(cache_path, config_path)
    except Exception as exc:  # noqa: BLE001 — surface as actionable abort, not a crash
        print(
            f"[moc-cache-loader] rebuild raised: {exc}",
            file=sys.stderr,
        )
        return None, ABORT_REBUILD_FAILED

    cache = _load_yaml(path)
    if is_stale(cache, now=now):
        # Builder ran but the target is still missing/stale (unwritable target,
        # broken clock, …) — abort rather than loop a full scan every run.
        print(
            "[moc-cache-loader] cache still stale after rebuild — aborting "
            f"({ABORT_REBUILD_FAILED})",
            file=sys.stderr,
        )
        return None, ABORT_REBUILD_FAILED

    cache = apply_shim(cache)  # type: ignore[arg-type]
    if not _has_usable_map_notes(cache):
        # Rebuilt fresh but zero MOCs — no usable map_notes. Treat as a failed
        # rebuild so the caller surfaces the "run /explore-vault" hint instead of
        # rebuilding endlessly.
        print(
            "[moc-cache-loader] rebuilt cache has no MOC entries — aborting "
            f"({ABORT_REBUILD_FAILED})",
            file=sys.stderr,
        )
        return None, ABORT_REBUILD_FAILED

    return cache, None
