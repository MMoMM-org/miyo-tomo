#!/usr/bin/env python3
# version: 0.1.0
"""test_retired_shell_checks.py — checks ported from three retired shell scripts.

`test-004-phase3.sh`, `test-004-phase4.sh` and `test-005-phase1.sh` went stale
after spec 018 and spec 034, and nothing ran them. This file keeps only the
checks that no pytest test covered: the rest of those scripts is covered by
`test_034_t2_4_state_joins_on_item_key.py`, `test_034_t2_3_reducer_reads_by_key.py`,
`test_topic_clusters.py` and `test_shared_ctx_tracker_syntax_from_config.py`.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
AGENTS_DIR = REPO_ROOT / "tomo" / "dot_claude" / "agents"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "test-005-phase1"
TEMPLATE = REPO_ROOT / "tomo" / "templates" / "item-result.template.json"

sys.path.insert(0, str(SCRIPTS_DIR))
from lib.item_key import to_filename  # noqa: E402
from lib.topic_clusters import normalise_topic  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_builder = _load("shared_ctx_builder_retired", "shared-ctx-builder.py")
_validator = _load("validate_result_retired", "validate-result.py")


# ── validate-result.py ───────────────────────────────────────────────────────
# The hints come from `validate_hand`, the path taken when `jsonschema` is not
# installed. With it, the schema answers first and these fixtures are too old
# for it, so the checks call the hand validator directly.


def _hand_errors(name: str) -> list[str]:
    """Validate a fixture written before item_key became a required field."""
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    data["item_key"] = data["path"]
    return _validator.validate_hand(data)


@pytest.mark.parametrize("name", ["valid_mixed_updates.json", "atomic_only.json"])
def test_valid_results_pass(name):
    assert _hand_errors(name) == []


@pytest.mark.parametrize("name, hint", [
    ("alias_log_entry_text.json", "use `content:` instead"),
    ("alias_log_link_target.json", "use `target_stem:` instead"),
    ("alias_tracker_type.json", "use `kind:` instead"),
])
def test_update_alias_is_rejected_with_the_right_hint(name, hint):
    assert any(hint in error for error in _hand_errors(name))


def test_update_without_kind_warns_and_counts_as_tracker(capsys):
    assert _hand_errors("legacy_no_kind.json") == []
    stderr = capsys.readouterr().err
    assert "WARN" in stderr
    assert "treated as tracker" in stderr


# ── item-result template ─────────────────────────────────────────────────────


def test_template_passes_the_hand_validator():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert _validator.validate_hand(template) == []


def test_template_shows_all_three_update_kinds():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    update_daily = next(a for a in template["actions"] if a.get("kind") == "update_daily")
    kinds = {u.get("kind") for u in update_daily["updates"]}
    assert {"tracker", "log_entry", "log_link"} <= kinds


# ── vault-example.yaml ───────────────────────────────────────────────────────


def _example() -> dict:
    return yaml.safe_load((REPO_ROOT / "tomo" / "config" / "vault-example.yaml").read_text(encoding="utf-8"))


def _example_tracker_fields() -> list[dict]:
    trackers = _example()["trackers"]
    return trackers["daily_note_trackers"]["today_fields"] + trackers["end_of_day_fields"]["fields"]


def test_example_has_trackers_in_both_groups():
    trackers = _example()["trackers"]
    assert trackers["daily_note_trackers"]["today_fields"]
    assert trackers["end_of_day_fields"]["fields"]


@pytest.mark.parametrize("field", _example_tracker_fields(), ids=lambda f: f["name"])
def test_example_tracker_field_is_complete(field):
    assert field.get("description", "").strip()
    assert isinstance(field.get("positive_keywords"), list)
    assert isinstance(field.get("negative_keywords"), list)


def test_example_daily_log_never_creates_daily_notes():
    daily_log = _example()["daily_log"]
    assert {"enabled", "section", "heading_level", "time_extraction", "link_format",
            "cutoff_days", "auto_create_if_missing"} <= set(daily_log)
    assert isinstance(daily_log["time_extraction"]["sources"], list)
    assert daily_log["auto_create_if_missing"] == {"past": False, "today": False, "future": False}


# ── Agents ───────────────────────────────────────────────────────────────────


_FORBIDDEN_IN_CODE = [re.compile(r"cat\s*<<\s*'?EOF'?"), re.compile(r';\s*echo\s+"EXIT:')]


@pytest.mark.parametrize("name", ["inbox-analyst.md", "suggestion-conductor.md", "synthesis-conductor.md"])
def test_agent_code_blocks_have_no_heredoc_or_exit_tail(name):
    in_code = False
    for line in (AGENTS_DIR / name).read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif in_code:
            assert not any(p.search(line) for p in _FORBIDDEN_IN_CODE), line


def test_inbox_analyst_has_no_kado_write():
    tools = re.search(r"^tools:.*$", (AGENTS_DIR / "inbox-analyst.md").read_text(encoding="utf-8"), re.M)
    assert tools is not None
    assert "kado-write" not in tools.group(0)


# ── shared-ctx tracker fields ────────────────────────────────────────────────


def _vault_cfg(enabled: bool = True, today: list[dict] | None = None, eod: list[dict] | None = None) -> dict:
    return {
        "concepts": {"calendar": {"granularities": {"daily": {
            "enabled": enabled, "path": "Calendar/301 Daily/",
        }}}},
        "naming": {"calendar_patterns": {"daily": "YYYY-MM-DD"}},
        "trackers": {
            "daily_note_trackers": {"section": "Habits", "today_fields": today or []},
            "end_of_day_fields": {"section": "End of the Day", "fields": eod or []},
        },
    }


def test_tracker_fields_map_types_sections_and_seed_keywords():
    block = _builder.build_daily_notes(_vault_cfg(
        today=[
            {"name": "Sport", "type": "boolean"},
            {"name": "WakeUpEnergy", "type": "integer", "scale": "1–5"},
        ],
        eod=[{"name": "Highlights", "type": "string"}],
    ))
    assert block["enabled"] is True
    fields = {f["name"]: f for f in block["tracker_fields"]}
    assert set(fields) == {"Sport", "WakeUpEnergy", "Highlights"}
    assert (fields["Sport"]["type"], fields["Sport"]["section"]) == ("bool", "Habits")
    assert fields["Sport"]["syntax"] == "inline_field"
    assert fields["WakeUpEnergy"]["type"] == "rating_1_5"
    assert {"wake up energy", "wakeupenergy"} <= set(fields["WakeUpEnergy"]["keywords"])
    assert fields["Highlights"]["type"] == "text"
    assert fields["Highlights"]["syntax"] == "callout_body"
    assert fields["Highlights"]["section"] == "End of the Day"


def test_daily_disabled_builds_no_daily_notes_block():
    cfg = _vault_cfg(enabled=False, today=[{"name": "Sport", "type": "boolean"}])
    assert _builder.build_daily_notes(cfg) is None


def test_custom_keywords_merge_with_seeded_ones():
    block = _builder.build_daily_notes(_vault_cfg(
        today=[{"name": "Sport", "type": "boolean", "keywords": ["Run", "yoga"]}],
    ))
    assert {"sport", "run", "yoga"} <= set(block["tracker_fields"][0]["keywords"])


# ── Topic normalisation ──────────────────────────────────────────────────────


@pytest.mark.parametrize("raw, expected", [
    ("Tools", "tool"),
    ("stories", "story"),
    ("Routines!", "routine"),
    ("shell", "shell"),
    ("", ""),
])
def test_normalise_topic_folds_case_plural_and_punctuation(raw, expected):
    assert normalise_topic(raw) == expected


# ── Reducer: update_daily rendering ──────────────────────────────────────────


RUN_ID = "test-retired"
ITEM_KEY = "100 Inbox/run-log.md"


def _atomic_action() -> dict:
    return {
        "kind": "create_atomic_note",
        "suggested_title": "Morning Run",
        "destination_concept": "atomic_note",
        "candidate_mocs": [{"path": "Atlas/200 Maps/Health (MOC).md", "score": 0.7, "pre_check": True}],
        "classification": {"category": "2200 - Mind-Body Connection", "confidence": 0.6},
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "tags_to_add": ["topic/personal/habits"],
        "atomic_note_worthiness": 0.65,
        "alternatives": [],
    }


def _daily_action() -> dict:
    return {
        "kind": "update_daily",
        "date": "2026-04-15",
        "daily_note_path": "Calendar/301 Daily/2026-04-15",
        "updates": [{
            "kind": "tracker", "field": "WakeUpEnergy", "value": 3, "syntax": "inline_field",
            "section": "Habits", "confidence": 0.8, "reason": "Mentions energy",
        }],
    }


def _reduce(tmp_path: Path, actions: list[dict]) -> dict:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    state = tmp_path / "inbox-state.jsonl"
    state.write_text(json.dumps({
        "run_id": RUN_ID, "stem": "run-log", "item_key": ITEM_KEY, "path": ITEM_KEY,
        "status": "done", "attempts": 1,
    }) + "\n", encoding="utf-8")
    (items_dir / to_filename(ITEM_KEY)).write_text(json.dumps({
        "schema_version": "1", "stem": "run-log", "item_key": ITEM_KEY, "path": ITEM_KEY,
        "type": "system_action", "type_confidence": 0.9,
        "date_relevance": {"date": "2026-04-15", "source": "filename"},
        "issues": [], "duration_ms": 1500, "actions": actions,
    }), encoding="utf-8")
    shared_ctx = tmp_path / "shared-ctx.json"
    shared_ctx.write_text(json.dumps({
        "schema_version": "1", "run_id": RUN_ID, "mocs": [], "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")
    output = tmp_path / "doc.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
         "--state", str(state), "--items-dir", str(items_dir), "--run-id", RUN_ID,
         "--profile", "miyo", "--shared-ctx", str(shared_ctx), "--output", str(output),
         "--threshold", "3", "--no-kado"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(output.read_text(encoding="utf-8"))


def test_reducer_moves_daily_updates_out_of_the_item_section(tmp_path):
    doc = _reduce(tmp_path, [_atomic_action(), _daily_action()])
    assert [a["kind"] for a in doc["sections"][0]["actions"]] == ["create_atomic_note"]
    update = doc["daily_notes_updates"][0]
    assert update["daily_note_stem"] == "2026-04-15"
    assert update["trackers"][0]["field"] == "WakeUpEnergy"


def test_reducer_links_a_daily_note_by_name_only(tmp_path):
    rendered = _reduce(tmp_path, [_daily_action()])["rendered_daily_updates_md"]
    assert "### [[2026-04-15]]" in rendered
    assert "[[Calendar/" not in rendered
    assert "- **WakeUpEnergy** → `3`" in rendered


def test_reducer_output_has_no_inbox_prefix_or_extension_in_links(tmp_path):
    doc = _reduce(tmp_path, [_atomic_action(), _daily_action()])
    rendered = [a["rendered_md"] for a in doc["sections"][0]["actions"]]
    rendered.append(doc["rendered_daily_updates_md"])
    for markdown in rendered:
        assert "[[+/" not in markdown
        assert ".md]]" not in markdown
