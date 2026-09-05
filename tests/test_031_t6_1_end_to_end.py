#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t6_1_end_to_end.py — spec 031 T6.1 end-to-end pipeline test.

Drives the pipeline's PUBLIC entry points, not internal helpers
[ref: memory: mock at orchestrator, not helper]:

  inbox-triage.build_attachment_index / resolve_inbox_attachments  (real ADR-1
    resolution — the recursive index + listNotes(fields=["links"]) call —
    against a FAKE Kado client, no live vault)
    -> resolved-attachments.json
  suggestions-reducer.py   (subprocess CLI, --resolved-attachments)
    -> suggestions-doc.json
  suggestions-render.py    (subprocess CLI)
    -> suggestions.md
  suggestion-parser.py     (subprocess CLI, after ticking [x] Approved)
    -> parsed JSON (confirmed_items[].attachments)
  lib.render_actions.build_actions   (the render orchestrator instruction-
    render.py's main() calls internally — driven directly here to avoid a
    live-Kado template-read dependency, matching the established pattern in
    tests/test_031_t2_6_phase2_validation.py)
    -> actions (move_note + move_asset)
  instructions-diff.run_diff / instructions-dryrun.main
    -> reconciliation + dry-run validation

The fixture mirrors the SDD's own ADR-1 traced walkthrough: notes live in
100 Inbox/Places/, images live in a SIBLING folder 100 Inbox/Images/ — NOT
co-located with the notes. Co-locating them would let the test pass whether
resolution actually works or silently falls back to a same-folder ("sibling
assumption") guess, which is the exact failure ADR-1 exists to prevent.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"

REDUCER = SCRIPTS_DIR / "suggestions-reducer.py"
RENDER = SCRIPTS_DIR / "suggestions-render.py"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"


def _load_mod(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


triage = _load_mod("inbox_triage_t61", "inbox-triage.py")
diff = _load_mod("instructions_diff_t61", "instructions-diff.py")
dryrun = _load_mod("instructions_dryrun_t61", "instructions-dryrun.py")

from lib.render_actions import build_actions  # noqa: E402

CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


# ---------------------------------------------------------------------------
# ADR-1 resolution — real inbox-triage.py functions, fake Kado client
# ---------------------------------------------------------------------------

def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _note_entry(path: str, embed_targets: list[str]) -> dict:
    return {"path": path, "links": [{"target": t, "kind": "embed"} for t in embed_targets]}


class _FakeClient:
    """Only what build_attachment_index/resolve_inbox_attachments call.

    depth=1 deliberately returns EMPTY — this fixture's notes and images
    both live in subfolders (Places/, Images/), never at the inbox root, so
    a regression that resolves against the depth=1 listing instead of the
    real recursive one would find nothing and this fixture would catch it.
    A fake that returned recursive_items regardless of depth would let that
    exact class of bug through undetected.
    """

    def __init__(self, recursive_items: list[dict], notes: list[dict]):
        self._recursive_items = recursive_items
        self._notes = notes

    def list_dir(self, path, *, depth=None, limit=500):
        if depth == 1:
            return []
        return self._recursive_items

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        return self._notes


def _resolve_and_persist(tmp_path: Path, recursive_items: list[dict], notes: list[dict]) -> Path:
    """Runs the real ADR-1 chain and writes resolved-attachments.json."""
    client = _FakeClient(recursive_items, notes)
    index = triage.build_attachment_index(client, INBOX_PATH)
    resolutions = triage.resolve_inbox_attachments(client, INBOX_PATH, index)
    out_path = tmp_path / "resolved-attachments.json"
    out_path.write_text(json.dumps(resolutions), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Reducer -> render -> parser (subprocess, public CLI entry points)
# ---------------------------------------------------------------------------

def _make_item_result(stem: str, *, title: str) -> dict:
    return {
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/Places/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "date_relevance": None,
        "issues": [],
        "duration_ms": 100,
        "actions": [{
            "kind": "create_atomic_note",
            "source_stem": stem,
            "suggested_title": title,
            "template": "Atomic Note.md",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [
                {"path": "Atlas/200 Maps/Home (MOC).md", "score": 0.6, "pre_check": False}
            ],
            "tags_to_add": [],
            "atomic_note_worthiness": 0.8,
            "classification": None,
        }],
    }


def _write_state(tmp_path: Path, stems: list[str]) -> Path:
    state_path = tmp_path / "state.jsonl"
    lines = [
        json.dumps({
            "stem": stem, "status": "done", "run_id": "t6-1-run",
            "started_at": "2026-09-06T09:00:00Z", "finished_at": "2026-09-06T09:00:01Z",
        })
        for stem in stems
    ]
    state_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return state_path


def _write_shared_ctx(tmp_path: Path) -> Path:
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps({"field_sections": {}}), encoding="utf-8")
    return p


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode}):\n"
        f"stderr: {result.stderr}\nstdout: {result.stdout[:800]}"
    )
    return result


