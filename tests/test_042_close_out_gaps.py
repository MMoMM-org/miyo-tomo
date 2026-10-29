#!/usr/bin/env python3
# version: 0.1.0
"""Spec 042 close-out — three criteria no existing test could fail.

The T5.4 trace broke each behaviour in a copy of the tree and ran the full
suite: nothing went red. Each test below closes one of those gaps.

Mechanisms each test falsifies:
  - F4-AC4: a parser that keys the link-member check on a bare " — " instead
    of LINK_MEMBER_MARKER. The T5.3d label "— note not found" carries that
    dash, so such a parser drops a labelled topic member from the squelch
    signature input and from the split lists.
  - F6-AC4: a lookup or discovery step that writes an ineligible or uncached
    neighbour's path to stderr, the report or the proposal doc.
  - F5-AC4: a failed lookup that changes anything in its cluster besides
    `link_members` and `link_lookup_status` (confidence, items, parents,
    existing up::) or in the other clusters.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import test_moc_discovery_links as _links  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402
from test_reducer_moc_proposal_mode import (  # noqa: E402
    _Cfg,
    _link_member,
    _link_report,
    render_moc_proposal_doc,
)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_parser = _load("suggestion_parser_042_gaps", "suggestion-parser.py")
_moc_parser = _load("moc_proposal_parser_042_gaps", "moc-proposal-parser.py")


# ── F4-AC4: a T5.3d label does not change which note a line is ───────────────


def _labelled_report(reason: str | None) -> dict:
    """Sleep Debt (topic) and Lost (link) carry a broken up:: with `reason`, or none."""
    if reason is None:
        lost = _link_member("Lost", ["Energy Level", "Sleep Debt"])
    else:
        lost = {
            **_link_member("Lost", ["Energy Level", "Sleep Debt"],
                           up_state="broken", up_target="Gone"),
            "up_broken_reason": reason,
        }
    report = _link_report([lost])
    rows = report["topic_clusters"][0]["existing_up"]
    for row in rows:
        if row["stem"] == "Sleep Debt":
            row.clear()
            row.update({"stem": "Sleep Debt", "state": "absent", "target": None})
            if reason is not None:
                row.update({"state": "broken", "target": "Gone", "reason": reason})
    return report


def test_t53d_labels_do_not_change_which_note_a_line_is() -> None:
    _, plain = render_moc_proposal_doc(_labelled_report(None), _Cfg())
    _, labelled = render_moc_proposal_doc(_labelled_report("unresolved"), _Cfg())
    assert "- [x] [[Sleep Debt]] (existing up:: [[Gone]] — note not found" in labelled
    assert "- [ ] [[Lost]] (existing up:: [[Gone]] — note not found" in labelled

    sections = _parser.enumerate_all_moc_sections(labelled)
    assert sections == _parser.enumerate_all_moc_sections(plain)
    assert sections[0][2] == ["Energy Level", "Sleep Debt", "Recovery Days"]

    split = _parser.enumerate_moc_sections_split(labelled)
    assert split == _parser.enumerate_moc_sections_split(plain)
    (cluster,) = split[1]
    assert cluster["candidate_stems"] == ["Energy Level", "Sleep Debt", "Recovery Days"]
    assert cluster["children"] == ["Energy Level", "Sleep Debt", "Recovery Days", "Lost"]

    def _accepted(body: str) -> list[str]:
        ticked = body.replace("- [ ] Accept", "- [x] Accept").replace(
            "- [ ] [[Lost]]", "- [x] [[Lost]]"
        )
        return _moc_parser.parse_moc_proposal(ticked)["confirmed_items"][0]["supporting_items"]

    assert _accepted(labelled) == _accepted(plain)
    assert sorted(_accepted(labelled)) == ["Energy Level", "Lost", "Recovery Days", "Sleep Debt"]


# ── F6-AC4: ineligible and uncached neighbours are never named ───────────────


def test_ineligible_and_uncached_neighbours_are_never_named(tmp_path, monkeypatch, capsys):
    """alpha and beta link the uncached `uncached.md` and the daily note: both are
    seen (one counted as skipped_uncached), neither is named anywhere."""
    _, report = _links._run_tag(tmp_path, monkeypatch, _links._GraphFake())
    err = capsys.readouterr().err
    assert report["link_stats"]["skipped_uncached"] == 1
    _, doc = render_moc_proposal_doc(report, _Cfg())
    for path in (_links.U, _links.DAILY):
        stem = path.rsplit("/", 1)[-1].removesuffix(".md")
        assert path not in err, path
        assert path not in json.dumps(report), path
        assert f"[[{stem}]]" not in doc, stem
    assert "uncached.md" not in err and "2026-01-01" not in err


# ── F5-AC4: a failed lookup changes nothing but its link fields ─────────────


class _FailOnDelta(_links._GraphFake):
    def graph(self, operation, path, limit=None):
        if path == _links.D:
            self.graph_calls.append((operation, path, limit))
            self.attempt_count += 1
            raise KadoError("boom")
        return super().graph(operation, path, limit)


_LINK_FIELDS = ("link_members", "link_lookup_status")


def _without_link_fields(cluster: dict) -> dict:
    return {k: v for k, v in cluster.items() if k not in _LINK_FIELDS}


def test_a_failed_lookup_changes_nothing_but_its_link_fields(tmp_path, monkeypatch):
    (tmp_path / "ok").mkdir()
    (tmp_path / "failed").mkdir()
    _, ok = _links._run_tag(tmp_path / "ok", monkeypatch, _links._GraphFake())
    _, failed = _links._run_tag(tmp_path / "failed", monkeypatch, _FailOnDelta())

    ok_by, failed_by = _links._by_topic(ok), _links._by_topic(failed)
    assert ok_by["solar"]["link_lookup_status"] == "done"
    assert failed_by["solar"]["link_lookup_status"] == "failed"
    assert failed_by["solar"]["link_members"] == []
    assert failed_by["energy"] == ok_by["energy"]
    assert [_without_link_fields(c) for c in failed["topic_clusters"]] == [
        _without_link_fields(c) for c in ok["topic_clusters"]
    ]
    rest = [k for k in ok if k not in ("topic_clusters", "link_stats", "run_id")]
    assert {k: failed[k] for k in rest} == {k: ok[k] for k in rest}
