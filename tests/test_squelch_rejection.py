#!/usr/bin/env python3
# version: 0.1.0
"""test_squelch_rejection.py — F-43 T5.2: Squelch persist on rejection.

4 tests covering `persist_rejected_clusters` in `lib/squelch_persist.py`:
  test_rejected_proposal_writes_squelch_entry
  test_partially_accepted_only_rejected_clusters_squelched
  test_runs_remaining_initialised_to_squelch_runs_config
  test_first_seen_at_iso_timestamp

Fixture strategy: construct a DiscoveryReport, run render_moc_proposal_doc to
get a live-rendered proposal-doc body (feedback_fixture_from_live_render.md),
then call persist_rejected_clusters directly with the body + a tmp registry path.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(LIB_DIR.parent))

# Load suggestions-reducer.py as module (hyphen in filename → importlib)
_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py"
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]

render_moc_proposal_doc = _mod.render_moc_proposal_doc  # type: ignore[attr-defined]

from lib import squelch, squelch_persist  # noqa: E402


# ── Stub config ──────────────────────────────────────────────────────────────


class _Cfg:
    """Minimal duck-typed config stub."""

    def __init__(self, max_results: int = 5, squelch_runs: int = 3):
        self.max_results = max_results
        self.squelch_runs = squelch_runs


# ── Report/cluster builders ──────────────────────────────────────────────────


def _candidate(stem: str) -> dict:
    return {
        "stem": stem,
        "path": f"Atlas/202 Notes/{stem}.md",
        "topics": [],
        "existing_up": None,
        "existing_up_broken": False,
        "classification": None,
        "level": 0,
    }


def _cluster(
    cluster_id: str,
    *,
    title: str,
    confidence: float,
    candidate_stems: list[str],
    topic_keywords: list[str],
) -> dict:
    return {
        "cluster_id": cluster_id,
        "title": title,
        "confidence": confidence,
        "candidate_stems": candidate_stems,
        "topic_keywords": topic_keywords,
        "slug": title.lower().replace(" ", "-"),
        "location": "Atlas/200 Maps/",
        "template": "t_moc_tomo",
        "existing_up": [],
    }


def _empty_report() -> dict:
    return {
        "schema_version": "1",
        "run_id": "test-run-id",
        "mode": "tag",
        "trigger_arg": "topic/applied/zsh",
        "profile": "miyo",
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


def _render_proposal(clusters: list[dict]) -> str:
    """Render a live proposal-doc body from clusters using the actual reducer."""
    report = _empty_report()
    report["candidates"] = [
        _candidate(s) for c in clusters for s in c["candidate_stems"]
    ]
    report["topic_clusters"] = clusters
    report["parent_options_per_cluster"] = {c["cluster_id"]: [] for c in clusters}
    _path, body = render_moc_proposal_doc(report, _Cfg())
    return body


# ── Tests ────────────────────────────────────────────────────────────────────


def test_rejected_proposal_writes_squelch_entry(tmp_path: Path) -> None:
    """1 cluster, Accept NOT ticked → registry gains 1 entry with the cluster's signature."""
    cluster = _cluster(
        "MOC01",
        title="Shell & Terminal (MOC)",
        confidence=0.78,
        candidate_stems=["oh-my-zsh", "zsh-aliases", "iterm-config"],
        topic_keywords=["shell", "terminal", "zsh"],
    )
    body = _render_proposal([cluster])
    # Accept is NOT ticked (live render produces `- [ ] Accept`)
    assert "- [ ] Accept" in body, "Fixture must have unticked Accept"

    registry_path = tmp_path / "moc-squelch.json"
    config = {"squelch_runs": 3}
    n_added = squelch_persist.persist_rejected_clusters(
        body,
        filename="tomo-moc-proposal-shell-terminal.md",
        registry_path=registry_path,
        config=config,
    )

    assert n_added == 1
    registry = squelch.load_registry(registry_path)
    assert len(registry) == 1
    entry = next(iter(registry.values()))
    assert entry.topic_signature  # non-empty hash
    assert entry.runs_remaining > 0


