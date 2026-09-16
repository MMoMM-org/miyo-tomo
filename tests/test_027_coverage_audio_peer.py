"""Spec 027 — coverage audit must count the audio-peer delete_source.

Paired-consumer contract: instruction-render's _build_delete_source_actions emits
TWO delete_source for a confirmed non-kept voice item (transcript + audio peer),
so instructions-diff's derive_expected MUST also count the peer — otherwise every
voice item trips a false coverage mismatch (expected 1, actual 2).

Regression guard for the bug found in live Pass-2 testing: the T3.3 paired delete
shipped without updating its paired consumer (derive_expected). Runs end-to-end
through the real producer (build_actions) + the real audit (run_diff).
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import jsonschema

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "tomo" / "scripts"

_spec_diff = importlib.util.spec_from_file_location(
    "instructions_diff", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec_diff)
assert _spec_diff.loader is not None
_spec_diff.loader.exec_module(diff)

_spec_ir = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec_ir)
assert _spec_ir.loader is not None
_spec_ir.loader.exec_module(ir)

CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _voice_item(keep_source: bool = False) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Shell aliases note",
        "source_path": "voice-note.md",
        "audio_peer": "voice-note.m4a",
        "keep_source": keep_source,
        "parent_mocs": [],
        "tags": [],
        "candidate_mocs": [],
    }


def _voice_manifest() -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Shell aliases note",
        "source_path": "voice-note.md",
        "audio_peer": "voice-note.m4a",
        "rendered_file": "2026-06-30_1200_shell-aliases.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
    }


def _instrs(actions: list[dict]) -> dict:
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "action_count": len(actions),
        "actions": actions,
    }


def _run(parsed: dict, instrs: dict) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, _obs = diff.run_diff(parsed, instrs)
    return rc, buf.getvalue()


def test_renderer_emits_two_deletes_for_voice_item():
    """Sanity: the producer emits transcript + audio delete for a non-kept voice item."""
    actions, _skipped_assets = ir.build_actions([_voice_manifest()], [_voice_item()], [], [], CFG)
    deletes = [a for a in actions if a["action"] == "delete_source"]
    assert len(deletes) == 2, f"expected 2 delete_source (transcript + audio), got {deletes}"


def test_derive_expected_counts_audio_peer():
    """derive_expected must count the audio peer — 2 expected deletes, not 1.

    Without the fix this returns 1 (transcript only) → false coverage mismatch.
    """
    parsed = {"confirmed_items": [_voice_item()], "daily_updates": [], "skipped": []}
    expected = diff.derive_expected(parsed)
    assert expected["counts"]["delete_source"] == 2, (
        f"expected 2 (transcript + audio peer), got {expected['counts']['delete_source']}"
    )


def test_voice_item_coverage_reconciles():
    """End-to-end: a confirmed non-kept voice item reconciles (rc=0), not a mismatch."""
    confirmed = [_voice_item()]
    actions, _skipped_assets = ir.build_actions([_voice_manifest()], confirmed, [], [], CFG)
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    rc, out = _run(parsed, _instrs(actions))
    assert rc == 0, f"voice item must reconcile (expected==actual deletes), got rc={rc}\n{out}"


def test_keep_source_voice_item_reconciles_with_zero_deletes():
    """Keep path: keep_source suppresses both deletes; expected==actual==0 → reconciles."""
    confirmed = [_voice_item(keep_source=True)]
    actions, _skipped_assets = ir.build_actions([_voice_manifest()], confirmed, [], [], CFG)
    deletes = [a for a in actions if a["action"] == "delete_source"]
    assert deletes == [], f"keep_source must suppress BOTH deletes, got {deletes}"
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    rc, out = _run(parsed, _instrs(actions))
    assert rc == 0, f"kept voice item must reconcile at 0 deletes, got rc={rc}\n{out}"


def test_audio_peer_stripped_from_move_note_before_wire():
    """Wire hygiene: the internal audio_peer must be stripped from move_note before
    serialization, else Hashi rejects it (additionalProperties:false → "/actions/N
    must NOT have additional properties"). The strip runs AFTER the delete builder
    consumed it, so the paired audio delete_source survives. Regression for the live
    Hashi validation failure on 2026-07-01.
    """
    confirmed = [_voice_item()]
    actions, _skipped_assets = ir.build_actions([_voice_manifest()], confirmed, [], [], CFG)
    # Pre-strip: build_actions already ran the delete builder → audio delete exists.
    assert any(
        a["action"] == "delete_source" and a["source_path"].endswith(".m4a")
        for a in actions
    ), "audio delete_source must exist before the strip"

    ir._strip_internal_link_fields(actions)

    move = next(a for a in actions if a["action"] == "move_note")
    assert "audio_peer" not in move, "audio_peer must be stripped from move_note before the wire"
    # The paired audio delete_source is a separate action and must survive the strip.
    assert any(
        a["action"] == "delete_source" and a["source_path"].endswith(".m4a")
        for a in actions
    ), "audio delete_source must survive the strip"

    # Strongest guard: the full doc validates against the real wire schema
    # (this is exactly what Hashi does — additionalProperties:false).
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "tomo" / "schemas" / "instructions.schema.json").read_text()
    )
    doc = {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-07-01T00:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }
    jsonschema.validate(doc, schema)
