"""Spec 042 owner decision B + 'around: is not squelched' — consumers of a rendered around doc.

The doc is rendered by the real reducer from the captured `--around knowledge`
report, so the parsers see exactly what production writes (no Confidence line,
`**Trigger:** around:knowledge` in the section).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import squelch_persist  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_reducer = _load("suggestions_reducer_b", "suggestions-reducer.py")
_parser = _load("suggestion_parser_b", "suggestion-parser.py")
_moc_parser = _load("moc_proposal_parser_b", "moc-proposal-parser.py")

AROUND_FIXTURE = TESTS_DIR / "fixtures" / "042-t3-2-around-report" / "report.json"


class _Cfg:
    max_results = 5
    squelch_runs = 3


def _around_doc() -> tuple[str, str]:
    report = json.loads(AROUND_FIXTURE.read_text(encoding="utf-8"))
    return _reducer.render_moc_proposal_doc(report, _Cfg())


def _topic_doc() -> tuple[str, str]:
    report = json.loads(AROUND_FIXTURE.read_text(encoding="utf-8"))
    report["mode"] = "tag"
    report["trigger_arg"] = "topic/applied/zsh"
    report.pop("around", None)
    return _reducer.render_moc_proposal_doc(report, _Cfg())


def _untick_accept(body: str) -> str:
    """The reducer renders Accept unticked; rejecting is leaving it so."""
    assert "- [ ] Accept" in body and "- [x] Accept" not in body
    return body


def _tick_accept(body: str) -> str:
    return body.replace("- [ ] Accept", "- [x] Accept", 1)


# ── Confidence is absent: every parser tolerates it ──────────────────────────


def test_around_doc_has_no_confidence_and_parsers_agree_on_the_rest() -> None:
    name, body = _around_doc()
    assert "**Confidence:**" not in body
    ticked = _tick_accept(body)

    proposals = _parser.parse_moc_proposal_doc(ticked, filename=name)
    assert [(p["moc_id"], p["title"]) for p in proposals] == [("MOC01", "knowledge (MOC)")]
    assert proposals[0]["children"] == ["knowledge"]

    sections = _parser.enumerate_all_moc_sections(body)
    # around sections are not squelch input (see the squelch tests below)
    assert sections == []

    ticked_c, unticked_c = _parser.enumerate_moc_sections_split(ticked)
    assert [c["moc_id"] for c in ticked_c] == ["MOC01"]
    assert ticked_c[0]["topic_keywords"] == ["habits", "goals"]
    assert unticked_c == []

    parsed = _moc_parser.parse_moc_proposal(ticked)
    assert parsed["total_sections"] == 1
    assert parsed["total_approved"] == 1
    item = parsed["confirmed_items"][0]
    assert (item["id"], item["title"], item["supporting_items"]) == (
        "MOC01", "knowledge (MOC)", ["knowledge"],
    )


# ── Rejection does not squelch an around doc, still squelches a topic doc ────


def test_rejecting_an_around_doc_writes_no_registry_entry(tmp_path: Path) -> None:
    name, body = _around_doc()
    reg = tmp_path / "moc-squelch.json"

    n = squelch_persist.persist_rejected_clusters(
        _untick_accept(body), filename=name, registry_path=reg, config={"squelch_runs": 3}
    )

    assert n == 0
    assert not reg.exists()


def test_rejecting_a_topic_doc_still_writes_a_registry_entry(tmp_path: Path) -> None:
    name, body = _topic_doc()
    reg = tmp_path / "moc-squelch.json"

    n = squelch_persist.persist_rejected_clusters(
        _untick_accept(body), filename=name, registry_path=reg, config={"squelch_runs": 3}
    )

    assert n == 1
    assert reg.exists()


def test_unticked_around_section_is_not_handed_to_squelch_unticked() -> None:
    _, body = _around_doc()

    ticked, unticked = _parser.enumerate_moc_sections_split(_untick_accept(body))

    assert ticked == []
    assert unticked == []


def test_unticked_topic_section_is_still_handed_to_squelch_unticked() -> None:
    _, body = _topic_doc()

    _, unticked = _parser.enumerate_moc_sections_split(_untick_accept(body))

    assert [c["moc_id"] for c in unticked] == ["MOC01"]
