#!/usr/bin/env python3
# version: 0.1.0
"""test_triage_cache_staleness.py — discovery-cache staleness warning (#36 / F-21).

The discovery cache (config/discovery-cache.yaml) is rebuilt by /explore-vault,
never by /inbox, so a run can silently rely on a months-old vault map. Triage now
emits a `stale_cache` drift_indicator (surfaced by the conductors) when the
cache's last_scan is older than the threshold. Fail-open: a missing / malformed /
future-dated cache produces no warning.

Issue: https://github.com/MMoMM-org/miyo-tomo/issues/36
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "inbox_triage", SCRIPTS_DIR / "inbox-triage.py"
)
triage = importlib.util.module_from_spec(_spec)
sys.modules["inbox_triage"] = triage
_spec.loader.exec_module(triage)

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)


def _write_cache(tmp_path: Path, last_scan, name="discovery-cache.yaml") -> Path:
    p = tmp_path / name
    doc = {"cache_version": 1}
    if last_scan is not None:
        doc["last_scan"] = last_scan
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


def _iso(days_ago: float) -> str:
    return (NOW - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── stale → warning ──────────────────────────────────────────────────────────


def test_stale_cache_emits_drift(tmp_path):
    cache = _write_cache(tmp_path, _iso(30))
    drift = triage.discovery_cache_staleness_drift(cache, 7, now=NOW)
    assert drift is not None
    assert drift["type"] == "stale_cache"
    assert drift["path"] == str(cache)
    assert "30 days old" in drift["detail"]
    assert "/explore-vault" in drift["detail"]


def test_just_over_threshold_emits_drift(tmp_path):
    cache = _write_cache(tmp_path, _iso(7.5))
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is not None


# ── fresh / boundary → no warning ────────────────────────────────────────────


def test_fresh_cache_no_drift(tmp_path):
    cache = _write_cache(tmp_path, _iso(1))
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


def test_exact_threshold_no_drift(tmp_path):
    """Exactly at the threshold is not yet stale (age <= stale_days)."""
    cache = _write_cache(tmp_path, _iso(7))
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


def test_future_last_scan_no_drift(tmp_path):
    """Clock skew (last_scan in the future) must not warn."""
    cache = _write_cache(tmp_path, _iso(-5))
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


# ── fail-open on bad/absent input ────────────────────────────────────────────


def test_missing_file_no_drift(tmp_path):
    assert triage.discovery_cache_staleness_drift(
        tmp_path / "nope.yaml", 7, now=NOW
    ) is None


def test_malformed_yaml_no_drift(tmp_path):
    p = tmp_path / "discovery-cache.yaml"
    p.write_text("last_scan: '2026-01-01T00:00:00Z'\n  bad: [indent", encoding="utf-8")
    assert triage.discovery_cache_staleness_drift(p, 7, now=NOW) is None


def test_missing_last_scan_key_no_drift(tmp_path):
    cache = _write_cache(tmp_path, None)
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


def test_non_string_last_scan_no_drift(tmp_path):
    cache = _write_cache(tmp_path, 12345)
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


def test_unparseable_timestamp_no_drift(tmp_path):
    cache = _write_cache(tmp_path, "not-a-date")
    assert triage.discovery_cache_staleness_drift(cache, 7, now=NOW) is None


# ── threshold is honored ─────────────────────────────────────────────────────


def test_custom_threshold_tightens(tmp_path):
    cache = _write_cache(tmp_path, _iso(2))
    assert triage.discovery_cache_staleness_drift(cache, 1, now=NOW) is not None


def test_custom_threshold_loosens(tmp_path):
    cache = _write_cache(tmp_path, _iso(30))
    assert triage.discovery_cache_staleness_drift(cache, 90, now=NOW) is None


# ── schema contract: the new drift type is accepted ──────────────────────────


def test_schema_accepts_stale_cache_drift():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item_schema = schema["properties"]["drift_indicators"]["items"]
    drift = {
        "path": "config/discovery-cache.yaml",
        "type": "stale_cache",
        "detail": "Vault discovery map is 30 days old; run /explore-vault.",
    }
    jsonschema.validate(instance=drift, schema=item_schema)  # must not raise


def test_schema_still_rejects_unknown_drift_type():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item_schema = schema["properties"]["drift_indicators"]["items"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            instance={"path": "x", "type": "totally_bogus"}, schema=item_schema
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
