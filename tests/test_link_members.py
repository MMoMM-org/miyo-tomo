"""Spec 042 T1.2 — NodeEligibility: which linked notes may become link members.

Every test starts from ONE eligible cached note and changes exactly one thing,
so each rule is falsified on its own (PRD F6-AC1, F6-AC2, F6-AC4).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.link_members import NodeEligibility  # noqa: E402

GOOD = "Vault/Notes/Idea.md"

PROFILE = {
    "concept_defaults": {
        "inbox": "Vault/Inbox/",
        "atomic_note": {
            "base_path": "Vault/Notes/",
            "subdirectories": [{"path": "Vault/Notes/Sub/"}],
        },
        "map_note": {"name_suffix": " (MOC)"},
        "calendar": {
            "base_path": "Vault/Cal/",
            "granularities": {
                "daily": {"enabled": True, "path": "Vault/Cal/Days/"},
                "weekly": {"enabled": True, "path": "Vault/Cal/Weeks/"},
                "yearly": {"enabled": False, "path": None},
            },
        },
    }
}

VAULT_CFG = {
    "concepts": {
        "calendar": {"granularities": {"daily": {"path": "Vault/Notes/Journal/ "}}},
    },
    "tomo": {"moc_structure_cache": {"exclude_paths": ["Vault/Notes/Private/"]}},
}


def _entry(path, kind="note", tags=None):
    return {"path": path, "kind": kind, "tags": tags or []}


def _make(extra_entries=(), profile=PROFILE, vault_cfg=VAULT_CFG):
    entries = [_entry(GOOD)] + list(extra_entries)
    cache = {
        "entries": entries,
        "map_notes": [e for e in entries if e["kind"] == "moc"],
    }
    return NodeEligibility(cache, copy.deepcopy(profile), copy.deepcopy(vault_cfg))


class TestEligibility:
    def test_cached_atomic_note_is_eligible(self):
        assert _make().check(GOOD) == (True, "ok")

    def test_non_md_path(self):
        e = _make([_entry("Vault/Notes/pic.png")])
        assert e.check("Vault/Notes/pic.png") == (False, "not-md")

    def test_outside_atomic_note_paths(self):
        p = "Elsewhere/Idea.md"
        assert _make([_entry(p)]).check(p) == (False, "out-of-scope")

    def test_atomic_subdirectory_is_in_scope(self):
        p = "Vault/Notes/Sub/Deep.md"
        assert _make([_entry(p)]).check(p) == (True, "ok")

    def test_sibling_prefix_is_not_in_scope(self):
        p = "Vault/Notes2/Idea.md"
        assert _make([_entry(p)]).check(p) == (False, "out-of-scope")

    def test_inbox_path(self):
        profile = copy.deepcopy(PROFILE)
        profile["concept_defaults"]["atomic_note"]["base_path"] = "Vault/"
        p = "Vault/Inbox/Draft.md"
        e = _make([_entry(p)], profile=profile)
        assert e.check(p) == (False, "inbox")

    def test_inbox_from_vault_config_overrides_profile(self):
        cfg = copy.deepcopy(VAULT_CFG)
        cfg["concepts"]["inbox"] = "Vault/Notes/Landing/"
        p = "Vault/Notes/Landing/Draft.md"
        assert _make([_entry(p)], vault_cfg=cfg).check(p) == (False, "inbox")

    @pytest.mark.parametrize(
        "path",
        [
            "Vault/Cal/2026-10-01.md",  # profile calendar base_path
            "Vault/Cal/Days/2026-10-01.md",  # profile granularity
            "Vault/Cal/Weeks/2026-W40.md",  # profile granularity
            "Vault/Notes/Journal/2026-10-01.md",  # vault-config, trailing space
            "Vault/Notes/Private/Secret.md",  # exclude_paths
        ],
    )
    def test_periodic_path(self, path):
        profile = copy.deepcopy(PROFILE)
        profile["concept_defaults"]["atomic_note"]["base_path"] = "Vault/"
        e = _make([_entry(path)], profile=profile)
        assert e.check(path) == (False, "periodic")
        assert e.is_periodic(path)
        assert not e.is_periodic(GOOD)

    def test_vault_config_calendar_base_path(self):
        cfg = copy.deepcopy(VAULT_CFG)
        cfg["concepts"]["calendar"]["base_path"] = "Vault/Notes/Cal2/"
        p = "Vault/Notes/Cal2/x.md"
        e = _make([_entry(p)], vault_cfg=cfg)
        assert e.check(p) == (False, "periodic")

    def test_real_profile_and_trailing_space_daily(self):
        profile = yaml.safe_load((REPO_ROOT / "tomo/profiles/miyo.yaml").read_text())
        cfg = {
            "concepts": {
                "calendar": {
                    "base_path": "Calendar/",
                    "granularities": {"daily": {"path": "Calendar/301 Daily/ "}},
                }
            }
        }
        note = "Atlas/202 Notes/2021 Thoughts/Idea.md"
        daily = "Calendar/301 Daily/2026-10-01.md"
        e = NodeEligibility(
            {"entries": [_entry(note), _entry(daily)], "map_notes": []}, profile, cfg
        )
        assert e.check(note) == (True, "ok")
        assert e.check(daily) == (False, "periodic")

    def test_moc_by_cache_kind(self):
        p = "Vault/Notes/Hub.md"
        e = _make([_entry(p, kind="moc")])
        assert e.check(p) == (False, "moc")
        assert e.is_moc(p) and not e.is_moc(GOOD)

    def test_moc_by_map_notes(self):
        p = "Vault/Notes/Hub.md"
        cache = {"entries": [_entry(GOOD), _entry(p)], "map_notes": [{"path": p}]}
        e = NodeEligibility(cache, PROFILE, VAULT_CFG)
        assert e.check(p) == (False, "moc")

    def test_moc_by_name_suffix(self):
        p = "Vault/Notes/Cooking (MOC).md"
        e = _make([_entry(p)])
        assert e.check(p) == (False, "moc")

    @pytest.mark.parametrize("tag", ["MiYo/Tomo/exclude/note", "#MiYo/Tomo/exclude/note"])
    def test_exclude_note_tag(self, tag):
        p = "Vault/Notes/Hidden.md"
        e = _make([_entry(p, tags=["topic/x", tag])])
        assert e.check(p) == (False, "excluded-tag")

    def test_exclude_moc_tag_does_not_exclude_a_note(self):
        p = "Vault/Notes/Other.md"
        e = _make([_entry(p, tags=["MiYo/Tomo/exclude/moc"])])
        assert e.check(p) == (True, "ok")

    def test_uncached_path(self):
        assert _make().check("Vault/Notes/New.md") == (False, "uncached")

    def test_periodic_and_uncached_reports_periodic(self):
        assert _make().check("Vault/Cal/Days/2026-10-02.md") == (False, "periodic")

    def test_missing_config_sections_do_not_raise(self):
        e = NodeEligibility({"entries": [_entry(GOOD)]}, {}, {})
        assert e.check(GOOD) == (True, "ok")

    def test_module_never_prints_or_logs(self, capsys):
        e = _make()
        for p in (GOOD, "Elsewhere/x.md", "Vault/Notes/New.md"):
            e.check(p)
        out = capsys.readouterr()
        assert out.out == "" and out.err == ""
