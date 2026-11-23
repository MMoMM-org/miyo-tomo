#!/usr/bin/env python3
# version: 0.1.0
"""test_047_baseline_e2e.py — the before-state of the /review document and of Pass 2 (spec 047 T1.3, ADR-11).

Spec 047 rebuilds how /review reads a period; PRD F2-AC1 asks that the document keeps its shape and F2-AC2
that Pass 2 writes the same instruction set. This module pins both on the old flow, for week 2026-W13,
month 2026-03 and quarter 2026-Q1 on the fake vault: Pass 1 → document → approve → preview → Pass 2
`deliver`, through tests/review_e2e_walk.py exactly as the skill calls the scripts.

The constructions (`CASES`): the week and the month on the fixture `CONFIG` with `proposals(kind)`; the
quarter on `Walk(..., quarter=True)` with `QUARTER_CONFIG` plus one mapped section of the quarterly
template (`QUARTER_SECTION_ROW`, the template's "Theme") and `proposals("quarter")` plus one section item
carrying the `monthly_only` mark and one without a mark. A mark suffix is rendered only on a section item,
so without the mapped section no document of the three would carry one and the fingerprint's `marks`
key could never fail. Week and month stay unmapped (every group, empty ones as "nothing found"); the
quarter is the mapped layout (empty groups omitted, the `%%review%%` divider).

Golden files, under tests/fixtures/047-baseline/, sorted-key JSON:
- `<kind>-fingerprint.json`: `review_doc_fingerprint.fingerprint()` of the Pass 1 document as written
  (before the user ticks Approved);
- `<kind>-instructions.json`: every file `deliver` wrote except the review document itself (the set JSON,
  its readable MD peer and, for a new note, the rendered note), by vault path, as a list of lines with the
  masked values replaced.

Masked, and nothing else: the value of `generated` (the set JSON's top-level key and the MD peer's
frontmatter key), and of `run_id` and `updated_at` in a `tomo:` frontmatter block — each only when the value
has the timestamp / run-id shape (`2026-11-23T07:12:27Z`, `2026-11-23T07-12-27Z-bb64ac`); any other value
stays and is compared. Action ids (`I01`) are deterministic and compared.

A normal run never writes a golden: a missing golden fails and names the command that writes it,
`TOMO_047_WRITE_BASELINE=1 ./venv/bin/python -m pytest tests/test_047_baseline_e2e.py::test_baseline`. With
`TOMO_047_WRITE_BASELINE=1` `test_baseline` (re)writes the goldens from this run, then compares; the helper
tests clear the variable, so a changed document never becomes a golden.

`assert_baseline(kind, document, pass2_files, allowed=frozenset())` is the comparison; `allowed` names the
fingerprint keys (as `review_doc_fingerprint.diff` names them: `top_lines`, `marks.s1` …) that may differ —
the named differences Phase 8 (T8.1) passes for the new flow. Empty, it is strict. The instruction set is
always compared strictly (F2-AC2). Every write a walk attempts is recorded per test and must lie under
the inbox. All data is synthetic.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, Tuple

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    INBOX, MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, QUARTER, QUARTER_DOC, QUARTER_PERIOD, QUARTER_STEM, WEEK,
    WEEK_DOC, WEEK_PERIOD, WEEK_STEM, Walk,
)
from review_privacy_fixture import CONFIG, QUARTER_CONFIG, proposals  # noqa: E402
from review_doc_fingerprint import diff, fingerprint  # noqa: E402  (after the walk: it puts tomo/scripts on the path)

GOLDEN_DIR = TESTS_DIR / "fixtures" / "047-baseline"
WRITE_ENV = "TOMO_047_WRITE_BASELINE"
REGEN = f"{WRITE_ENV}=1 ./venv/bin/python -m pytest tests/test_047_baseline_e2e.py::test_baseline"

QUARTER_TEMPLATE = "t_quarter.md"
QUARTER_SECTION_ROW = {"id": "s1", "heading": "Theme", "level": 2, "parent": None, "occurrence": 1,
                       "description": "what the quarter's theme was", "placement": "under"}
QUARTER_SECTION_ITEMS = [{"text": "theme only monthly", "sources": ["2026-02"], "mark": "monthly_only"},
                         {"text": "theme day", "sources": ["2026-01-12"]}]

_TIMESTAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
_RUN_ID = r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-[0-9a-f]{6}"
# (pattern over one line, the placeholder for its value group); anchored on the key, the value by its shape
_MASKS = (
    (re.compile(rf'^(  "generated": ")({_TIMESTAMP})(",?)$'), "<timestamp>"),     # the set JSON
    (re.compile(rf"^(generated: )({_TIMESTAMP})()$"), "<timestamp>"),             # the MD peer's frontmatter
    (re.compile(rf"^(  run_id: )({_RUN_ID})()$"), "<run_id>"),                    # a tomo: block
    (re.compile(rf"^(  updated_at: ')({_TIMESTAMP})(')$"), "<timestamp>"),        # a tomo: block
)


def _quarter_config() -> dict:
    config = copy.deepcopy(QUARTER_CONFIG)
    config["review"]["quarterly"]["sections"] = {QUARTER_TEMPLATE: [dict(QUARTER_SECTION_ROW)]}
    return config


def _quarter_proposals() -> dict:
    props = proposals(QUARTER)
    props["sections"] = [{"key": "s1", "items": copy.deepcopy(QUARTER_SECTION_ITEMS)}]
    return props


@dataclass(frozen=True)
class Case:
    kind: str
    period: str
    stem: str
    doc: str
    quarter: bool
    config: Callable[[], dict]
    proposals: Callable[[], dict]


CASES: Dict[str, Case] = {
    WEEK: Case(WEEK, WEEK_PERIOD, WEEK_STEM, WEEK_DOC, False, lambda: copy.deepcopy(CONFIG), lambda: proposals(WEEK)),
    MONTH: Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, False, lambda: copy.deepcopy(CONFIG),
                lambda: proposals(MONTH)),
    QUARTER: Case(QUARTER, QUARTER_PERIOD, QUARTER_STEM, QUARTER_DOC, True, _quarter_config, _quarter_proposals),
}


def mask(text: str) -> List[str]:
    """``text`` as lines, the masked values (module docstring) replaced by their placeholder."""
    out = []
    for line in text.split("\n"):
        for pattern, placeholder in _MASKS:
            line = pattern.sub(lambda m, p=placeholder: f"{m.group(1)}{p}{m.group(3)}", line)
        out.append(line)
    return out


def golden_paths(kind: str) -> Tuple[Path, Path]:
    return GOLDEN_DIR / f"{kind}-fingerprint.json", GOLDEN_DIR / f"{kind}-instructions.json"


def _dump(data) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _load(path: Path):
    if not path.exists():
        pytest.fail(f"golden file {path} is missing; write it with: {REGEN}")
    return json.loads(path.read_text(encoding="utf-8"))


def _instruction_diff(golden: dict, actual: dict) -> List[str]:
    """Per differing vault path: the path and its first differing line (index, golden, actual)."""
    out = []
    for path in sorted(set(golden) | set(actual)):
        a, b = golden.get(path), actual.get(path)
        if a == b:
            continue
        if a is None or b is None:
            out.append(f"{path}: {'missing' if b is None else 'not in the golden'}")
            continue
        index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        out.append(f"{path}: line {index}: golden {a[index] if index < len(a) else '<end>'!r} "
                   f"!= actual {b[index] if index < len(b) else '<end>'!r}")
    return out


def assert_baseline(kind: str, document: str, pass2_files: Dict[str, str],
                    allowed: FrozenSet[str] = frozenset()) -> None:
    """The document's fingerprint equals the golden except the ``allowed`` keys; the Pass 2 files equal theirs."""
    fp_path, set_path = golden_paths(kind)
    actual_fp = fingerprint(document)
    actual_set = {path: mask(text) for path, text in pass2_files.items()}
    if os.environ.get(WRITE_ENV) == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        fp_path.write_text(_dump(actual_fp), encoding="utf-8")
        set_path.write_text(_dump(actual_set), encoding="utf-8")
    golden_fp = _load(fp_path)
    golden_set = _load(set_path)
    actual_fp = json.loads(_dump(actual_fp))           # the golden's JSON types (tuples become lists)
    differing = [key for key in diff(golden_fp, actual_fp) if key not in allowed]
    assert differing == [], f"{fp_path.name}: fingerprint keys differ: {differing}"
    changed = _instruction_diff(golden_set, actual_set)
    assert changed == [], f"{set_path.name}: instruction files differ: {changed}"


