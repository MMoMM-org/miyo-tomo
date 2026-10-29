# version: 0.1.0
"""moc_discovery_args.py — CLI surface of moc-discovery.py: parser, mode routing, profile.

The argument set, defaults and help text are the script's public contract with
the moc-architect agent; they live here so the CLI file only orchestrates.
`moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_args.md (issue #216).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from lib.moc_discovery_common import DEFAULT_PROFILES_DIR, _load_yaml


DEFAULT_CONFIG_PATH = "config/vault-config.yaml"
# spec 021 T2.1: moc-discovery now reads the MOC-structure cache via
# lib/moc_cache_loader (TTL + rebuild-if-stale + entries[kind==moc]→map_notes
# shim), not discovery-cache.yaml directly. The loader rebuilds inline when the
# cache is stale/missing/corrupt (ADR-3).
DEFAULT_CACHE_PATH = "config/moc-structure-cache.yaml"
# ADR-8: squelch sidecar at tomo-instance/state/moc-squelch.json. Default
# resolves relative to TOMO_INSTANCE env var (Docker runtime) or cwd (tests /
# host dev runs). The `--squelch-state` flag overrides this default.
DEFAULT_SQUELCH_STATE_PATH = str(
    Path(os.environ.get("TOMO_INSTANCE", ".")) / "state" / "moc-squelch.json"
)


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
    scope.add_argument(
        "--around",
        metavar="NAME_OR_PATH",
        help=(
            "One new-MOC proposal from a cached seed note's links (stem, [[stem]], "
            "stem.md or vault path). Single pass: not combinable with "
            "--emit-phase1 / --phase1-input / --check-moc-uplinks."
        ),
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
      --around X  → ("around", X)           # spec 042 F2; `around:X` free text is NOT parsed here
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
        ("around", "around", "--around"),
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
