#!/usr/bin/env python3
# version: 0.3.0
"""test_vault_summary.py — Behavioural tests for vault-summary.py.

Verifies that the aggregator reads pre-computed stats from pipeline artifacts
and emits a correct JSON summary. Each test asserts non-vacuous values so that
wrong aggregation logic produces a real failure.

Covers:
  - moc_count + moc_max_depth from moc-output.json tree_stats
  - accumulation_cluster_count retired (spec 021 ADR-10) — asserted absent
  - notes_per_concept from scan-output.json vault_structure.concepts_mapped
  - tag_namespace_count + unique_tag_count from vault-config.yaml tags.prefixes
  - frontmatter required/optional counts from tags.prefixes[].required_for
  - relationship markers from vault-config.yaml relationships.markers
  - tracker_field_count from vault-config.yaml trackers
  - graceful degradation: missing input file -> null fields, exit 0, valid JSON
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "vault-summary.py"

# ──────────────────────────────────────────────────────────────────────────────
# Module loader (hyphenated filename)
# ──────────────────────────────────────────────────────────────────────────────

_spec = importlib.util.spec_from_file_location("vault_summary", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

aggregate_summary = _mod.aggregate_summary
load_json_safe = _mod.load_json_safe
load_yaml_safe = _mod.load_yaml_safe


# ──────────────────────────────────────────────────────────────────────────────
# Fixture builders — minimal but structurally faithful to real artifacts
# ──────────────────────────────────────────────────────────────────────────────

def _write_json(data: object, tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_yaml(data: object, tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


def _make_moc_output(tmp_path: Path, total_mocs: int = 7, max_depth: int = 3) -> Path:
    data = {
        "map_notes": [
            {
                "path": f"Maps/moc-{i}.md",
                "title": f"MOC {i}",
                "level": i % (max_depth + 1),
                "parent_moc": None if i == 0 else "Maps/moc-0.md",
                "child_mocs": [],
            }
            for i in range(total_mocs)
        ],
        "placeholder_links": [],
        "tree_stats": {
            "total_mocs": total_mocs,
            "root_mocs": 2,
            "max_depth": max_depth,
            "cycles_broken": 0,
        },
    }
    return _write_json(data, tmp_path, "moc-output.json")


def _make_scan_output(tmp_path: Path) -> Path:
    data = {
        "vault_structure": {
            "total_notes": 120,
            "total_files": 130,
            "concepts_mapped": {
                "inbox": {"path": "Inbox/", "note_count": 20, "file_count": 20, "subdirectories": []},
                "atomic_note": {"path": "Atlas/202 Notes/", "note_count": 80, "file_count": 80, "subdirectories": []},
                "map_note": {"path": "Atlas/200 Maps/", "note_count": 7, "file_count": 7},
                "source": {"path": "X/600 Resources/", "note_count": 13, "file_count": 13},
            },
            "unmapped_folders": ["logs/", "assets/"],
        }
    }
    return _write_json(data, tmp_path, "scan-output.json")


def _make_discovery_cache(tmp_path: Path) -> Path:
    data = {
        "cache_version": 1,
        "last_scan": "2026-06-05T07:00:00Z",
        "scan_stats": {
            "total_notes": 120,
            "total_map_notes": 7,
            "total_classification_maps": 0,
            "total_tags_unique": 0,
        },
        "vault_structure": {},
        "map_notes": [],
        "placeholder_links": [],
        "classifications": {},
        "tag_patterns": {},
        "frontmatter_usage": {},
        "orphans": [],
    }
    return _write_yaml(data, tmp_path, "discovery-cache.yaml")


def _make_vault_config(tmp_path: Path) -> Path:
    data = {
        "schema_version": 2,
        "profile": "lyt",
        "concepts": {
            "inbox": "Inbox/",
            "atomic_note": {"base_path": "Atlas/202 Notes/"},
        },
        "tags": {
            "prefixes": {
                "type": {
                    "description": "Note type.",
                    "known_values": ["note/normal", "note/quote"],
                    "wildcard": False,
                    "proposable": False,
                    "required_for": ["atomic_note", "map_note"],
                },
                "status": {
                    "description": "Lifecycle stage.",
                    "known_values": ["fleeting/🎗️", "permanent/❗", "permanent/💾"],
                    "wildcard": False,
                    "proposable": True,
                    "required_for": [],
                },
                "topic": {
                    "description": "Thematic topic.",
                    "known_values": ["japan", "mind", "applied"],
                    "wildcard": True,
                    "proposable": True,
                    "required_for": [],
                },
            }
        },
        "relationships": {
            "markers": [
                {"marker": "up::", "position": "body"},
                {"marker": "related::", "position": "body"},
            ]
        },
        "callouts": {
            "protected": ["warning", "danger", "important"],
            "editable": ["note", "tip", "info", "example", "quote", "summary", "connect"],
        },
        "trackers": {
            "daily_note_trackers": ["mood", "energy", "focus"],
            "end_of_day_fields": ["highlight", "intention"],
        },
        "templates": {
            "base_path": "X/930 Templater/",
            "mapping": {
                "map_note": {"path": "t_moc_tomo.md"},
                "atomic_note": {"path": "t_note_tomo.md"},
                "daily": {"path": "t_day.md"},
                "project": None,
            },
        },
    }
    return _write_yaml(data, tmp_path, "vault-config.yaml")


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestMocStats:
    """moc_count + moc_max_depth come from tree_stats (not recomputed)."""

    def test_moc_count_equals_tree_stats_total_mocs(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=7, max_depth=3)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["moc_count"] == 7

    def test_moc_max_depth_equals_tree_stats_max_depth(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=7, max_depth=3)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["moc_max_depth"] == 3

    def test_key_moc_titles_contains_map_note_titles(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=5, max_depth=1)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        titles = result["key_moc_titles"]
        assert isinstance(titles, list)
        assert len(titles) == 5
        assert "MOC 0" in titles


class TestAccumulationClusterCountRetired:
    """accumulation_cluster_count was retired with Condition B (spec 021 ADR-10).
    vault-summary.py must no longer emit the field."""

    def test_accumulation_cluster_count_absent_from_summary(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert "accumulation_cluster_count" not in result, (
            "accumulation_cluster_count must be absent from vault-summary output (T3.3)"
        )


class TestNotesPerConcept:
    """notes_per_concept maps concept name -> note_count from scan-output."""

    def test_notes_per_concept_covers_all_mapped_concepts(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        npc = result["notes_per_concept"]
        assert isinstance(npc, dict)
        assert npc.get("inbox") == 20
        assert npc.get("atomic_note") == 80

    def test_total_notes_from_scan_vault_structure(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["total_notes"] == 120


class TestTagStats:
    """tag_namespace_count and unique_tag_count from vault-config tags.prefixes."""

    def test_tag_namespace_count_equals_prefix_count(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture has 3 prefixes: type, status, topic
        assert result["tag_namespace_count"] == 3

    def test_unique_tag_count_sums_all_known_values(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # type: 2 values, status: 3 values, topic: 3 values => 8 total
        assert result["unique_tag_count"] == 8

    def test_tag_prefix_table_has_one_entry_per_namespace(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        tpt = result["tag_prefix_table"]
        assert isinstance(tpt, dict)
        assert "type" in tpt
        assert "status" in tpt
        assert "topic" in tpt
        # Each entry is a non-empty example value
        assert tpt["type"]
        assert tpt["status"]


class TestFrontmatterStats:
    """frontmatter_required_count / frontmatter_optional_count from tags.prefixes."""

    def test_required_count_is_prefixes_with_nonempty_required_for(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Only "type" has required_for set in the fixture
        assert result["frontmatter_required_count"] == 1

    def test_optional_count_is_prefixes_without_required_for(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # "status" and "topic" have empty required_for
        assert result["frontmatter_optional_count"] == 2


class TestRelationshipMarkers:
    """relationship_markers extracted from vault-config.yaml relationships.markers."""

    def test_relationship_markers_list(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        rm = result["relationship_markers"]
        assert isinstance(rm, list)
        # Fixture has 2 markers
        assert len(rm) == 2
        markers = [m["marker"] for m in rm]
        assert "up::" in markers
        assert "related::" in markers


class TestTrackerAndCalloutStats:
    """tracker_field_count and callout protected/editable counts."""

    def test_tracker_field_count_sums_daily_and_eod_fields(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture: 3 daily_note_trackers + 2 end_of_day_fields = 5
        assert result["tracker_field_count"] == 5

    def test_callout_protected_count(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture: 3 protected callouts
        assert result["callout_protected_count"] == 3

    def test_callout_editable_count(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture: 7 editable callouts
        assert result["callout_editable_count"] == 7


class TestTemplateStats:
    """templates_found_count / templates_missing_count from vault-config templates.mapping."""

    def test_templates_found_count_nonzero_when_paths_present(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture: map_note, atomic_note, daily have paths => 3 found
        assert result["templates_found_count"] == 3

    def test_templates_missing_count_counts_null_entries(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        # Fixture: project mapping is None => 1 missing
        assert result["templates_missing_count"] == 1


class TestGracefulDegradation:
    """Missing or unreadable input files yield null fields — exit 0, valid JSON."""

    def test_missing_moc_file_yields_null_moc_fields(self, tmp_path):
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(tmp_path / "nonexistent-moc.json"),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["moc_count"] is None
        assert result["moc_max_depth"] is None
        # Other fields still populated from the files that exist
        assert result["total_notes"] == 120

    def test_missing_scan_file_yields_null_scan_fields(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=4)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(tmp_path / "nonexistent-scan.json"),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["total_notes"] is None
        assert result["notes_per_concept"] == {}
        # MOC data still populated
        assert result["moc_count"] == 4

    def test_missing_cache_file_still_returns_valid_summary(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=4)
        scan_path = _make_scan_output(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(tmp_path / "nonexistent-cache.yaml"),
            config_path=str(config_path),
        )

        # accumulation_cluster_count retired (T3.3); a missing cache must not crash.
        assert "accumulation_cluster_count" not in result
        assert result["moc_count"] == 4

    def test_missing_config_file_yields_null_tag_fields(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(tmp_path / "nonexistent-config.yaml"),
        )

        # Tag fields — None when config is absent (W2: distinguishes "0 configured" vs "missing")
        assert result["tag_namespace_count"] is None
        assert result["unique_tag_count"] is None
        assert result["relationship_markers"] == []
        # Scalar config fields must also be None, not 0 (W2 consistency)
        assert result["frontmatter_required_count"] is None
        assert result["frontmatter_optional_count"] is None
        assert result["callout_protected_count"] is None
        assert result["callout_editable_count"] is None
        assert result["tracker_field_count"] is None
        assert result["templates_found_count"] is None
        assert result["templates_missing_count"] is None

    def test_all_files_missing_still_returns_valid_dict(self, tmp_path):
        result = aggregate_summary(
            scan_path=str(tmp_path / "no-scan.json"),
            mocs_path=str(tmp_path / "no-mocs.json"),
            cache_path=str(tmp_path / "no-cache.yaml"),
            config_path=str(tmp_path / "no-config.yaml"),
        )

        assert isinstance(result, dict)
        assert "moc_count" in result
        assert "accumulation_cluster_count" not in result
        assert "total_notes" in result
        assert "tag_namespace_count" in result

    def test_cli_all_files_missing_exits_0_valid_json(self, tmp_path):
        """CLI: missing files -> exit 0, stdout is valid JSON."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--scan", str(tmp_path / "no-scan.json"),
                "--mocs", str(tmp_path / "no-mocs.json"),
                "--cache", str(tmp_path / "no-cache.yaml"),
                "--config", str(tmp_path / "no-config.yaml"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}; stderr: {result.stderr}"
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, dict)