# ── the walk ──


@pytest.fixture
def make_walk(tmp_path, monkeypatch, capsys, request):
    walks: List[Walk] = []

    def make(case: Case, root: Path | None = None) -> Walk:
        root = root or tmp_path / f"walk{len(walks)}"
        root.mkdir()
        w = Walk(root, monkeypatch, capsys, request.node.nodeid, config=case.config(), quarter=case.quarter)
        w.vault._record = w.vault.recorded.append     # per test only: the e2e sweeps own review_e2e_walk.WRITES
        walks.append(w)
        return w

    yield make
    outside = [p for w in walks for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def run_old_flow(w: Walk, case: Case) -> Tuple[str, Dict[str, str]]:
    """Pass 1 → the document → approve → preview → deliver; ``(document as written, files deliver wrote)``."""
    out = w.pass1(case.period, case.kind, case.proposals())
    assert out["status"] == "written" and out["doc_path"] == case.doc and out["rejected"] == [], out
    document = w.doc(case.doc)
    w.approve(case.doc)
    assert w.parse(case.stem)["approved"] is True
    assert w.preview(case.stem)["problems"] == []
    before = len(w.vault.recorded)
    out = w.deliver(case.stem)
    assert out["status"] == "delivered", out
    written = [p for p in w.vault.recorded[before:] if p != case.doc]
    assert written and all(p.startswith(INBOX) for p in written), written
    return document, {path: w.vault.text(path) for path in written}


@pytest.mark.parametrize("kind", list(CASES))
def test_baseline(kind, make_walk):
    document, files = run_old_flow(make_walk(CASES[kind]), CASES[kind])
    assert_baseline(kind, document, files)


def test_the_quarter_baseline_carries_a_mark_suffix_and_every_kind_its_set():
    """Without a mark in a golden the `marks` key could never fail; without a set the F2-AC2 half is empty."""
    marks = _load(golden_paths(QUARTER)[0])["marks"]
    assert [m for items in marks.values() for item in items for m in item] == ["monthly_only"], marks
    for kind in CASES:
        files = _load(golden_paths(kind)[1])
        assert f"{INBOX}{CASES[kind].stem}_instructions.json" in files, (kind, sorted(files))
        assert f"{INBOX}{CASES[kind].stem}_instructions.md" in files, (kind, sorted(files))


def test_mask_replaces_only_the_shaped_values():
    text = ('{\n  "generated": "2026-11-23T07:12:27Z",\n  "profile": "miyo"\n}\n---\ntomo:\n'
            "  run_id: 2026-11-23T07-12-27Z-bb64ac\n  updated_at: '2026-11-23T07:12:27Z'\n"
            "generated: 2026-11-23T07:12:27Z\n  run_id: r-test\n- 2026-11-23T07:12:27Z stays\n")
    assert mask(text) == ['{', '  "generated": "<timestamp>",', '  "profile": "miyo"', '}', '---', 'tomo:',
                          '  run_id: <run_id>', "  updated_at: '<timestamp>'", 'generated: <timestamp>',
                          '  run_id: r-test', '- 2026-11-23T07:12:27Z stays', '']


# ── the helper T8.1 passes the named differences to ──


def _with_top_line(document: str) -> str:
    """One extra line above the first part, like a previous-note line: only `top_lines` changes."""
    return document.replace("- [ ] Approved\n", "- [ ] Approved\nPrevious: [[2026-W12]]\n", 1)


def test_an_allowed_key_passes_and_a_strict_run_names_it(make_walk, monkeypatch):
    monkeypatch.delenv(WRITE_ENV, raising=False)      # a changed document must never become the golden
    document, files = run_old_flow(make_walk(CASES[WEEK]), CASES[WEEK])
    changed = _with_top_line(document)
    assert diff(fingerprint(document), fingerprint(changed)) == ["top_lines"]
    assert_baseline(WEEK, changed, files, allowed=frozenset({"top_lines"}))
    with pytest.raises(AssertionError, match=r"week-fingerprint\.json: fingerprint keys differ: \['top_lines'\]"):
        assert_baseline(WEEK, changed, files)


def test_a_key_outside_allowed_fails_and_the_set_is_never_allowed(make_walk, monkeypatch):
    monkeypatch.delenv(WRITE_ENV, raising=False)
    document, files = run_old_flow(make_walk(CASES[MONTH]), CASES[MONTH])
    dropped = re.sub(r"\n## Vault growth\n- nothing found\n", "\n", document, count=1)
    assert dropped != document
    with pytest.raises(AssertionError, match=r"month-fingerprint\.json: fingerprint keys differ: .*'parts'"):
        assert_baseline(MONTH, _with_top_line(dropped), files, allowed=frozenset({"top_lines"}))
    set_json = f"{INBOX}{MONTH_STEM}_instructions.json"
    tampered = {**files, set_json: files[set_json].replace('"I01"', '"I02"', 1)}
    with pytest.raises(AssertionError, match=r"month-instructions\.json: instruction files differ: .*_instructions"
                                             r"\.json: line \d+"):
        assert_baseline(MONTH, document, tampered, allowed=frozenset({"top_lines", "parts", "groups"}))


def test_a_missing_golden_fails_and_names_the_command(monkeypatch, tmp_path):
    monkeypatch.setattr(sys.modules[__name__], "GOLDEN_DIR", tmp_path)
    monkeypatch.delenv(WRITE_ENV, raising=False)
    with pytest.raises(pytest.fail.Exception, match=re.escape(REGEN)):
        _load(golden_paths(WEEK)[0])
    assert list(tmp_path.iterdir()) == [], "a normal run writes no golden"
