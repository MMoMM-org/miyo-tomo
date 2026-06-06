#!/usr/bin/env python3
# version: 0.14.0
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
from lib.moc_cache_loader import load_moc_cache  # noqa: E402
from lib.orphan_link import emit_orphan_suggestions  # noqa: E402
from lib.slugify import slugify  # noqa: E402, F401
from lib.up_parse import parse_up_from_content  # noqa: E402
from lib.squelch import (  # noqa: E402
    decrement_all as _squelch_decrement_all,
    load_registry as _squelch_load_registry,
    save_registry_atomic as _squelch_save_registry_atomic,
)
from lib.topic_signature import (  # noqa: E402
    candidate_stems as _lib_candidate_stems,
    cluster_topic_set as _lib_cluster_topic_set,
    compute_topic_signature as _lib_compute_topic_signature,
)


# ──────────────────────────────────────────────────────────────────────────────
# Paths & defaults
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG_PATH = "config/vault-config.yaml"
# spec 021 T2.1: moc-discovery now reads the MOC-structure cache via
# lib/moc_cache_loader (TTL + rebuild-if-stale + entries[kind==moc]→map_notes
# shim), not discovery-cache.yaml directly. The loader rebuilds inline when the
# cache is stale/missing/corrupt (ADR-3).
DEFAULT_CACHE_PATH = "config/moc-structure-cache.yaml"
DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"
# ADR-8: squelch sidecar at tomo-instance/state/moc-squelch.json. Default
# resolves relative to TOMO_INSTANCE env var (Docker runtime) or cwd (tests /
# host dev runs). The `--squelch-state` flag overrides this default.
DEFAULT_SQUELCH_STATE_PATH = str(
    Path(os.environ.get("TOMO_INSTANCE", ".")) / "state" / "moc-squelch.json"
)

LOG_PREFIX = "[moc-discovery]"

