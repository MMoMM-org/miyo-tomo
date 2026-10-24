#!/usr/bin/env python3
# version: 0.1.0
"""test_040_duplicate_proposals.py — spec 040 T3.1: the reducer's duplicate mutator.

An analyst that proposes a new MOC whose name already exists (by the cluster
key: marker stripped, normalised, plural-folded) must not reach the owner as a
"create MOC" offer. The reducer converts it once per action, before render,
persist and cluster collection (SDD ADR-6): the proposal is cleared and every
matching eligible thematic MOC is appended as an unticked candidate.

RED on `main`: the summary key `duplicate_proposals_converted` does not exist
there, and nothing converts.

Mechanisms falsified:
  - no conversion / conversion after render → rendered markdown and wire state
  - conversion that ignores the cluster key  → "Vacations", "Project"/"Projects"
  - conversion against classification or excluded MOCs → Dewey and 000 Index rows
  - conversion of suppressed atomics          → the sub-worthy "Vacation" row
  - duplicate candidate paths                 → the already-listing row
  - fail-closed context handling              → missing/invalid context rows
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER = SCRIPTS_DIR / "suggestions-reducer.py"
sys.path.insert(0, str(SCRIPTS_DIR))
from lib.item_key import to_filename  # noqa: E402

_ENV = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR) + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
RUN = "test-040-dup"

VACATION = "Atlas/200 Maps/Vacation (MOC).md"
JAPAN = "Atlas/200 Maps/Japan (MOC).md"
PROJECTS_A = "Atlas/200 Maps/Projects.md"
PROJECTS_B = "Efforts/Work/Projects.md"

_CTX_MOCS = [
    {"name": "Vacation (MOC)", "path": VACATION, "title": "Vacation (MOC)", "topics": ["vacation"], "is_classification": False},
    {"name": "Japan (MOC)", "path": JAPAN, "title": "Japan (MOC)", "topics": ["japan"], "is_classification": False},
    {"name": PROJECTS_A, "path": PROJECTS_A, "title": "Projects", "topics": ["projects"], "is_classification": False},
    {"name": PROJECTS_B, "path": PROJECTS_B, "title": "Projects", "topics": ["work"], "is_classification": False},
    {"name": "2000 - Knowledge", "path": "Atlas/200 Maps/2000 - Knowledge.md", "title": "2000 - Knowledge",
     "topics": ["knowledge"], "is_classification": True},
    # "000 Index" is tagged MiYo/Tomo/exclude/moc in the vault: the builder never emits it.
]

# stem -> (proposed topic, worthiness, candidate_mocs the analyst listed)
_ITEMS = {
    "vacations": ("Vacations", 0.8, [{"path": JAPAN, "score": 0.3, "pre_check": False}]),
    "project": ("Project", 0.8, []),
    "projects-pair": ("Projects", 0.8, []),
    "already-listed": ("Vacation (MOC)", 0.8, [{"path": VACATION, "score": 0.2, "pre_check": False}]),
    "urlaub": ("Urlaub", 0.8, []),
    "dewey": ("2000 - Knowledge", 0.8, []),
    "excluded-index": ("000 Index", 0.8, []),
    "suppressed": ("Vacation", 0.3, []),
}
CONVERTED = {"vacations", "project", "projects-pair", "already-listed"}


def _ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1", "run_id": RUN, "mocs": _CTX_MOCS, "tag_prefixes": [],
        "classification_keywords": {}, "asset_folder": "Atlas/290 Assets/295 Attachments/",
        "placeholder_targets": [],
    }), encoding="utf-8")


def _result(items_dir: Path, stem: str, topic: str, worthiness: float, candidates: list) -> None:
    key = f"100 Inbox/{stem}.md"
    action = {
        "kind": "create_atomic_note",
        "suggested_title": f"Note {stem}",
        "atomic_note_worthiness": worthiness,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": candidates,
        "needs_new_moc": True,
        "proposed_moc_topic": topic,
        "tags_to_add": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "alternatives": [],
    }
    (items_dir / to_filename(key)).write_text(json.dumps({
        "schema_version": "1", "stem": stem, "path": key, "item_key": key,
        "type": "fleeting_note", "type_confidence": 0.9, "force_atomic": False,
        "actions": [action], "candidate_mocs": candidates,
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "needs_new_moc": True, "proposed_moc_topic": topic, "tags_to_add": [],
        "atomic_note_worthiness": worthiness, "alternatives": [], "issues": [], "duration_ms": 0,
    }), encoding="utf-8")


def _reduce(tmp_path: Path, ctx: str = "valid") -> tuple[dict, str]:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    for stem, (topic, worth, cands) in _ITEMS.items():
        _result(items_dir, stem, topic, worth, [dict(c) for c in cands])
    state = tmp_path / "state.jsonl"
    state.write_text("".join(json.dumps({
        "stem": s, "path": f"100 Inbox/{s}.md", "item_key": f"100 Inbox/{s}.md",
        "status": "done", "run_id": RUN, "ts": "2026-10-24T10:00:00Z",
    }) + "\n" for s in _ITEMS), encoding="utf-8")
    shared_ctx = tmp_path / "shared-ctx.json"
    if ctx == "valid":
        _ctx(shared_ctx)
    elif ctx == "invalid":
        shared_ctx.write_text("{not json", encoding="utf-8")
    out = tmp_path / "doc.json"
    proc = subprocess.run([
        sys.executable, str(REDUCER), "--state", str(state), "--items-dir", str(items_dir),
        "--run-id", RUN, "--profile", "miyo", "--shared-ctx", str(shared_ctx),
        "--output", str(out), "--no-kado",
    ], capture_output=True, text=True, env=_ENV)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8")), proc.stderr


def _by_stem(doc: dict) -> dict[str, dict]:
    out = {}
    for section in doc["sections"]:
        atomics = [a for a in section["actions"] if a["kind"] == "create_atomic_note"]
        out[section["stem"]] = atomics[0]
    return out


def _summary_count(stderr: str) -> str:
    line = [ln for ln in stderr.splitlines() if ln.startswith("suggestions-reducer: done=")][-1]
    marker = "duplicate_proposals_converted="
    assert marker in line, line
    return line.split(marker, 1)[1].split()[0]


@pytest.fixture(scope="module")
def reduced(tmp_path_factory):
    return _reduce(tmp_path_factory.mktemp("dup"))


def test_exactly_the_four_duplicates_are_converted(reduced):
    _doc, stderr = reduced
    assert _summary_count(stderr) == "4"


def test_converted_actions_list_the_existing_moc_unticked(reduced):
    doc, _ = reduced
    actions = _by_stem(doc)
    paths = {s: [c["path"] for c in actions[s].get("candidate_mocs", [])] for s in actions}
    assert paths["vacations"] == [JAPAN, VACATION]          # the analyst's own first stays first
    assert paths["project"] == [PROJECTS_A, PROJECTS_B]     # every colliding path
    assert paths["projects-pair"] == [PROJECTS_A, PROJECTS_B]
    assert paths["already-listed"] == [VACATION]            # no duplicate path
    for stem in CONVERTED:
        for cand in actions[stem]["candidate_mocs"]:
            if cand["path"] in (VACATION, PROJECTS_A, PROJECTS_B) and stem != "already-listed":
                assert cand == {"path": cand["path"], "anchor": None, "pre_check": False, "score": 0.0}


def test_converted_actions_drop_the_new_moc_offer(reduced):
    doc, _ = reduced
    actions = _by_stem(doc)
    for stem in CONVERTED:
        md = actions[stem]["rendered_md"]
        assert "No good thematic MOC matched" not in md, stem
    md = actions["vacations"]["rendered_md"]
    line = "- [ ] [[Atlas/200 Maps/Vacation (MOC)]]"
    assert line in md
    after = md.split(line, 1)[1].lstrip("\n")
    assert not after.startswith("**Placement:**")


def test_only_unconverted_topics_reach_proposed_mocs(reduced):
    doc, _ = reduced
    names = " | ".join(json.dumps(p, ensure_ascii=False) for p in doc.get("proposed_mocs") or [])
    assert "Urlaub" in names and "Knowledge" in names and "000 Index" in names
    for gone in ("Vacation", "Project"):
        assert gone not in names, names


def test_unconverted_and_suppressed_actions_are_unchanged(reduced):
    doc, _ = reduced
    actions = _by_stem(doc)
    for stem in ("urlaub", "dewey", "excluded-index"):
        assert "No good thematic MOC matched" in actions[stem]["rendered_md"], stem
        assert not actions[stem].get("candidate_mocs"), stem
    assert "Vacation (MOC)]]" not in actions["suppressed"]["rendered_md"]


def test_wire_projection_shows_the_appended_moc_unselected(reduced):
    doc, _ = reduced
    spec = importlib.util.spec_from_file_location("suggestions_render_040", SCRIPTS_DIR / "suggestions-render.py")
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)
    section = next(s for s in doc["sections"] if s["stem"] == "vacations")
    action = next(a for a in section["actions"] if a["kind"] == "create_atomic_note")
    wire = render._wire_note(section, action)
    cand = next(c for c in wire["candidate_mocs"] if c["path"] == VACATION)
    assert cand["selected"] is False and cand["source"] == "tomo"


@pytest.mark.parametrize("ctx", ["missing", "invalid"])
def test_without_a_usable_context_nothing_converts(tmp_path, ctx):
    doc, stderr = _reduce(tmp_path, ctx=ctx)
    assert _summary_count(stderr) == "0"
    assert "No good thematic MOC matched" in _by_stem(doc)["vacations"]["rendered_md"]
