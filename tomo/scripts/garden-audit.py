#!/usr/bin/env python3
# version: 0.1.1
"""garden-audit.py — Scan orchestrator for the Knowledge-Garden Audit skill (spec 030).

Runs six checks over the MOC-structure cache, kado-graph-audit results, and
listDir modified times, applies GardenExclusions, and emits garden-audit-doc.json.
This doc is the intermediate contract feeding garden-audit-render.py (Phase 3).

Data-source split (ADR-5):
  cache       → unparented (up_state=="absent"), broken_up (up_state=="broken"),
                duplicate_stem (stem groups)
  graph_audit → orphan (orphans[]), dead_link (deadLinks[])
  listDir     → stale_moc (modified timestamp vs threshold)

broken_up is CACHE-ONLY — never triggers a graph_audit call.

Graceful partial (SDD Error Handling):
  If graph_audit raises, skip orphan + dead_link, record them in skipped_checks,
  still produce cache + listDir findings. Never crash.

Public entry point for callers and tests:
  run_scan(entries, *, graph_audit_fn, list_dir_fn, exclusions=None,
           stale_moc_days=90, run_id=None, profile=None, generated=None,
           today=None) -> dict

Design notes: docs/tomo/scripts/garden-audit.md
"""
from __future__ import annotations

import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.orphan_link import emit_orphan_suggestions  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Tier + ordering constants
# ──────────────────────────────────────────────────────────────────────────────

_TIER: dict[str, str] = {
    "broken_up":      "integrity",
    "dead_link":      "integrity",
    "unparented":     "structure",
    "orphan":         "structure",
    "duplicate_stem": "advisory",
    "stale_moc":      "advisory",
}

_FIXABLE: frozenset[str] = frozenset(["unparented", "orphan", "broken_up", "dead_link"])

# Default stale-MOC threshold in days
_DEFAULT_STALE_MOC_DAYS = 90


# ──────────────────────────────────────────────────────────────────────────────
# Finding factory helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"F{counter[0]:02d}"


def _finding(fid: str, check: str, path: str, stem: str | None, detail: dict) -> dict:
    """Build a fully-shaped finding dict."""
    fixable = check in _FIXABLE
    tier = _TIER[check]
    f: dict = {
        "id": fid,
        "check": check,
        "tier": tier,
        "fixable": fixable,
        "target": {"path": path, "stem": stem},
        "detail": detail,
    }
    if fixable:
        f["decision"] = {"selected": True, "action": None}
    return f


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────

def _check_unparented(
    entries: list[dict],
    exclusions,
    counter: list[int],
) -> list[dict]:
    """Check 1: unparented notes (up_state=="absent") — cache-only.

    Reuses emit_orphan_suggestions for candidate MOC scoring.
    """
    absent = [
        e for e in entries
        if isinstance(e, dict)
        and e.get("kind") == "note"
        and e.get("up_state") == "absent"
    ]
    if not absent:
        return []

    # Score candidates via orphan_link (notes-only pass for unparented)
    suggestions = emit_orphan_suggestions(entries, kinds=("note",))
    # Index by path for quick lookup
    by_path = {s["path"]: s for s in suggestions}

    findings = []
    for entry in absent:
        path = entry.get("path", "")
        if exclusions and exclusions.is_excluded(entry, "unparented"):
            continue
        sugg = by_path.get(path, {})
        candidates = sugg.get("candidates") or []
        findings.append(_finding(
            _make_id(counter),
            "unparented",
            path,
            entry.get("stem"),
            {"candidate_mocs": candidates},
        ))
    return findings


def _check_broken_up(
    entries: list[dict],
    exclusions,
    counter: list[int],
) -> list[dict]:
    """Check 3: broken up:: (up_state=="broken" + up_target) — cache-only, NEVER triggers graph_audit."""
    findings = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("up_state") != "broken":
            continue
        path = entry.get("path", "")
        if exclusions and exclusions.is_excluded(entry, "broken_up"):
            continue
        findings.append(_finding(
            _make_id(counter),
            "broken_up",
            path,
            entry.get("stem"),
            {"up_target": entry.get("up_target")},
        ))
    return findings


