#!/usr/bin/env python3
# version: 0.7.1
"""moc-discovery.py — Discover MOC candidates and emit a DiscoveryReport.

Backs the `/moc-propose` skill (F-43, spec 013-moc-creation-skill). Accepts a
mutually-exclusive scope flag (`--tag`, `--folder`, `--class`, `--title`), an
optional free-text positional, or no args (whole-vault density scan), and walks
through the six discovery phases described in the SDD §Pseudocode (lines
845-895):

    Phase 1   — Candidate selection (mode handlers + pre-filter + caps)
    Phase 2   — Topic extraction (cache lookup + LLM cache-miss batching)
    Phase 3   — Cluster detection (thin wrapper around lib.topic_clusters)
    Phase 4   — Title generation (per-profile suffix rules + mode override)
    Phase 5   — Parent resolution (classification keyword overlap, top-3)
    Phase 6   — Duplicate detection (Jaccard ≥ 0.80) + squelch read-only lookup
    Phase 6.5 — Existing-up:: validation per candidate (absent/valid/broken)

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
import hashlib
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))

# Available for downstream phases (filename slug derivation in T2.6+ duplicate
# detection and T3.x render). Imported here per F-43 plan T2.5 to centralize
# the slugify SSoT (lib/slugify.py) — DiscoveryReport in T2.5 emits cluster.title
# only, so this is wired ahead of use.
from lib.slugify import slugify  # noqa: E402, F401


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
# Phase 4 — Title generation (per-profile suffix + mode override)
# ──────────────────────────────────────────────────────────────────────────────


# Profile name → MOC-title suffix appended after the topic. Empty string =
# plain title (LYT-style). Both profiles use a hardcoded suffix for now;
# tier-3/lyt-moc/new-moc-proposal.md §7 documents a future "(MOC)" form
# stored on the profile, but per the spec the canonical TopicTitle for the
# proposed-MOC pipeline is the plain "<Topic> MOC" / "<Topic>" pair.
_PROFILE_TITLE_SUFFIX: dict[str, str] = {
    "miyo": " MOC",
    "lyt": "",
}


def _topic_title(cluster: dict) -> str:
    """Title-case a cluster's normalised topic into a TopicTitle.

    Phase 3's reducer normalises topics (lowercase, plural-fold) and emits the
    cluster keyed off the normalised form. For display we Title-Case it —
    "shell" → "Shell". Multi-word topics have their internal whitespace
    preserved ("knowledge management" → "Knowledge Management").
    """
    topic_raw = (cluster.get("topic") or "").strip()
    if not topic_raw:
        return ""
    # `str.title()` is good enough here: cluster topics are short
    # noun-phrases produced by Phase 2's topic extractor and Phase 3's
    # normalisation already lower-cased them.
    return topic_raw.title()


def phase4_title(
    cluster: dict,
    profile: dict,
    mode: str,
    trigger_arg: str,
) -> str:
    """Per-cluster title generation, profile- and mode-aware.

    Args:
        cluster: A Phase-3 `Cluster` dict (`{topic, items, parent, tags}`).
        profile: The active profile dict (post-`yaml.safe_load`). Only the
            top-level `name` field is consulted — title-suffix policy is keyed
            off the canonical profile name (`"MiYo"` / `"LYT (...)"`).
        mode: The /moc-propose run mode (`tag` / `folder` / `class` / `title`
            / `free-text` / `scan`).
        trigger_arg: The mode's argument; used verbatim when `mode == "title"`.

    Returns:
        The proposed MOC title string.

    Behaviour:
      - `mode == "title"` → user input wins regardless of profile.
      - Otherwise: TitleCase(cluster.topic) + profile suffix.

    Pure: input dicts are not mutated.
    """
    # User-provided title — verbatim, untouched (PRD AC-2.4).
    if mode == "title":
        return trigger_arg

    topic_title = _topic_title(cluster)
    profile_name = (profile.get("name") or "").strip()
    # Resolve to lowercase short-name key. miyo.yaml → "MiYo"; lyt.yaml →
    # "LYT (Linking Your Thinking)". The first whitespace-token, lowered,
    # collapses both to a stable lookup key.
    short = profile_name.split()[0].lower() if profile_name else "miyo"
    suffix = _PROFILE_TITLE_SUFFIX.get(short, "")
    return f"{topic_title}{suffix}"


# ──────────────────────────────────────────────────────────────────────────────
# Phase 5 — Parent resolution (classification keyword overlap)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ParentOption:
    """One offered parent for a Proposed MOC.

    Per SDD §Application Data Models line 547:
        parent_options_per_cluster: dict[cluster_id, list of {moc_stem,
                                                              confidence,
                                                              label}]
    """

    moc_stem: str
    confidence: float
    label: str


def _cluster_topic_keywords(cluster: dict) -> list[str]:
    """Extract the keyword bag a cluster will be scored against.

    Two shapes are supported:
      - Phase-3 default: only `cluster.topic` (single normalised string).
        Returns `[topic]`.
      - Future / explicit: `cluster.topic_keywords: list[str]` set upstream
        by callers carrying multi-keyword context.

    The result is lower-cased, whitespace-trimmed, and de-duplicated — same
    treatment the lib applies to candidates.
    """
    raw: list[str] = []
    if isinstance(cluster.get("topic_keywords"), list):
        raw.extend(str(t) for t in cluster["topic_keywords"] if t)
    if cluster.get("topic"):
        raw.append(str(cluster["topic"]))

    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        norm = t.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _category_keywords(cat: dict) -> list[str]:
    """Lower-cased, deduplicated keyword list from a profile category."""
    raw = cat.get("keywords") or []
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        norm = str(t).strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _format_parent_label(klass: str, name: str) -> str:
    """Human-readable label, e.g. `"Applied Sciences (Dewey 2600)"`."""
    return f"{name} (Dewey {klass})"


def _format_parent_stem(klass: str, name: str) -> str:
    """Canonical classification-MOC stem, e.g. `"2600 - Applied Sciences"`.

    Mirrors the existing convention seen across miyo vault MOCs and the
    tier-3 docs (e.g. `Atlas/200 Maps/2600 - Applied Sciences.md`).
    """
    return f"{klass} - {name}"


def phase5_resolve_parents(
    cluster: dict,
    profile: dict,
    cache: dict,
) -> list[ParentOption]:
    """Match cluster topics against profile classification → top-3 ParentOptions.

    Args:
        cluster: Phase-3 `Cluster` (or enriched with `topic_keywords`).
        profile: The active profile dict. Reads
            `profile.classification.categories` — a mapping
            `{NNNN: {name, keywords}}`.
        cache: The discovery cache. Reserved for future MOC-level matching
            (per SDD line 877 — `cache.moc_likes`); currently unused by the
            classification-only resolver.

    Returns:
        List of `ParentOption` sorted by `confidence` DESC, capped at 3
        entries. Categories with zero keyword overlap are excluded. An
        empty list signals "no confident parent" (the caller should fall
        back to top-level placement per SDD §Pseudocode line 877 +
        tier-3/lyt-moc/moc-matching.md §5).

    Pure: input dicts are not mutated.
    """
    del cache  # reserved for MOC-level matching in T2.6+

    classification = profile.get("classification") or {}
    categories = classification.get("categories") or {}
    if not categories:
        return []

    cluster_keywords = _cluster_topic_keywords(cluster)
    if not cluster_keywords:
        return []
    cluster_set = set(cluster_keywords)

    scored: list[ParentOption] = []
    for klass_key, cat in categories.items():
        if not isinstance(cat, dict):
            continue
        klass = str(klass_key)
        name = (cat.get("name") or "").strip()
        cat_keywords = _category_keywords(cat)
        if not cat_keywords:
            continue
        cat_set = set(cat_keywords)
        overlap = cluster_set & cat_set
        if not overlap:
            continue
        # Overlap-ratio score, denominator = max(len(cluster_keywords), 1)
        # to prevent div-by-zero on degenerate empty input (already
        # short-circuited above, but kept defensive).
        confidence = len(overlap) / max(len(cluster_keywords), 1)
        scored.append(
            ParentOption(
                moc_stem=_format_parent_stem(klass, name),
                confidence=round(confidence, 4),
                label=_format_parent_label(klass, name),
            )
        )

    # Sort descending by confidence; stable on ties (insertion order = profile
    # iteration order, which is YAML-key order — deterministic).
    scored.sort(key=lambda p: p.confidence, reverse=True)
    return scored[:3]


# ──────────────────────────────────────────────────────────────────────────────
# Phase 6 — Duplicate detection (Jaccard ≥ 0.80) + squelch read-only lookup
# ──────────────────────────────────────────────────────────────────────────────

# Jaccard threshold for duplicate detection (SDD §Implementation Examples /
# Example 3, line 704). A cluster whose topic-set has ≥ 0.80 set-similarity
# with any existing MOC's topic-set is treated as a duplicate and skipped.
JACCARD_DUP_THRESHOLD = 0.80


def _jaccard(a: set[str], b: set[str]) -> float:
    """Set-similarity score: ``len(a ∩ b) / len(a ∪ b)``.

    Returns 0.0 when either side is empty — an empty input cannot meaningfully
    overlap with anything, and the SDD's Example 3 explicitly skips empty
    `moc.topics` rather than letting them score 1.0 by accident.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster_topic_set(cluster: dict) -> set[str]:
    """Normalised topic bag for Jaccard comparison.

    Mirrors `_cluster_topic_keywords` (Phase 5) but returns a set: lowercased,
    whitespace-stripped, deduplicated. Honours both the explicit
    `topic_keywords` list AND the single-string `topic` field (Phase 3 default).
    """
    out: set[str] = set()
    if isinstance(cluster.get("topic_keywords"), list):
        for t in cluster["topic_keywords"]:
            if t:
                norm = str(t).strip().lower()
                if norm:
                    out.add(norm)
    topic = cluster.get("topic")
    if topic:
        norm = str(topic).strip().lower()
        if norm:
            out.add(norm)
    return out


