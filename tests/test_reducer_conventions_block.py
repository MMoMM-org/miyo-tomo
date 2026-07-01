#!/usr/bin/env python3
# version: 0.1.0
"""test_reducer_conventions_block.py — reducer suffix + conventions block (028 T2.3).

The reducer must:
  1. Emit an additive top-level `conventions` block into suggestions-doc.json,
     carrying the active profile's resolved markers + MOC suffix.
  2. Apply the MOC-title suffix from the resolved profile (not a hardcoded
     " (MOC)") in `_ensure_moc_suffix`.
  3. Keep the existing wire otherwise unchanged and schema-valid.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

_ensure_moc_suffix = _mod._ensure_moc_suffix  # type: ignore[attr-defined]


# ── Unit: _ensure_moc_suffix takes the suffix as a parameter ──────────────────


def test_ensure_moc_suffix_miyo_parity() -> None:
    assert _ensure_moc_suffix("Shell", " (MOC)") == "Shell (MOC)"
    # legacy ' MOC' → suffix conversion preserved
    assert _ensure_moc_suffix("Shell MOC", " (MOC)") == "Shell (MOC)"
    # apply-once
    assert _ensure_moc_suffix("Shell (MOC)", " (MOC)") == "Shell (MOC)"
    # bare "MOC" guard
    assert _ensure_moc_suffix("MOC", " (MOC)") == "MOC"


def test_ensure_moc_suffix_empty_is_noop() -> None:
    assert _ensure_moc_suffix("Shell", "") == "Shell"
    assert _ensure_moc_suffix("Shell MOC", "") == "Shell MOC"


# ── End-to-end: conventions block written to suggestions-doc.json ─────────────


def _run(tmp_path: Path, profile: str) -> dict:
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    items = tmp_path / "items"
    items.mkdir()
    out = tmp_path / f"doc-{profile}.json"
    result = subprocess.run(
        [
            "python3", str(SCRIPT_PATH),
            "--state", str(state),
            "--items-dir", str(items),
            "--run-id", "test-run",
            "--profile", profile,
            "--output", str(out),
            "--shared-ctx", str(tmp_path / "nope.json"),
            "--no-kado",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"reducer failed ({profile}): {result.stderr.decode()}"
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_conventions_block_miyo(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    assert doc["conventions"] == {
        "parent_marker": "up::",
        "peer_marker": "related::",
        "moc_suffix": " (MOC)",
    }


def test_conventions_block_lyt(tmp_path: Path) -> None:
    doc = _run(tmp_path, "lyt")
    assert doc["conventions"]["moc_suffix"] == ""
    assert doc["conventions"]["parent_marker"] == "up::"


def test_doc_still_schema_valid_with_conventions(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)  # must not raise


def test_existing_wire_fields_unchanged(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    # Additive-only: the pre-028 required fields remain present and untouched.
    for key in ("schema_version", "generated", "run_id", "profile", "sections"):
        assert key in doc
    assert doc["profile"] == "miyo"
    assert doc["schema_version"] == "1"


# ── F-55: resolved suffix is threaded into build_topic_clusters ───────────────
#
# The reducer resolves `moc_suffix` from the active profile and must thread it
# into `build_topic_clusters` so `strip_moc_marker` uses the profile marker —
# NOT the hardcoded default "MOC".  Under a no-suffix profile (lyt,
# moc_suffix=""), a proposed-MOC topic that happens to contain the word "MOC"
# must be left intact (empty suffix → strip is a no-op).  If the suffix is not
# threaded, the helper falls back to the default marker and wrongly strips
# "MOC" from the topic.


def _run_with_moc_topic(tmp_path: Path, profile: str, topic: str) -> dict:
    """Run the reducer end-to-end with a single needs_new_moc atomic whose
    proposed_moc_topic is `topic`, and return the emitted doc."""
    items = tmp_path / "items"
    items.mkdir()
    stem = "board-games"
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps({
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "status": "done",
            "run_id": "test-run",
            "ts": "2026-07-01T10:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )
    (items / f"{stem}.result.json").write_text(
        json.dumps({
            "schema_version": "1",
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "type": "fleeting_note",
            "type_confidence": 0.9,
            "force_atomic": False,
            "actions": [{
                "kind": "create_atomic_note",
                "suggested_title": "Board Games Note",
                "atomic_note_worthiness": 0.8,
                "template": "t_note_tomo",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [],
                "needs_new_moc": True,
                "proposed_moc_topic": topic,
                "tags_to_add": [],
                "classification": {"category": "100 Philosophy", "confidence": 0.9},
                "alternatives": [],
            }],
            "candidate_mocs": [],
            "classification": {"category": "100 Philosophy", "confidence": 0.9},
            "needs_new_moc": True,
            "proposed_moc_topic": topic,
            "tags_to_add": [],
            "atomic_note_worthiness": 0.8,
            "alternatives": [],
            "issues": [],
            "duration_ms": 0,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    out = tmp_path / f"doc-{profile}.json"
    result = subprocess.run(
        [
            "python3", str(SCRIPT_PATH),
            "--state", str(state),
            "--items-dir", str(items),
            "--run-id", "test-run",
            "--profile", profile,
            "--output", str(out),
            "--shared-ctx", str(tmp_path / "nope.json"),
            "--no-kado",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"reducer failed ({profile}): {result.stderr.decode()}"
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_lyt_empty_suffix_does_not_strip_moc_from_topic(tmp_path: Path) -> None:
    """lyt profile (moc_suffix="") → a topic ending in "MOC" is NOT stripped.

    RED against the un-threaded call (build_topic_clusters without suffix):
    strip_moc_marker falls back to the default "MOC" marker and yields
    "Board Games". GREEN once the resolved suffix ("" for lyt) is threaded:
    the empty marker makes the strip a no-op and the topic survives verbatim.
    """
    doc = _run_with_moc_topic(tmp_path, "lyt", "Board Games MOC")
    topics = [pm["topic"] for pm in doc.get("proposed_mocs", [])]
    assert topics == ["Board Games MOC"], (
        f"lyt empty suffix must be a no-op; got {topics!r} "
        "(the default 'MOC' marker was wrongly applied)"
    )


def test_miyo_suffix_still_strips_moc_marker(tmp_path: Path) -> None:
    """miyo profile (moc_suffix=' (MOC)') still strips the trailing marker so
    the bare topic is clustered — proves the threaded suffix keeps parity."""
    doc = _run_with_moc_topic(tmp_path, "miyo", "Board Games MOC")
    topics = [pm["topic"] for pm in doc.get("proposed_mocs", [])]
    assert topics == ["Board Games"], f"miyo should strip the marker; got {topics!r}"


# ── F-55 W1: render_create_atomic_note inline **Note:** text threads the suffix ─
#
# The per-item inline "**Note:** ... (topic: *<topic>*)" line calls
# strip_moc_marker on proposed_moc_topic. It must use the RESOLVED profile
# suffix, not the hardcoded default. Under lyt (moc_suffix="") the inline text
# must preserve a topic ending in "MOC"; under miyo it still strips — matching
# the Proposed MOCs section so the two never disagree.


def _atomic_rendered_md(doc: dict) -> str:
    """Return the rendered_md of the first create_atomic_note action in the doc."""
    for section in doc.get("sections", []):
        for action in section.get("actions", []):
            if action.get("kind") == "create_atomic_note":
                return action.get("rendered_md", "")
    return ""


def test_lyt_inline_moc_note_preserves_marker(tmp_path: Path) -> None:
    """lyt (moc_suffix="") → the inline **Note:** topic keeps its "MOC" word.

    RED against the un-threaded call (strip_moc_marker without suffix): the
    default "MOC" marker strips it to "Board Games" in the inline text while the
    Proposed MOCs section preserves it — a visible inconsistency. GREEN once the
    resolved "" suffix is threaded and the strip becomes a no-op.
    """
    doc = _run_with_moc_topic(tmp_path, "lyt", "Board Games MOC")
    md = _atomic_rendered_md(doc)
    assert "topic: *Board Games MOC*" in md, (
        f"lyt inline note must preserve the marker; got rendered_md:\n{md}"
    )
    assert "topic: *Board Games*" not in md


def test_miyo_inline_moc_note_strips_marker(tmp_path: Path) -> None:
    """miyo (moc_suffix=' (MOC)') → the inline **Note:** topic still strips."""
    doc = _run_with_moc_topic(tmp_path, "miyo", "Board Games MOC")
    md = _atomic_rendered_md(doc)
    assert "topic: *Board Games*" in md, (
        f"miyo inline note must strip the marker; got rendered_md:\n{md}"
    )
    assert "topic: *Board Games MOC*" not in md
