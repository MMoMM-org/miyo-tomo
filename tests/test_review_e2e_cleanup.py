#!/usr/bin/env python3
# version: 0.1.0
"""test_review_e2e_cleanup.py — a review set's MD peer names what Hashi's cleanup may trash (spec 046 T6.3).

Hashi's cleanup after a full apply (Hashi ADR-018 §4, #146) reads `tomo.sources[]` from the MD peer's
frontmatter, then merges `tomo.state: applied`, trashes every `sources[].path`, the peer and the set JSON.
Owner decision 2026-11-17: a review set's peer lists the review document and, for a new-note delivery, the
new note's inbox copy — never the review target (the user's week, month or quarter note). A withdrawn
set's peer lists nothing (`sources: []`). After the cleanup the review is not listed, `status` is
`not-found`, and a later `/review` of the period starts fresh and delivers against the note as it is. A
cleanup that stopped midway (document gone, set left; set gone, document left) never reads as
`failed-delivery` and never blocks the next run. The cleanup is simulated on the fake's files, the way the
walk simulates Hashi's apply. Named `test_review_e2e_*` so the shared inbox sweep
(`review_e2e_walk.sweep_writes_under_inbox`) covers its writes. All data is synthetic.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    CONFIG, INBOX, MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, MONTH_TARGET, WEEK, WEEK_DOC, WEEK_PERIOD,
    WEEK_STEM, WEEK_TARGET, Walk, frontmatter, tomo_sections,
)
from lib import review_actions as ra  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402

NEW_NOTE = f"{INBOX}{MONTH_PERIOD}.md"


def _set_json(stem: str) -> str:
    return f"{INBOX}{stem}_instructions.json"


def _set_md(stem: str) -> str:
    return f"{INBOX}{stem}_instructions.md"


@pytest.fixture
def ready(tmp_path, monkeypatch, capsys, request):
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=CONFIG)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def _sources(walk: Walk, stem: str) -> list:
    return frontmatter(walk.vault.text(_set_md(stem)))["tomo"].get("sources")


def hashi_cleanup(walk: Walk, stem: str, *, stop_after: int = 3) -> list[str]:
    """Hashi's cleanupAfterFullApply on the fake: trash every `sources[].path` (a gone path only warns), then
    the peer, then the set JSON; `stop_after` ends it after that many of the three stages. Returns the warned paths."""
    sources = _sources(walk, stem)
    assert isinstance(sources, list), "no tomo.sources: Hashi writes nothing and trashes nothing"
    warned = [s["path"] for s in sources if walk.vault.files.pop(s["path"], None) is None]
    if stop_after >= 2:
        del walk.vault.files[_set_md(stem)]
    if stop_after >= 3:
        del walk.vault.files[_set_json(stem)]
    return warned


def _delivered_month(walk: Walk) -> None:
    walk.pass1(MONTH_PERIOD, MONTH)
    walk.approve(MONTH_DOC)
    out = walk.deliver(MONTH_STEM)
    assert out["status"] == "delivered" and out["mode"] == "new-note", out


def _delivered_week(walk: Walk) -> None:
    walk.pass1(WEEK_PERIOD, WEEK)
    walk.approve(WEEK_DOC)
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["mode"] == "insert", out


def _rerun_delivers(walk: Walk, stem: str, period: str, kind: str, doc: str, target: str) -> None:
    """A later `/review` of the period: nothing open, Pass 1 writes a fresh document, the delivery re-runs."""
    out = walk.start(period)
    assert out["open_reviews"] == [] and out["request"]["kind"] == kind, out
    out = walk.pass1(period, kind)
    assert out["status"] == "written" and out["doc_path"] == doc and out["target_exists"] is True, out
    assert walk.meta(stem)["steps_done"] == [] and walk.listing() == [(stem, "open")]
    walk.approve(doc)
    out = walk.deliver(stem)
    assert out["status"] == "delivered" and out["mode"] == "replace", out
    assert walk.hashi_apply(stem) == ["applied"] and tomo_sections(walk.vault.text(target)) == 1


# ── the peer's sources ────────────────────────────────────────────────────────────────────


def test_week_peer_lists_the_review_document_and_never_the_target(ready: Walk):
    _delivered_week(ready)
    assert _sources(ready, WEEK_STEM) == [{"path": WEEK_DOC}]


def test_month_new_note_peer_lists_the_document_then_the_new_notes_inbox_copy(ready: Walk):
    _delivered_month(ready)
    sources = _sources(ready, MONTH_STEM)
    assert sources == [{"path": MONTH_DOC}, {"path": NEW_NOTE}]
    assert MONTH_TARGET not in [s["path"] for s in sources]


def test_withdrawn_peer_lists_no_source(ready: Walk):
    walk = ready
    _delivered_week(walk)
    assert walk.drop(WEEK_STEM)["status"] == "withdrawn"
    assert _sources(walk, WEEK_STEM) == []
    assert WEEK_DOC in walk.vault.files, "a drop leaves the document to the user"


def test_peer_block_passes_the_doc_frontmatter_schema_strictly(monkeypatch):
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    plan = ra.ReviewPlan(ra.NEW_NOTE, "Cal/2026-03.md", False, [], {})
    plan.note_path = "In/2026-03.md"
    meta = rdl.ReviewMeta({"run_id": "r", "generated": "2026-11-17T08:00:00Z", "doc_path": "In/2026-03 Review.md"})
    block = frontmatter(rdl.set_md(plan, meta, None))["tomo"]
    assert block["sources"] == [{"path": "In/2026-03 Review.md"}, {"path": "In/2026-03.md"}]
    assert list(block) == ["doc_type", "state", "run_id", "updated_at", "sources"], "the /inbox peer's key order"
    assert os.environ["TOMO_SCHEMA_STRICT"] == "1"


def test_a_meta_without_doc_path_lists_no_source():
    plan = ra.ReviewPlan(ra.INSERT, "Cal/2026-W13.md", False, [], {})
    meta = rdl.ReviewMeta({"run_id": "r", "generated": "2026-11-17T08:00:00Z"})
    assert frontmatter(rdl.set_md(plan, meta, None))["tomo"]["sources"] == []


# ── after the cleanup ─────────────────────────────────────────────────────────────────────


def test_week_after_a_full_cleanup_is_nothing_open_and_the_rerun_replaces_the_block(ready: Walk):
    walk = ready
    _delivered_week(walk)
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    assert hashi_cleanup(walk, WEEK_STEM) == []
    assert WEEK_TARGET in walk.vault.files and WEEK_DOC not in walk.vault.files
    assert walk.listing() == []
    assert walk.status(WEEK_STEM) == {"status": "not-found", "stem": WEEK_STEM, "doc_path": WEEK_DOC}
    _rerun_delivers(walk, WEEK_STEM, WEEK_PERIOD, WEEK, WEEK_DOC, WEEK_TARGET)


def test_month_after_a_full_cleanup_warns_on_the_moved_note_and_the_rerun_inserts_into_it(ready: Walk):
    walk = ready
    _delivered_month(walk)
    assert walk.hashi_apply(MONTH_STEM) == ["applied"]
    assert hashi_cleanup(walk, MONTH_STEM) == [NEW_NOTE], "the moved inbox copy is already gone: Hashi only warns"
    assert MONTH_TARGET in walk.vault.files and walk.listing() == []
    _rerun_delivers(walk, MONTH_STEM, MONTH_PERIOD, MONTH, MONTH_DOC, MONTH_TARGET)


# ── a cleanup that stopped midway ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("stop_after", [1, 2], ids=["peer-and-set-left", "set-left"])
def test_document_gone_set_left_is_nothing_open_and_the_rerun_writes_over_the_applied_set(ready: Walk, stop_after):
    walk = ready
    _delivered_week(walk)
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    hashi_cleanup(walk, WEEK_STEM, stop_after=stop_after)
    assert WEEK_DOC not in walk.vault.files and _set_json(WEEK_STEM) in walk.vault.files
    assert walk.listing() == []
    assert walk.status(WEEK_STEM)["status"] == "not-found"
    _rerun_delivers(walk, WEEK_STEM, WEEK_PERIOD, WEEK, WEEK_DOC, WEEK_TARGET)


def test_set_gone_document_left_is_finished_and_the_rerun_starts_over(ready: Walk):
    """Hashi could not trash the document (it only warns) and went on: the peer and the set are gone."""
    walk = ready
    _delivered_week(walk)
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    kept = walk.vault.files[WEEK_DOC]
    hashi_cleanup(walk, WEEK_STEM)
    walk.vault.files[WEEK_DOC] = kept
    assert walk.listing() == [], "a complete delivery whose set is gone is finished, never failed-delivery"
    assert walk.status(WEEK_STEM) == {"state": None, "stem": WEEK_STEM}
    walk.read(WEEK_PERIOD, WEEK)
    out = walk.write(WEEK_STEM, WEEK)
    assert out["status"] == "refused" and out["problems"] == ["review-exists"], out
    assert walk.replace(WEEK_STEM, "--confirm")["status"] == "replaced"
    walk.approve(WEEK_DOC)
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["mode"] == "replace", out


def test_the_review_target_is_never_a_source_even_when_a_path_names_it():
    """Hashi trashes every listed path: a document or inbox copy path equal to the target is dropped."""
    plan = ra.ReviewPlan(ra.NEW_NOTE, "In/2026-03.md", False, [], {})
    plan.note_path = "In/2026-03.md"
    meta = rdl.ReviewMeta({"run_id": "r", "generated": "2026-11-17T08:00:00Z", "doc_path": "In/2026-03.md"})
    assert rdl.peer_sources(plan, meta) == []
