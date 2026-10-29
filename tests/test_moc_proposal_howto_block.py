"""Spec 042 T5.3c: the moc-proposal doc header carries a how-to block that no reader parses."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.link_members import LINK_MEMBER_MARKER  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_reducer = _load("suggestions_reducer_howto", "suggestions-reducer.py")
_parser = _load("suggestion_parser_howto", "suggestion-parser.py")
_moc_parser = _load("moc_proposal_parser_howto", "moc-proposal-parser.py")
_triage = _load("inbox_triage_howto", "inbox-triage.py")

AROUND = TESTS_DIR / "fixtures" / "042-t3-2-around-report" / "report.json"
EXTENSION = TESTS_DIR / "fixtures" / "042-t4-2-extension-report" / "report.json"

# Literal on purpose: pins the owner-approved wording; do not import it from the reducer.
HOWTO = (
    "> **How to use this proposal**\n"
    "> 1. Review each section below. Untick members that do not\n"
    ">    belong; tick link members (`— linked with …`) that do.\n"
    "> 2. Check the parent, and tick the up::-Handling Override if\n"
    ">    existing `up::` links should stay.\n"
    "> 3. Tick **Accept** on every section you want. Sections\n"
    ">    without Accept are ignored.\n"
    "> 4. Run `/inbox`. Tomo turns the accepted sections into an\n"
    ">    instruction set; apply it with Hashi to create or extend\n"
    ">    the MOC, add the `up::` links and list the members.\n"
)
HEADER = "# MOC Proposal\n\n" + HOWTO + "\n"


class _Cfg:
    max_results = 5
    squelch_runs = 3


def _render(path: Path, **override) -> str:
    report = json.loads(path.read_text(encoding="utf-8"))
    report.update(override)
    return _reducer.render_moc_proposal_doc(report, _Cfg())[1]


def _new_moc() -> str:
    return _render(AROUND, mode="tag", trigger_arg="topic/applied/zsh", around=None)


def _docs() -> dict[str, str]:
    return {"new": _new_moc(), "around": _render(AROUND), "extension": _render(EXTENSION)}


def test_howto_block_renders_exactly_before_first_section_in_every_kind() -> None:
    for kind, body in _docs().items():
        assert HEADER in body, kind
        assert body.index(HEADER) < body.index("### "), kind
        assert body.count("How to use this proposal") == 1, kind


def test_uplink_check_doc_has_no_howto_block() -> None:
    body = _render(AROUND, mode="check-moc-uplinks", around=None)
    assert "# MOC Uplink Check" in body
    assert "How to use this proposal" not in body


def test_howto_block_is_not_a_member_link_line_or_accept_hit() -> None:
    # the block contains the link-line marker and the word Accept
    assert LINK_MEMBER_MARKER.strip() in HOWTO
    for body in _docs().values():
        header = body.split("### ", 1)[0]
        assert not _triage._RE_ACCEPT.search(header)
        assert not re.search(r"^\s*-\s+\[", header, re.MULTILINE)
        assert not _parser.RE_CHECKED.match(header.strip())


def test_readers_give_identical_results_with_and_without_the_block() -> None:
    for kind, body in _docs().items():
        bare = body.replace(HOWTO + "\n", "")
        assert bare != body
        assert _parser.enumerate_all_moc_sections(body) == _parser.enumerate_all_moc_sections(bare), kind
        assert _parser.enumerate_moc_sections_split(body) == _parser.enumerate_moc_sections_split(bare), kind
        ticked = body.replace("- [ ] Accept", "- [x] Accept")
        ticked_bare = bare.replace("- [ ] Accept", "- [x] Accept")
        assert _parser.parse_moc_proposal_doc(ticked) == _parser.parse_moc_proposal_doc(ticked_bare), kind
        assert _moc_parser.parse_moc_proposal(ticked) == _moc_parser.parse_moc_proposal(ticked_bare), kind
        assert bool(_triage._RE_ACCEPT.search(body)) == bool(_triage._RE_ACCEPT.search(bare)), kind
        assert _moc_parser.parse_moc_proposal(ticked)["total_sections"] >= 1


def test_untouched_doc_without_the_block_still_parses() -> None:
    body = _new_moc().replace(HOWTO + "\n", "")
    assert "# MOC Proposal\n\n### MOC01" in body
    assert _parser.enumerate_all_moc_sections(body)
