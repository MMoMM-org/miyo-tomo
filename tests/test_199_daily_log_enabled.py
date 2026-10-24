#!/usr/bin/env python3
# version: 0.1.0
"""test_199_daily_log_enabled.py — #199: the daily-log switch reaches the analyst.

`vault-example.yaml` documents `daily_log.enabled`, the daily-log wizard
writes it, and `inbox-analyst.md` Step 8b skips the log when it is `false`.
The builder must carry it into `shared_ctx.daily_notes.daily_log`, and the
schema must accept it.

RED on `main`: the builder drops the key and the schema forbids it, so a
vault that switched the log off still got log entries.

Mechanisms falsified:
  - key dropped by the builder        → `false` round-trip, built context
  - default not "on"                  → absent key keeps today's behaviour
  - schema still forbidding the key   → validation of a built context
  - optional in the schema            → a context without it is rejected
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA = json.loads((REPO_ROOT / "tomo" / "schemas" / "shared-ctx.schema.json").read_text())
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("shared_ctx_builder_199", SCRIPTS_DIR / "shared-ctx-builder.py")
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder_199"] = scb  # dataclasses resolve their module by name
_spec.loader.exec_module(scb)


def test_absent_key_defaults_to_on():
    assert scb.build_daily_log({})["enabled"] is True
    assert scb.build_daily_log({"daily_log": {"section": "Log"}})["enabled"] is True


@pytest.mark.parametrize("value", [True, False])
def test_the_configured_value_is_carried(value):
    assert scb.build_daily_log({"daily_log": {"enabled": value}})["enabled"] is value


def _build(tmp_path: Path, daily_log: dict | None) -> dict:
    cfg = {
        "profile": "miyo", "tags": {"prefixes": {}},
        "concepts": {"map_note": {"paths": ["Atlas/200 Maps/"]},
                     "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/301 Daily/"}}}},
    }
    if daily_log is not None:
        cfg["daily_log"] = daily_log
    (tmp_path / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (tmp_path / "cache.yaml").write_text(yaml.safe_dump({"map_notes": []}), encoding="utf-8")
    out = subprocess.run([
        sys.executable, str(SCRIPTS_DIR / "shared-ctx-builder.py"), "--cache", str(tmp_path / "cache.yaml"),
        "--vault-config", str(tmp_path / "vault-config.yaml"), "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
        "--run-id", "r199", "--output", str(tmp_path / "ctx.json"), "--skip-reconcile",
    ], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads((tmp_path / "ctx.json").read_text())


def test_a_switched_off_log_reaches_the_built_context(tmp_path):
    ctx = _build(tmp_path, {"enabled": False})
    assert ctx["daily_notes"]["daily_log"]["enabled"] is False
    jsonschema.validate(ctx, SCHEMA)


def test_the_schema_requires_the_switch(tmp_path):
    ctx = _build(tmp_path, None)
    jsonschema.validate(ctx, SCHEMA)
    without = copy.deepcopy(ctx)
    del without["daily_notes"]["daily_log"]["enabled"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(without, SCHEMA)