# User-facing abort messages (SDD §Error Handling, lines 830-833). German strings
# match the user vault locale; cache-empty intentionally English because it
# instructs the user to run a Tomo command (`/explore-vault`).
ABORT_MESSAGES: dict[str, str] = {
    "cache-empty": (
        "MOC proposal requires vault cache. Please run /explore-vault first to "
        "populate discovery-cache.yaml."
    ),
    "zero-candidates": "No notes found for this topic.",
    "candidate-cap-exceeded": (
        "Too many candidates found — narrow the search scope."
    ),
    "cache-miss-cap-exceeded": (
        "Too many notes without cache entry — please run /explore-vault first."
    ),
    "cache-rebuild-failed": (
        "MOC structure cache could not be rebuilt (target unwritable or no MOCs "
        "found). Please run /explore-vault and check the vault configuration."
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
        help=f"Path to the MOC-structure cache (default: {DEFAULT_CACHE_PATH}). "
             "Loaded via moc_cache_loader (rebuild-if-stale + map_notes shim).",
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
        help="Override candidate_cap (default 500: vault-config tomo.moc_proposal).",
    )
    parser.add_argument(
        "--check-moc-uplinks",
        action="store_true",
        help="Audit MOC parentage only: run the orphan link-or-create pass over "
             "kind==moc entries (skip the clustering pipeline). Emits a "
             "check-moc-uplinks DiscoveryReport.",
    )
    parser.add_argument(
        "--squelch-state",
        metavar="PATH",
        default=DEFAULT_SQUELCH_STATE_PATH,
        help=(
            f"Path to moc-squelch.json sidecar (ADR-8). "
            f"Default: $TOMO_INSTANCE/state/moc-squelch.json "
            f"(currently resolves to {DEFAULT_SQUELCH_STATE_PATH})."
        ),
    )

    # T6.5: agent-side LLM split. `--emit-phase1` exits after Phase 1 writing
    # candidate paths + cache-resolved topics (null for cache misses) so the
    # moc-architect agent can extract missing topics LLM-side and feed them
    # back via `--phase1-input`. The two flags are mutually exclusive.
    phase1_io = parser.add_mutually_exclusive_group()
    phase1_io.add_argument(
        "--emit-phase1",
        metavar="PATH",
        default=None,
        help=(
            "Run Phase 1 only; write candidates JSON to PATH with topics from "
            "cache (null for misses); exit before Phase 2."
        ),
    )
    phase1_io.add_argument(
        "--phase1-input",
        metavar="PATH",
        default=None,
        help=(
            "Skip Phase 1; load candidates (with pre-populated topics) from "
            "PATH. Phase 2 short-circuits on candidates whose topics are "
            "already set — no LLMClient needed."
        ),
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
        "orphan_suggestions": [],
        "orphan_total": 0,
        "orphan_overflow": 0,
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
        raw = _handle_scan(cache)
    else:  # pragma: no cover — route_input only emits the six modes above.
        raise ValueError(f"phase1: unknown mode {mode!r}")

    _log(f"phase1: {len(raw)} raw candidate(s) before pre-filter")
    filtered = restrict_to_atomic_note_paths(raw, profile)
    _log(f"phase1: {len(filtered)} candidate(s) after atomic-note pre-filter")

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
    """Index cache entries by path → topics for O(1) hit lookup in Phase 2.

    Indexes two sources (last-writer-wins on duplicate paths — the cache-builder
    dedupes, this is a defensive belt-and-braces):

    1. `cache["entries"]` (kind==moc AND kind==note) — covers scan-mode candidates
       whose topics come from the cache entry rather than from an LLM call.
       Before T5.1 this was a miss for kind==note paths, forcing spurious LLM
       batching for every scan candidate.

    2. `cache["map_notes"]` (kind==moc shim, populated by apply_shim in the
       loader) — kept for backward compat with title/free-text mode, which
       constructs candidates from map_notes and needs its hits to resolve here.
    """
    out: dict[str, list[str]] = {}

    # Pass 1: all entries (moc + note) from the unified entries list.
    for entry in cache.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        topics = [str(t) for t in (entry.get("topics") or []) if t]
        out[path] = topics

    # Pass 2: map_notes shim — applies on top so MOC hits from the shim layer
    # are never shadowed by a stale entries pass.
    for entry in cache.get("map_notes") or []:
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        topics = [str(t) for t in (entry.get("topics") or []) if t]
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
        # T6.5: short-circuit on pre-populated topics (--phase1-input flow).
        # The moc-architect agent ran a topic-extract subagent between
        # --emit-phase1 and --phase1-input, so cache misses are already
        # resolved at the candidate level — no LLM call needed here.
        if c.topics:
            hits.append(c)
            continue
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
    "miyo": " (MOC)",
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
    short = profile_name.split()[0].lower() if profile_name else "miyo"
    suffix = _PROFILE_TITLE_SUFFIX.get(short, "")
    if suffix and topic_title.endswith(" MOC"):
        topic_title = topic_title[:-4]
    if topic_title.strip().upper() == "MOC":
        return topic_title
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

    Delegates to lib.topic_signature.cluster_topic_set — single implementation
    shared with squelch-persist (T5.2 factoring).
    """
    return _lib_cluster_topic_set(cluster)


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

    Delegates to lib.topic_signature.candidate_stems — single implementation
    shared with squelch-persist (T5.2 factoring).
    """
    return _lib_candidate_stems(cluster)


def _compute_topic_signature(cluster: dict) -> str:
    """Stable hash for squelch keying — SDD §Implementation Examples / Example 2.

    Delegates to lib.topic_signature.compute_topic_signature — single
    implementation shared with squelch-persist (T5.2 factoring).
    """
    return _lib_compute_topic_signature(cluster)


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

# Match a single inline ``up::`` relationship line whose target is a wikilink.
# T2.2: target RESOLUTION now goes through lib/up_parse.parse_up_from_content
# (dual-up: inline + frontmatter). This regex is retained ONLY to count inline
# markers for the multi-`up::` malformed-note warning — it no longer resolves
# the target. (Mirrors up_parse._INLINE_UP so the warning matches what up_parse
# would have picked as the inline candidate.)
_UP_MARKER_RE = re.compile(r"^[\s>\-]*up::\s*\[\[(.+?)\]\]", re.MULTILINE)


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

            # Multi-inline-`up::` detection: count inline marker hits before
            # resolving so the warning fires per-note, not per-cluster. (The
            # warning is inline-specific — a single frontmatter `up:` plus one
            # inline `up::` is the normal conflict case, resolved by inline-wins,
            # not a malformed multi-marker note.)
            inline_targets = _UP_MARKER_RE.findall(content)
            if len(inline_targets) > 1:
                multi_up_count += 1
                _log(
                    f"WARN: multiple up:: markers in {path}; using first "
                    f"({inline_targets[0]!r}, dropped {len(inline_targets) - 1} more)"
                )

            # T2.2 (C1/ADR-6): resolve the `up` relationship from the SAME
            # read_note content via the up_parse SSoT — recognises both inline
            # `up:: [[X]]` and frontmatter `up:` (inline wins on conflict),
            # splitting the frontmatter block locally with no extra Kado call.
            target = parse_up_from_content(content).target
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


def _load_moc_config(config_path: Path):
    """Lazy-load MocProposalConfig from shared-ctx-builder to avoid import cycle.

    The sys.modules registration is required because Python 3.14's dataclass
    machinery inspects the owning module's ``__dict__`` during class processing
    (same fix applied in test_moc_proposal_config.py).
    """
    import importlib.util as _ilu

    _name = "shared_ctx_builder"
    if _name not in sys.modules:
        _path = SCRIPT_DIR / "shared-ctx-builder.py"
        _spec = _ilu.spec_from_file_location(_name, _path)
        _mod = _ilu.module_from_spec(_spec)
        sys.modules[_name] = _mod
        _spec.loader.exec_module(_mod)
    return sys.modules[_name].load_moc_proposal_config(config_path)


def _build_kado_client():
    """Instantiate KadoClient; fall back to a null stub on KadoError.

    Title/free-text mode is cache-only in Phase 1, so the stub is enough for
    those modes. Scan/tag/folder/class modes will raise KadoError on the first
    Kado call and surface a clear error via the phase1 handler. Phase 6.5 read
    failures are caught per-candidate and treated as state="absent".
    """
    from lib.kado_client import KadoClient as _KC, KadoError as _KE

    class _NullKadoClient:
        """Stand-in when Kado is unreachable. Read errors degrade to state='absent'."""

        def _fail(self) -> None:
            raise _KE("Kado unavailable — client not initialised")

        def search_by_tag(self, *_a, **_k):  # pragma: no cover
            self._fail()

        def list_dir(self, *_a, **_k):  # pragma: no cover
            self._fail()

        def read_note(self, *_a, **_k):  # pragma: no cover
            self._fail()

    try:
        return _KC()
    except _KE as exc:
        _log(
            f"WARN: Kado client unavailable ({exc}); "
            f"tag/folder/class/scan modes will fail; "
            f"title/free-text and Phase 6.5 degrade gracefully"
        )
        return _NullKadoClient()


def _enrich_cluster(
    cluster: dict,
    idx: int,
    profile_dict: dict,
    cache: dict,
    mode: str,
    trigger_arg: str,
    denom: int,
    moc_location: str,
) -> tuple[dict, list[dict]]:
    """Apply Phase 4 (title) + Phase 5 (parents) + metadata to one raw cluster.

    Returns (enriched_cluster, parent_options_list). Pure — does not mutate input.
    """
    cluster_id = f"MOC{idx:02d}"
    title = phase4_title(cluster, profile_dict, mode, trigger_arg)
    parent_opts = phase5_resolve_parents(cluster, profile_dict, cache)

    confidence = round(len(cluster.get("items") or []) / denom, 4)
    topic_kw = [cluster["topic"]] if cluster.get("topic") else []

    enriched = dict(cluster)
    enriched.update({
        "cluster_id": cluster_id,
        "title": title,
        "confidence": confidence,
        "candidate_stems": list(cluster.get("items") or []),
        "topic_keywords": topic_kw,
        "location": moc_location,
        "template": "t_moc_tomo",
        "slug": slugify(title),
        "existing_up": [],
    })
    serialised_parents = [
        {"moc_stem": p.moc_stem, "confidence": p.confidence, "label": p.label}
        for p in parent_opts
    ]
    return enriched, serialised_parents


def _cap_orphans(
    suggestions: list[dict], cap: int
) -> tuple[list[dict], int, int]:
    """Truncate a (pre-ordered) orphan-suggestion list to `cap` (ADR-12).

    `suggestions` arrives link-first ordered from emit_orphan_suggestions, so the
    head is the most-actionable. Returns (kept, total, overflow). A cap < 0 (or
    a total at/under the cap) keeps everything with overflow 0.
    """
    total = len(suggestions)
    if cap is not None and cap >= 0 and total > cap:
        return suggestions[:cap], total, total - cap
    return suggestions, total, 0


def _run_moc_uplink_check(
    cache: dict, config_path: Path, profile_name: str
) -> dict:
    """Focused MOC-parentage audit (ADR-12 / `--check-moc-uplinks`).

    Runs ONLY the orphan link-or-create pass over `kind=="moc"` entries — no
    clustering pipeline — and returns a `check-moc-uplinks` DiscoveryReport with
    the (capped) MOC orphan suggestions.
    """
    moc_config = _load_moc_config(config_path)
    orphan_all = emit_orphan_suggestions(cache.get("entries") or [], kinds=("moc",))
    kept, total, overflow = _cap_orphans(orphan_all, moc_config.orphan_display_cap)
    _log(f"check-moc-uplinks: {total} orphan MOC(s) → {len(kept)} shown (overflow {overflow})")
    report = empty_report("check-moc-uplinks", "", profile_name)
    report["orphan_suggestions"] = kept
    report["orphan_total"] = total
    report["orphan_overflow"] = overflow
    return report


def _run_pipeline(
    args,
    cache: dict,
    squelch_registry: dict,
    config_path: Path,
    profile_name: str,
    mode: str,
    trigger_arg: str,
    pre_loaded_candidates: list[Candidate] | None = None,
) -> tuple[dict | None, int]:
    """Execute Phase 1 → Phase 6.5 and return (report_dict, exit_code).

    Called by main() after the pre-flight checks (cache-empty, squelch
    decrement) have passed. Returns (None, exit_code) when an abort-report
    is emitted directly inside this helper (abort_reason paths), so the caller
    skips the json.dump step. For successful or partial-failure runs, the
    assembled DiscoveryReport dict is returned.

    When `pre_loaded_candidates` is provided (T6.5 `--phase1-input` flow), Phase 1
    is skipped — the candidates already carry their topics, populated by the
    moc-architect agent's topic-extract subagent between the two passes.

    Exit codes: 0 = clean, 1 = partial (some dups/squelched), 2 = fatal.
    """
    moc_config = _load_moc_config(config_path)
    if args.candidate_cap is not None:
        import dataclasses as _dc
        moc_config = _dc.replace(moc_config, candidate_cap=args.candidate_cap)

    profile_path = DEFAULT_PROFILES_DIR / f"{profile_name}.yaml"
    profile_dict = _load_yaml(profile_path)
    kado_client = _build_kado_client()

    if pre_loaded_candidates is not None:
        candidates = pre_loaded_candidates
        _log(f"phase1: skipped (--phase1-input); {len(candidates)} candidate(s) loaded")
    else:
        # Phase 1 — Candidate selection
        candidates, abort1 = phase1_select_candidates(
            mode, trigger_arg, profile_dict, cache, kado_client, moc_config
        )
        if abort1 is not None:
            _log(f"phase1: abort → {abort1!r}")
            _emit_abort_report(mode, trigger_arg, profile_name, abort1)
            return None, 0
        _log(f"phase1: {len(candidates)} candidate(s) selected")

    candidates_total = len(candidates)

    # Phase 2 — Topic extraction. With --phase1-input, every candidate already
    # has `topics` populated by the agent's topic-extract subagent, so the
    # short-circuit inside phase2_extract_topics treats them all as hits and
    # never invokes llm_client.
    candidates_with_topics, abort2 = phase2_extract_topics(
        candidates, cache, moc_config, llm_client=None
    )
    if abort2 is not None:
        _log(f"phase2: abort → {abort2!r}")
        _emit_abort_report(mode, trigger_arg, profile_name, abort2)
        return None, 0

    _log(f"phase2: {len(candidates_with_topics)} candidate(s) with topics")

    # Phase 3 — Cluster detection
    raw_clusters = phase3_cluster(candidates_with_topics, moc_config)
    _log(f"phase3: {len(raw_clusters)} raw cluster(s) (threshold={moc_config.min_notes})")

    # Phase 4+5 — Enrich clusters (title, parents, metadata)
    denom = max(1, len(candidates_with_topics))
    _map_note_cfg = (profile_dict.get("concept_defaults") or {}).get("map_note") or {}
    moc_location = (_map_note_cfg.get("paths") or ["Atlas/200 Maps/"])[0]

    enriched_clusters: list[dict] = []
    parent_options_per_cluster: dict[str, list[dict]] = {}
    for idx, cluster in enumerate(raw_clusters, start=1):
        enriched, parents = _enrich_cluster(
            cluster, idx, profile_dict, cache, mode, trigger_arg, denom, moc_location
        )
        enriched_clusters.append(enriched)
        parent_options_per_cluster[enriched["cluster_id"]] = parents

    _log(f"phase4+5: enriched {len(enriched_clusters)} cluster(s)")

    # Phase 6 — Duplicate detection + squelch
    kept_clusters, duplicates_skipped, squelched = phase6_dedupe(
        enriched_clusters, cache, squelch_registry, moc_config
    )
    _log(f"phase6: kept={len(kept_clusters)} dup={len(duplicates_skipped)} squelched={len(squelched)}")

    # Phase 6.5 — Existing up:: validation
    kept_clusters = phase65_validate_existing_up(
        kept_clusters, candidates_with_topics, kado_client, cache
    )
    _log(f"phase6.5: existing_up:: decorated {len(kept_clusters)} cluster(s)")

    kept_clusters.sort(key=lambda c: c.get("confidence", 0.0), reverse=True)

    # Case (a) — orphan link-or-create pass (ADR-7). A NEW pass over the cache
    # entries (notes AND MOCs with up_state=="absent"), scored vs the MOC set →
    # top-3 link suggestions or a create-new proposal. Independent of Phase 6
    # duplicates_skipped (H2) and the atomic-note pre-filter (H3). Sourced from
    # the full cache.entries the loader leaves on the cache dict.
    # ADR-12: default scan emits NOTE orphans only (MOC orphans are noise on the
    # notes-discovery path — surfaced on demand via --check-moc-uplinks). Ordered
    # link-first by the pass, then truncated to orphan_display_cap so the cap
    # keeps the most-actionable suggestions; the rest are summarised via overflow.
    orphan_all = emit_orphan_suggestions(cache.get("entries") or [], kinds=("note",))
    orphan_suggestions, orphan_total, orphan_overflow = _cap_orphans(
        orphan_all, moc_config.orphan_display_cap
    )
    _log(
        f"case-a: {orphan_total} note orphan(s) → {len(orphan_suggestions)} shown "
        f"(overflow {orphan_overflow})"
    )

    report = empty_report(mode, trigger_arg, profile_name)
    report.update({
        "candidates_total": candidates_total,
        "candidates_after_prefilter": len(candidates),
        "candidates_capped": False,
        "candidates": [
            {
                "stem": c.stem,
                "path": c.path,
                "topics": c.topics,
                "existing_up": c.existing_up,
                "classification": c.classification,
                "level": c.level,
            }
            for c in candidates_with_topics
        ],
        "topic_clusters": kept_clusters,
        "parent_options_per_cluster": parent_options_per_cluster,
        "duplicates_skipped": duplicates_skipped,
        "squelched": squelched,
        "orphan_suggestions": orphan_suggestions,
        "orphan_total": orphan_total,
        "orphan_overflow": orphan_overflow,
    })

    _log(f"emitting DiscoveryReport: clusters={len(kept_clusters)} mode={mode!r}")
    partial = (len(duplicates_skipped) > 0 or len(squelched) > 0) and len(kept_clusters) > 0
    return report, (1 if partial else 0)


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


def _load_phase1_input(path: Path) -> tuple[str, str, str, list[Candidate]]:
    """Load a phase1-input JSON file → (mode, trigger_arg, profile, candidates).

    Raises ValueError on malformed input. Used by the `--phase1-input` flow
    after the moc-architect agent has populated topics for cache-miss
    candidates between the `--emit-phase1` and `--phase1-input` passes.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("phase1-input must be a JSON object")
    mode = payload.get("mode")
    trigger_arg = payload.get("trigger_arg", "")
    profile = payload.get("profile")
    raw_candidates = payload.get("candidates")
    if not isinstance(mode, str) or not isinstance(profile, str):
        raise ValueError("phase1-input requires string `mode` and `profile`")
    if not isinstance(raw_candidates, list):
        raise ValueError("phase1-input requires list `candidates`")

    candidates: list[Candidate] = []
    for entry in raw_candidates:
        if not isinstance(entry, dict):
            continue
        topics_raw = entry.get("topics")
        topics = [str(t) for t in topics_raw if t] if isinstance(topics_raw, list) else []
        candidates.append(
            Candidate(
                stem=str(entry.get("stem") or ""),
                path=str(entry.get("path") or ""),
                topics=topics,
                existing_up=entry.get("existing_up"),
                classification=entry.get("classification"),
                level=int(entry.get("level") or 0),
            )
        )
    return mode, str(trigger_arg), profile, candidates


_BODY_EXCERPT_CHARS = 800  # cap per-note body included in phase1 JSON for agent extraction


def _write_phase1_emit(
    path: Path,
    mode: str,
    trigger_arg: str,
    profile_name: str,
    candidates: list[Candidate],
    cache: dict,
    moc_config,
    kado_client,
) -> str | None:
    """Write the --emit-phase1 JSON: candidates with cache-resolved topics or null.

    For each cache-miss candidate, includes a `body_excerpt` (first
    `_BODY_EXCERPT_CHARS` characters) so the moc-architect agent can extract
    topics inline without needing Kado MCP access. The agent rewrites the
    file with all topics populated, then re-invokes the script with
    `--phase1-input`.

    Enforces the cache-miss cap (CON-6: 5 batches × 10 notes = 50) here too,
    since phase 2's enforcement is skipped on the --phase1-input flow.

    Returns the abort_reason if the cap was exceeded, otherwise None.
    """
    topics_by_path = _build_topics_index(cache)
    misses_count = sum(1 for c in candidates if c.path not in topics_by_path)
    cap = getattr(moc_config, "cache_miss_max_batches", 5)
    max_misses = cap * LLM_BATCH_SIZE
    abort_reason: str | None = None
    if misses_count > max_misses:
        _log(
            f"emit-phase1: cache-miss-cap-exceeded "
            f"(misses={misses_count} > cap={max_misses})"
        )
        abort_reason = "cache-miss-cap-exceeded"

    out_candidates: list[dict] = []
    for c in candidates:
        if c.path in topics_by_path:
            out_candidates.append(
                {"stem": c.stem, "path": c.path, "topics": list(topics_by_path[c.path])}
            )
            continue
        # Cache miss — fetch body for agent-side topic extraction (unless aborting).
        body_excerpt = ""
        if abort_reason is None:
            try:
                note = kado_client.read_note(c.path)
                content = (note.get("content") if isinstance(note, dict) else "") or ""
                body_excerpt = content[:_BODY_EXCERPT_CHARS]
            except Exception as exc:  # noqa: BLE001 — kado errors are heterogeneous
                _log(f"emit-phase1: read_note failed for {c.path}: {exc}; body_excerpt empty")
        out_candidates.append(
            {
                "stem": c.stem,
                "path": c.path,
                "topics": None,
                "body_excerpt": body_excerpt,
            }
        )

    out = {
        "schema_version": "1",
        "mode": mode,
        "trigger_arg": trigger_arg,
        "profile": profile_name,
        "abort_reason": abort_reason,
        "abort_message": ABORT_MESSAGES.get(abort_reason) if abort_reason else None,
        "candidates": out_candidates,
    }
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return abort_reason


def main(argv: list[str] | None = None) -> int:
    """Top-level orchestration. Returns exit code 0 / 1 / 2."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)

    # ── --phase1-input branch: skip Phase 1, derive mode/trigger from JSON ────
    # T6.5: agent has already extracted topics for cache misses LLM-side.
    if args.phase1_input:
        try:
            mode, trigger_arg, profile_name, pre_loaded = _load_phase1_input(
                Path(args.phase1_input)
            )
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"{LOG_PREFIX} FATAL: --phase1-input load failed: {exc}", file=sys.stderr)
            return 2
        _log(f"phase1-input: mode={mode} trigger_arg={trigger_arg!r} candidates={len(pre_loaded)}")

        cache_path = Path(args.cache)
        # spec 021 T2.1: read the MOC-structure cache via the loader — rebuild
        # inline if stale/missing/corrupt (ADR-3), then shim entries→map_notes.
        cache, cache_abort = load_moc_cache(str(cache_path), str(config_path))
        if cache_abort is not None:
            _log(f"{cache_abort}: cache_path={cache_path} → abort {cache_abort!r}")
            return _emit_abort_report(mode, trigger_arg, profile_name, cache_abort)

        squelch_path = Path(args.squelch_state)
        squelch_registry = _squelch_load_registry(squelch_path)
        squelch_registry = _squelch_decrement_all(squelch_registry)
        _squelch_save_registry_atomic(squelch_path, squelch_registry)

        report, exit_code = _run_pipeline(
            args, cache, squelch_registry, config_path, profile_name,
            mode, trigger_arg, pre_loaded_candidates=pre_loaded,
        )
        if report is not None:
            json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        return exit_code

    # ── Normal flow + --emit-phase1 branch ───────────────────────────────────
    try:
        mode, trigger_arg = route_input(args)
    except ValueError as exc:
        print(f"{LOG_PREFIX} FATAL: {exc}", file=sys.stderr)
        return 2
    _log(f"mode={mode} trigger_arg={trigger_arg!r}")

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

    # Cache load (SDD §Pseudocode line 851 — fires BEFORE Phase 1).
    # spec 021 T2.1: the MOC-structure cache is read via moc_cache_loader, which
    # rebuilds inline when stale/missing/corrupt (ADR-3) and projects
    # entries[kind==moc] → map_notes (shim). A fresh cache loads with no rebuild;
    # a rebuild that still yields no usable map_notes aborts cache-rebuild-failed
    # (not a re-scan every run) so the agent surfaces the "run /explore-vault" hint.
    cache_path = Path(args.cache)
    cache, cache_abort = load_moc_cache(str(cache_path), str(config_path))
    if cache_abort is not None:
        _log(f"{cache_abort}: cache_path={cache_path} → abort {cache_abort!r}")
        return _emit_abort_report(mode, trigger_arg, profile_name, cache_abort)

    # ── --check-moc-uplinks branch: MOC-parentage audit only, no clustering ──
    # ADR-12: a focused pass over kind==moc orphans. No squelch decrement (no
    # clustering run), no Phase 1–6. Checked before --emit-phase1 (the agent
    # never combines them).
    if args.check_moc_uplinks:
        report = _run_moc_uplink_check(cache, config_path, profile_name)
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # ── --emit-phase1 branch: run Phase 1 only, write JSON, exit ─────────────
    # T6.5: no squelch decrement here; squelch is a per-discovery-run counter
    # and a two-pass invocation counts as one run (decremented in pass 2).
    if args.emit_phase1:
        moc_config = _load_moc_config(config_path)
        if args.candidate_cap is not None:
            import dataclasses as _dc
            moc_config = _dc.replace(moc_config, candidate_cap=args.candidate_cap)
        profile_path = DEFAULT_PROFILES_DIR / f"{profile_name}.yaml"
        profile_dict = _load_yaml(profile_path)
        kado_client = _build_kado_client()
        candidates, abort1 = phase1_select_candidates(
            mode, trigger_arg, profile_dict, cache, kado_client, moc_config
        )
        if abort1 is not None:
            _log(f"phase1: abort → {abort1!r}")
            return _emit_abort_report(mode, trigger_arg, profile_name, abort1)
        abort_emit = _write_phase1_emit(
            Path(args.emit_phase1), mode, trigger_arg, profile_name,
            candidates, cache, moc_config, kado_client,
        )
        if abort_emit is not None:
            _log(f"emit-phase1: abort → {abort_emit!r} (written to file)")
        else:
            _log(f"emit-phase1: wrote {len(candidates)} candidate(s) to {args.emit_phase1}")
        return 0

    # ── Squelch: load → decrement → persist (T5.1) ───────────────────────────
    # SDD §Pseudocode lines 881-884: run at start of each discovery pipeline so
    # the updated runs_remaining is in effect for Phase-6 filtering.
    # Missing file → empty registry (first-run case). Corrupt → warn + empty.
    # Raises on I/O errors during save so partial writes can't silently corrupt
    # the sidecar (save_registry_atomic uses tmp-then-rename).
    squelch_path = Path(args.squelch_state)
    squelch_registry = _squelch_load_registry(squelch_path)
    squelch_registry = _squelch_decrement_all(squelch_registry)
    _squelch_save_registry_atomic(squelch_path, squelch_registry)
    _log(
        f"squelch: loaded+decremented {len(squelch_registry)} active entries "
        f"from {squelch_path}"
    )

    report, exit_code = _run_pipeline(
        args, cache, squelch_registry, config_path, profile_name, mode, trigger_arg
    )
    if report is not None:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
