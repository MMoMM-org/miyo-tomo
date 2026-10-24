#!/usr/bin/env python3
# version: 0.1.0
"""test_040_shared_ctx_names.py — spec 040 T1.4: eligible MOCs, delivered names,
placeholder targets.

Each analyst will read the *names* of all eligible MOCs and fetch detail only
for the ones it nominates (SDD ADR-1/2). That needs, per MOC, one delivered
`name` that resolves to exactly one entry: the title, or the path when titles
collide (the one inside the configured MOC folders keeps the title when it is
the only one there). Excluded MOCs (`MiYo/Tomo/exclude/moc`) are not eligible
(ADR-5). `placeholder_targets` replaces `placeholder_links` in the context and
is always written (ADR-7).
"""
from __future__ import annotations

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

_spec = importlib.util.spec_from_file_location("shared_ctx_builder_040", SCRIPTS_DIR / "shared-ctx-builder.py")
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder_040"] = scb  # dataclasses resolve their module by name
_spec.loader.exec_module(scb)

from lib.orphan_link import emit_orphan_suggestions  # noqa: E402

FOLDERS = ("Atlas/200 Maps/",)


def _moc(path, title, tags=None, **extra):
    entry = {"path": path, "title": title, "topics": [title.lower()], "tags": tags or ["type/others/moc"]}
    entry.update(extra)
    return entry


def _traced_cache():
    """The six-row example from SDD 'Implementation Examples — assigning names (traced)'."""
    return {"map_notes": [
        _moc("Atlas/200 Maps/Projects.md", "Projects"),
        _moc("Efforts/Work/Projects.md", "Projects"),
        _moc("Atlas/200 Maps/Vacation (MOC).md", "Vacation (MOC)"),
        _moc("Areas/Health/Fitness.md", "Fitness"),
        _moc("Areas/A/Notes.md", "Notes"),
        _moc("Areas/B/Notes.md", "Notes"),
    ]}


# ── delivered names ──────────────────────────────────────────────────────────

def test_traced_example_yields_exactly_the_sdd_names():
    by_path = {m["path"]: m["name"] for m in scb.build_mocs(_traced_cache(), FOLDERS)}
    assert by_path == {
        "Atlas/200 Maps/Projects.md": "Projects",
        "Efforts/Work/Projects.md": "Efforts/Work/Projects.md",
        "Atlas/200 Maps/Vacation (MOC).md": "Vacation (MOC)",
        "Areas/Health/Fitness.md": "Fitness",
        "Areas/A/Notes.md": "Areas/A/Notes.md",
        "Areas/B/Notes.md": "Areas/B/Notes.md",
    }


def test_two_colliding_mocs_both_inside_the_folders_both_carry_paths():
    cache = {"map_notes": [_moc("Atlas/200 Maps/Projects.md", "Projects"),
                           _moc("Atlas/200 Maps/Sub/Projects.md", "Projects")]}
    names = {m["name"] for m in scb.build_mocs(cache, FOLDERS)}
    assert names == {"Atlas/200 Maps/Projects.md", "Atlas/200 Maps/Sub/Projects.md"}


def test_titles_differing_only_in_case_collide():
    cache = {"map_notes": [_moc("Atlas/200 Maps/Projects.md", "Projects"),
                           _moc("Efforts/projects.md", "projects")]}
    by_path = {m["path"]: m["name"] for m in scb.build_mocs(cache, FOLDERS)}
    assert by_path == {"Atlas/200 Maps/Projects.md": "Projects", "Efforts/projects.md": "Efforts/projects.md"}


def test_every_name_is_unique():
    names = [m["name"] for m in scb.build_mocs(_traced_cache(), FOLDERS)]
    assert len(names) == len(set(names))


def test_without_moc_folders_every_colliding_moc_carries_its_path():
    by_path = {m["path"]: m["name"] for m in scb.build_mocs(_traced_cache())}
    assert by_path["Atlas/200 Maps/Projects.md"] == "Atlas/200 Maps/Projects.md"
    assert by_path["Atlas/200 Maps/Vacation (MOC).md"] == "Vacation (MOC)"


def test_mocs_are_sorted_by_path():
    paths = [m["path"] for m in scb.build_mocs(_traced_cache(), FOLDERS)]
    assert paths == sorted(paths)


def test_classification_mocs_keep_a_bare_name_and_their_flag():
    cache = {"map_notes": [_moc("Atlas/200 Maps/2900 - History & Geography.md", "2900 - History & Geography")]}
    (moc,) = scb.build_mocs(cache, FOLDERS)
    assert moc["name"] == "2900 - History & Geography"
    assert moc["is_classification"] is True  # guard: unchanged behaviour


