"""A tracker field's configured `syntax` must win over the type-derived guess.

`vault-config-trackers.schema.json` declares `syntax` on every tracker field —
"How the field is serialised in the daily note" — with four allowed values.
`build_tracker_fields` never read it. It called `_syntax_for(field_type)`
unconditionally, which maps `text` → `callout_body` and everything else →
`inline_field`, and wrote that into shared-ctx.

Found by Hashi on the 2026-09-15 run, phrased as a question rather than a bug
report. From one source note Tomo emitted `Sport` and `HealthFood` as
`inline_field` and `ToBed` as `callout_body` — the first two are `type:
boolean`, the third is `type: text`. All three are configured `inline_field`.

The vault settles it: `Calendar/301 Daily/2026-09-08.md` writes

    ## Habit
    ### Yesterday
    - ToBed:: 23:30

an inline field under a heading, with no callout named Habit anywhere. Applying
the emitted action against that note is a hard `Section not found: Habit`.
Hashi added a callout to their QA vault to make our value work rather than
reporting it — so the run passed 28/28 and the defect stayed invisible.

The derivation stays as the fallback: a config that omits `syntax` keeps the
behaviour it has today, and only an explicit value overrides it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "shared-ctx-builder.py"

_spec = importlib.util.spec_from_file_location("shared_ctx_builder", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# The module defines a frozen dataclass at import time, and dataclasses resolves
# its annotations through sys.modules — registering before exec is required.
sys.modules["shared_ctx_builder"] = _mod
_spec.loader.exec_module(_mod)


def _cfg(fields: list[dict], section: str = "Habit") -> dict:
    return {"trackers": {"daily_note_trackers": {"section": section, "today_fields": fields}}}


def _by_name(cfg: dict) -> dict[str, dict]:
    return {f["name"]: f for f in _mod.build_tracker_fields(cfg)}


class TestTheLiveCase:
    """The three fields from the 2026-09-15 run, verbatim from vault-config."""

    @staticmethod
    def _fields() -> dict[str, dict]:
        return _by_name(_cfg([
            {"name": "Sport", "type": "boolean", "syntax": "inline_field",
             "description": "Did physical exercise today."},
            {"name": "HealthFood", "type": "boolean", "syntax": "inline_field",
             "description": "Ate healthy food today."},
            {"name": "ToBed", "type": "text", "syntax": "inline_field",
             "description": "Time went to bed yesterday — HH:MM format."},
        ]))

    def test_tobed_keeps_its_configured_inline_field(self):
        """The observed defect: `text` derived `callout_body` over the config."""
        syntax = self._fields()["ToBed"]["syntax"]
        assert syntax == "inline_field", (
            f"ToBed serialised as {syntax!r}; the config says 'inline_field' and "
            f"the daily note writes '- ToBed:: 23:30' under a heading"
        )

    def test_all_three_agree_with_the_config(self):
        fields = self._fields()
        assert [fields[n]["syntax"] for n in ("Sport", "HealthFood", "ToBed")] == [
            "inline_field", "inline_field", "inline_field"
        ]

    def test_the_other_fields_are_untouched(self):
        """Only `syntax` changes — type, section and keywords stay as they were."""
        tobed = self._fields()["ToBed"]
        assert tobed["type"] == "text"
        assert tobed["section"] == "Habit"
        assert tobed["active"] is True


class TestTheFallbackSurvives:
    """A config without `syntax` must behave exactly as it does today."""

    @pytest.mark.parametrize("field_type,expected", [
        ("text", "callout_body"),
        ("string", "callout_body"),
        ("boolean", "inline_field"),
        ("integer", "inline_field"),
        ("time", "callout_body"),      # time maps to text in TYPE_MAP
    ])
    def test_derivation_applies_when_syntax_is_absent(self, field_type, expected):
        fields = _by_name(_cfg([{"name": "F", "type": field_type, "description": "d"}]))
        assert fields["F"]["syntax"] == expected

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_blank_syntax_falls_back_rather_than_emitting_it(self, blank):
        """An empty string must not reach the wire as a syntax value."""
        fields = _by_name(_cfg([
            {"name": "F", "type": "text", "syntax": blank, "description": "d"},
        ]))
        assert fields["F"]["syntax"] == "callout_body"


class TestEveryDeclaredValueIsHonoured:
    @pytest.mark.parametrize("configured", [
        "inline_field", "callout_body", "task_checkbox", "checkbox",
    ])
    def test_each_enum_value_from_the_schema_survives(self, configured):
        """All four are legal per vault-config-trackers.schema.json."""
        fields = _by_name(_cfg([
            {"name": "F", "type": "boolean", "syntax": configured, "description": "d"},
        ]))
        assert fields["F"]["syntax"] == configured

    def test_callout_body_can_be_asked_for_on_a_boolean(self):
        """The derivation would never produce this — only the config can."""
        fields = _by_name(_cfg([
            {"name": "F", "type": "boolean", "syntax": "callout_body", "description": "d"},
        ]))
        assert fields["F"]["syntax"] == "callout_body"
