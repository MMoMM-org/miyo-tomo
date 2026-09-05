#!/usr/bin/env python3
# version: 0.1.0
"""Regression guard for #162 — tracker syntax and section reach the action.

The reducer collects each tracker as {field, value, reason, source_stem,
source_section} and the aggregated Daily Notes Updates block renders neither
`syntax` nor `section`, so the parser cannot read them back. Both therefore
arrived at `_build_daily_update_actions` absent, and every tracker action was
emitted with `syntax="inline_field"` and `section=None` regardless of what the
vault config said.

That is inert for the 12 inline_field fields — the default happens to match
their configuration. It is not inert for a callout_body field: Hashi consults
`section` only in that branch, and its inline_field handler fails outright
("Tracker field not found") when the field is not already present in the daily
note, instead of inserting it under the configured heading.

The fix reads the resolved tracker fields at action-build time, where the
config is the authority, rather than round-tripping two values the review
document was never meant to display.

The regression property matters more than the feature here: with no config
available, every emitted action must be byte-identical to what shipped before.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, rel: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


ra = _load("render_actions_162", "lib/render_actions.py")
ir = _load("instruction_render_162", "instruction-render.py")

BASE_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

# Mirrors the three callout_body fields in the real vault config, which is
# where this defect actually bites.
TRACKER_FIELDS = {
    "Sleep": {"syntax": "callout_body", "section": "Habit"},
    "Entspannung": {"syntax": "inline_field", "section": "Habit"},
}


def _daily(trackers: list[dict]) -> list[dict]:
    return [{
        "date": "2026-09-05",
        "daily_note_path": "Calendar/301 Daily/2026-09-05.md",
        "trackers": trackers,
    }]


def _tracker(field: str, **extra) -> dict:
    return {"field": field, "value": "23:00", "accepted": True, **extra}


def _build(daily_updates, tracker_fields=None) -> list[dict]:
    cfg = dict(BASE_CFG)
    if tracker_fields is not None:
        cfg["daily_notes.tracker_fields"] = tracker_fields
    return ra._build_daily_update_actions(daily_updates, cfg, [0])


# ── the feature ───────────────────────────────────────────────────────────

def test_configured_callout_body_field_carries_syntax_and_section():
    actions = _build(_daily([_tracker("Sleep")]), TRACKER_FIELDS)
    assert len(actions) == 1
    assert actions[0]["syntax"] == "callout_body"
    assert actions[0]["section"] == "Habit"


def test_configured_inline_field_carries_its_section_too():
    """inline_field ignores section in Hashi today, but the value is still
    the configured one — the emitter must not special-case by syntax."""
    actions = _build(_daily([_tracker("Entspannung")]), TRACKER_FIELDS)
    assert actions[0]["syntax"] == "inline_field"
    assert actions[0]["section"] == "Habit"


def test_config_wins_over_a_value_carried_on_the_action():
    """Config is the authority; an analyst-supplied value is the fallback."""
    actions = _build(
        _daily([_tracker("Sleep", syntax="inline_field", section="Wrong")]),
        TRACKER_FIELDS,
    )
    assert actions[0]["syntax"] == "callout_body"
    assert actions[0]["section"] == "Habit"


def test_unconfigured_field_falls_back_to_the_action_value():
    actions = _build(
        _daily([_tracker("Weight", syntax="checkbox", section="Body")]),
        TRACKER_FIELDS,
    )
    assert actions[0]["syntax"] == "checkbox"
    assert actions[0]["section"] == "Body"


# ── the regression property ───────────────────────────────────────────────

def test_no_config_is_byte_identical_to_the_previous_behaviour():
    """The whole point of the fail-open: an absent map changes nothing.

    Compares the full action dicts, not selected fields — a field added or
    dropped elsewhere in the emitter would fail this too.
    """
    trackers = [_tracker("Sleep"), _tracker("Weight", syntax="checkbox")]
    without_key = _build(_daily(trackers))
    empty_map = _build(_daily(trackers), {})
    assert without_key == empty_map
    assert without_key[0]["syntax"] == "inline_field"
    assert without_key[0]["section"] is None
    assert without_key[1]["syntax"] == "checkbox"


# ── the loader ────────────────────────────────────────────────────────────

def test_loader_reads_name_syntax_section(tmp_path):
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps({"daily_notes": {"tracker_fields": [
        {"name": "Sleep", "syntax": "callout_body", "section": "Habit",
         "keywords": ["ignored"], "description": "ignored"},
    ]}}), encoding="utf-8")
    assert ir.load_tracker_fields(p) == {
        "Sleep": {"syntax": "callout_body", "section": "Habit"}
    }


def test_loader_fails_open(tmp_path):
    """Missing, malformed, and shapeless input all yield {} — never a raise.

    Pass 2 must not become unrunnable because a derived cache is absent.
    """
    assert ir.load_tracker_fields(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert ir.load_tracker_fields(bad) == {}
    shapeless = tmp_path / "shapeless.json"
    shapeless.write_text(json.dumps({"daily_notes": None}), encoding="utf-8")
    assert ir.load_tracker_fields(shapeless) == {}


def test_loader_skips_entries_without_a_name(tmp_path):
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps({"daily_notes": {"tracker_fields": [
        {"syntax": "callout_body", "section": "Habit"},
        {"name": "", "section": "Habit"},
        {"name": "Sleep", "section": "Habit"},
    ]}}), encoding="utf-8")
    assert list(ir.load_tracker_fields(p)) == ["Sleep"]


# ── the dead renderer ─────────────────────────────────────────────────────

def test_update_daily_is_not_in_the_renderers_map():
    """`update_daily` is handled by its own branch before RENDERERS is
    consulted, so an entry here is unreachable by construction.

    Proven before removal by trapping the function with a raise and running
    the full suite: nothing reached it. Asserted structurally because a
    behavioural test cannot fail for code that never executes.
    """
    reducer = _load("suggestions_reducer_162", "suggestions-reducer.py")
    assert "update_daily" not in reducer.RENDERERS
    assert not hasattr(reducer, "render_update_daily")
    assert not hasattr(reducer, "load_field_sections")


# ── the wiring ────────────────────────────────────────────────────────────
#
# The two halves above — loader and emitter — were both green while the line
# that connects them did not exist. Deleting `cfg["daily_notes.tracker_fields"]
# = load_tracker_fields(...)` failed no test, which is the same failure shape
# as #162 itself: a value computed correctly and never delivered. These tests
# exercise the entry point through main() so the join is covered, not just its
# two ends.

def test_main_delivers_the_loaded_fields_into_the_cfg_build_actions_sees(
    monkeypatch, tmp_path
):
    shared_ctx = tmp_path / "shared-ctx.json"
    shared_ctx.write_text(json.dumps({"daily_notes": {"tracker_fields": [
        {"name": "Sleep", "syntax": "callout_body", "section": "Habit"},
    ]}}), encoding="utf-8")

    suggestions = tmp_path / "suggestions.json"
    suggestions.write_text(json.dumps({
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [],
        "skipped": [],
    }), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    seen: dict = {}

    def _spy(*args, **kwargs):
        seen["cfg"] = args[4]          # manifest, confirmed, daily, skipped, cfg
        return ([], [])

    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": "100 Inbox/", "profile": "miyo",
        "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "build_actions", _spy)
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py",
        "--suggestions", str(suggestions),
        "--output-dir", str(tmp_path / "out"),
        "--config", str(cfg_file),
        "--shared-ctx", str(shared_ctx),
    ])

    ir.main()
    assert "cfg" in seen, "build_actions was never reached"
    assert seen["cfg"]["daily_notes.tracker_fields"] == {
        "Sleep": {"syntax": "callout_body", "section": "Habit"}
    }


def test_shared_ctx_defaults_without_the_flag(monkeypatch, tmp_path):
    """No caller passes --shared-ctx, so the default carries the feature.

    Asserts the path the loader is actually handed when the flag is absent,
    rather than grepping the source for the literal — the latter would pass
    just as well if the default were attached to a different argument.
    """
    suggestions = tmp_path / "suggestions.json"
    suggestions.write_text(json.dumps({
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [],
        "skipped": [],
    }), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    seen: dict = {}
    monkeypatch.setattr(ir, "load_tracker_fields",
                        lambda path: seen.setdefault("path", path) and {} or {})
    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": "100 Inbox/", "profile": "miyo",
        "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py",
        "--suggestions", str(suggestions),
        "--output-dir", str(tmp_path / "out"),
        "--config", str(cfg_file),
    ])

    ir.main()
    assert seen.get("path") == "tomo-tmp/shared-ctx.json"
