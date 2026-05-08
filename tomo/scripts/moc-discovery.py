#!/usr/bin/env python3
# version: 0.1.0
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
    """
    if getattr(args, "tag", None):
        return ("tag", args.tag)
    if getattr(args, "folder", None):
        return ("folder", args.folder)
    if getattr(args, "klass", None):
        return ("class", args.klass)
    if getattr(args, "title", None):
        return ("title", args.title)
    if getattr(args, "free_text", None):
        return ("free-text", args.free_text)
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
# Discovery phases — stubs for T2.2-T2.7
# ──────────────────────────────────────────────────────────────────────────────


def phase1_select_candidates(*_args, **_kwargs):
    """Mode-dispatch: tag/folder/class/title/free-text/scan → candidate stems."""
    raise NotImplementedError("T2.2 — phase1_select_candidates pending")


def phase2_prefilter_atomic_notes(*_args, **_kwargs):
    """Restrict candidates to the profile's atomic-note paths."""
    raise NotImplementedError("T2.3 — phase2_prefilter_atomic_notes pending")


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

    mode, trigger_arg = route_input(args)
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

    # Full discovery flow lands in T2.2-T2.7. Until then, surface clearly.
    _log("ERROR: discovery phases not yet implemented (T2.2-T2.7)")
    raise NotImplementedError(
        "moc-discovery.py full pipeline pending — use --dry-run for T2.1 scaffolding"
    )


if __name__ == "__main__":
    sys.exit(main())
