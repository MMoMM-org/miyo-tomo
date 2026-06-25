"""test_vault_summary_render_md.py — #72: deterministic vault-config.md render.

vault-explorer Step 10b used to free-compose vault-config.md, which drifted from
the YAML in format AND facts (listing ignore-callouts as editable, fabricating a
vault name and relationship markers). render_markdown() must render only what the
data actually contains, faithfully and deterministically.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
_spec = importlib.util.spec_from_file_location("vault_summary", SCRIPTS_DIR / "vault-summary.py")
_vs = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["vault_summary"] = _vs
_spec.loader.exec_module(_vs)


def _config() -> dict:
    return {
        "profile": "miyo",
        "concepts": {
            "inbox": "100 Inbox/",
            "atomic_note": {"path": "Atlas/202 Notes/"},
            "map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]},
            "calendar": {"base_path": "Calendar/"},
        },
        "callouts": {
            "editable": {"connect": "nav", "anchor": "intro", "blocks": "key concepts"},
            "protected": {"shell": "dvjs"},
            "ignore": {"rainbow": "divider", "recycle": "divider", "orbit": "divider"},
        },
        "relationships": {"markers": []},
    }


def _summary(**over) -> dict:
    base = {
        "total_notes": 3923,
        "notes_per_concept": {"inbox": 23, "atomic_note": 281, "map_note": 27, "calendar": 3061},
        "unmapped_folders": ["logs/"],
        "moc_count": 63,
        "moc_max_depth": None,
        "key_moc_titles": ["000 Index", "Japan (MOC)"],
        "frontmatter_required_count": 1,
        "frontmatter_optional_count": 12,
        "tag_namespace_count": 2,
        "unique_tag_count": 10,
        "tag_prefix_table": {"type": "note/normal", "topic": "applied/ai"},
        "relationship_markers": [],
        "callout_protected_count": 1,
        "callout_editable_count": 3,
        "tracker_field_count": 3,
        "templates_found_count": 4,
        "templates_missing_count": 2,
        "cache_path": "config/discovery-cache.yaml",
    }
    base.update(over)
    return base


# ── The drift bug: callout classification must come straight from the YAML ──


class TestCalloutClassificationFaithful:
    def test_ignore_callouts_not_listed_as_editable(self):
        md = _vs.render_markdown(_summary(), _config())
        callouts = md.split("## Callouts", 1)[1].split("## ", 1)[0]
        editable_line = next(line for line in callouts.splitlines() if "editable" in line)
        for name in ("rainbow", "recycle", "orbit"):
            assert name not in editable_line, f"{name} (ignore) leaked into editable"

    def test_ignore_callouts_listed_under_ignore(self):
        md = _vs.render_markdown(_summary(), _config())
        callouts = md.split("## Callouts", 1)[1]
        ignore_line = next(line for line in callouts.splitlines() if "ignore" in line)
        for name in ("rainbow", "recycle", "orbit"):
            assert name in ignore_line

    def test_editable_names_from_config_in_order(self):
        md = _vs.render_markdown(_summary(), _config())
        assert "**3 editable:** connect, anchor, blocks" in md

    def test_protected_names_from_config(self):
        md = _vs.render_markdown(_summary(), _config())
        assert "**1 protected:** shell" in md


# ── No fabrication: render only what the data holds ─────────────────────────


class TestNoFabrication:
    def test_empty_relationship_markers_not_fabricated(self):
        md = _vs.render_markdown(_summary(), _config())
        rel = md.split("## Relationships", 1)[1].split("## ", 1)[0]
        assert "No markers configured" in rel
        assert "| `up::`" not in rel

    def test_no_fabricated_vault_name(self):
        md = _vs.render_markdown(_summary(), _config())
        assert "MiYo Vault" not in md  # there is no vault_name in config

    def test_framework_from_profile(self):
        assert "- **Framework:** MiYo" in _vs.render_markdown(_summary(), _config())


# ── Folder-layout path derivation across concept shapes ─────────────────────


class TestFolderLayoutPaths:
    def test_paths_resolved_for_each_concept_shape(self):
        md = _vs.render_markdown(_summary(), _config())
        assert "| inbox | `100 Inbox/` | 23 |" in md            # bare string
        assert "| atomic_note | `Atlas/202 Notes/` | 281 |" in md  # {path}
        assert "| map_note | `Atlas/200 Maps/` | 27 |" in md       # {paths:[...]}
        assert "| calendar | `Calendar/` | 3061 |" in md           # {base_path}


# ── moc_count fallback (artifact has map_notes, no tree_stats) ───────────────


class TestMocStatsFallback:
    def test_count_falls_back_to_map_notes_len(self):
        mocs = {"map_notes": [{"title": "A"}, {"title": "B"}], "placeholder_links": []}
        count, depth, titles = _vs._extract_moc_stats(mocs)
        assert count == 2
        assert depth is None
        assert titles == ["A", "B"]

    def test_tree_stats_total_wins_when_present(self):
        mocs = {"tree_stats": {"total_mocs": 99, "max_depth": 3}, "map_notes": [{"title": "A"}]}
        count, depth, _ = _vs._extract_moc_stats(mocs)
        assert count == 99
        assert depth == 3

    def test_none_input_safe(self):
        assert _vs._extract_moc_stats(None) == (None, None, [])


# ── Determinism + graceful degradation ──────────────────────────────────────


class TestRenderRobustness:
    def test_deterministic_same_input_same_output(self):
        a = _vs.render_markdown(_summary(), _config(), updated="2026-06-17")
        b = _vs.render_markdown(_summary(), _config(), updated="2026-06-17")
        assert a == b

    def test_missing_config_does_not_crash(self):
        md = _vs.render_markdown(_summary(), None)
        assert "## Vault Info" in md
        assert md.endswith("\n")

    def test_section_omitted_when_data_absent(self):
        md = _vs.render_markdown(_summary(moc_count=None), _config())
        assert "## MOCs" not in md