def _check_orphan(
    graph_result: dict,
    entries: list[dict],
    exclusions,
    counter: list[int],
) -> list[dict]:
    """Check 2: orphan notes (from graph_audit orphans[]).

    Builds fake absent-note entries for each graph orphan, then calls
    emit_orphan_suggestions ONCE over the augmented entry list (S1: batch,
    not per-orphan — avoids O(N_orphans × N_entries) work on large vaults).
    """
    path_to_entry = {e.get("path", ""): e for e in entries if isinstance(e, dict)}

    # Collect non-excluded orphan paths and their augmented entries
    orphan_items = []
    for item in graph_result.get("orphans") or []:
        path = item.get("path", "")
        stem = Path(path).stem if path else None
        entry = path_to_entry.get(path) or {"path": path, "stem": stem, "tags": []}
        if exclusions and exclusions.is_excluded(entry, "orphan"):
            continue
        fake_entry = dict(entry)
        fake_entry.setdefault("up_state", "absent")
        fake_entry.setdefault("kind", "note")
        fake_entry.setdefault("topics", [])
        fake_entry["path"] = path  # ensure path is set even for cache-miss entries
        orphan_items.append((path, stem, fake_entry))

    if not orphan_items:
        return []

    # Build augmented entry list: base entries (excluding any that share a path
    # with an orphan item so we don't double-count) + one fake entry per orphan
    orphan_paths = {path for path, _, _ in orphan_items}
    base_entries = [e for e in entries if e.get("path") not in orphan_paths]
    augmented = base_entries + [fake for _, _, fake in orphan_items]

    # Single emit_orphan_suggestions call for all orphans (batch pattern)
    suggestions = emit_orphan_suggestions(augmented, kinds=("note",))
    by_path = {s["path"]: s for s in suggestions}

    findings = []
    for path, stem, _ in orphan_items:
        matched = by_path.get(path)
        candidates = matched.get("candidates", []) if matched else []
        findings.append(_finding(
            _make_id(counter),
            "orphan",
            path,
            stem,
            {"candidate_mocs": candidates},
        ))
    return findings


def _check_dead_link(
    graph_result: dict,
    entries: list[dict],
    exclusions,
    counter: list[int],
) -> list[dict]:
    """Check 4: dead wikilinks (from graph_audit deadLinks[])."""
    path_to_entry = {e.get("path", ""): e for e in entries if isinstance(e, dict)}

    findings = []
    for item in graph_result.get("deadLinks") or []:
        source = item.get("source", "")
        target = item.get("target", "")
        count = item.get("count", 1)
        stem = Path(source).stem if source else None
        entry = path_to_entry.get(source) or {"path": source, "stem": stem, "tags": []}
        if exclusions and exclusions.is_excluded(entry, "dead_link"):
            continue
        findings.append(_finding(
            _make_id(counter),
            "dead_link",
            source,
            stem,
            {"dead_target": target, "count": count},
        ))
    return findings


def _check_duplicate_stem(
    entries: list[dict],
    exclusions,
    counter: list[int],
) -> list[dict]:
    """Check 5: duplicate stems (group entries[] by stem) — advisory.

    Exclusion is applied per-path: any path for which is_excluded returns True
    is dropped from the group first. A finding is only emitted when ≥2
    non-excluded paths remain; the first remaining path is the finding target.
    """
    # Build path→entry index for exclusion checks
    path_to_entry: dict[str, dict] = {}
    groups: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stem = entry.get("stem")
        path = entry.get("path", "")
        if stem:
            groups[stem].append(path)
            path_to_entry[path] = entry

    findings = []
    for stem, paths in groups.items():
        if len(paths) < 2:
            continue
        # Filter out any path whose entry is excluded for duplicate_stem
        if exclusions:
            remaining = [
                p for p in paths
                if not exclusions.is_excluded(
                    path_to_entry.get(p) or {"path": p, "stem": stem, "tags": []},
                    "duplicate_stem",
                )
            ]
        else:
            remaining = paths
        if len(remaining) < 2:
            continue
        findings.append(_finding(
            _make_id(counter),
            "duplicate_stem",
            remaining[0],
            stem,
            {"dupes": remaining},
        ))
    return findings