# ── eligibility ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tag", ["MiYo/Tomo/exclude/moc", "#MiYo/Tomo/exclude/moc", "miyo/tomo/exclude/MOC"])
def test_excluded_moc_is_not_eligible(tag):
    cache = {"map_notes": [_moc("Atlas/200 Maps/000 Index.md", "000 Index", tags=["type/others/moc", tag]),
                           _moc("Atlas/200 Maps/Vacation (MOC).md", "Vacation (MOC)")]}
    assert [m["path"] for m in scb.build_mocs(cache, FOLDERS)] == ["Atlas/200 Maps/Vacation (MOC).md"]


def test_exclude_note_alone_keeps_a_moc_eligible():
    cache = {"map_notes": [_moc("Atlas/200 Maps/Vacation (MOC).md", "Vacation (MOC)", tags=["MiYo/Tomo/exclude/note"])]}
    assert len(scb.build_mocs(cache, FOLDERS)) == 1


def test_entry_without_tags_is_kept():
    entry = _moc("Atlas/200 Maps/Vacation (MOC).md", "Vacation (MOC)")
    del entry["tags"]
    assert len(scb.build_mocs({"map_notes": [entry]}, FOLDERS)) == 1  # guard


def test_an_excluded_moc_frees_its_title_for_the_other_holder():
    cache = {"map_notes": [_moc("Atlas/200 Maps/Projects.md", "Projects", tags=["MiYo/Tomo/exclude/moc"]),
                           _moc("Efforts/Work/Projects.md", "Projects")]}
    (moc,) = scb.build_mocs(cache, FOLDERS)
    assert moc["name"] == "Projects"


def test_moc_propose_link_pool_still_contains_an_excluded_moc():
    """F5-AC2 guard: the exclude tag still only suppresses /moc-propose audit output."""
    entries = [
        {"kind": "moc", "path": "Atlas/200 Maps/Japan (MOC).md", "stem": "Japan (MOC)",
         "topics": ["japan", "travel"], "tags": ["MiYo/Tomo/exclude/moc"], "up_state": "valid"},
        {"kind": "note", "path": "Notes/Kyoto.md", "stem": "Kyoto",
         "topics": ["japan", "travel"], "tags": [], "up_state": "absent"},
    ]
    (suggestion,) = emit_orphan_suggestions(entries)
    assert suggestion["mode"] == "link_existing"
    assert [c["target_moc"] for c in suggestion["candidates"]] == ["Japan (MOC)"]


# ── placeholder targets ──────────────────────────────────────────────────────

def test_placeholder_targets_are_sorted_unique_moc_names():
    cache = {"placeholder_links": [
        {"target": "Weinbau (MOC)", "referenced_by": "a.md"},
        {"target": "Weinbau (MOC)", "referenced_by": "b.md"},
        {"target": "Burgen MOC", "referenced_by": "a.md"},
        {"target": "Just A Note", "referenced_by": "a.md"},
    ]}
    assert scb.build_placeholder_targets(cache) == ["Burgen MOC", "Weinbau (MOC)"]


def test_placeholder_targets_is_an_empty_list_without_placeholders():
    assert scb.build_placeholder_targets({}) == []


# ── the written context ──────────────────────────────────────────────────────

def _write_inputs(tmp_path: Path, cache: dict) -> list[str]:
    (tmp_path / "cache.yaml").write_text(yaml.safe_dump(cache), encoding="utf-8")
    (tmp_path / "vault-config.yaml").write_text(yaml.safe_dump({
        "profile": "miyo",
        "tags": {"prefixes": {}},
        "concepts": {"map_note": {"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]}},
    }), encoding="utf-8")
    return [
        sys.executable, str(SCRIPTS_DIR / "shared-ctx-builder.py"),
        "--cache", str(tmp_path / "cache.yaml"),
        "--vault-config", str(tmp_path / "vault-config.yaml"),
        "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
        "--run-id", "r040", "--output", str(tmp_path / "ctx.json"), "--skip-reconcile",
    ]


def test_built_context_has_names_targets_and_no_placeholder_links(tmp_path):
    cache = _traced_cache()
    out = subprocess.run(_write_inputs(tmp_path, cache), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    ctx = json.loads((tmp_path / "ctx.json").read_text())
    assert "placeholder_links" not in ctx
    assert ctx["placeholder_targets"] == []
    assert {m["name"] for m in ctx["mocs"]} >= {"Projects", "Efforts/Work/Projects.md"}
    jsonschema.validate(ctx, SCHEMA)


def test_schema_rejects_old_placeholder_links_and_missing_targets(tmp_path):
    out = subprocess.run(_write_inputs(tmp_path, _traced_cache()), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    ctx = json.loads((tmp_path / "ctx.json").read_text())

    with_links = dict(ctx, placeholder_links=[{"target": "X (MOC)", "referenced_by": "a.md"}])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(with_links, SCHEMA)

    without_targets = {k: v for k, v in ctx.items() if k != "placeholder_targets"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(without_targets, SCHEMA)

    nameless = dict(ctx, mocs=[{k: v for k, v in m.items() if k != "name"} for m in ctx["mocs"]])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(nameless, SCHEMA)
