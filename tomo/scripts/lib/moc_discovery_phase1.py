# version: 0.2.0
"""moc_discovery_phase1.py — Phase 1 of moc-discovery: candidate selection.

One handler per run mode (tag / folder / class / title / free-text / scan)
produces raw candidates; the atomic-note pre-filter, the folder-home filter and
the zero / cap checks then decide whether the pipeline continues. Also holds the cache-empty
predicate that guards Phase 1. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_phase1.md (issue #216).
"""
from __future__ import annotations

from lib.folder_homes import atomic_roots, drop_home_members, folder_homes
from lib.moc_discovery_common import Candidate, _log, _stem_from_path
from lib.moc_tags import EXCLUDE_NOTE_TAG


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Candidate selection
# ──────────────────────────────────────────────────────────────────────────────


def _candidate_from_path(path: str) -> Candidate:
    """Build a Phase-1 Candidate from a vault-relative `.md` path."""
    return Candidate(stem=_stem_from_path(path), path=path)


def _atomic_note_paths(profile: dict) -> list[str]:
    """Allowed prefixes for atomic-note pre-filter.

    Returns the union of `concept_defaults.atomic_note.base_path` and each
    `subdirectories[].path`. Trailing `/` is preserved — callers do prefix
    comparison against these strings, so consistency matters.
    """
    cd = (profile.get("concept_defaults") or {}).get("atomic_note") or {}
    out: list[str] = []
    base = cd.get("base_path")
    if base:
        out.append(base)
    for sd in cd.get("subdirectories") or []:
        if isinstance(sd, dict) and sd.get("path"):
            out.append(sd["path"])
    return out


def _is_md_file(item: dict) -> bool:
    """Client-side `.md` filter for kado-read listDir results (ADR-6).

    Folders carry `type: 'folder'`; files may be `.md`, `.canvas`, images,
    binaries — only `.md` count as atomic-note candidates. The Kado client
    guarantees `path` is present, so we require `path` to end in `.md` —
    no `name` fallback (would yield blank-path candidates downstream).
    """
    if item.get("type") == "folder":
        return False
    path = item.get("path", "") or ""
    return path.endswith(".md")


def _handle_tag(trigger_arg: str, kado_client) -> list[Candidate]:
    """Tag mode (ADR-7): `byTag` query is `#<tag>*` — literal `*` glob suffix."""
    query = f"#{trigger_arg}*"
    _log(f"phase1: byTag query={query!r}")
    items = kado_client.search_by_tag(query)
    out: list[Candidate] = []
    for item in items:
        path = item.get("path", "") or ""
        if path.endswith(".md"):
            out.append(_candidate_from_path(path))
    return out


def _handle_folder(trigger_arg: str, kado_client) -> list[Candidate]:
    """Folder mode: recursive listDir + client-side `.md` filter (ADR-6)."""
    _log(f"phase1: listDir folder={trigger_arg!r} depth=10")
    items = kado_client.list_dir(trigger_arg, depth=10)
    return [_candidate_from_path(item.get("path", "")) for item in items if _is_md_file(item)]


def _resolve_class_subdir(klass: str, profile: dict) -> str | None:
    """Resolve a Dewey class (e.g. `2600`) to its atomic-note subdirectory.

    Returns the first subdirectory whose `dewey_parent` matches `int(klass)`,
    or None if no match. Profiles without `dewey_parent` (e.g. lyt.yaml)
    return None — class mode is miyo-specific by design (the Dewey numbering
    is part of the miyo conventions).
    """
    try:
        target = int(klass)
    except (TypeError, ValueError):
        return None
    cd = (profile.get("concept_defaults") or {}).get("atomic_note") or {}
    for sd in cd.get("subdirectories") or []:
        if isinstance(sd, dict) and sd.get("dewey_parent") == target:
            return sd.get("path")
    return None


def _handle_class(trigger_arg: str, profile: dict, kado_client) -> list[Candidate]:
    """Class mode: resolve Dewey class via profile → listDir on the subdir."""
    subdir = _resolve_class_subdir(trigger_arg, profile)
    if not subdir:
        _log(
            f"WARN: --class {trigger_arg!r} did not match any atomic-note "
            f"subdirectory in profile (no dewey_parent={trigger_arg})"
        )
        return []
    _log(f"phase1: class={trigger_arg!r} → listDir {subdir!r} depth=10")
    items = kado_client.list_dir(subdir, depth=10)
    return [_candidate_from_path(item.get("path", "")) for item in items if _is_md_file(item)]


def _handle_title_or_freetext(trigger_arg: str, cache: dict) -> list[Candidate]:
    """Title / free-text mode: substring-match against `cache.map_notes[].topics`.

    The discovery cache already holds topics per note — title/free-text
    discovery does not need Kado at all in Phase 1, only the cache. A
    candidate is selected when ANY of its cached topics contains the
    trigger string (case-insensitive).
    """
    needle = (trigger_arg or "").strip().lower()
    if not needle:
        return []
    out: list[Candidate] = []
    seen_paths: set[str] = set()
    for entry in cache.get("map_notes") or []:
        path = (entry.get("path") or "").strip()
        if not path or path in seen_paths:
            continue
        topics = entry.get("topics") or []
        if any(needle in (str(t) or "").lower() for t in topics):
            seen_paths.add(path)
            out.append(_candidate_from_path(path))
    _log(f"phase1: title/free-text {trigger_arg!r} matched {len(out)} cached note(s)")
    return out