def test_partially_accepted_only_rejected_clusters_squelched(
    tmp_path: Path,
) -> None:
    """3 clusters, only MOC02's Accept ticked → registry has 2 entries (MOC01, MOC03)."""
    clusters = [
        _cluster(
            "MOC01",
            title="Python Tooling (MOC)",
            confidence=0.82,
            candidate_stems=["pip-tools", "virtualenv", "poetry"],
            topic_keywords=["python", "tooling", "packaging"],
        ),
        _cluster(
            "MOC02",
            title="Shell & Terminal (MOC)",
            confidence=0.78,
            candidate_stems=["oh-my-zsh", "zsh-aliases", "iterm-config"],
            topic_keywords=["shell", "terminal", "zsh"],
        ),
        _cluster(
            "MOC03",
            title="Networking (MOC)",
            confidence=0.65,
            candidate_stems=["tcp-ip-notes", "dns-config", "firewall-rules"],
            topic_keywords=["network", "tcp", "dns"],
        ),
    ]
    body = _render_proposal(clusters)

    # Tick Accept only for MOC02
    body = body.replace(
        "### MOC02 — Shell & Terminal (MOC)\n\n- [ ] Accept",
        "### MOC02 — Shell & Terminal (MOC)\n\n- [x] Accept",
    )

    registry_path = tmp_path / "moc-squelch.json"
    config = {"squelch_runs": 3}
    n_added = squelch_persist.persist_rejected_clusters(
        body,
        filename="tomo-moc-proposal-mixed.md",
        registry_path=registry_path,
        config=config,
    )

    assert n_added == 2  # MOC01 and MOC03 are rejected
    registry = squelch.load_registry(registry_path)
    assert len(registry) == 2


def test_runs_remaining_initialised_to_squelch_runs_config(
    tmp_path: Path,
) -> None:
    """Config squelch_runs=3 → entry's runs_remaining=3."""
    cluster = _cluster(
        "MOC01",
        title="Networking (MOC)",
        confidence=0.65,
        candidate_stems=["tcp-ip-notes", "dns-config"],
        topic_keywords=["network", "tcp"],
    )
    body = _render_proposal([cluster])

    registry_path = tmp_path / "moc-squelch.json"
    config = {"squelch_runs": 3}
    squelch_persist.persist_rejected_clusters(
        body,
        filename="tomo-moc-proposal-networking.md",
        registry_path=registry_path,
        config=config,
    )

    registry = squelch.load_registry(registry_path)
    assert len(registry) == 1
    entry = next(iter(registry.values()))
    assert entry.runs_remaining == 3


def test_first_seen_at_iso_timestamp(tmp_path: Path) -> None:
    """Entry's first_seen_at parses as a valid ISO 8601 timestamp."""
    cluster = _cluster(
        "MOC01",
        title="Rust Programming (MOC)",
        confidence=0.72,
        candidate_stems=["rust-ownership", "cargo-intro"],
        topic_keywords=["rust", "systems", "programming"],
    )
    body = _render_proposal([cluster])

    registry_path = tmp_path / "moc-squelch.json"
    config = {"squelch_runs": 3}
    squelch_persist.persist_rejected_clusters(
        body,
        filename="tomo-moc-proposal-rust.md",
        registry_path=registry_path,
        config=config,
    )

    registry = squelch.load_registry(registry_path)
    entry = next(iter(registry.values()))

    # Must parse as ISO 8601 — fromisoformat accepts both Z and +HH:MM suffixes.
    # Normalize "Z" → "+00:00" for Python < 3.11 compatibility.
    ts_str = entry.first_seen_at.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    assert dt.tzinfo is not None, "first_seen_at must be timezone-aware"