def _parsed_confirmed_items(
    tmp_path: Path, item_results: dict[str, dict], resolved_attachments_path: Path,
) -> list[dict]:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    for stem, result in item_results.items():
        (items_dir / f"{stem}.result.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
    state_path = _write_state(tmp_path, list(item_results.keys()))
    shared_ctx_path = _write_shared_ctx(tmp_path)

    doc_path = tmp_path / "suggestions-doc.json"
    _run([
        sys.executable, str(REDUCER),
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", "t6-1-run",
        "--profile", "miyo",
        "--output", str(doc_path),
        "--shared-ctx", str(shared_ctx_path),
        "--resolved-attachments", str(resolved_attachments_path),
    ])
    assert doc_path.exists()

    md_path = tmp_path / "suggestions.md"
    _run([sys.executable, str(RENDER), "--input", str(doc_path), "--output", str(md_path)])
    assert md_path.exists()

    md_text = md_path.read_text(encoding="utf-8")
    md_text = md_text.replace("- [ ] Approved", "- [x] Approved", 1)
    md_path.write_text(md_text, encoding="utf-8")

    result = _run([sys.executable, str(PARSER), "--file", str(md_path)])
    return json.loads(result.stdout)["confirmed_items"]


# ---------------------------------------------------------------------------
# Build actions the way instruction-render.py's main() would, minus the
# live-Kado template read (same simplification test_031_t2_6 already uses).
# ---------------------------------------------------------------------------

def _stem_of(source_path: str) -> str:
    return Path(source_path).stem


def _manifest_from_confirmed(confirmed: list[dict]) -> list[dict]:
    return [
        {
            "id": item["id"],
            "action": item.get("action"),
            "title": item.get("title") or _stem_of(item["source_path"]),
            "source_path": item["source_path"],
            "rendered_file": f"2026-09-06_1200_{_stem_of(item['source_path'])}.md",
            "destination": "Atlas/202 Notes/",
            "parent_moc": item.get("parent_moc") or "",
            "parent_mocs": item.get("parent_mocs") or [],
            "tags": item.get("tags") or [],
            "attachments": item.get("attachments") or [],
        }
        for item in confirmed
    ]


def _instructions_envelope(actions: list[dict]) -> dict:
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-09-06T12:00:00Z",
        "profile": "miyo",
        "action_count": len(actions),
        "actions": actions,
    }


