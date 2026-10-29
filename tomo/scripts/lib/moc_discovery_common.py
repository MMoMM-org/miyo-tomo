# version: 0.1.0
"""moc_discovery_common.py — Shared primitives of the moc-discovery pipeline.

Every `lib/moc_discovery_*` module logs through the same `[moc-discovery]`
prefix, works on the same `Candidate` record and resolves the same profiles
directory; keeping them in one place stops the phase modules from importing
each other just to reach a log helper. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_common.md (issue #216).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# Profiles live beside scripts/ (tomo/profiles in the source tree,
# <instance>/profiles at runtime) — two levels above this lib module.
DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"


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
    "around-periodic": "around: periodic notes cannot be a MOC seed",
    "cache-rebuild-failed": (
        "MOC structure cache could not be rebuilt (target unwritable or no MOCs "
        "found). Please run /explore-vault and check the vault configuration."
    ),
}


def _log(msg: str) -> None:
    """Write a stderr progress line — matches sibling moc-tree-builder style."""
    print(f"{LOG_PREFIX} {msg}", file=sys.stderr)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file → dict; empty / missing → {}."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


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


def _load_moc_config(config_path: Path):
    """Lazy-load MocProposalConfig from shared-ctx-builder to avoid import cycle.

    The sys.modules registration is required because Python 3.14's dataclass
    machinery inspects the owning module's ``__dict__`` during class processing
    (same fix applied in test_moc_proposal_config.py).
    """
    import importlib.util as _ilu

    _name = "shared_ctx_builder"
    if _name not in sys.modules:
        _path = Path(__file__).resolve().parent.parent / "shared-ctx-builder.py"
        _spec = _ilu.spec_from_file_location(_name, _path)
        _mod = _ilu.module_from_spec(_spec)
        sys.modules[_name] = _mod
        _spec.loader.exec_module(_mod)
    return sys.modules[_name].load_moc_proposal_config(config_path)