def _moc_topic_set(map_note: dict) -> set[str]:
    """Lowercased topic-set for an existing MOC entry from `cache.map_notes`."""
    topics = map_note.get("topics") or []
    out: set[str] = set()
    for t in topics:
        if t:
            norm = str(t).strip().lower()
            if norm:
                out.add(norm)
    return out


def _candidate_stems(cluster: dict) -> list[str]:
    """Pull the cluster's per-candidate identifiers for signature stability.

    Phase 3's `Cluster` TypedDict carries `items: list[str]` — the
    `section_id`s used by the reducer. Where callers enrich the cluster with
    full Candidate dicts (forward-compat with T2.7), accept those too and
    fall back to ``stem`` / ``path``.
    """
    items = cluster.get("items") or []
    stems: list[str] = []
    for it in items:
        if isinstance(it, str):
            if it:
                stems.append(it)
        elif isinstance(it, dict):
            stem = it.get("stem") or it.get("path") or ""
            if stem:
                stems.append(stem)
    return stems


def _compute_topic_signature(cluster: dict) -> str:
    """Stable hash for squelch keying — SDD §Implementation Examples / Example 2.

    Signature shape:

        sha1( "|".join(sorted(lower(topic_keywords)))
              + "::"
              + "|".join(sorted(candidate_stems)[:5]) ).hexdigest()[:16]

    Truncating candidate_stems at 5 keeps the signature stable across small
    candidate-set drift (one note added/removed across runs); truncating the
    sha1 hex digest at 16 chars is fine for the ~100s of entries the squelch
    registry will ever hold.
    """
    topics = sorted(_cluster_topic_set(cluster))
    stems = sorted(_candidate_stems(cluster))[:5]
    payload = "|".join(topics) + "::" + "|".join(stems)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _normalise_title(title: str) -> str:
    """Case-insensitive title comparator — strip + lower."""
    return (title or "").strip().lower()


