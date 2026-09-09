#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t4_2_invariant_holds.py — #165's invariant holds under item_key.

T2.6 (Phase 2) hoisted `_stem_of` to module-level `_item_key_of` and routed
the Force-Atomic reconciliation through it (ADR-1: item identity is the
vault-relative path, verbatim). The invariant this file exists to prove:
the daily-log path (`source_stem` on a log_entry) and the primary/
resolve-doc path (`source_path` on a parsed section) must derive identity
through that SAME function. If they ever diverge — one re-keyed through a
basename-taking helper, the other left on `_item_key_of` — an approved
proposal parses cleanly into a lookup nothing reads: exactly the #165
livelock, but this time invisible to the original regression test, whose
fixtures use a root-level path only, and largely invisible to T2.6's own
namesake tests, which exercise the daily-log-driven primary-doc atomic
block path rather than the SUPPRESSED-block resolve subflow #165 was
about.

Four cases (spec 034 Phase 4, T4.2):
  1. #165's own fixtures, extended to a subfolder source — promotion
     still works (the suppressed-block section-level loop).
  2. Two suppressed same-named notes in different subfolders, both
     Force-Atomic'd — each promotes independently, on its own resolve-doc
     section.
  3. The daily-log-driven Force Atomic Note path joins to a resolve-doc
     section for a subfolder source — end-to-end proof that `source_stem`
     (daily log) and `source_path` (resolve doc) derive the same key,
     not just that `_item_key_of` is one callable in the abstract.

Honesty note (see report to team-lead): case 1 mirrors T2.6's own
`test_165_suppressed_force_atomic_resolves_for_a_subfolder_source`, which
that task's own commentary disclosed passes even against the pre-fix
parser for a SINGLE item — a subfolder path with no namesake to collide
with proves "both sides agree," not "the value is path-qualified rather
than basename." Case 2 is what actually forces the distinction; case 1 is
kept because the "both sides agree" property is independently part of the
invariant, and can be mutation-broken by making one site diverge from the
other. Case 3 is not a restatement of T2.6's direct dual-call unit test
(`test_item_key_of_is_one_module_level_function_used_by_both_paths`) — it
never calls `_item_key_of` itself, only exercises the real daily-log and
resolve-doc parsing call sites through a subprocess run of the parser.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer_034_t42", "suggestions-reducer.py")


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers — mirror test_165_suppressed_force_atomic_resolve.py's
# own helpers so the parser is fed the shapes the real renderer emits.
# ──────────────────────────────────────────────────────────────────────

def _suppressed_block(stem: str, *, ticked: bool) -> str:
    md = _reducer.render_suppressed_atomic(
        {
            "kind": "create_atomic_note",
            "suggested_title": stem,
            "atomic_note_worthiness": 0.4,
            "stem": stem,
            "suppressed": True,
        },
        stem,
    )
    if ticked:
        md = md.replace(
            "- [ ] Force Atomic Note (create a standalone note for this item)",
            "- [x] Force Atomic Note (create a standalone note for this item)",
        )
    return md


def _doc_header(*, source_items: int) -> list[str]:
    return [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-06T14:45:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        f"source_items: {source_items}",
        "run_id: 2026-09-06T14-41-53Z-test034t42",
        "---",
        "",
        "# Inbox Suggestions — 2026-09-06",
        "",
        "- [x] Approved — check this box when you have finished reviewing, "
        "then run `/inbox` for Pass 2",
        "",
        "## Summary",
        "",
        f"- Items processed: {source_items}",
        "",
    ]


def _primary_doc_suppressed(sections: list[tuple[str, str]]) -> str:
    """`sections` is a list of (section_id, stem) pairs, each ticked."""
    lines = _doc_header(source_items=len(sections)) + ["## Suggestions", ""]
    for section_id, stem in sections:
        lines.append(f"### {section_id} — {stem}")
        lines.append(_suppressed_block(stem, ticked=True))
        lines.append("")
    return "\n".join(lines)


def _resolve_doc(sections: list[tuple[str, str]]) -> str:
    """`sections` is a list of (section_id, stem) pairs, each approved."""
    lines = [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-06T15:05:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        f"source_items: {len(sections)}",
        "run_id: 2026-09-06T15-03-03Z-test034t42",
        "tomo:",
        "  doc_type: suggestions-fan",
        "---",
        "",
        "# Inbox Suggestions — Force-Atomic Resolve — 2026-09-06",
        "",
        "- [x] Approved",
        "",
        "## Summary",
        "",
        f"- Items processed: {len(sections)}",
        "",
        "## Suggestions",
        "",
    ]
    for section_id, stem in sections:
        lines += [
            f"### {section_id} — {stem} resolved",
            "",
            f"**Source:** [[{stem}]]",
            f"**Suggested name:** {stem} resolved",
            "**Template:** [[t_note_tomo]]",
            "**Location:** [[Atlas/202 Notes/]]",
            "",
            f"**Summary:** Resolved atomic proposal for {stem}.",
            "",
            "**Decision (atomic note):**",
            "- [x] Approve",
            "- [ ] Keep source files",
            "",
        ]
    return "\n".join(lines)