def _parsed_envelope(confirmed: list[dict]) -> dict:
    return {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_end_to_end_pipeline_produces_move_note_and_move_asset(tmp_path):
    """The SDD's own ADR-1 walkthrough, driven end to end: two notes in
    100 Inbox/Places/ embed images by bare filename from the SIBLING folder
    100 Inbox/Images/ — resolution must find them there, not assume the
    embed lives beside its note."""
    recursive_items = [
        _listdir_item(INBOX_PATH + "Places/Dresden.md"),
        _listdir_item(INBOX_PATH + "Places/Prag.md"),
        _listdir_item(INBOX_PATH + "Images/karte.jpg"),
        _listdir_item(INBOX_PATH + "Images/prag-karte.jpg"),
    ]
    notes = [
        _note_entry(INBOX_PATH + "Places/Dresden.md", ["karte.jpg"]),
        _note_entry(INBOX_PATH + "Places/Prag.md", ["prag-karte.jpg"]),
    ]
    resolved_path = _resolve_and_persist(tmp_path, recursive_items, notes)
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    assert resolved[INBOX_PATH + "Places/Dresden.md"]["attachments"] == [
        INBOX_PATH + "Images/karte.jpg"
    ]
    assert resolved[INBOX_PATH + "Places/Prag.md"]["attachments"] == [
        INBOX_PATH + "Images/prag-karte.jpg"
    ]

    item_results = {
        "Dresden": _make_item_result("Dresden", title="Dresden — Snow city"),
        "Prag": _make_item_result("Prag", title="Prag — Old town"),
    }
    confirmed = _parsed_confirmed_items(tmp_path, item_results, resolved_path)
    # source_path downstream of the parser is the wikilink stem (how this
    # pipeline names a note everywhere), not the vault-relative path — the
    # attachments field is the new, spec-031 field that DOES carry full paths.
    assert {c["source_path"] for c in confirmed} == {"Dresden", "Prag"}
    for c in confirmed:
        if c["source_path"] == "Dresden":
            assert c["attachments"] == [INBOX_PATH + "Images/karte.jpg"]
        else:
            assert c["attachments"] == [INBOX_PATH + "Images/prag-karte.jpg"]

    manifest = _manifest_from_confirmed(confirmed)
    actions, _skipped_assets = build_actions(manifest, confirmed, [], [], CFG)

    move_notes = [a for a in actions if a["action"] == "move_note"]
    move_assets = [a for a in actions if a["action"] == "move_asset"]
    assert len(move_notes) == 2
    assert {a["source"] for a in move_assets} == {
        INBOX_PATH + "Images/karte.jpg", INBOX_PATH + "Images/prag-karte.jpg",
    }
    assert all(
        a["destination"].startswith("Atlas/290 Assets/295 Attachments/")
        for a in move_assets
    )

    # Schema validation (AC-F4.4)
    from lib.render_resolve import _strip_internal_link_fields
    _strip_internal_link_fields(actions)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instrs = _instructions_envelope(actions)
    validate(instance=instrs, schema=schema)

    # instructions-diff reconciles (AC-F5.1)
    parsed = _parsed_envelope(confirmed)
    rc, observations = diff.run_diff(parsed, instrs)
    assert rc == 0, f"diff must reconcile with no mismatch, observations={observations}"

    # instructions-dryrun exits 0 (AC-F5.4)
    instrs_path = tmp_path / "instructions.json"
    instrs_path.write_text(json.dumps(instrs), encoding="utf-8")
    argv = sys.argv
    try:
        sys.argv = ["instructions-dryrun.py", str(instrs_path), "--quiet"]
        dry_rc = dryrun.main()
    finally:
        sys.argv = argv
    assert dry_rc == 0


def test_shared_image_embedded_by_two_notes_yields_one_action(tmp_path):
    """Two approved notes embedding the SAME image -> exactly one move_asset
    action (global dedup), proven through the full chain (AC-F4.2)."""
    recursive_items = [
        _listdir_item(INBOX_PATH + "Places/Berlin.md"),
        _listdir_item(INBOX_PATH + "Places/Hamburg.md"),
        _listdir_item(INBOX_PATH + "Images/shared.jpg"),
    ]
    notes = [
        _note_entry(INBOX_PATH + "Places/Berlin.md", ["shared.jpg"]),
        _note_entry(INBOX_PATH + "Places/Hamburg.md", ["shared.jpg"]),
    ]
    resolved_path = _resolve_and_persist(tmp_path, recursive_items, notes)

    item_results = {
        "Berlin": _make_item_result("Berlin", title="Berlin — Capital"),
        "Hamburg": _make_item_result("Hamburg", title="Hamburg — Port city"),
    }
    confirmed = _parsed_confirmed_items(tmp_path, item_results, resolved_path)
    manifest = _manifest_from_confirmed(confirmed)
    actions, _skipped_assets = build_actions(manifest, confirmed, [], [], CFG)

    move_assets = [a for a in actions if a["action"] == "move_asset"]
    assert len(move_assets) == 1, f"expected 1 deduped move_asset, got {move_assets}"
    assert move_assets[0]["source"] == INBOX_PATH + "Images/shared.jpg"
