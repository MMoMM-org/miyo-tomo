#!/usr/bin/env python3
# version: 0.1.0
"""test_031_phase5_attachments_preamble.py — the run-level attachments preamble line.

Covers spec 031 Phase 5 strand B: AC-F3.1's "destination folder" half is a
single run-level line ("Attachments will be filed to `<folder>`."), rendered
once per document and only when at least one item carries attachments — not
per item (T3.2/Phase 3 render source paths only, which is final).

Producer: shared-ctx-builder.py reads concepts.asset from vault-config.yaml
and writes it to shared-ctx.json as `asset_folder`, defaulting to
DEFAULT_ASSET_FOLDER (tomo/scripts/lib/render_actions.py) when unconfigured.

Consumer: suggestions-reducer.py reads `asset_folder` back from shared-ctx.json
(load_asset_folder, fail-open like load_field_sections) and renders the
preamble (render_attachments_preamble) onto suggestions-doc.json's
`attachments_preamble` field. suggestions-render.py splats it into the
document header when non-empty (same pattern as decision_precedence_note).

A round-trip test proves only that producer and consumer agree with each
other, not that either is right — both are written by the same author from
the same assumption (spec 031's own closing lesson). So this file includes
at least one assertion against a hand-written shared-ctx.json fixture that
was NOT produced by shared-ctx-builder.py, independently pinning the
consumer's contract.

Spec: docs/XDD/specs/031-inbox-attachment-filing/ (Phase 5 strand B)
Ref: PRD/AC-F3.1
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"
SHARED_CTX_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "shared-ctx.schema.json"
SUGGESTIONS_DOC_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


scb = _load("shared_ctx_builder_p5b", "shared-ctx-builder.py")
reducer = _load("suggestions_reducer_p5b", "suggestions-reducer.py")
render = _load("suggestions_render_p5b", "suggestions-render.py")

DEFAULT_ASSET_FOLDER = scb.DEFAULT_ASSET_FOLDER
CUSTOM_FOLDER = "Vault/Custom Assets/"


# ---------------------------------------------------------------------------
# Producer — shared-ctx-builder.build_asset_folder
# ---------------------------------------------------------------------------


def test_build_asset_folder_reads_configured_value():
    vault_cfg = {"concepts": {"asset": CUSTOM_FOLDER}}
    assert scb.build_asset_folder(vault_cfg) == CUSTOM_FOLDER


def test_build_asset_folder_defaults_when_concepts_asset_absent():
    vault_cfg = {"concepts": {"inbox": "+/"}}
    assert scb.build_asset_folder(vault_cfg) == DEFAULT_ASSET_FOLDER


def test_build_asset_folder_defaults_when_concepts_block_absent():
    assert scb.build_asset_folder({}) == DEFAULT_ASSET_FOLDER


def test_build_asset_folder_defaults_when_value_is_blank():
    vault_cfg = {"concepts": {"asset": "   "}}
    assert scb.build_asset_folder(vault_cfg) == DEFAULT_ASSET_FOLDER


# ---------------------------------------------------------------------------
# Producer end-to-end — main() writes asset_folder to shared-ctx.json
# ---------------------------------------------------------------------------


def _run_shared_ctx_main(tmp_path: Path, vault_cfg: dict) -> dict:
    cache_file = tmp_path / "cache.yaml"
    vault_cfg_file = tmp_path / "vault-config.yaml"
    out_file = tmp_path / "shared-ctx.json"
    profiles_dir = REPO_ROOT / "tomo" / "profiles"

    cache_file.write_text(yaml.dump({"map_notes": []}))
    vault_cfg_file.write_text(yaml.dump(vault_cfg))

    argv = [
        "shared-ctx-builder.py",
        "--cache", str(cache_file),
        "--vault-config", str(vault_cfg_file),
        "--profiles-dir", str(profiles_dir),
        "--output", str(out_file),
        "--run-id", "test-p5b",
        "--skip-reconcile",
    ]
    with patch("sys.argv", argv), \
         patch.object(scb, "build_tag_prefixes", return_value=[]), \
         patch.object(scb, "build_classification_keywords", return_value={}), \
         patch.object(scb, "build_daily_notes", return_value=None):
        rc = scb.main()
    assert rc == 0, f"shared-ctx-builder main() returned {rc}"
    return json.loads(out_file.read_text())


def test_main_writes_configured_asset_folder(tmp_path):
    ctx = _run_shared_ctx_main(tmp_path, {"profile": "miyo", "concepts": {"asset": CUSTOM_FOLDER}})
    assert ctx["asset_folder"] == CUSTOM_FOLDER


def test_main_writes_default_asset_folder_when_unconfigured(tmp_path):
    ctx = _run_shared_ctx_main(tmp_path, {"profile": "miyo"})
    assert ctx["asset_folder"] == DEFAULT_ASSET_FOLDER


def test_main_output_validates_against_shared_ctx_schema(tmp_path):
    import jsonschema
    ctx = _run_shared_ctx_main(tmp_path, {"profile": "miyo", "concepts": {"asset": CUSTOM_FOLDER}})
    schema = json.loads(SHARED_CTX_SCHEMA.read_text())
    jsonschema.validate(instance=ctx, schema=schema)


# ---------------------------------------------------------------------------
# Consumer — suggestions-reducer.load_asset_folder
#
# Uses a HAND-WRITTEN shared-ctx.json fixture, not one produced by
# shared-ctx-builder.py — independently pins the consumer's contract rather
# than merely proving producer and consumer agree with each other.
# ---------------------------------------------------------------------------


def test_load_asset_folder_reads_independently_derived_fixture(tmp_path):
    """A hand-written shared-ctx.json (not from shared-ctx-builder) with a
    non-default asset_folder is read back exactly."""
    ctx_path = tmp_path / "shared-ctx.json"
    ctx_path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": "hand-written",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
        "asset_folder": "Hand Written/Vault Path/",
    }))
    assert reducer.load_asset_folder(ctx_path) == "Hand Written/Vault Path/"


def test_load_asset_folder_defaults_when_key_absent(tmp_path):
    ctx_path = tmp_path / "shared-ctx.json"
    ctx_path.write_text(json.dumps({
        "schema_version": "1", "run_id": "x", "mocs": [],
        "tag_prefixes": [], "classification_keywords": {},
    }))
    assert reducer.load_asset_folder(ctx_path) == DEFAULT_ASSET_FOLDER


def test_load_asset_folder_fails_open_on_missing_file(tmp_path):
    assert reducer.load_asset_folder(tmp_path / "does-not-exist.json") == DEFAULT_ASSET_FOLDER


def test_load_asset_folder_fails_open_on_malformed_json(tmp_path):
    ctx_path = tmp_path / "shared-ctx.json"
    ctx_path.write_text("{not valid json")
    assert reducer.load_asset_folder(ctx_path) == DEFAULT_ASSET_FOLDER


def test_load_asset_folder_none_path_fails_open():
    assert reducer.load_asset_folder(None) == DEFAULT_ASSET_FOLDER


# ---------------------------------------------------------------------------
# Consumer — render_attachments_preamble
# ---------------------------------------------------------------------------


def _section(*, attachments: list | None = None) -> dict:
    item = {
        "title": "My Note", "template": "t_note_tomo.md", "location": "Atlas/202 Notes/",
        "tags": [], "audio_peer": None, "worthiness": 0.8,
        "suppressed": False, "force_atomic": False,
        "attachments": attachments if attachments is not None else [],
    }
    return {
        "id": "S01", "stem": "memo",
        "actions": [{"kind": "create_atomic_note", "rendered_md": "x", "item": item}],
    }


def test_preamble_empty_when_no_item_has_attachments():
    sections = [_section(), _section()]
    assert reducer.render_attachments_preamble(sections, DEFAULT_ASSET_FOLDER) == ""


def test_preamble_empty_when_sections_list_is_empty():
    assert reducer.render_attachments_preamble([], DEFAULT_ASSET_FOLDER) == ""


def test_preamble_present_when_one_item_has_attachments():
    sections = [_section(), _section(attachments=["100 Inbox/Images/karte.jpg"])]
    preamble = reducer.render_attachments_preamble(sections, DEFAULT_ASSET_FOLDER)
    assert preamble != ""
    assert f"`{DEFAULT_ASSET_FOLDER}`" in preamble


def test_preamble_names_the_configured_folder_not_a_hardcoded_default():
    """Proves the folder is threaded through, not hardcoded — a custom
    configured value must appear verbatim, and the hardcoded default must not."""
    sections = [_section(attachments=["100 Inbox/scan.pdf"])]
    preamble = reducer.render_attachments_preamble(sections, CUSTOM_FOLDER)
    assert f"`{CUSTOM_FOLDER}`" in preamble
    assert DEFAULT_ASSET_FOLDER not in preamble


def test_preamble_rendered_once_not_per_attachment():
    """Two items, each with attachments — still exactly one preamble line
    (a single string, not a per-item repeat)."""
    sections = [
        _section(attachments=["100 Inbox/a.jpg"]),
        _section(attachments=["100 Inbox/b.jpg", "100 Inbox/c.jpg"]),
    ]
    preamble = reducer.render_attachments_preamble(sections, DEFAULT_ASSET_FOLDER)
    assert preamble.count(DEFAULT_ASSET_FOLDER) == 1


# ---------------------------------------------------------------------------
# End-to-end reducer run — hand-written shared-ctx.json + real item-result.json
# ---------------------------------------------------------------------------

_extra = str(SCRIPTS_DIR)
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}


def _write_state(path: Path, stem: str) -> None:
    path.write_text(json.dumps({
        "stem": stem, "path": f"100 Inbox/{stem}.md", "status": "done",
        "run_id": "test-p5b", "ts": "2026-09-05T10:00:00Z",
    }) + "\n", encoding="utf-8")


def _write_result(items_dir: Path, stem: str, attachments: list | None) -> None:
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
    if attachments is not None:
        action["attachments"] = attachments
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1", "stem": stem, "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note", "type_confidence": 0.9, "force_atomic": False,
        "actions": [action], "issues": [], "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _write_hand_written_shared_ctx(path: Path, asset_folder: str) -> None:
    """Independently-derived fixture — hand-written, not produced by
    shared-ctx-builder.py."""
    path.write_text(json.dumps({
        "schema_version": "1", "run_id": "test-p5b", "mocs": [],
        "tag_prefixes": [], "classification_keywords": {},
        "asset_folder": asset_folder,
    }), encoding="utf-8")


def _run_reducer(tmp_path: Path, stem: str, attachments: list | None, asset_folder: str) -> dict:
    items_dir = tmp_path / "items"
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _write_hand_written_shared_ctx(shared_ctx, asset_folder)
    _write_state(state, stem)
    _write_result(items_dir, stem, attachments)

    result = subprocess.run(
        [
            sys.executable, str(REDUCER_PATH),
            "--state", str(state), "--items-dir", str(items_dir),
            "--run-id", "test-p5b", "--profile", "miyo",
            "--shared-ctx", str(shared_ctx), "--output", str(output),
            "--no-kado",
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, f"reducer exit {result.returncode};\nstderr:\n{result.stderr}"
    return json.loads(output.read_text(encoding="utf-8"))


def test_end_to_end_preamble_names_the_independently_configured_folder(tmp_path):
    doc = _run_reducer(tmp_path, "prague-trip", ["100 Inbox/Images/karte.jpg"], "Hand Written/Assets/")
    assert doc["attachments_preamble"] == "Attachments will be filed to `Hand Written/Assets/`."


def test_end_to_end_no_preamble_when_no_attachments(tmp_path):
    doc = _run_reducer(tmp_path, "prague-trip", None, "Hand Written/Assets/")
    assert doc["attachments_preamble"] == ""


def test_end_to_end_doc_validates_against_suggestions_doc_schema(tmp_path):
    import jsonschema
    doc = _run_reducer(tmp_path, "prague-trip", ["100 Inbox/scan.pdf"], "Hand Written/Assets/")
    schema = json.loads(SUGGESTIONS_DOC_SCHEMA.read_text())
    jsonschema.validate(instance=doc, schema=schema)


def test_end_to_end_markdown_header_carries_the_preamble(tmp_path):
    """The final rendered markdown (suggestions-render.py) surfaces the
    preamble line — not just the intermediate suggestions-doc.json."""
    doc = _run_reducer(tmp_path, "prague-trip", ["100 Inbox/scan.pdf"], "Hand Written/Assets/")
    header_lines = render.render_header(doc)
    assert "> Attachments will be filed to `Hand Written/Assets/`." in header_lines


def test_end_to_end_markdown_header_has_no_preamble_when_no_attachments(tmp_path):
    doc = _run_reducer(tmp_path, "prague-trip", None, "Hand Written/Assets/")
    header_lines = render.render_header(doc)
    assert not any("Attachments will be filed" in ln for ln in header_lines)