def _daily_log_doc(entries: list[tuple[str, bool]]) -> str:
    """`entries` is a list of (source_stem, force_atomic) pairs.

    No matching primary-doc atomic section is included — branch (a) of the
    daily-driven reconciliation loop must find nothing, forcing the join
    down to branch (b)/(c).
    """
    lines = _doc_header(source_items=len(entries)) + [
        "## Daily Notes Updates", "", "### [[2026-09-06]]", "",
        "**Possible Log Entries (inline text):**",
    ]
    for stem, force_atomic in entries:
        lines += [
            f"- after_last_line — Note about {stem} worth splitting.",
            "  - Reason: worthiness 0.3 — force atomic requested",
            f"  - Source: [[{stem}]]",
            "  - [ ] Accept",
            f"  - [{'x' if force_atomic else ' '}] Force Atomic Note "
            "(create/keep a standalone note for this item)",
        ]
    lines += ["", "## Suggestions", ""]
    return "\n".join(lines)


def _run_parser(tmp_path: Path, primary: str, resolve: str | None) -> dict:
    ppath = tmp_path / "2026-09-06_1445_suggestions.md"
    ppath.write_text(primary, encoding="utf-8")
    cmd = [sys.executable, str(PARSER), "--file", str(ppath)]
    if resolve is not None:
        rpath = tmp_path / "2026-09-06_1505_suggestions-fan.md"
        rpath.write_text(resolve, encoding="utf-8")
        cmd += ["--fan-resolve-file", str(rpath)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"parser exit {proc.returncode}\n{proc.stderr}"
    return json.loads(proc.stdout)


def _source_paths(entries: list[dict]) -> list[str | None]:
    return [e.get("source_path") for e in entries]


# ──────────────────────────────────────────────────────────────────────
# 1. #165's own scenario, replayed for a subfolder source
# ──────────────────────────────────────────────────────────────────────

def test_165_suppressed_force_atomic_promotes_for_a_subfolder_source(tmp_path):
    """Same as #165's original test, but the source lives in a subfolder."""
    stem = "Places/Bautzen"
    out = _run_parser(
        tmp_path,
        _primary_doc_suppressed([("S01", stem)]),
        _resolve_doc([("S01", stem)]),
    )
    assert _source_paths(out["confirmed_items"]) == [stem], (
        "the approved resolve-doc proposal for a subfolder source must be "
        "consumed, not re-parked"
    )
    assert out["pending_fan_resolutions"] == [], (
        "subfolder source was re-parked despite an approved resolve "
        "proposal — #165's livelock, reintroduced for the subfolder case"
    )


# ──────────────────────────────────────────────────────────────────────
# 2. Two suppressed same-named notes, both Force-Atomic'd, must promote
#    independently — the case a basename-only key would collapse
# ──────────────────────────────────────────────────────────────────────

def test_two_suppressed_namesakes_force_atomic_promote_independently(tmp_path):
    stem_a = "Places/Diary"
    stem_b = "Other/Diary"
    out = _run_parser(
        tmp_path,
        _primary_doc_suppressed([("S01", stem_a), ("S02", stem_b)]),
        _resolve_doc([("S01", stem_a), ("S02", stem_b)]),
    )
    assert sorted(_source_paths(out["confirmed_items"])) == sorted([stem_a, stem_b]), (
        "both namesakes must be individually promoted from their own "
        "resolve-doc proposal — a basename-only key would collapse them "
        "into one lookup entry and drop or duplicate a promotion"
    )
    assert out["pending_fan_resolutions"] == [], (
        "neither namesake should be re-parked; each has its own approved "
        "resolve-doc section"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. The daily-log path (`source_stem`) and the resolve-doc path
#    (`source_path`) must derive identity through the SAME function —
#    proven end-to-end, not by calling `_item_key_of` directly
# ──────────────────────────────────────────────────────────────────────

def test_daily_log_force_atomic_joins_resolve_doc_for_subfolder_source(tmp_path):
    """Force Atomic Note ticked on a daily-log entry (branch a/b/c loop),
    no matching primary-doc atomic section, but an approved resolve-doc
    section for the same subfolder path. Must promote via branch (b), not
    park via branch (c) — proving `source_stem` and `source_path` agree
    for a path-qualified value at the real call sites, not merely that
    `_item_key_of` is one callable in the abstract.
    """
    stem = "Places/Weimar"
    out = _run_parser(
        tmp_path,
        _daily_log_doc([(stem, True)]),
        _resolve_doc([("S01", stem)]),
    )
    assert _source_paths(out["confirmed_items"]) == [stem], (
        "the daily-log Force Atomic Note and the resolve-doc **Source:** "
        "line for the same subfolder path must join to one promoted item"
    )
    assert out["pending_fan_resolutions"] == [], (
        "the daily-log path and resolve-doc path derived different keys "
        "for the same subfolder source — reconciliation parked it instead "
        "of consuming the approved proposal"
    )
