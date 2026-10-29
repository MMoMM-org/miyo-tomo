#!/usr/bin/env python3
# version: 0.1.0
"""test_up_state.py — the shared up-target classification (#216).

`lib/up_state.classify_up_target` is the one place that turns a parsed `up`
target into (up_state, up_broken_reason). Two callers use it:
`moc-tree-builder.py` `build_entries` (writes the cache) and `moc-discovery.py`
`phase65_validate_existing_up` (decorates topic members). The parity test runs
both real entry points on the same vault and asserts each one's answer equals
the helper's, so a caller that stops using the helper (or drifts) turns it red.

No live Kado: both callers read through local fakes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.up_state import classify_up_target  # noqa: E402
from lib.kado_client import KadoNotFoundError  # noqa: E402


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_builder = _load("moc_tree_builder_up_state", "moc-tree-builder.py")
_disc = _load("moc_discovery_up_state", "moc-discovery.py")


# ── The helper on its own ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "target, expected",
    [
        (None, ("absent", None)),
        ("Home", ("valid", None)),
        ("Idea", ("broken", "not-a-moc")),
        ("Nonexistent", ("broken", "unresolved")),
        ("Shared", ("valid", None)),  # in both sets: the MOC wins the tie
    ],
)
def test_classify_up_target(target, expected):
    assert classify_up_target(target, {"Home", "Shared"}, {"Idea", "Shared"}) == expected


# ── Parity: both callers answer what the helper answers ──────────────────────

_MAPS = "Atlas/200 Maps/"
_NOTES = "Atlas/202 Notes/"
_MOC = f"{_MAPS}Home.md"
_PLAIN = f"{_NOTES}Idea.md"
# child stem → its `up` declaration (None = no up line)
_CHILDREN = {
    "no-up": None,
    "to-moc": "up:: [[Home]]",
    "to-note": "up:: [[Idea]]",
    "to-ghost": "up:: [[Ghost]]",
    "fm-to-moc": "FM:Home",
}


def _content(decl):
    if decl is None:
        return "# child\n"
    if decl.startswith("FM:"):
        return f"---\nup: \"[[{decl[3:]}]]\"\n---\n# child\n"
    return f"# child\n\n{decl}\n"


class _Kado:
    def __init__(self, notes):
        self._notes = notes

    def search_by_tag(self, tag, limit=500):
        return [{"path": _MOC}]

    def list_notes(self, path, **kwargs):
        return [{"path": p} for p in self._notes if p.startswith(path)]

    def read_note(self, path):
        if path not in self._notes:
            raise KadoNotFoundError(path)
        return {"content": self._notes[path]}


def _vault():
    notes = {
        _MOC: "---\ntitle: Home\ntags:\n  - type/others/moc\n---\n# Home\n",
        _PLAIN: "# Idea\n",
    }
    for stem, decl in _CHILDREN.items():
        notes[f"{_NOTES}{stem}.md"] = _content(decl)
    return notes


def _config():
    return {
        "concepts": {
            "map_note": {"paths": [_MAPS], "tags": ["type/others/moc"]},
            "atomic_note": {"path": _NOTES},
        },
        "tomo": {
            "moc_structure_cache": {
                "scope_paths": [_MAPS, _NOTES],
                "exclude_paths": [],
                "ttl_days": 1,
                "moc_tag": "type/others/moc",
            }
        },
    }


def test_both_callers_classify_like_the_helper():
    notes = _vault()
    cache, _feed = _builder.run_with_client(_Kado(notes), _config())
    entries = {e["stem"]: e for e in cache["entries"]}
    moc_stems = {s for s, e in entries.items() if e["kind"] == "moc"}
    note_stems = {s for s, e in entries.items() if e["kind"] == "note"}

    disc_cache = {
        "map_notes": [e for e in cache["entries"] if e["kind"] == "moc"],
        "entries": cache["entries"],
    }
    candidates = [_disc.Candidate(stem=s, path=f"{_NOTES}{s}.md") for s in _CHILDREN]
    clusters = [{"topic": "t", "items": list(_CHILDREN), "parent": "", "tags": []}]
    (cluster,) = _disc.phase65_validate_existing_up(clusters, candidates, _Kado(notes), disc_cache)
    rows = {r["stem"]: r for r in cluster["existing_up"]}

    seen = set()
    for stem in _CHILDREN:
        entry, row = entries[stem], rows[stem]
        assert entry["up_target"] == row["target"]
        expected = classify_up_target(entry["up_target"], moc_stems, note_stems)
        assert (entry["up_state"], entry["up_broken_reason"]) == expected, stem
        assert (row["state"], row.get("reason")) == expected, stem
        seen.add(expected)
    # every branch of the helper is exercised
    assert seen == {
        ("absent", None), ("valid", None), ("broken", "not-a-moc"), ("broken", "unresolved"),
    }
