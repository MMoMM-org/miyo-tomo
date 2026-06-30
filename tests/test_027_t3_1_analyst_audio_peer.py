#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t3_1_analyst_audio_peer.py — Contract tests for T3.1 (spec 027 / ADR-2).

Verifies that inbox-analyst.md gained audio_peer extraction from transcript
frontmatter source: key, and that item-result.schema.json declares audio_peer
as an allowed field on create_atomic_note.

Strategy: prose-contract assertions on the agent file + jsonschema fixture
validation.  The agent is LLM-loaded at runtime — the contract tests ensure
the right instructions are present, not that the LLM executes them exactly.

Tests are RED against the current file (no audio_peer) and GREEN after T3.1.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
AGENT_PATH = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "item-result.schema.json"


def _agent_text() -> str:
    assert AGENT_PATH.exists(), f"Agent file not found: {AGENT_PATH}"
    return AGENT_PATH.read_text()


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _step2_text() -> str:
    """Extract Step 2 section (between '### Step 2' and '### Step 2b')."""
    text = _agent_text()
    start = text.find("### Step 2 —")
    end = text.find("### Step 2b")
    assert start != -1, "'### Step 2 —' not found in agent file"
    assert end != -1, "'### Step 2b' not found in agent file"
    return text[start:end]


def _voice_detection_text() -> str:
    """Extract the Voice-transcript detection paragraph from Step 7."""
    text = _agent_text()
    start = text.find("**Voice-transcript detection.**")
    end = text.find("**`force_atomic=true` override.**")
    assert start != -1, "'**Voice-transcript detection.**' not found in agent file"
    assert end != -1, "'**`force_atomic=true` override.**' not found in agent file"
    return text[start:end]


def _step9_text() -> str:
    """Extract Step 9 section (between '### Step 9' and '### Step 10')."""
    text = _agent_text()
    start = text.find("### Step 9")
    end = text.find("### Step 10")
    assert start != -1, "'### Step 9' not found in agent file"
    assert end != -1, "'### Step 10' not found in agent file"
    return text[start:end]


def _step10_text() -> str:
    """Extract Step 10 section (between '### Step 10 —' and '### Step 10b')."""
    text = _agent_text()
    start = text.find("### Step 10 —")
    end = text.find("### Step 10b")
    assert start != -1, "'### Step 10 —' not found in agent file"
    assert end != -1, "'### Step 10b' not found in agent file"
    return text[start:end]


# ── Contract tests — agent prose ──────────────────────────────────────────────


def test_step2_extracts_source_frontmatter_key():
    """Step 2 Extract list must mention the source: frontmatter key (ADR-2)."""
    step2 = _step2_text()
    assert "source:" in step2, (
        "Step 2 Extract list must mention 'source:' — the audio peer key "
        "written to transcript frontmatter by voice_render.py (T3.1 / ADR-2)"
    )


def test_voice_detection_emits_audio_peer():
    """Voice-transcript detection section must instruct emission of audio_peer (ADR-2)."""
    vd = _voice_detection_text()
    assert "audio_peer" in vd, (
        "Voice-transcript detection section must mention 'audio_peer' — "
        "the field derived from transcript frontmatter source: key (T3.1 / ADR-2)"
    )


def test_voice_detection_derives_vault_relative_path():
    """Voice detection must instruct combining transcript directory + source filename."""
    vd = _voice_detection_text()
    # The analyst must resolve source: into a vault-relative path by
    # combining the transcript's directory with the source filename.
    # Check for language indicating this combination step.
    has_dir_combine = (
        "directory" in vd
        or "dir" in vd.lower()
        or "path" in vd
    )
    assert has_dir_combine, (
        "Voice-transcript detection must describe combining the transcript "
        "path directory with the source: filename to form a vault-relative "
        "audio_peer path (T3.1 / ADR-2)"
    )


def test_step9_stamps_audio_peer_on_atomic_notes():
    """Step 9 must instruct stamping audio_peer on create_atomic_note for voice items."""
    step9 = _step9_text()
    assert "audio_peer" in step9, (
        "Step 9 must mention 'audio_peer' for create_atomic_note voice items (T3.1)"
    )


def test_step10_placeholder_table_includes_audio_peer():
    """Step 10.2 placeholder table must include an audio_peer row."""
    step10 = _step10_text()
    assert "audio_peer" in step10 or "AUDIO_PEER" in step10, (
        "Step 10.2 placeholder table must include an audio_peer / AUDIO_PEER row "
        "so the LLM knows how to fill the field (T3.1)"
    )


# ── Schema tests ──────────────────────────────────────────────────────────────


def test_schema_declares_audio_peer_on_create_atomic_note():
    """item-result.schema.json must declare audio_peer in create_atomic_note properties."""
    schema = _schema()
    can_props = schema["$defs"]["create_atomic_note"]["properties"]
    assert "audio_peer" in can_props, (
        "item-result.schema.json create_atomic_note must declare 'audio_peer' "
        "property — schema has additionalProperties:false so undeclared fields "
        "fail validation (T3.1 / ADR-2)"
    )


def test_schema_audio_peer_is_string_or_null():
    """audio_peer schema type must allow string and null (optional field)."""
    schema = _schema()
    ap = schema["$defs"]["create_atomic_note"]["properties"]["audio_peer"]
    # Accept either {"type": ["string", "null"]} or {"oneOf": [...]}
    type_val = ap.get("type", [])
    if isinstance(type_val, list):
        assert "string" in type_val and "null" in type_val, (
            f"audio_peer type must be ['string', 'null']; got {type_val!r}"
        )
    else:
        # oneOf form
        assert "oneOf" in ap, (
            f"audio_peer must be string|null; got schema: {ap!r}"
        )


# ── Fixture validation ────────────────────────────────────────────────────────


def _minimal_result(audio_peer=None) -> dict:
    """Minimal valid item-result fixture; optionally adds audio_peer."""
    action: dict = {
        "kind": "create_atomic_note",
        "source_stem": "2026-04-08-interview",
        "suggested_title": "Interview Notes",
        "template": "atomic_note",
        "location": "100 Inbox/",
        "candidate_mocs": [],
        "tags_to_add": [],
        "atomic_note_worthiness": 0.8,
        "alternatives": [],
    }
    if audio_peer is not None:
        action["audio_peer"] = audio_peer
    return {
        "schema_version": "1",
        "stem": "2026-04-08-interview",
        "path": "100 Inbox/2026-04-08-interview.md",
        "type": "fleeting_note",
        "type_confidence": 0.7,
        "actions": [action],
    }


def test_audio_peer_present_validates_against_schema():
    """A result with audio_peer set to a vault-relative path must validate (T3.1)."""
    fixture = _minimal_result(audio_peer="100 Inbox/2026-04-08_1430_interview.m4a")
    schema = _schema()
    jsonschema.validate(instance=fixture, schema=schema)  # raises on failure


def test_audio_peer_null_validates_against_schema():
    """A result with audio_peer=null (explicit None) must validate (non-voice items)."""
    fixture = _minimal_result(audio_peer=None)
    # Explicitly set null in the action
    fixture["actions"][0]["audio_peer"] = None
    schema = _schema()
    jsonschema.validate(instance=fixture, schema=schema)


def test_audio_peer_absent_validates_against_schema():
    """A result without audio_peer key at all must still validate (non-voice items)."""
    fixture = _minimal_result()  # no audio_peer key
    schema = _schema()
    jsonschema.validate(instance=fixture, schema=schema)