def _handle_scan(cache: dict) -> list[Candidate]:
    """Scan mode: source candidates from cache orphans (kind==note, up_state==absent).

    ADR-11: The old live list_dir enumeration counted EVERY atomic note (including
    already-MOC-linked notes) toward the candidate cap, causing candidate-cap-exceeded
    on whole-vault /moc-propose runs. The fix: source only orphans from the cache
    (up_state==absent means no existing up:: link). No live Kado call is made.
    """
    seen: set[str] = set()
    out: list[Candidate] = []
    for entry in cache.get("entries") or []:
        if entry.get("kind") != "note":
            continue
        if entry.get("up_state") != "absent":
            continue
        # ADR-13 B-note: notes tagged exclude/note are never clustered.
        if EXCLUDE_NOTE_TAG in (entry.get("tags") or []):
            continue
        path = (entry.get("path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        stem = (entry.get("stem") or _stem_from_path(path))
        topics = [str(t) for t in (entry.get("topics") or []) if t]
        out.append(Candidate(stem=stem, path=path, topics=topics))
    _log(f"phase1: scan sourced {len(out)} orphan candidate(s) from cache (up_state==absent)")
    return out


def restrict_to_atomic_note_paths(
    candidates: list[Candidate], profile: dict
) -> list[Candidate]:
    """Strict pre-filter: keep only candidates whose path lies under atomic-note.

    Emits a stderr WARN when candidates fall outside the allowed prefixes
    and continues with only the in-scope intersection (no abort here — the
    caller checks `len(candidates) == 0` after pre-filter for the
    `zero-candidates` abort).
    """
    allowed = _atomic_note_paths(profile)
    if not allowed:
        # Nothing to constrain against → pass through unchanged.
        return list(candidates)

    in_scope: list[Candidate] = []
    out_of_scope: list[Candidate] = []
    for c in candidates:
        if any(c.path.startswith(prefix) for prefix in allowed):
            in_scope.append(c)
        else:
            out_of_scope.append(c)

    if out_of_scope:
        _log(
            f"WARN: {len(out_of_scope)} candidate(s) outside atomic-note paths — "
            f"intersected to {len(in_scope)} in-scope candidate(s)"
        )

    return in_scope


def phase1_select_candidates(
    mode: str,
    trigger_arg: str,
    profile: dict,
    cache: dict,
    kado_client,
    config,
    vault_cfg: dict | None = None,
) -> tuple[list[Candidate], str | None]:
    """Run mode handler → pre-filter → folder-home filter → cap/zero checks.

    The folder-home filter drops candidates inside the folder of a MOC named
    like that folder (lib.folder_homes); ``vault_cfg`` supplies the atomic-note
    root, the profile's base path is the fallback.

    Returns
    -------
    (candidates, abort_reason)
        On success: (list of in-scope Candidates, None).
        On `zero-candidates` or `candidate-cap-exceeded`: ([], abort_reason).
    """
    if mode == "tag":
        raw = _handle_tag(trigger_arg, kado_client)
    elif mode == "folder":
        raw = _handle_folder(trigger_arg, kado_client)
    elif mode == "class":
        raw = _handle_class(trigger_arg, profile, kado_client)
    elif mode in ("title", "free-text"):
        raw = _handle_title_or_freetext(trigger_arg, cache)
    elif mode == "scan":
        raw = _handle_scan(cache)
    else:  # pragma: no cover — route_input only emits the six modes above.
        raise ValueError(f"phase1: unknown mode {mode!r}")

    _log(f"phase1: {len(raw)} raw candidate(s) before pre-filter")
    filtered = restrict_to_atomic_note_paths(raw, profile)
    _log(f"phase1: {len(filtered)} candidate(s) after atomic-note pre-filter")

    homes = folder_homes((cache or {}).get("map_notes") or [], atomic_roots(vault_cfg, profile))
    filtered, dropped = drop_home_members(filtered, homes)
    if dropped:
        per_home = ", ".join(f"{label}: {n}" for label, n in dropped.most_common())
        _log(f"phase1: dropped {sum(dropped.values())} candidate(s) a folder-home MOC holds ({per_home})")

    if len(filtered) == 0:
        return ([], "zero-candidates")

    cap = getattr(config, "candidate_cap", 500)
    if len(filtered) > cap:
        _log(f"phase1: candidate-cap-exceeded ({len(filtered)} > {cap})")
        return ([], "candidate-cap-exceeded")

    return (filtered, None)


# ──────────────────────────────────────────────────────────────────────────────
# Cache-empty pre-check (SDD §Pseudocode line 851 — fires BEFORE Phase 1)
# ──────────────────────────────────────────────────────────────────────────────


def validate_cache_loaded(cache: dict | None) -> str | None:
    """Return `"cache-empty"` when the discovery cache is unusable, else None.

    NOTE (spec 021 T2.1): main() no longer calls this — cache loading + the
    cache-empty determination now live in lib/moc_cache_loader.load_moc_cache
    (which mirrors this contract: a fresh cache with no kind==moc map_notes →
    "cache-empty"). Retained as the documented, separately-tested predicate.

    A cache is "loaded" when it carries a non-empty `map_notes` list. Any of
    the three failure modes — file missing (cache=None from a guarded loader),
    file present but `map_notes` key absent, file present but `map_notes: []` —
    short-circuits the rest of the pipeline. Per SDD §Error Handling this
    yields `abort_reason="cache-empty"` and a user-facing message asking the
    user to run `/explore-vault` first.

    The pre-check is separable so `main()` can fire it before mode routing /
    Phase 1, matching the spec's pseudocode (`1. VALIDATE → cache exists →
    else abort cache-empty`). Tests exercise it directly without spinning up
    the full pipeline.
    """
    if cache is None:
        return "cache-empty"
    if not isinstance(cache, dict):
        return "cache-empty"
    map_notes = cache.get("map_notes")
    if not map_notes:  # None, missing, or [] all collapse to "no usable cache"
        return "cache-empty"
    return None
