#!/usr/bin/env python3
# version: 0.4.0
"""moc-discovery.py — Discover MOC candidates and emit a DiscoveryReport.

Backs the `/moc-propose` skill (F-43, spec 013-moc-creation-skill). Accepts a
mutually-exclusive scope flag (`--tag`, `--folder`, `--class`, `--title`), an
optional free-text positional, or no args (whole-vault density scan), and walks
through the six discovery phases described in the SDD §Pseudocode (lines
845-895):

    Phase 1 — Candidate selection (mode handlers + pre-filter + caps)
    Phase 2 — Topic extraction (cache lookup + LLM cache-miss batching)
    Phase 3 — Cluster detection (thin wrapper around lib.topic_clusters)
    Phase 4 — Title generation (T2.5 — pending)
    Phase 5 — Parent resolution (T2.5 — pending)
    Phase 6 — Duplicate detection (T2.6 — pending)
    Phase 6.5 — Existing-up:: validation (T2.7 — pending)

The full algorithm lands in T2.2-T2.7. T2.1 ships the CLI surface, mode
routing (`route_input`), profile resolution, and the `--dry-run` JSON path so
downstream tasks have a stable scaffold to fill in.

Usage:
    python3 moc-discovery.py [--tag X | --folder X | --class X | --title X] [free-text]
                             [--config PATH] [--profile NAME] [--cache PATH]
                             [--dry-run] [--candidate-cap N]

Output:
    Stdout — DiscoveryReport JSON (see SDD §Application Data Models, lines 534-553).
    Stderr — progress logs, prefixed `[moc-discovery]`.

Exit codes (SDD §Error Handling):
    0 success
    1 partial-failure
    2 fatal (cache missing, profile unresolved)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))


# ──────────────────────────────────────────────────────────────────────────────
# Paths & defaults
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG_PATH = "config/vault-config.yaml"
DEFAULT_CACHE_PATH = "config/discovery-cache.yaml"
DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"

LOG_PREFIX = "[moc-discovery]"

# User-facing abort messages (SDD §Error Handling, lines 830-833). German strings
# match the user vault locale; cache-empty intentionally English because it
# instructs the user to run a Tomo command (`/explore-vault`).
ABORT_MESSAGES: dict[str, str] = {
    "cache-empty": (
        "MOC proposal requires vault cache. Please run /explore-vault first to "
        "populate discovery-cache.yaml."
    ),
    "zero-candidates": "Keine Notes zum Topic gefunden",
    "candidate-cap-exceeded": (
        "Mehr als die erlaubte Anzahl Kandidaten gefunden — Suchbereich einschränken"
    ),
    "cache-miss-cap-exceeded": (
        "Notes ohne Cache-Eintrag — bitte zuerst /explore-vault laufen lassen"
    ),
}

# Phase 2 LLM batching — fixed at 10 per SDD §Pseudocode line 864 (chunk(misses, 10)).
LLM_BATCH_SIZE = 10


def _log(msg: str) -> None:
    """Write a stderr progress line — matches sibling moc-tree-builder style."""
    print(f"{LOG_PREFIX} {msg}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# CLI parsing + mode routing
# ──────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser. Kept as a separate helper for testing."""
    parser = argparse.ArgumentParser(
        prog="moc-discovery",
        description=(
            "Discover MOC candidates and emit a DiscoveryReport JSON.\n\n"
            "Output: JSON to stdout. Progress and warnings: stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mutually-exclusive scope flags. `class` is reserved → dest="klass".
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--tag",
        metavar="PREFIX",
        help="Tag-prefix scan via kado-search byTag with glob `*`.",
    )
    scope.add_argument(
        "--folder",
        metavar="PATH",
        help="Recursive listDir, client-side .md filter.",
    )
    scope.add_argument(
        "--class",
        dest="klass",
        metavar="NNNN",
        help="Profile-aware classification subdirectory scan (e.g. 2600).",
    )
    scope.add_argument(
        "--title",
        metavar="TEXT",
        help="Title-seeded discovery; user input becomes the proposed MOC title.",
    )

    # Free-text positional — used when none of the scope flags match.
    parser.add_argument(
        "free_text",
        nargs="?",
        default=None,
        metavar="FREE_TEXT",
        help="Free-text topic match (default when no scope flag is given).",
    )

    parser.add_argument(
        "--config",
        metavar="PATH",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to vault-config.yaml (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help="Profile name override (default: read from vault-config.yaml).",
    )
    parser.add_argument(
        "--cache",
        metavar="PATH",
        default=DEFAULT_CACHE_PATH,
        help=f"Path to discovery-cache.yaml (default: {DEFAULT_CACHE_PATH}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit a minimal DiscoveryReport JSON and skip discovery phases.",
    )
    parser.add_argument(
        "--candidate-cap",
        type=int,
        metavar="N",
        default=None,
        help="Override candidate_cap (default: vault-config tomo.moc_proposal).",
    )

    return parser


def route_input(args: argparse.Namespace) -> tuple[str, str]:
    """Map parsed CLI args to (mode, trigger_arg).

    Precedence (PRD/AC-1.1-1.7):
      --tag X     → ("tag", X)
      --folder X  → ("folder", X)
      --class X   → ("class", X)
      --title X   → ("title", X)
      free-text X → ("free-text", X)        # AC-1.7: `foo:bar` stays free-text
      no args     → ("scan", "")            # AC-1.6: whole-vault density scan

    Each scope flag uses an explicit `is not None` check (not truthiness) so
    that an accidental empty string (`--tag ""`) raises ValueError instead of
    silently falling through to scan mode.
    """
    for attr, mode, label in (
        ("tag", "tag", "--tag"),
        ("folder", "folder", "--folder"),
        ("klass", "class", "--class"),
        ("title", "title", "--title"),
        ("free_text", "free-text", "free-text positional"),
    ):
        value = getattr(args, attr, None)
        if value is not None:
            if value == "":
                raise ValueError(f"{label} requires a non-empty value")
            return (mode, value)
    return ("scan", "")


# ──────────────────────────────────────────────────────────────────────────────
# Profile resolution
# ──────────────────────────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file → dict; empty / missing → {}."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def resolve_profile(
    config_path: Path,
    profile_override: str | None,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> str:
    """Resolve the active profile name; raise FileNotFoundError if it's missing.

    Order:
      1. CLI `--profile` override (if given).
      2. `vault-config.yaml::profile` (default `"miyo"` per shared-ctx-builder).
    """
    if profile_override:
        name = profile_override
    else:
        cfg = _load_yaml(config_path)
        name = str(cfg.get("profile") or "miyo")

    profile_path = profiles_dir / f"{name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(
            f"profile YAML not found: {profile_path} (resolved name={name!r})"
        )
    return name


# ──────────────────────────────────────────────────────────────────────────────
# DiscoveryReport scaffolding
# ──────────────────────────────────────────────────────────────────────────────


def empty_report(mode: str, trigger_arg: str, profile: str) -> dict[str, Any]:
    """Build a minimal DiscoveryReport with all phase-derived fields zeroed.

    Schema mirrors SDD §Application Data Models lines 534-553. Filled-in
    versions land in T2.2-T2.7 as each phase produces real data.
    """
    return {
        "schema_version": "1",
        "run_id": uuid.uuid4().hex,
        "mode": mode,
        "trigger_arg": trigger_arg,
        "profile": profile,
        "candidates_total": 0,
        "candidates_after_prefilter": 0,
        "candidates_capped": False,
        "candidates": [],
        "topic_clusters": [],
        "parent_options_per_cluster": {},
        "duplicates_skipped": [],
        "squelched": [],
        "abort_reason": None,
        "abort_message": None,
        "extracted_via_llm_count": 0,
        "cache_miss_batches_used": 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Candidate selection
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Candidate:
    """One atomic-note candidate considered for a Proposed MOC.

    Phase 1 only fills `stem` and `path`. Subsequent phases enrich each
    candidate in-place with `topics`, `existing_up`, `classification`, and
    `level`. Keeping the dataclass loose (mutable, default-empty) is
    deliberate — phase boundaries hand a list of these between handlers
    without copy-on-write.
    """

    stem: str
    path: str
    topics: list[str] = field(default_factory=list)
    existing_up: str | None = None
    classification: str | None = None
    level: int = 0


def _stem_from_path(path: str) -> str:
    """`Atlas/202 Notes/2611 Code Snippets/zsh.md` → `zsh`."""
    name = os.path.basename(path)
    if name.endswith(".md"):
        name = name[:-3]
    return name


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


def _handle_scan(profile: dict, kado_client) -> list[Candidate]:
    """Scan mode: listDir on each atomic-note subdirectory (whole-vault density)."""
    cd = (profile.get("concept_defaults") or {}).get("atomic_note") or {}
    paths = [sd["path"] for sd in (cd.get("subdirectories") or []) if sd.get("path")]
    if not paths and cd.get("base_path"):
        paths = [cd["base_path"]]
    _log(f"phase1: scan over {len(paths)} atomic-note path(s)")
    seen: set[str] = set()
    out: list[Candidate] = []
    for p in paths:
        items = kado_client.list_dir(p, depth=10)
        for item in items:
            if _is_md_file(item):
                ipath = item.get("path", "") or ""
                if ipath and ipath not in seen:
                    seen.add(ipath)
                    out.append(_candidate_from_path(ipath))
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
) -> tuple[list[Candidate], str | None]:
    """Run mode handler → pre-filter → cap/zero checks.

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
        raw = _handle_scan(profile, kado_client)
    else:  # pragma: no cover — route_input only emits the six modes above.
        raise ValueError(f"phase1: unknown mode {mode!r}")

    _log(f"phase1: {len(raw)} raw candidate(s) before pre-filter")
    filtered = restrict_to_atomic_note_paths(raw, profile)
    _log(f"phase1: {len(filtered)} candidate(s) after atomic-note pre-filter")

    if len(filtered) == 0:
        return ([], "zero-candidates")

    cap = getattr(config, "candidate_cap", 200)
    if len(filtered) > cap:
        _log(f"phase1: candidate-cap-exceeded ({len(filtered)} > {cap})")
        return ([], "candidate-cap-exceeded")

    return (filtered, None)


# ──────────────────────────────────────────────────────────────────────────────
# Cache-empty pre-check (SDD §Pseudocode line 851 — fires BEFORE Phase 1)
# ──────────────────────────────────────────────────────────────────────────────


def validate_cache_loaded(cache: dict | None) -> str | None:
    """Return `"cache-empty"` when the discovery cache is unusable, else None.

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


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Topic extraction (cache lookup + bounded LLM batching)
# ──────────────────────────────────────────────────────────────────────────────


class LLMClient(Protocol):
    """Minimal LLM-batch-extract surface consumed by Phase 2.

    Implementations take a list of cache-miss `Candidate`s and return one
    dict per candidate, shaped `{"path": str, "topics": list[str]}`. Phase 2
    splits misses into chunks of `LLM_BATCH_SIZE` (10) and fans out one call
    per chunk; the real production client lives outside T2.3 and gets wired
    in `main()` later (T2.8).
    """

    def batch_extract(self, batch: list["Candidate"]) -> list[dict]: ...  # pragma: no cover


def _build_topics_index(cache: dict) -> dict[str, list[str]]:
    """Index `cache.map_notes` by path → topics for O(1) hit lookup."""
    out: dict[str, list[str]] = {}
    for entry in cache.get("map_notes") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        topics = [str(t) for t in (entry.get("topics") or []) if t]
        # Last-writer-wins on duplicate paths — cache-builder dedupes these
        # already, this is a defensive belt-and-braces.
        out[path] = topics
    return out


def _batch_llm_extract(
    candidates: list[Candidate],
    llm_client: LLMClient,
    batch_size: int = LLM_BATCH_SIZE,
) -> list[Candidate]:
    """Chunk cache-miss candidates and call the LLM once per chunk.

    Returns the input candidates with their `topics` field populated from the
    LLM response. Order is preserved within and across chunks so callers can
    re-merge with cache hits without losing per-mode ordering.

    Pre-condition: caller has already verified `ceil(len(candidates)/batch_size)
    <= cache_miss_max_batches`. This helper does NOT enforce the cap — that
    decision is the caller's so the abort path can short-circuit before any
    LLM contact.
    """
    if not candidates:
        return []

    # Index input candidates by path so we can apply the LLM response onto
    # the same instances (preserving any existing fields downstream phases set).
    by_path: dict[str, Candidate] = {c.path: c for c in candidates}

    for start in range(0, len(candidates), batch_size):
        chunk = candidates[start : start + batch_size]
        response = llm_client.batch_extract(chunk)
        for entry in response or []:
            path = entry.get("path")
            topics = entry.get("topics") or []
            if not path or path not in by_path:
                continue
            by_path[path].topics = [str(t) for t in topics if t]

    return candidates


def phase2_extract_topics(
    candidates: list[Candidate],
    cache: dict,
    config,
    llm_client: LLMClient | None,
) -> tuple[list[Candidate], str | None]:
    """Resolve topics per candidate via cache-first lookup + bounded LLM fallback.

    Returns
    -------
    (candidates_with_topics, abort_reason)
        On success: (merged hits + LLM-extracted misses, None).
        On `cache-miss-cap-exceeded`: ([], "cache-miss-cap-exceeded").

    Algorithm (SDD §Pseudocode lines 861-867):
      hits   := [c for c in candidates if c in cache]
      misses := [c for c in candidates if c not in cache]
      batches := chunk(misses, 10)
      if len(batches) > config.cache_miss_max_batches → abort
      extracted := llm_batch_extract(batches)
      candidates_with_topics := merge(hits, extracted)
    """
    topics_by_path = _build_topics_index(cache)

    hits: list[Candidate] = []
    misses: list[Candidate] = []
    for c in candidates:
        cached = topics_by_path.get(c.path)
        if cached is not None:
            # Copy onto the candidate so downstream phases see populated topics.
            c.topics = list(cached)
            hits.append(c)
        else:
            misses.append(c)

    cap = getattr(config, "cache_miss_max_batches", 5)
    batches_needed = math.ceil(len(misses) / LLM_BATCH_SIZE) if misses else 0
    if batches_needed > cap:
        _log(
            f"phase2: cache-miss-cap-exceeded "
            f"(misses={len(misses)} → batches={batches_needed} > cap={cap})"
        )
        return ([], "cache-miss-cap-exceeded")

    _log(
        f"phase2: cache-hits={len(hits)} cache-misses={len(misses)} "
        f"batches={batches_needed}"
    )

    if misses:
        if llm_client is None:
            # Caller has not wired an LLM client yet (T2.8 production wiring).
            # Surface clearly rather than silently emitting empty topics.
            raise RuntimeError(
                "phase2_extract_topics: llm_client is required when there are "
                "cache misses. Pass a real LLMClient or ensure the cache covers "
                "every Phase 1 candidate."
            )
        _batch_llm_extract(misses, llm_client)

    # Merge preserves input order: a candidate's position in the output
    # matches its position in the input list. Each candidate appears exactly
    # once because hits and misses are disjoint by construction.
    return (list(candidates), None)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Cluster detection (thin wrapper around lib.topic_clusters)
# ──────────────────────────────────────────────────────────────────────────────


def phase3_cluster(
    candidates_with_topics: list[Candidate], config
) -> list[dict]:
    """Group candidates by normalised topic — thin wrapper around T1.5.

    Each candidate from Phase 2 carries `topics: list[str]` (one or more).
    The reducer's existing algorithm operates on one `ClusterCandidate` per
    `(candidate, topic)` pair, so a candidate that carries `[shell, terminal]`
    contributes to BOTH the `shell` cluster and the `terminal` cluster — the
    "shared note across clusters" case the SDD calls out for `/moc-propose`.

    Per SDD §Pseudocode lines 869-871:
        clusters := topic_clusters(candidates_with_topics, threshold=config.min_notes)
        if len(clusters) == 0 → return empty report (NOT an abort; the user-facing
                                "no significant clusters" message is surfaced by
                                the outer pipeline).

    Phase 3 itself never aborts — empty output is a valid normal outcome.
    Aborts in this pipeline live in Phase 1 (zero-candidates,
    candidate-cap-exceeded) and Phase 2 (cache-miss-cap-exceeded).

    Args:
        candidates_with_topics: Phase-2-enriched Candidates with `topics`
            populated (cache hits + LLM-extracted misses, merged in input order).
        config: Anything exposing `min_notes: int` — typically a
            `MocProposalConfig` from `shared-ctx-builder.load_moc_proposal_config`.

    Returns:
        `list[Cluster]` from `lib.topic_clusters.build_topic_clusters` (a list
        of `{topic, items, parent, tags}` TypedDicts). `items` carries the
        contributing candidate stems (preserved as `section_id` upstream).
        Pure: input is not mutated; a fresh list is returned each call.
    """
    # Local import keeps the lib dependency colocated with its only consumer
    # in this module (mirrors the other helpers' file-local-import pattern).
    from lib.topic_clusters import ClusterCandidate, build_topic_clusters

    # Explode one ClusterCandidate per (candidate, topic) pair. Candidates
    # without topics are skipped — `build_topic_clusters` would drop them
    # anyway via its empty-topic guard, but skipping here is explicit and
    # avoids feeding the lib pointless rows.
    items: list[ClusterCandidate] = []
    for c in candidates_with_topics:
        for topic in c.topics or []:
            items.append(
                ClusterCandidate(
                    section_id=c.stem,
                    topic=topic,
                    # No parent at Phase 3 — parent_options land in Phase 5.
                    parent="",
                    # Candidate carries no leaf tags in Phase 3 yet; tag-fold
                    # in `_compute_moc_tags` is a no-op on empty input.
                    tags=[],
                )
            )

    threshold = getattr(config, "min_notes", 3)
    return build_topic_clusters(items, threshold=threshold)


# ──────────────────────────────────────────────────────────────────────────────
# Discovery phases — stubs for T2.5-T2.7
# ──────────────────────────────────────────────────────────────────────────────


def phase4_generate_titles(*_args, **_kwargs):
    """Per-profile title generation (Dewey `(MOC)` suffix vs LYT plain)."""
    raise NotImplementedError("T2.5 — phase4_generate_titles pending")


def phase5_match_parents(*_args, **_kwargs):
    """Match topic keywords against profile.classification.categories."""
    raise NotImplementedError("T2.6 — phase5_match_parents pending")


def phase6_filter_duplicates_and_squelch(*_args, **_kwargs):
    """Drop near-duplicate clusters; honour the squelch registry."""
    raise NotImplementedError("T2.7 — phase6_filter_duplicates_and_squelch pending")


def phase6_5_apply_candidate_cap(*_args, **_kwargs):
    """Enforce the candidate_cap; set candidates_capped flag."""
    raise NotImplementedError("T2.7 — phase6_5_apply_candidate_cap pending")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def _emit_abort_report(
    mode: str, trigger_arg: str, profile_name: str, abort_reason: str
) -> int:
    """Write a DiscoveryReport with `abort_reason` set and return exit 0.

    Per SDD §Error Handling, all four `abort_reason` values are user-facing
    states (not fatal errors): the agent reads the JSON, surfaces the
    German/English message, and the user retries. Fatal exits are reserved
    for unresolved profiles and unreachable Kado.
    """
    report = empty_report(mode, trigger_arg, profile_name)
    report["abort_reason"] = abort_reason
    report["abort_message"] = ABORT_MESSAGES.get(abort_reason, abort_reason)
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Top-level orchestration. Returns exit code 0 / 1 / 2."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        mode, trigger_arg = route_input(args)
    except ValueError as exc:
        print(f"{LOG_PREFIX} FATAL: {exc}", file=sys.stderr)
        return 2
    _log(f"mode={mode} trigger_arg={trigger_arg!r}")

    config_path = Path(args.config)

    # Profile resolution — exit 2 fatal if unresolved (SDD line 834).
    try:
        profile_name = resolve_profile(config_path, args.profile)
    except FileNotFoundError as exc:
        print(f"{LOG_PREFIX} FATAL: {exc}", file=sys.stderr)
        return 2

    _log(f"profile={profile_name}")

    # Dry-run path: emit a minimal DiscoveryReport and exit. No Kado calls,
    # no cache check (the dry-run is the T2.1 scaffolding contract).
    if args.dry_run:
        _log("dry-run — emitting minimal DiscoveryReport, skipping discovery phases")
        report = empty_report(mode, trigger_arg, profile_name)
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Cache-empty pre-check (SDD §Pseudocode line 851 — fires BEFORE Phase 1).
    # Missing file → load_yaml returns {}; populated `map_notes: []` cache → also
    # empty. Both collapse to `cache-empty` so the agent can surface the same
    # "run /explore-vault" hint regardless of which failure mode fired.
    cache_path = Path(args.cache)
    cache = _load_yaml(cache_path) if cache_path.exists() else None
    cache_abort = validate_cache_loaded(cache)
    if cache_abort is not None:
        _log(f"cache-empty: cache_path={cache_path} → abort {cache_abort!r}")
        return _emit_abort_report(mode, trigger_arg, profile_name, cache_abort)

    # Full discovery flow lands in T2.5-T2.7. Until then, surface clearly.
    _log("ERROR: discovery phases not yet implemented (T2.5-T2.7)")
    raise NotImplementedError(
        "moc-discovery.py full pipeline pending — use --dry-run for T2.1 scaffolding"
    )


if __name__ == "__main__":
    sys.exit(main())
