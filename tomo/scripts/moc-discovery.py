#!/usr/bin/env python3
# version: 0.2.0
"""moc-discovery.py — Discover MOC candidates and emit a DiscoveryReport.

Backs the `/moc-propose` skill (F-43, spec 013-moc-creation-skill). Accepts a
mutually-exclusive scope flag (`--tag`, `--folder`, `--class`, `--title`), an
optional free-text positional, or no args (whole-vault density scan), and walks
through the six discovery phases described in the SDD §Pseudocode (lines
845-895):

    Phase 1 — select candidates per mode
    Phase 2 — pre-filter to atomic-note paths
    Phase 3 — cluster candidates by topic
    Phase 4 — title generation per profile
    Phase 5 — parent-MOC matching against classification map
    Phase 6 — duplicate / squelch suppression
    Phase 6.5 — apply candidate cap

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
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
# Discovery phases — stubs for T2.3-T2.7
# ──────────────────────────────────────────────────────────────────────────────


def phase3_cluster_by_topic(*_args, **_kwargs):
    """Group candidates by normalised topic (delegates to lib.topic_clusters)."""
    raise NotImplementedError("T2.4 — phase3_cluster_by_topic pending")


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

    # Dry-run path: emit a minimal DiscoveryReport and exit. No Kado calls.
    if args.dry_run:
        _log("dry-run — emitting minimal DiscoveryReport, skipping discovery phases")
        report = empty_report(mode, trigger_arg, profile_name)
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Full discovery flow lands in T2.3-T2.7. Until then, surface clearly.
    _log("ERROR: discovery phases not yet implemented (T2.3-T2.7)")
    raise NotImplementedError(
        "moc-discovery.py full pipeline pending — use --dry-run for T2.1 scaffolding"
    )


if __name__ == "__main__":
    sys.exit(main())
