"""The tracker values Tomo's prose offers must be values the pipeline accepts (#212).

The trackers wizard, vault-explorer and vault-example.yaml each list tracker
`type` and `syntax` values by hand. They drifted from the writer and the wire:
`frontmatter` and `type: scale` fail the writer, `task_checkbox` passes it and
then fails the instructions schema. This reads what each file offers and checks
it against the writer's sets and the wire enums.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WIZARD = REPO / "tomo" / "dot_claude" / "skills" / "tomo-trackers-wizard" / "SKILL.md"
EXPLORER = REPO / "tomo" / "dot_claude" / "agents" / "vault-explorer.md"
EXAMPLE = REPO / "tomo" / "config" / "vault-example.yaml"
SCHEMAS = REPO / "tomo" / "schemas"

_spec = importlib.util.spec_from_file_location(
    "vault_config_writer_212", REPO / "tomo" / "scripts" / "vault-config-writer.py"
)
_writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_writer)


def _wire_syntaxes() -> set[str]:
    schema = json.loads((SCHEMAS / "instructions.schema.json").read_text(encoding="utf-8"))
    found: list[list[str]] = []

    def walk(node):
        if isinstance(node, dict):
            syntax = node.get("syntax")
            if isinstance(syntax, dict) and "enum" in syntax:
                found.append(syntax["enum"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    assert found, "no syntax enum in instructions.schema.json"
    return set.intersection(*(set(e) for e in found))


ALLOWED_SYNTAXES = _wire_syntaxes() & _writer.TRACKER_SYNTAXES
ALLOWED_TYPES = _writer.TRACKER_TYPES


def _pipe_values(text: str, pattern: str) -> set[str]:
    match = re.search(pattern, text, re.M)
    assert match, pattern
    return {v.strip() for v in match.group(1).split("|")}


def _backticked(fragment: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", fragment))


def test_the_allowed_syntaxes_are_the_three_wire_values():
    assert ALLOWED_SYNTAXES == {"inline_field", "callout_body", "checkbox"}


class TestWizard:
    text = WIZARD.read_text(encoding="utf-8")

    def test_interface_types(self):
        assert _pipe_values(self.text, r"^  type: (.+)$") == ALLOWED_TYPES

    def test_interface_syntaxes(self):
        assert _pipe_values(self.text, r"^  syntax\?: (.+)$") == ALLOWED_SYNTAXES

    def test_syntax_step_offers(self):
        step = self.text[self.text.index("#### 3.2 Syntax") : self.text.index("#### 3.3")]
        offered = set(re.findall(r"^  - `([a-z_]+)`", step, re.M))
        assert offered == ALLOWED_SYNTAXES

    def test_yaml_examples(self):
        assert set(re.findall(r"^ +syntax: (\S+)$", self.text, re.M)) <= ALLOWED_SYNTAXES


class TestExplorer:
    text = EXPLORER.read_text(encoding="utf-8")

    def _emit_sentence(self) -> str:
        return self.text[self.text.index("emit FOUR JSON fields") :][:400]

    def test_declared_types(self):
        fragment = re.search(r"`type` \(enum: ([^)]*)\)", self._emit_sentence()).group(1)
        assert _backticked(fragment) <= ALLOWED_TYPES

    def test_declared_syntaxes(self):
        fragment = re.search(r"`syntax` \(enum: ([^)]*)\)", self._emit_sentence()).group(1)
        assert _backticked(fragment) <= ALLOWED_SYNTAXES

    def test_parse_rules_and_examples(self):
        step = self.text[self.text.index("### Step 7") : self.text.index("### Step 8")]
        named = set(re.findall(r"syntax: `([a-z_]+)`", step))
        named |= set(re.findall(r'"syntax": "([a-z_]+)"', step))
        assert named and named <= ALLOWED_SYNTAXES
        assert "task_checkbox" not in step
        assert set(re.findall(r'"type": "([a-z_]+)"', step)) <= ALLOWED_TYPES

    def test_frontmatter_trackers_are_skipped_and_reported(self):
        step = self.text[self.text.index("### Step 7") : self.text.index("### Step 8")]
        assert "Do NOT offer them as tracker fields" in " ".join(step.split())
        assert "frontmatter trackers skipped" in step

    def test_fixture_payload_passes_the_real_writer_validation(self):
        step = self.text[self.text.index("### Step 7") : self.text.index("### Step 8")]
        payload = json.loads(re.search(r"```json\n(.*?)```", step, re.S).group(1))
        fields = payload["daily_note_trackers"]["today_fields"] + payload["end_of_day_fields"]["fields"]
        for field in fields:
            assert field["type"] in _writer.TRACKER_TYPES
            assert field["syntax"] in ALLOWED_SYNTAXES


class TestExample:
    text = EXAMPLE.read_text(encoding="utf-8")
    section = text[text.index("# Trackers\n") :]

    def test_comment_types(self):
        assert _pipe_values(self.section, r"^#   type\s+— ([^(]+?)\s*(?:\(|$)") == ALLOWED_TYPES

    def test_comment_syntaxes(self):
        assert _pipe_values(self.section, r"^#   syntax\s+— (.+)$") == ALLOWED_SYNTAXES

    def test_end_of_day_fields_reach_the_pipeline(self):
        spec = importlib.util.spec_from_file_location(
            "shared_ctx_builder_212", REPO / "tomo" / "scripts" / "shared-ctx-builder.py"
        )
        builder = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = builder  # dataclasses look their module up here
        spec.loader.exec_module(builder)
        groups = builder._collect_tracker_groups(yaml.safe_load(self.text)["trackers"])
        names = {f["name"] for _, fields in groups for f in fields}
        assert {"Sport", "Highlights"} <= names

    @pytest.mark.parametrize("key", ["today_fields"])
    def test_configured_values(self, key):
        trackers = yaml.safe_load(self.text)["trackers"]
        fields = trackers["daily_note_trackers"][key] + trackers["end_of_day_fields"]["fields"]
        assert {f["syntax"] for f in fields} <= ALLOWED_SYNTAXES
        assert {f["type"] for f in fields} <= ALLOWED_TYPES