class TestMalformedInputs:
    """Corrupt files yield None for affected fields without raising — W1 coverage."""

    def test_corrupt_json_moc_file_yields_null_moc_fields(self, tmp_path):
        corrupt_json = tmp_path / "bad-moc.json"
        corrupt_json.write_text("{broken", encoding="utf-8")
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(corrupt_json),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["moc_count"] is None
        assert result["moc_max_depth"] is None
        # Other sources unaffected
        assert result["total_notes"] == 120

    def test_corrupt_json_scan_file_yields_null_scan_fields(self, tmp_path):
        corrupt_json = tmp_path / "bad-scan.json"
        corrupt_json.write_text("{broken", encoding="utf-8")
        moc_path = _make_moc_output(tmp_path, total_mocs=3)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(corrupt_json),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["total_notes"] is None
        assert result["notes_per_concept"] == {}
        # MOC data still populated from valid file
        assert result["moc_count"] == 3

    def test_corrupt_yaml_cache_file_does_not_crash(self, tmp_path):
        corrupt_yaml = tmp_path / "bad-cache.yaml"
        corrupt_yaml.write_text("key: [unclosed", encoding="utf-8")
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(corrupt_yaml),
            config_path=str(config_path),
        )

        # accumulation_cluster_count retired (T3.3); a corrupt cache must not crash.
        assert "accumulation_cluster_count" not in result
        # Config fields still populated from valid vault-config
        assert result["tag_namespace_count"] == 3

    def test_corrupt_yaml_config_file_yields_null_config_fields(self, tmp_path):
        corrupt_yaml = tmp_path / "bad-config.yaml"
        corrupt_yaml.write_text("key: [unclosed", encoding="utf-8")
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(corrupt_yaml),
        )

        assert result["tag_namespace_count"] is None
        assert result["frontmatter_required_count"] is None
        assert result["callout_protected_count"] is None
        assert result["tracker_field_count"] is None
        assert result["templates_found_count"] is None
        # Unaffected sources still populated
        assert result["moc_count"] is not None

    def test_load_json_safe_returns_none_on_corrupt_input(self, tmp_path):
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{broken", encoding="utf-8")

        result = load_json_safe(str(corrupt), "test-label")

        assert result is None

    def test_load_yaml_safe_returns_none_on_corrupt_input(self, tmp_path):
        corrupt = tmp_path / "corrupt.yaml"
        corrupt.write_text("key: [unclosed", encoding="utf-8")

        result = load_yaml_safe(str(corrupt), "test-label")

        assert result is None


class TestMocTitleCap:
    """key_moc_titles is capped at 10 entries — S3 boundary."""

    def test_key_moc_titles_capped_at_ten_when_more_mocs_present(self, tmp_path):
        moc_path = _make_moc_output(tmp_path, total_mocs=15, max_depth=1)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert len(result["key_moc_titles"]) == 10

    def test_untitled_map_notes_dropped_before_cap(self, tmp_path):
        """map_notes with empty/missing title are filtered out; the cap still holds."""
        data = {
            "map_notes": (
                [{"path": f"Maps/t-{i}.md", "title": f"MOC {i}"} for i in range(12)]
                + [{"path": "Maps/empty.md", "title": ""}]      # falsy → dropped
                + [{"path": "Maps/none.md", "title": None}]      # None → dropped
                + [{"path": "Maps/missing.md"}]                  # no key → dropped
            ),
            "placeholder_links": [],
            "tree_stats": {"total_mocs": 15, "root_mocs": 1, "max_depth": 1, "cycles_broken": 0},
        }
        moc_path = _write_json(data, tmp_path, "moc-output.json")
        result = aggregate_summary(
            scan_path=str(_make_scan_output(tmp_path)),
            mocs_path=str(moc_path),
            cache_path=str(_make_discovery_cache(tmp_path)),
            config_path=str(_make_vault_config(tmp_path)),
        )
        titles = result["key_moc_titles"]
        assert len(titles) == 10                       # cap holds
        assert "" not in titles and None not in titles  # no falsy titles leaked
        assert all(t.startswith("MOC ") for t in titles)


class TestCachePath:
    """cache_path in the summary is the path passed as --cache."""

    def test_cache_path_echoes_input_path(self, tmp_path):
        moc_path = _make_moc_output(tmp_path)
        scan_path = _make_scan_output(tmp_path)
        cache_path = _make_discovery_cache(tmp_path)
        config_path = _make_vault_config(tmp_path)

        result = aggregate_summary(
            scan_path=str(scan_path),
            mocs_path=str(moc_path),
            cache_path=str(cache_path),
            config_path=str(config_path),
        )

        assert result["cache_path"] == str(cache_path)