def _find_exact_title_match(
    cluster_title: str, map_notes: list[dict]
) -> str | None:
    """Return the matching MOC's title (or stem) on a case-insensitive title hit."""
    needle = _normalise_title(cluster_title)
    if not needle:
        return None
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        existing_title = _normalise_title(entry.get("title") or "")
        if existing_title and existing_title == needle:
            # Prefer the human-readable title for the report; fall back to
            # path stem so the agent always has something to surface.
            return (
                str(entry.get("title")
                    or _stem_from_path(entry.get("path") or ""))
            )
    return None


def _find_jaccard_match(
    cluster_topics: set[str], map_notes: list[dict]
) -> tuple[str | None, float]:
    """Scan map_notes for the first MOC whose topics overlap ≥ 0.80.

    Returns (existing_moc_label, jaccard) — `(None, 0.0)` when no MOC clears
    the threshold. Stops on the first hit so the report names a single
    "winning" duplicate (matches SDD Example 3's early-return).
    """
    if not cluster_topics:
        return (None, 0.0)
    for entry in map_notes or []:
        if not isinstance(entry, dict):
            continue
        moc_topics = _moc_topic_set(entry)
        if not moc_topics:
            continue
        score = _jaccard(cluster_topics, moc_topics)
        if score >= JACCARD_DUP_THRESHOLD:
            label = (
                str(entry.get("title")
                    or _stem_from_path(entry.get("path") or ""))
            )
            return (label, score)
    return (None, 0.0)


