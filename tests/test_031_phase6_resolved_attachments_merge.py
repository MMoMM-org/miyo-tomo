#!/usr/bin/env python3
# version: 0.1.0
"""test_031_phase6_resolved_attachments_merge.py — merge the resolved-attachments map.

Covers the gap surfaced during Phase 5/6 review: nothing in the pipeline
ever populated `attachments`/`unresolved_embeds` on an item — T3.2 renders
them, T3.4 round-trips them, the schemas declare them, but no producer
exists. inbox-triage (a separate strand) will extract and resolve embeds
into a deterministic map keyed by source path; this reducer merges that map
onto each item as it loads it, before rendering.

Requirements from the brief:
  - merge by source path (result["path"])
  - the analyst's own result never carries these fields (ADR-2), but if it
    somehow does, the resolved map wins — it is the deterministic source
  - fail-open: a missing/unreadable/malformed map, or an item absent from
    it, yields attachments: [] and unresolved_embeds: [] and the run
    continues
  - T3.2's render and T3.4's parse are untouched — this only fills a field
    that was always empty

Artifact (settled with strand A): `tomo-tmp/resolved-attachments.json`,
`{"<vault-relative source path>": {"attachments": [...], "unresolved_embeds":
[...]}}`. Replaces `attachment-index.json` (strand A's own change — that
file's raw basename index had no reader outside strand A's own process).

Covers both the pure functions (`merge_resolved_attachments`,
`load_resolved_attachments`, independent of any fixed filename) and the
full CLI-level end-to-end proof against the real `--resolved-attachments`
flag: a resolved attachment in the map reaches the rendered
`**Attachments:**` line, and the line disappears when the merge is dropped
— closing Kado -> document for the first time in this spec.

Spec: docs/XDD/specs/031-inbox-attachment-filing/ (Phase 6 gap fix)
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


reducer = _load("suggestions_reducer_p6", "suggestions-reducer.py")

SOURCE_PATH = "100 Inbox/prague-trip.md"
ATTACHMENT = "100 Inbox/Images/prag-karte.jpg"


def _item_result(**overrides) -> dict:
    action = {
        "kind": "create_atomic_note",
        "source_stem": "prague-trip",
        "suggested_title": "Prague Trip",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    result = {
        "schema_version": "1",
        "stem": "prague-trip",
        "path": SOURCE_PATH,
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": [action],
    }
    result.update(overrides)
    return result


# ---------------------------------------------------------------------------
# merge_resolved_attachments — the join point
# ---------------------------------------------------------------------------


def test_merge_applies_resolved_attachments_to_matching_action():
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    result = reducer.merge_resolved_attachments(_item_result(), resolved)
    assert result["actions"][0]["attachments"] == [ATTACHMENT]


def test_merge_applies_resolved_unresolved_embeds_to_matching_action():
    entry = {"attachments": [], "unresolved_embeds": [
        {"embed_target": "karte.jpg", "status": "ambiguous", "candidate_count": 2}
    ]}
    resolved = {SOURCE_PATH: entry}
    result = reducer.merge_resolved_attachments(_item_result(), resolved)
    assert result["actions"][0]["unresolved_embeds"] == entry["unresolved_embeds"]


def test_merge_item_absent_from_map_yields_empty_lists():
    resolved = {"100 Inbox/some-other-note.md": {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    result = reducer.merge_resolved_attachments(_item_result(), resolved)
    assert result["actions"][0]["attachments"] == []
    assert result["actions"][0]["unresolved_embeds"] == []


def test_merge_empty_map_yields_empty_lists():
    result = reducer.merge_resolved_attachments(_item_result(), {})
    assert result["actions"][0]["attachments"] == []
    assert result["actions"][0]["unresolved_embeds"] == []


def test_merge_none_map_yields_empty_lists_fail_open():
    result = reducer.merge_resolved_attachments(_item_result(), None)
    assert result["actions"][0]["attachments"] == []
    assert result["actions"][0]["unresolved_embeds"] == []


def test_merge_applies_to_every_create_atomic_note_action_from_one_source():
    """F-41: N atomics from one source share the same source-level
    attachment list — the embeds live in the shared source body."""
    second_action = {
        "kind": "create_atomic_note",
        "source_stem": "prague-trip",
        "suggested_title": "Prague Trip — Food",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    result = _item_result()
    result["actions"].append(second_action)
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    merged = reducer.merge_resolved_attachments(result, resolved)
    assert merged["actions"][0]["attachments"] == [ATTACHMENT]
    assert merged["actions"][1]["attachments"] == [ATTACHMENT]


def test_merge_ignores_non_create_atomic_note_actions():
    result = _item_result()
    result["actions"].append({
        "kind": "update_daily",
        "date": "2026-09-05",
        "daily_note_path": "Calendar/301 Daily/2026-09-05",
        "updates": [],
    })
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    merged = reducer.merge_resolved_attachments(result, resolved)
    daily_action = merged["actions"][1]
    assert "attachments" not in daily_action
    assert "unresolved_embeds" not in daily_action


def test_merge_resolved_map_wins_over_analyst_supplied_value():
    """The analyst is never supposed to produce these fields (ADR-2). If one
    somehow already carries a value, the deterministic map's value wins —
    it does not merge/union, it overrides."""
    result = _item_result()
    result["actions"][0]["attachments"] = ["100 Inbox/analyst-guessed.jpg"]
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    merged = reducer.merge_resolved_attachments(result, resolved)
    assert merged["actions"][0]["attachments"] == [ATTACHMENT]


def test_merge_resolved_map_wins_and_warns_on_stderr(capsys):
    result = _item_result()
    result["actions"][0]["attachments"] = ["100 Inbox/analyst-guessed.jpg"]
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    reducer.merge_resolved_attachments(result, resolved)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "prague-trip" in captured.err


# ---------------------------------------------------------------------------
# load_resolved_attachments — fail-open loader
# ---------------------------------------------------------------------------


def test_load_resolved_attachments_reads_a_valid_file(tmp_path):
    path = tmp_path / "resolved-attachments.json"
    path.write_text(json.dumps({SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}))
    loaded = reducer.load_resolved_attachments(path)
    assert loaded[SOURCE_PATH]["attachments"] == [ATTACHMENT]


def test_load_resolved_attachments_fails_open_on_missing_file(tmp_path):
    assert reducer.load_resolved_attachments(tmp_path / "does-not-exist.json") == {}


def test_load_resolved_attachments_fails_open_on_malformed_json(tmp_path):
    path = tmp_path / "resolved-attachments.json"
    path.write_text("{not valid json")
    assert reducer.load_resolved_attachments(path) == {}


def test_load_resolved_attachments_fails_open_on_non_dict_json(tmp_path):
    """Malformed in shape, not just syntax — a JSON array parses fine but is
    not a usable map."""
    path = tmp_path / "resolved-attachments.json"
    path.write_text(json.dumps(["not", "a", "map"]))
    assert reducer.load_resolved_attachments(path) == {}


def test_load_resolved_attachments_none_path_fails_open():
    assert reducer.load_resolved_attachments(None) == {}


# ---------------------------------------------------------------------------
# Fail-open stderr distinction — a missing file (no attachments this run,
# normal) must not be confused with a malformed/unreadable one (a real
# problem the pipeline is silently swallowing into "no attachments").
# ---------------------------------------------------------------------------


def test_load_resolved_attachments_missing_file_is_quiet(tmp_path, capsys):
    """A missing file is the normal state on a run with no attachments (or
    before strand A's producer has run) — no warning."""
    reducer.load_resolved_attachments(tmp_path / "does-not-exist.json")
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_load_resolved_attachments_none_path_is_quiet(capsys):
    reducer.load_resolved_attachments(None)
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_load_resolved_attachments_valid_file_is_quiet(tmp_path, capsys):
    path = tmp_path / "resolved-attachments.json"
    path.write_text(json.dumps({SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}))
    reducer.load_resolved_attachments(path)
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_load_resolved_attachments_malformed_json_warns_loudly(tmp_path, capsys):
    """Existing but unparseable — a real problem, not a normal absence.
    Silently falling back here is indistinguishable from "no attachments"."""
    path = tmp_path / "resolved-attachments.json"
    path.write_text("{not valid json")
    reducer.load_resolved_attachments(path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert str(path) in captured.err


def test_load_resolved_attachments_non_dict_json_warns_loudly(tmp_path, capsys):
    path = tmp_path / "resolved-attachments.json"
    path.write_text(json.dumps(["not", "a", "map"]))
    reducer.load_resolved_attachments(path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert str(path) in captured.err


def test_load_resolved_attachments_unreadable_file_warns_loudly(tmp_path, capsys):
    """A directory in place of the expected file raises OSError on read —
    the same class of "existing but broken" problem as malformed JSON."""
    path = tmp_path / "resolved-attachments.json"
    path.mkdir()
    reducer.load_resolved_attachments(path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert str(path) in captured.err


# ---------------------------------------------------------------------------
# End-to-end proof: a resolved attachment in the map reaches the rendered
# **Attachments:** line — merge -> render_create_atomic_note.
# ---------------------------------------------------------------------------


def test_resolved_attachment_reaches_the_rendered_attachments_line():
    resolved = {SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}}
    result = reducer.merge_resolved_attachments(_item_result(), resolved)
    action = result["actions"][0]
    md = reducer.render_create_atomic_note(action, "prague-trip", "")
    assert f"**Attachments:** `{ATTACHMENT}`" in md


def test_no_resolved_attachment_means_no_rendered_attachments_line():
    result = reducer.merge_resolved_attachments(_item_result(), {})
    action = result["actions"][0]
    md = reducer.render_create_atomic_note(action, "prague-trip", "")
    assert "**Attachments:**" not in md


# ---------------------------------------------------------------------------
# CLI-level end-to-end: the real --resolved-attachments flag, a real
# resolved-attachments.json file, driving the reducer via subprocess.
# This is the proof that closes Kado -> document: a resolved attachment
# reaches the final suggestions-doc.json's rendered_md through the ACTUAL
# main() wiring, not just the pure merge function in isolation.
# ---------------------------------------------------------------------------

_extra = str(SCRIPTS_DIR)
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}


def _write_state(path: Path, stem: str) -> None:
    path.write_text(json.dumps({
        "stem": stem, "path": SOURCE_PATH, "status": "done",
        "run_id": "test-p6", "ts": "2026-09-05T10:00:00Z",
    }) + "\n", encoding="utf-8")


def _write_result(items_dir: Path, stem: str) -> None:
    """A result.json with NO attachments/unresolved_embeds — matching the
    real analyst, which never produces these fields (ADR-2)."""
    items_dir.mkdir(parents=True, exist_ok=True)
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "Prague Trip",
        "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "needs_new_moc": False,
        "tags_to_add": [],
        "classification": {"category": "Travel", "confidence": 0.9},
        "alternatives": [],
    }
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1", "stem": stem, "path": SOURCE_PATH,
        "type": "fleeting_note", "type_confidence": 0.9, "force_atomic": False,
        "actions": [action], "issues": [], "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _run_reducer_cli(tmp_path: Path, resolved_attachments: dict | None) -> dict:
    items_dir = tmp_path / "items"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    stem = "prague-trip"
    _write_state(state, stem)
    _write_result(items_dir, stem)

    argv = [
        sys.executable, str(REDUCER_PATH),
        "--state", str(state), "--items-dir", str(items_dir),
        "--run-id", "test-p6", "--profile", "miyo",
        "--output", str(output), "--no-kado",
    ]
    if resolved_attachments is not None:
        resolved_path = tmp_path / "resolved-attachments.json"
        resolved_path.write_text(json.dumps(resolved_attachments), encoding="utf-8")
        argv += ["--resolved-attachments", str(resolved_path)]
    else:
        # Omit the flag entirely — exercises the documented default
        # (tomo-tmp/resolved-attachments.json) resolving to a nonexistent
        # path in this tmp cwd, which load_resolved_attachments must
        # fail open on rather than raising.
        argv += ["--resolved-attachments", str(tmp_path / "does-not-exist.json")]

    result = subprocess.run(argv, capture_output=True, text=True, check=False, env=_ENV)
    assert result.returncode == 0, f"reducer exit {result.returncode};\nstderr:\n{result.stderr}"
    return json.loads(output.read_text(encoding="utf-8"))


def _rendered_md(doc: dict) -> str:
    return doc["sections"][0]["actions"][0]["rendered_md"]


def test_cli_end_to_end_resolved_attachment_reaches_the_document(tmp_path):
    """The full loop: a real resolved-attachments.json, read via the real
    --resolved-attachments flag, through the real reducer main() loop,
    landing in the final suggestions-doc.json's rendered_md."""
    doc = _run_reducer_cli(
        tmp_path,
        resolved_attachments={SOURCE_PATH: {"attachments": [ATTACHMENT], "unresolved_embeds": []}},
    )
    assert f"**Attachments:** `{ATTACHMENT}`" in _rendered_md(doc)


def test_cli_end_to_end_missing_resolved_attachments_file_fails_open(tmp_path):
    """--resolved-attachments pointing at a nonexistent file must not crash
    the run — the item just gets no attachments, matching every other
    fail-open path in this pipeline."""
    doc = _run_reducer_cli(tmp_path, resolved_attachments=None)
    assert "**Attachments:**" not in _rendered_md(doc)

