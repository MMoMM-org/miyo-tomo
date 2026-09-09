#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_6_parser_single_derivation.py — the parser derives identity once.

Covers T2.6 (XDD 034 Phase 2): `suggestion-parser.py`'s Force-Atomic
reconciliation joined items by `_stem_of` — a lowercased, folder-stripped
bare filename. Two notes with the same filename in different subfolders
collapsed to one key, so `sections_by_stem`, `already_in`, `seen_pending`
and the MOC-member binding pass could silently merge, suppress or
mis-attribute one source to the other.

`_item_key_of` replaces `_stem_of`: same call sites, but the derived value
is the vault-relative path verbatim (ADR-1, via `lib.item_key.derive`) — no
basename extraction, no lowercasing. It is a single MODULE-LEVEL function
(not a `main()`-local closure) so this file can call it directly, and so
every join site — the daily-log `source_stem` path and the primary/
resolve-doc `source_path` path alike — is provably the same callable.

#165 (see docs/tomo/scripts/suggestion-parser.md) is the regression this
guards: its original test never exercised a subfolder path, so a
derivation that still collapsed namesakes could pass it. This file adds a
subfolder-path replay of that exact scenario alongside the new namesake
tests.

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


_parser = _load("suggestion_parser_034_t26", "suggestion-parser.py")
_reducer = _load("suggestions_reducer_034_t26", "suggestions-reducer.py")


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers (mirror test_suggestion_parser_multi_atomic.py /
# test_165_suppressed_force_atomic_resolve.py so the parser sees the same
# shapes the real renderer emits)
# ──────────────────────────────────────────────────────────────────────

def _doc_header() -> list[str]:
    return [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-06T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 2",
        "run_id: 2026-09-06T10-00-00Z-test034t26",
        "---",
        "",
        "# Inbox Suggestions — 2026-09-06",
        "",
        "- [x] Approved — check this box when you have finished reviewing",
        "",
        "## Summary",
        "",
        "- Items processed: 2",
        "",
    ]


def _atomic_block(source: str, title: str, *, accept: bool) -> list[str]:
    """One atomic block as the reducer/renderer emit it — starts at **Source:**."""
    return [
        f"**Source:** [[{source}]]",
        f"**Suggested name:** {title}",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "",
        "**Decision (atomic note):**",
        f"- [{'x' if accept else ' '}] Approve",
        "- [ ] Keep source files",
        "      (don't delete the original(s) after the note is created — "
        "you may still need them)",
        "",
    ]


def _daily_log_entry_block(source: str, *, force_atomic: bool) -> list[str]:
    return [
        "**Possible Log Entries (inline text):**",
        f"- after_last_line — Note about {source} worth splitting.",
        "  - Reason: worthiness 0.3 — force atomic requested",
        f"  - Source: [[{source}]]",
        "  - [ ] Accept",
        f"  - [{'x' if force_atomic else ' '}] Force Atomic Note "
        "(create/keep a standalone note for this item)",
        "",
    ]


def _run_parser(
    tmp_path: Path,
    primary: str,
    *,
    suggestions_doc: dict | None = None,
) -> dict:
    ppath = tmp_path / "2026-09-06_1000_suggestions.md"
    ppath.write_text(primary, encoding="utf-8")
    cmd = [sys.executable, str(PARSER), "--file", str(ppath)]
    if suggestions_doc is not None:
        dpath = tmp_path / "suggestions-doc.json"
        dpath.write_text(json.dumps(suggestions_doc), encoding="utf-8")
        cmd += ["--suggestions-doc", str(dpath)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"parser exit {proc.returncode}\n{proc.stderr}"
    return json.loads(proc.stdout)


def _source_paths(entries: list[dict]) -> list[str | None]:
    return [e.get("source_path") for e in entries]


# ──────────────────────────────────────────────────────────────────────
# 1. Force Atomic on one namesake must not sweep in the other
#    (AC: "two same-named sources produce two independent confirmed
#    items"; also proves `already_in` no longer cross-suppresses)
# ──────────────────────────────────────────────────────────────────────

def test_force_atomic_on_one_namesake_does_not_promote_the_other(tmp_path):
    doc = "\n".join(
        _doc_header()
        + ["## Daily Notes Updates", "", "### [[2026-09-06]]", ""]
        + _daily_log_entry_block("Places/Meeting", force_atomic=True)
        + ["## Suggestions", "", "### S01 — Places Meeting", ""]
        + _atomic_block("Places/Meeting", "Places Meeting", accept=False)
        + ["### S02 — Other Meeting", ""]
        + _atomic_block("Other/Meeting", "Other Meeting", accept=False)
    )
    out = _run_parser(tmp_path, doc)

    assert _source_paths(out["confirmed_items"]) == ["Places/Meeting"], (
        "Force Atomic Note on Places/Meeting must not also promote the "
        "unrelated namesake Other/Meeting"
    )
    skipped_paths = _source_paths(out["skipped"])
    assert "Other/Meeting" in skipped_paths, (
        "Other/Meeting was never approved and never force-atomic'd — it "
        "must stay skipped, not be swept in by a colliding stem key"
    )


# ──────────────────────────────────────────────────────────────────────
# 2. `seen_pending` must track namesakes independently
# ──────────────────────────────────────────────────────────────────────

def test_seen_pending_does_not_suppress_a_namesakes_park(tmp_path):
    doc = "\n".join(
        _doc_header()
        + ["## Daily Notes Updates", "", "### [[2026-09-06]]", ""]
        + _daily_log_entry_block("Places/Diary", force_atomic=True)
        + _daily_log_entry_block("Other/Diary", force_atomic=True)
        + ["## Suggestions", ""]
    )
    out = _run_parser(tmp_path, doc)

    pending_paths = {p["source_path"] for p in out["pending_fan_resolutions"]}
    assert pending_paths == {"Places/Diary.md", "Other/Diary.md"}, (
        "both namesakes have Force Atomic Note ticked with no matching "
        "section anywhere — both must be parked for the resolve subflow, "
        "not just the first one processed"
    )


# ──────────────────────────────────────────────────────────────────────
# 3. A proposed MOC binds to the source that justified it
# ──────────────────────────────────────────────────────────────────────

def test_proposed_moc_binds_to_justifying_source_not_namesake(tmp_path):
    doc = "\n".join(
        _doc_header()
        + ["## Suggestions", "", "### S01 — Places Weimar", ""]
        + _atomic_block("Places/Weimar", "Places Weimar", accept=True)
        + ["### S02 — Other Weimar", ""]
        + _atomic_block("Other/Weimar", "Other Weimar", accept=True)
        + [
            "## Proposed MOCs",
            "",
            "### Proposed MOC: Weimar Trip",
            "",
            "- [x] Approve",
            "- [ ] Skip",
            "",
            "**Name:** Weimar Trip (MOC)",
            "**Parent:** [[2700 - Art  Recreation]]",
            "**Supporting items:**",
            "",
        ]
    )
    suggestions_doc = {
        "sections": [
            {"id": "S01", "stem": "Places/Weimar"},
            {"id": "S02", "stem": "Other/Weimar"},
        ],
        # Only S01 justified the proposed MOC — S02 is an unrelated namesake.
        "proposed_mocs": [{"topic": "Weimar Trip", "items": ["S01"]}],
    }
    out = _run_parser(tmp_path, doc, suggestions_doc=suggestions_doc)

    by_path = {c["source_path"]: c["id"] for c in out["confirmed_items"] if c.get("source_path")}
    moc = next(c for c in out["confirmed_items"] if c.get("action") == "create_moc")

    assert moc["supporting_items"] == by_path["Places/Weimar"], (
        "the MOC must bind to S01 (Places/Weimar), the source recorded in "
        "the structured doc — not to its namesake Other/Weimar"
    )
    assert by_path["Other/Weimar"] not in (moc.get("supporting_items") or ""), (
        "Other/Weimar never justified this MOC and must not appear in its "
        "supporting_items"
    )


# ──────────────────────────────────────────────────────────────────────
# 4. #165 stays fixed for a subfolder source (the existing regression
#    fixture is flat and would not catch a re-introduced collapse)
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


def _primary_doc_165(stem: str, *, ticked: bool) -> str:
    return "\n".join(
        _doc_header()
        + ["## Suggestions", "", f"### S01 — {stem}", _suppressed_block(stem, ticked=ticked), ""]
    )


def _resolve_doc_165(stem: str) -> str:
    return "\n".join([
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-06T10:05:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-09-06T10-05-00Z-test034t26",
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
        "- Items processed: 1",
        "",
        "## Suggestions",
        "",
        f"### S01 — {stem} resolved",
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
    ])


def test_165_suppressed_force_atomic_resolves_for_a_subfolder_source(tmp_path):
    """Same livelock scenario as #165's original regression test, but the
    source now lives in a subfolder — the original fixture is flat and
    would stay green even if the derivation collapsed namesakes again."""
    stem = "Places/Bautzen"
    ppath = tmp_path / "2026-09-06_1000_suggestions.md"
    ppath.write_text(_primary_doc_165(stem, ticked=True), encoding="utf-8")
    rpath = tmp_path / "2026-09-06_1005_suggestions-fan.md"
    rpath.write_text(_resolve_doc_165(stem), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable, str(PARSER),
            "--file", str(ppath),
            "--fan-resolve-file", str(rpath),
        ],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, f"parser exit {proc.returncode}\n{proc.stderr}"
    out = json.loads(proc.stdout)

    assert _source_paths(out["confirmed_items"]) == [stem], (
        "the approved resolve-doc proposal for a subfolder source must be "
        "consumed, not re-parked"
    )
    assert out["pending_fan_resolutions"] == [], (
        "subfolder source was re-parked despite an approved resolve "
        "proposal — #165's livelock, reintroduced for the subfolder case"
    )


# ──────────────────────────────────────────────────────────────────────
# 5. The daily-log path and the primary/resolve-doc path agree, because
#    they derive identity through the same function
# ──────────────────────────────────────────────────────────────────────

def test_item_key_of_is_one_module_level_function_used_by_both_paths():
    """`_item_key_of` must be reachable at module scope (not a `main()`-
    local closure) so both call sites are provably the same callable, and
    it must preserve a path-qualified value verbatim — no basename
    extraction, no lowercasing (ADR-1)."""
    assert hasattr(_parser, "_item_key_of"), (
        "_item_key_of must be a module-level function, not nested inside "
        "main(), or the daily-log and primary/resolve-doc call sites "
        "cannot be proven to share one implementation"
    )

    # The value as it arrives from a primary/resolve-doc **Source:** wikilink.
    from_primary_doc = "Places/Weimar"
    # The value as it arrives from a daily-log "- Source:" wikilink.
    from_daily_log = "Places/Weimar"

    key_a = _parser._item_key_of(from_primary_doc)
    key_b = _parser._item_key_of(from_daily_log)

    assert key_a == key_b == "Places/Weimar", (
        "both paths must derive the identical, verbatim item key for the "
        "same path-qualified source"
    )

    # A different subfolder note with the same basename must NOT collapse
    # to the same key — the whole point of ADR-1.
    assert _parser._item_key_of("Other/Weimar") != key_a

    # Verbatim: no lowercasing, no folder/extension stripping.
    assert _parser._item_key_of("Places/Weimar.md") == "Places/Weimar.md"
    assert _parser._item_key_of("PLACES/Weimar") == "PLACES/Weimar"

    # Falsy input degrades to "" at both call sites (existing `if stem:`
    # guards throughout the reconciliation pass depend on this).
    assert _parser._item_key_of(None) == ""
    assert _parser._item_key_of("") == ""