def phase6_dedupe(
    clusters: list[dict],
    cache: dict,
    squelch_registry: dict,
    config,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Filter near-duplicate clusters and consult the squelch registry.

    Three skip checks run in order, each short-circuiting before the next:

      1. **Exact-title match** — cluster's proposed title (case-insensitive)
         equals any `cache.map_notes[].title`. Reported as
         ``reason="exact-title"``.
      2. **Jaccard ≥ 0.80** — cluster's topic-set against each existing MOC's
         topic-set. Reported as ``reason="80-percent-overlap"``.
      3. **Active squelch** — topic signature (sha1 of normalised topic +
         sorted candidate stems) is present in `squelch_registry` with
         ``runs_remaining > 0``. Reported in the ``squelched`` list.

    Squelch is **read-only** in this phase. Decrement / persist / append on
    user rejection happens in Phase 5 wiring (T5.1, T5.2) — Phase 6 only
    consults `lib.squelch.is_active`.

    Args:
        clusters: Phase-3 (or Phase-4-enriched) `Cluster` dicts. Each carries
            ``topic`` (str) plus optional ``topic_keywords`` (list[str]),
            ``title`` (str — set by Phase 4), ``items`` (list[str]).
        cache: Discovery cache dict; Phase 6 reads ``map_notes`` only.
        squelch_registry: ``dict[str, SquelchEntry]`` from
            `lib.squelch.load_registry`. Empty dict = no entries active.
        config: Reserved for future tuning (e.g. configurable threshold).
            Not read in this phase — accepting it keeps the signature stable
            for downstream tasks.

    Returns:
        ``(kept_clusters, duplicates_skipped, squelched)`` — matching the
        DiscoveryReport shape (SDD lines 548-549).

        - ``kept_clusters``: subset of `clusters` (identity-preserved) that
          passed all three checks.
        - ``duplicates_skipped``: list of
          ``{cluster_id, reason, existing_moc}`` dicts.
        - ``squelched``: list of ``{cluster_id, runs_remaining}`` dicts.

    Pure: input lists / dicts are not mutated. The squelch registry is
    never decremented or rewritten here.
    """
    del config  # reserved — Phase 6 reads no config fields today.

    map_notes: list[dict] = list(cache.get("map_notes") or [])

    kept: list[dict] = []
    duplicates_skipped: list[dict] = []
    squelched: list[dict] = []

    # Local import keeps the lib dependency colocated with its only caller in
    # this module — same pattern as `phase3_cluster`.
    from lib.squelch import is_active as _squelch_is_active

    for idx, cluster in enumerate(clusters or [], start=1):
        cluster_id = f"MOC{idx:02d}"

        # ── 1. Exact-title match ────────────────────────────────────────────
        existing = _find_exact_title_match(cluster.get("title") or "", map_notes)
        if existing is not None:
            duplicates_skipped.append({
                "cluster_id": cluster_id,
                "reason": "exact-title",
                "existing_moc": existing,
            })
            _log(
                f"phase6: cluster {cluster_id!r} title={cluster.get('title')!r} "
                f"matches existing MOC {existing!r} — skipping (exact-title)"
            )
            continue

        # ── 2. Jaccard overlap ≥ 0.80 ──────────────────────────────────────
        cluster_topics = _cluster_topic_set(cluster)
        match_label, score = _find_jaccard_match(cluster_topics, map_notes)
        if match_label is not None:
            duplicates_skipped.append({
                "cluster_id": cluster_id,
                "reason": "80-percent-overlap",
                "existing_moc": match_label,
            })
            _log(
                f"phase6: cluster {cluster_id!r} topic-set overlaps "
                f"{match_label!r} (jaccard={score:.2f}) — skipping"
            )
            continue

        # ── 3. Squelch lookup (read-only) ──────────────────────────────────
        signature = _compute_topic_signature(cluster)
        if _squelch_is_active(squelch_registry or {}, signature):
            entry = (squelch_registry or {}).get(signature)
            runs_remaining = entry.runs_remaining if entry is not None else 0
            squelched.append({
                "cluster_id": cluster_id,
                "runs_remaining": runs_remaining,
            })
            _log(
                f"phase6: cluster {cluster_id!r} signature={signature!r} is "
                f"squelched (runs_remaining={runs_remaining}) — skipping"
            )
            continue

        kept.append(cluster)

    _log(
        f"phase6: kept={len(kept)} duplicates={len(duplicates_skipped)} "
        f"squelched={len(squelched)}"
    )

    return (kept, duplicates_skipped, squelched)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 6.5 — Existing-`up::` validation per candidate
# ──────────────────────────────────────────────────────────────────────────────

# Match a single ``up::`` relationship line whose target is a wikilink. The
# anchor is a line-start (`(?m)^`) optionally preceded by whitespace; the
# target captured group strips the surrounding `[[` / `]]`. Multi-line bodies
# are scanned with `re.MULTILINE` so each `up::` line is a candidate match —
# Phase 6.5 then picks the first hit and warns on multi-hits.
_UP_MARKER_RE = re.compile(r"^\s*up::\s*\[\[(.+?)\]\]", re.MULTILINE)


def _extract_first_up_marker(content: str) -> str | None:
    """Return the first ``up:: [[Target]]`` target, or None when absent.

    Matches multi-line bodies — leading whitespace is allowed, the marker
    must start its own line, and the wikilink target is returned without
    the surrounding `[[` / `]]`. Multiple `up::` lines on the same note
    are the caller's concern: this helper deliberately surfaces only the
    first match so callers can decide whether to warn.

    A note body without any `up::` line, or with `up::` followed by a
    non-wikilink target, returns None — Rule 4.1 / 4.4 then applies and
    the new MOC becomes the child's `up::` regardless of override.
    """
    if not content:
        return None
    match = _UP_MARKER_RE.search(content)
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def _moc_stems_from_cache(cache: dict) -> set[str]:
    """Build a stem-set of every MOC indexed in `cache.map_notes`.

    Phase 6.5 consults this set to decide whether an extracted `up::`
    target is "valid" (target stem present in cache) or "broken"
    (target stem absent). Path is reduced to its basename without
    `.md` to match the wikilink-target shape (which carries the stem,
    not the full path).
    """
    stems: set[str] = set()
    for entry in cache.get("map_notes") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if path:
            stems.add(_stem_from_path(path))
        # Honour explicit titles too — a wikilink target may use the
        # human-readable title rather than the file stem when they differ.
        title = (entry.get("title") or "").strip()
        if title:
            stems.add(title)
    return stems


def phase65_validate_existing_up(
    clusters: list[dict],
    candidates: list[Candidate],
    kado_client,
    cache: dict,
) -> list[dict]:
    """Decorate each cluster's children with their existing-`up::` state.

    For every child stem in ``cluster.items``, read the candidate's note
    body via Kado, extract the first `up::` marker, and classify it
    against `cache.map_notes`:

      - No `up::` line                 → state="absent",  target=None
      - `up:: [[X]]` and X in cache    → state="valid",   target="X"
      - `up:: [[X]]` and X NOT in cache → state="broken",  target="X"

    Multiple `up::` lines on the same child surface as a stderr WARN —
    Phase 6.5 keeps the first match and downstream Rule 4.2 / 4.5 logic
    operates on it. Reading from Kado is the only side-effect.

    .. note::
        The plan signature is documented as ``(clusters, kado_client)``;
        the implementation accepts ``candidates`` and ``cache`` too because
        (a) Phase-3 clusters carry stems but not paths, so we need the
        upstream candidates list to resolve stem → path for Kado reads,
        and (b) cache.map_notes is the authoritative MOC index used to
        classify `valid` vs. `broken` targets without an extra Kado round
        trip per candidate. Documented as a deviation in plan/phase-2.md
        T2.7.

    Args:
        clusters: Phase-6-kept clusters (`{topic, items, parent, tags,
            ...}`). Each cluster's `items` is a list of candidate stems.
        candidates: The Phase-1/2 candidate list, used to resolve
            stem → path. Stems missing from the lookup map are skipped
            (defensive — should never happen in normal flow).
        kado_client: Anything exposing ``read_note(path) -> {"content": str, ...}``.
        cache: Discovery cache dict; Phase 6.5 reads `map_notes` only.

    Returns:
        The input clusters, each augmented in-place with an
        ``existing_up: list[{stem, state, target}]`` field. Order follows
        ``cluster.items`` for deterministic downstream rendering.

    Side effects:
        - One `kado_client.read_note` call per candidate.
        - Stderr WARN per multi-`up::` body.
        - Stderr WARN per failed Kado read (treated as absent, loop continues).
    """
    stem_to_path: dict[str, str] = {c.stem: c.path for c in candidates if c.stem}
    moc_stems = _moc_stems_from_cache(cache)

    multi_up_count = 0

    for cluster in clusters or []:
        rows: list[dict] = []
        for item in cluster.get("items") or []:
            # Cluster items can be plain stems (Phase-3 default) OR enriched
            # dicts (forward-compat with downstream tasks). Normalise here.
            if isinstance(item, str):
                stem = item
            elif isinstance(item, dict):
                stem = item.get("stem") or item.get("path") or ""
            else:
                continue
            if not stem:
                continue

            path = stem_to_path.get(stem)
            if not path:
                # Defensive: cluster references a stem that never appeared
                # in candidates — skip rather than guess at a path.
                _log(
                    f"phase6.5: WARN: cluster item {stem!r} not in candidate "
                    f"list; skipping existing-up:: validation for this child"
                )
                continue

            # Guard against Kado read failures (note deleted between
            # candidate collection and Phase 6.5, network error, permission
            # denied, …). A single failing read must NOT abort decoration of
            # the remaining candidates — we treat the unreadable child as
            # `state="absent"` so downstream rendering keeps moving.
            try:
                note = kado_client.read_note(path)
            except Exception as exc:  # noqa: BLE001 — defensive boundary
                _log(
                    f"phase6.5: WARN: kado read_note({path!r}) failed "
                    f"({type(exc).__name__}: {exc}); treating as absent"
                )
                rows.append({"stem": stem, "state": "absent", "target": None})
                continue

            content = note.get("content", "") if isinstance(note, dict) else ""

            # Multi-`up::` detection: count regex hits before extracting
            # so the warning fires per-note, not per-cluster.
            all_targets = _UP_MARKER_RE.findall(content)
            if len(all_targets) > 1:
                multi_up_count += 1
                _log(
                    f"WARN: multiple up:: markers in {path}; using first "
                    f"({all_targets[0]!r}, dropped {len(all_targets) - 1} more)"
                )

            target = _extract_first_up_marker(content)
            if target is None:
                state: str = "absent"
            elif target in moc_stems:
                state = "valid"
            else:
                state = "broken"

            rows.append({"stem": stem, "state": state, "target": target})

        cluster["existing_up"] = rows

    _log(
        f"phase6.5: decorated {len(clusters or [])} cluster(s); "
        f"multi-up:: warnings={multi_up_count}"
    )
    return list(clusters or [])


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
