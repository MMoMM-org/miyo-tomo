#!/usr/bin/env python3
# version: 0.1.0
"""test_tracker_config_durability.py — curated tracker config must survive.

Two mechanisms were destroying tracker configuration silently, and between
them they made every tracker in a live vault inert:

1. `/explore-vault` rediscovers tracker fields by scanning daily notes and
   emits name/type/syntax/description only. `vault-config-writer.py trackers`
   then REPLACES the whole `trackers:` block, so every keyword list entered
   through `tomo-trackers-wizard` was dropped.

2. `shared-ctx-builder.enforce_budget` emptied negative_keywords, then
   positive_keywords, then keywords — before touching a single MOC — whenever
   the context exceeded 40 KB. Measured 2026-09-13 on the live instance: the
   untrimmed context was 42104 bytes, so this fired on EVERY run while MOC
   data held 77% of the payload.

Neither had a test. Both failed silently: the schema does not require
keywords, the config still validates, and the analyst degrades to a
description fallback without complaining — so the only symptom is that
trackers stop matching, which reads as "nothing matched" rather than
"the configuration is gone".

These tests are the tripwire for both.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_writer = _load("vault_config_writer", "vault-config-writer.py")
_ctx = _load("shared_ctx_builder", "shared-ctx-builder.py")


def _curated_config() -> dict:
    """A config as it looks after someone ran the trackers wizard."""
    return {
        "trackers": {
            "enabled": True,
            "daily_note_trackers": {
                "section": "Habit",
                "today_fields": [
                    {
                        "name": "Sport",
                        "type": "boolean",
                        "syntax": "inline_field",
                        "description": "Did physical exercise today.",
                        "positive_keywords": ["laufen", "gelaufen", "joggen"],
                        "negative_keywords": ["video"],
                        "active": False,
                    },
                    {
                        "name": "Sleep",
                        "type": "text",
                        "syntax": "inline_field",
                        "description": "Hours slept.",
                        "positive_keywords": ["geschlafen"],
                    },
                ],
            },
        }
    }


def _rediscovery_input() -> dict:
    """What /explore-vault emits: no keywords, no active, no enabled."""
    return {
        "daily_note_trackers": {
            "section": "Habit",
            "today_fields": [
                {
                    "name": "Sport",
                    "type": "boolean",
                    "syntax": "inline_field",
                    "description": "Did physical exercise today. Detected from daily notes.",
                },
                {
                    "name": "Sleep",
                    "type": "text",
                    "syntax": "inline_field",
                    "description": "Hours slept. Detected from daily notes.",
                },
            ],
        }
    }


class TestWriterPreservesCuratedValues:
    """The /explore-vault overwrite path."""

    def test_keywords_survive_a_rediscovery_write(self):
        data = _rediscovery_input()
        _writer.preserve_curated_tracker_keys(data, _curated_config())
        fields = {f["name"]: f for f in data["daily_note_trackers"]["today_fields"]}
        assert fields["Sport"]["positive_keywords"] == ["laufen", "gelaufen", "joggen"]
        assert fields["Sport"]["negative_keywords"] == ["video"]
        assert fields["Sleep"]["positive_keywords"] == ["geschlafen"]

    def test_the_active_switch_survives(self):
        """Switching a tracker off is a user decision, not a discoverable fact."""
        data = _rediscovery_input()
        _writer.preserve_curated_tracker_keys(data, _curated_config())
        fields = {f["name"]: f for f in data["daily_note_trackers"]["today_fields"]}
        assert fields["Sport"]["active"] is False

    def test_the_master_switch_survives(self):
        existing = _curated_config()
        existing["trackers"]["enabled"] = False
        data = _rediscovery_input()
        _writer.preserve_curated_tracker_keys(data, existing)
        assert data["enabled"] is False

    def test_a_supplied_value_is_not_overwritten_by_the_old_one(self):
        """Preservation fills gaps; it never overrules an explicit change."""
        data = _rediscovery_input()
        data["daily_note_trackers"]["today_fields"][0]["positive_keywords"] = ["neu"]
        _writer.preserve_curated_tracker_keys(data, _curated_config())
        assert data["daily_note_trackers"]["today_fields"][0]["positive_keywords"] == ["neu"]

    def test_an_explicitly_emptied_list_is_respected(self):
        """`[]` present means cleared on purpose — absent means not supplied."""
        data = _rediscovery_input()
        data["daily_note_trackers"]["today_fields"][0]["positive_keywords"] = []
        _writer.preserve_curated_tracker_keys(data, _curated_config())
        assert data["daily_note_trackers"]["today_fields"][0]["positive_keywords"] == []

    def test_a_renamed_field_keeps_nothing(self):
        """Matching is by name; a rename is a real change, not an omission."""
        data = _rediscovery_input()
        data["daily_note_trackers"]["today_fields"][0]["name"] = "Exercise"
        _writer.preserve_curated_tracker_keys(data, _curated_config())
        renamed = data["daily_note_trackers"]["today_fields"][0]
        assert "positive_keywords" not in renamed

    def test_it_reports_what_it_restored(self):
        """A silent rescue is only half a fix — the run log must say so."""
        restored = _writer.preserve_curated_tracker_keys(
            _rediscovery_input(), _curated_config()
        )
        assert any("Sport.positive_keywords" in r for r in restored)
        assert any("Sport.active" in r for r in restored)

    def test_end_to_end_through_the_writer(self, tmp_path):
        """The whole path: curated YAML in, rediscovery JSON applied, YAML out."""
        config = tmp_path / "vault-config.yaml"
        config.write_text(yaml.safe_dump(_curated_config()), encoding="utf-8")
        payload = tmp_path / "trackers.json"
        payload.write_text(json.dumps(_rediscovery_input()), encoding="utf-8")

        args = type("A", (), {
            "input": str(payload), "config": str(config), "stdout": False,
        })()
        assert _writer.cmd_trackers(args) == 0

        written = yaml.safe_load(config.read_text(encoding="utf-8"))
        sport = written["trackers"]["daily_note_trackers"]["today_fields"][0]
        assert sport["positive_keywords"] == ["laufen", "gelaufen", "joggen"]
        assert sport["active"] is False


class TestBudgetNeverShedsConfiguration:
    """The enforce_budget path."""

    def _ctx_with_trackers(self, moc_count: int) -> dict:
        return {
            "schema_version": "1",
            "run_id": "t",
            "daily_notes": {
                "trackers_enabled": True,
                "tracker_fields": [
                    {
                        "name": "Sport",
                        "type": "boolean",
                        "section": "Habit",
                        "syntax": "inline_field",
                        "keywords": ["sport"],
                        "description": "Did physical exercise today.",
                        "positive_keywords": ["laufen", "gelaufen", "joggen"],
                        "negative_keywords": ["video"],
                        "active": True,
                    }
                ],
            },
            "mocs": [
                {
                    "title": f"MOC {i}",
                    "path": f"m{i}.md",
                    "topics": [f"topic-{i}-{j}" for j in range(40)],
                    "headings": [{"text": f"H{j}", "level": 2} for j in range(40)],
                    "editable_callouts": [{"name": f"c{j}"} for j in range(10)],
                }
                for i in range(moc_count)
            ],
        }

    def test_keywords_survive_severe_budget_pressure(self):
        """The defect: keyword lists were shed BEFORE any MOC data."""
        ctx = self._ctx_with_trackers(moc_count=40)
        assert len(_ctx.serialize(ctx)) > 4000
        trimmed, _ = _ctx.enforce_budget(ctx, 4000)
        field = trimmed["daily_notes"]["tracker_fields"][0]
        assert field["positive_keywords"] == ["laufen", "gelaufen", "joggen"]
        assert field["negative_keywords"] == ["video"]
        assert field["keywords"] == ["sport"]

    def test_the_description_survives_too(self):
        ctx = self._ctx_with_trackers(moc_count=40)
        trimmed, _ = _ctx.enforce_budget(ctx, 4000)
        assert trimmed["daily_notes"]["tracker_fields"][0]["description"] == (
            "Did physical exercise today."
        )

    def test_derived_moc_data_is_what_gets_shed(self):
        """Non-vacuity: the budget must still actually shrink something."""
        ctx = self._ctx_with_trackers(moc_count=40)
        before = len(_ctx.serialize(ctx))
        trimmed, _ = _ctx.enforce_budget(ctx, 4000)
        after = len(_ctx.serialize(trimmed))
        assert after < before
        assert not any(m.get("editable_callouts") for m in trimmed["mocs"])


class TestUnusableTrackersAreReported:
    def _ctx(self, **daily) -> dict:
        base = {"trackers_enabled": True, "tracker_fields": []}
        base.update(daily)
        return {"daily_notes": base}

    def test_an_active_field_without_positive_keywords_is_named(self, capsys):
        ctx = self._ctx(tracker_fields=[{"name": "Sport", "positive_keywords": []}])
        assert _ctx.warn_unusable_trackers(ctx) == ["Sport"]
        assert "Sport" in capsys.readouterr().err

    def test_seeded_keywords_do_not_silence_the_warning(self, capsys):
        """`keywords` is seeded from the field name and never read by the
        matching rule — counting it would hide exactly the live configuration
        this warning exists to report."""
        ctx = self._ctx(tracker_fields=[
            {"name": "Sport", "keywords": ["sport"], "positive_keywords": []}
        ])
        assert _ctx.warn_unusable_trackers(ctx) == ["Sport"]

    def test_an_inactive_field_is_not_reported(self, capsys):
        ctx = self._ctx(tracker_fields=[
            {"name": "Sport", "positive_keywords": [], "active": False}
        ])
        assert _ctx.warn_unusable_trackers(ctx) == []
        assert capsys.readouterr().err == ""

    def test_disabling_trackers_silences_everything(self, capsys):
        """'I do not use trackers' is a configuration, not a misconfiguration."""
        ctx = self._ctx(
            trackers_enabled=False,
            tracker_fields=[{"name": "Sport", "positive_keywords": []}],
        )
        assert _ctx.warn_unusable_trackers(ctx) == []
        assert capsys.readouterr().err == ""

    def test_a_usable_field_is_silent(self, capsys):
        ctx = self._ctx(tracker_fields=[
            {"name": "Sport", "positive_keywords": ["laufen"]}
        ])
        assert _ctx.warn_unusable_trackers(ctx) == []
        assert capsys.readouterr().err == ""


class TestSwitchesDefaultToOn:
    """An existing config predates both switches and must not change behaviour."""

    @staticmethod
    def _cfg(trackers: dict) -> dict:
        # build_daily_notes returns None unless the daily granularity is on.
        return {
            "concepts": {"calendar": {"granularities": {"daily": {
                "enabled": True, "path": "Calendar/301 Daily/",
            }}}},
            "trackers": trackers,
        }

    def test_absent_master_switch_means_enabled(self):
        block = _ctx.build_daily_notes(
            self._cfg({"daily_note_trackers": {"today_fields": []}})
        )
        assert block["trackers_enabled"] is True

    def test_an_explicit_master_false_reaches_the_context(self):
        block = _ctx.build_daily_notes(
            self._cfg({"enabled": False, "daily_note_trackers": {"today_fields": []}})
        )
        assert block["trackers_enabled"] is False

    def test_absent_active_means_active(self):
        fields = _ctx.build_tracker_fields({
            "trackers": {"daily_note_trackers": {"section": "Habit", "today_fields": [
                {"name": "Sport", "type": "boolean", "syntax": "inline_field",
                 "description": "d"},
            ]}}
        })
        assert fields[0]["active"] is True

    def test_an_explicit_false_is_carried_into_the_context(self):
        fields = _ctx.build_tracker_fields({
            "trackers": {"daily_note_trackers": {"section": "Habit", "today_fields": [
                {"name": "Sport", "type": "boolean", "syntax": "inline_field",
                 "description": "d", "active": False},
            ]}}
        })
        assert fields[0]["active"] is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
