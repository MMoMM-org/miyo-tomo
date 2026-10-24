#!/usr/bin/env python3
# version: 0.1.0
"""test_200_classification_candidates.py — #200: no classification MOC as a note candidate.

Dewey-layer MOCs are MOC-only containers: they never link a note. The analyst
is told not to nominate one, and the reducer drops any candidate the context
marks `is_classification: true` before render and persist.

RED on `main`: the reducer keeps classification candidates, has no
`classification_candidates_dropped=` summary key, and Step 4 still allows
classification names to be nominated.

Mechanisms falsified:
  - no drop / drop after render       → rendered markdown, persisted candidates
  - drop by title pattern, not flag    → a Dewey-looking thematic MOC is kept
  - fail-closed context handling       → missing/invalid context drops nothing
  - prose still allowing nomination    → Step 4 and the decision table text
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER = SCRIPTS_DIR / "suggestions-reducer.py"
AGENT = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
sys.path.insert(0, str(SCRIPTS_DIR))
from lib.classification_candidates import (  # noqa: E402
    drop_classification_candidates,
    load_classification_paths,
)
from lib.item_key import to_filename  # noqa: E402

_ENV = {**os.environ, "PYTHONPATH": str(SCRIPTS_DIR)}
RUN = "test-200"
DEWEY = "Atlas/200 Maps/2900 - History & Geography.md"
TRIP = "Atlas/200 Maps/Trip (MOC).md"
# A thematic MOC whose title merely looks numbered: the context flag decides, not the title.
YEAR = "Atlas/200 Maps/2026 - Year Review.md"

_CTX = {
    "schema_version": "1", "run_id": RUN, "tag_prefixes": [], "classification_keywords": {},
    "asset_folder": "Atlas/290 Assets/", "placeholder_targets": [],
    "mocs": [
        {"name": "2900 - History & Geography", "path": DEWEY, "title": "2900 - History & Geography",
         "topics": ["history"], "is_classification": True},
        {"name": "Trip (MOC)", "path": TRIP, "title": "Trip (MOC)", "topics": ["trip"], "is_classification": False},
        {"name": "2026 - Year Review", "path": YEAR, "title": "2026 - Year Review", "topics": ["year"],
         "is_classification": False},
    ],
}


def _write_ctx(path: Path) -> Path:
    path.write_text(json.dumps(_CTX), encoding="utf-8")
    return path


# ── lib ──────────────────────────────────────────────────────────────────────

def test_only_flagged_paths_are_classification(tmp_path):
    assert load_classification_paths(_write_ctx(tmp_path / "ctx.json")) == {DEWEY}


@pytest.mark.parametrize("content", [None, "{not json", json.dumps({"mocs": "x"}), json.dumps([1])])
def test_an_unusable_context_yields_no_paths(tmp_path, content):
    ctx = tmp_path / "ctx.json"
    if content is not None:
        ctx.write_text(content, encoding="utf-8")
    assert load_classification_paths(ctx) == set()
    assert load_classification_paths(None) == set()


def test_drop_removes_flagged_candidates_and_keeps_order():
    action = {"candidate_mocs": [{"path": DEWEY, "score": 0.4, "pre_check": False},
                                 {"path": TRIP, "score": 0.3, "pre_check": False},
                                 {"path": YEAR, "score": 0.2, "pre_check": False}]}
    assert drop_classification_candidates(action, {DEWEY}) == 1
    assert [c["path"] for c in action["candidate_mocs"]] == [TRIP, YEAR]


def test_drop_without_candidates_is_a_no_op():
    action = {"kind": "create_atomic_note"}
    assert drop_classification_candidates(action, {DEWEY}) == 0
    assert "candidate_mocs" not in action


# ── reducer ──────────────────────────────────────────────────────────────────

def _reduce(tmp_path: Path, ctx: str = "valid") -> tuple[dict, str]:
    items = tmp_path / "items"
    items.mkdir()
    key = "100 Inbox/Freiberg.md"
    cands = [{"path": DEWEY, "score": 0.3, "pre_check": False}, {"path": TRIP, "score": 0.3, "pre_check": False}]
    action = {
        "kind": "create_atomic_note", "suggested_title": "Freiberg", "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo", "location": "Atlas/202 Notes/", "candidate_mocs": cands,
        "needs_new_moc": False, "proposed_moc_topic": None, "tags_to_add": [],
        "classification": {"category": "900 History & Geography", "confidence": 0.8}, "alternatives": [],
    }
    (items / to_filename(key)).write_text(json.dumps({
        "schema_version": "1", "stem": "Freiberg", "path": key, "item_key": key, "type": "fleeting_note",
        "type_confidence": 0.9, "force_atomic": False, "actions": [action], "candidate_mocs": cands,
        "classification": action["classification"], "needs_new_moc": False, "proposed_moc_topic": None,
        "tags_to_add": [], "atomic_note_worthiness": 0.8, "alternatives": [], "issues": [], "duration_ms": 0,
    }), encoding="utf-8")
    state = tmp_path / "state.jsonl"
    state.write_text(json.dumps({"stem": "Freiberg", "path": key, "item_key": key, "status": "done",
                                 "run_id": RUN, "ts": "2026-10-24T10:00:00Z"}) + "\n", encoding="utf-8")
    shared = tmp_path / "shared-ctx.json"
    if ctx == "valid":
        _write_ctx(shared)
    elif ctx == "invalid":
        shared.write_text("{not json", encoding="utf-8")
    out = tmp_path / "doc.json"
    proc = subprocess.run([sys.executable, str(REDUCER), "--state", str(state), "--items-dir", str(items),
                           "--run-id", RUN, "--profile", "miyo", "--shared-ctx", str(shared),
                           "--output", str(out), "--no-kado"], capture_output=True, text=True, env=_ENV)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8")), proc.stderr


def _atomic(doc: dict) -> dict:
    (section,) = doc["sections"]
    return next(a for a in section["actions"] if a["kind"] == "create_atomic_note")


def _summary(stderr: str) -> str:
    return [ln for ln in stderr.splitlines() if ln.startswith("suggestions-reducer: done=")][-1]


def test_the_reducer_drops_the_classification_candidate_before_render(tmp_path):
    doc, stderr = _reduce(tmp_path)
    action = _atomic(doc)
    assert [c["path"] for c in action["candidate_mocs"]] == [TRIP]
    assert "2900 - History & Geography" not in action["rendered_md"]
    assert "[[Atlas/200 Maps/Trip (MOC)]]" in action["rendered_md"]
    assert " classification_candidates_dropped=1 duplicate_proposals_converted=0 " in _summary(stderr)


@pytest.mark.parametrize("ctx", ["missing", "invalid"])
def test_without_a_usable_context_nothing_is_dropped(tmp_path, ctx):
    doc, stderr = _reduce(tmp_path, ctx=ctx)
    assert [c["path"] for c in _atomic(doc)["candidate_mocs"]] == [DEWEY, TRIP]
    assert " classification_candidates_dropped=0 " in _summary(stderr)


# ── analyst prose ────────────────────────────────────────────────────────────

def _step4() -> str:
    text = AGENT.read_text(encoding="utf-8")
    return text[text.index("### Step 4"):text.index("### Step 5")]


def test_step_4_never_nominates_a_classification_name():
    step4 = " ".join(_step4().split())
    assert "classification names may both be nominated" not in step4
    assert "Never nominate a classification name" in step4
    assert "Never list a MOC with `is_classification: true` in `candidate_mocs`" in step4


def test_row_3_proposes_when_only_classification_fits():
    rows = [ln for ln in _step4().splitlines() if ln.startswith("| 3 |")]
    assert len(rows) == 1 and "only a classification" in rows[0].lower() and "0.15" in rows[0]
