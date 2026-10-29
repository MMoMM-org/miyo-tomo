# version: 0.1.0
"""moc_discovery_report.py — DiscoveryReport assembly and emission for moc-discovery.py.

Every exit path of the script writes the same DiscoveryReport shape: the empty
scaffold, the candidate rows, the abort report and the pipeline report are
built here once so the cluster pipeline and `--around` cannot drift apart.

Rationale: docs/tomo/scripts/lib/moc_discovery_report.md (issue #216).
"""
from __future__ import annotations

import json
import sys
import uuid
from typing import Any

from lib.moc_discovery_common import ABORT_MESSAGES


# ──────────────────────────────────────────────────────────────────────────────
# DiscoveryReport scaffolding
# ──────────────────────────────────────────────────────────────────────────────


_EMPTY_LINK_STATS: dict[str, int] = {
    "lookups": 0,
    "attempts": 0,
    "failed": 0,
    "clusters_skipped_budget": 0,
    "clusters_sampled": 0,
    "members_total": 0,
    "skipped_uncached": 0,
}


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
        "link_stats": dict(_EMPTY_LINK_STATS),
        "around": None,
        "extension": None,
    }


def candidate_rows(candidates) -> list[dict]:
    """Serialise Candidates into the DiscoveryReport `candidates` rows."""
    return [
        {
            "stem": c.stem,
            "path": c.path,
            "topics": c.topics,
            "existing_up": c.existing_up,
            "classification": c.classification,
            "level": c.level,
        }
        for c in candidates
    ]


def emit_report(report: dict) -> None:
    """Write a DiscoveryReport to stdout as indented JSON plus a newline."""
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


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


def build_pipeline_report(
    mode: str,
    trigger_arg: str,
    profile_name: str,
    candidates_total: int,
    candidates_after_prefilter: int,
    candidates_with_topics,
    kept_clusters: list[dict],
    parent_options_per_cluster: dict[str, list[dict]],
    duplicates_skipped: list[dict],
    squelched: list[dict],
    link_stats: dict[str, int],
) -> dict:
    """The cluster pipeline's DiscoveryReport (orphans stay empty — ADR-13 D1)."""
    report = empty_report(mode, trigger_arg, profile_name)
    report.update({
        "candidates_total": candidates_total,
        "candidates_after_prefilter": candidates_after_prefilter,
        "candidates_capped": False,
        "candidates": candidate_rows(candidates_with_topics),
        "topic_clusters": kept_clusters,
        "parent_options_per_cluster": parent_options_per_cluster,
        "duplicates_skipped": duplicates_skipped,
        "squelched": squelched,
        "orphan_suggestions": [],
        "orphan_total": 0,
        "orphan_overflow": 0,
        "link_stats": link_stats,
    })
    return report