def _check_stale_moc(
    entries: list[dict],
    list_dir_fn,
    exclusions,
    counter: list[int],
    stale_moc_days: int,
    today: date,
) -> tuple[list[dict], list[str], str]:
    """Check 6: stale MOCs (listDir modified older than stale_moc_days) — advisory.

    Returns (findings, skipped_checks, skipped_reason).
    When list_dir_fn raises, degrades gracefully: returns ([], ["stale_moc"], reason)
    mirroring the graph-unavailable pattern (SDD Error Handling).
    """
    moc_paths = {
        e.get("path", ""): e
        for e in entries
        if isinstance(e, dict) and e.get("kind") == "moc"
    }
    if not moc_paths:
        return [], [], ""

    # Fetch all items from the root; filter to MOC paths
    try:
        items = list_dir_fn(path="/") or []
    except Exception as exc:  # noqa: BLE001 — graceful partial per SDD Error Handling
        return [], ["stale_moc"], f"not run (listDir unavailable): {exc}"

    cutoff_dt = datetime(
        today.year, today.month, today.day, tzinfo=timezone.utc
    )

    findings = []
    for item in items:
        if item.get("type") != "file":
            continue
        path = item.get("path", "")
        if path not in moc_paths:
            continue
        mtime_str = item.get("modified", "")
        if not mtime_str:
            continue
        try:
            mtime_dt = datetime.fromisoformat(mtime_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if mtime_dt.tzinfo is None:
            mtime_dt = mtime_dt.replace(tzinfo=timezone.utc)
        age_days = (cutoff_dt - mtime_dt).total_seconds() / 86400
        if age_days < stale_moc_days:
            continue
        entry = moc_paths[path]
        if exclusions and exclusions.is_excluded(entry, "stale_moc"):
            continue
        stem = entry.get("stem") or Path(path).stem
        findings.append(_finding(
            _make_id(counter),
            "stale_moc",
            path,
            stem,
            {"mtime": mtime_str},
        ))
    return findings, [], ""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def run_scan(
    entries: list[dict],
    *,
    graph_audit_fn,
    list_dir_fn,
    exclusions=None,
    stale_moc_days: int = _DEFAULT_STALE_MOC_DAYS,
    run_id: str | None = None,
    profile: str | None = None,
    generated: str | None = None,
    today: date | None = None,
) -> dict:
    """Run all six garden-audit checks and return a garden-audit-doc dict.

    Parameters
    ----------
    entries:
        MOC-structure cache entries (list of dicts with path/stem/kind/up_state/
        up_target/topics/tags).
    graph_audit_fn:
        Callable(**kwargs) -> {"orphans": [...], "deadLinks": [...], "total": {...}}.
        Raise any exception to signal unavailability — scan degrades gracefully.
    list_dir_fn:
        Callable(path=str, **kwargs) -> list of {"type","path","modified",...}.
    exclusions:
        Optional GardenExclusions instance. None means nothing is excluded.
    stale_moc_days:
        Age threshold for stale-MOC detection.
    run_id, profile, generated:
        Run metadata; auto-generated when absent.
    today:
        Pin the reference date (used for stale-MOC threshold). Defaults to date.today().

    Returns
    -------
    dict matching garden-audit-doc.schema.json
    """
    effective_today = today or date.today()
    effective_run_id = run_id or str(uuid.uuid4())
    effective_generated = generated or datetime.now(timezone.utc).isoformat()

    counter: list[int] = [0]  # mutable int for _make_id

    # ── Cache-only checks (order: integrity first, then structure, then advisory) ──
    broken_findings   = _check_broken_up(entries, exclusions, counter)
    unparented_findings = _check_unparented(entries, exclusions, counter)
    dup_findings      = _check_duplicate_stem(entries, exclusions, counter)

    # ── Graph-dependent checks (orphan + dead_link) ──
    skipped_checks: list[str] = []
    skipped_reason = ""
    graph_findings: list[dict] = []
    try:
        graph_result = graph_audit_fn()
        graph_findings += _check_orphan(graph_result, entries, exclusions, counter)
        graph_findings += _check_dead_link(graph_result, entries, exclusions, counter)
    except Exception as exc:  # noqa: BLE001 — graceful partial per SDD Error Handling
        skipped_checks = ["orphan", "dead_link"]
        skipped_reason = f"not run (graph unavailable): {exc}"

    # ── listDir check ──
    stale_findings, stale_skipped, stale_reason = _check_stale_moc(
        entries, list_dir_fn, exclusions, counter, stale_moc_days, effective_today
    )
    if stale_skipped:
        skipped_checks.extend(stale_skipped)
        skipped_reason = "; ".join(filter(None, [skipped_reason, stale_reason]))

    # ── Assemble in severity order: integrity > structure > advisory (SDD tier ordering) ──
    integrity_findings = broken_findings + [f for f in graph_findings if f["check"] == "dead_link"]
    structure_findings = unparented_findings + [f for f in graph_findings if f["check"] == "orphan"]
    advisory_findings  = dup_findings + stale_findings

    all_findings = integrity_findings + structure_findings + advisory_findings

    # Re-sequence IDs in severity order
    for i, f in enumerate(all_findings, start=1):
        f["id"] = f"F{i:02d}"

    reappeared = exclusions.reappeared_exclusions() if exclusions else []

    doc: dict = {
        "run_id": effective_run_id,
        "generated": effective_generated,
        "profile": profile,
        "skipped_checks": skipped_checks,
        "skipped_checks_reason": skipped_reason,
        "reappeared_exclusions": reappeared,
        "findings": all_findings,
    }
    return doc
