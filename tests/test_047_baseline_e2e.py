#!/usr/bin/env python3
# version: 0.3.1
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
the named differences Phase 8 (T8.1) passes for the new flow. Empty, it is strict. `test_baseline` passes
`ALLOWED` (`top_lines`) since spec 047 T5.4: the fixture walk reads previous notes, which the document now
names at the top. The instruction set is
always compared strictly (F2-AC2). Every write a walk attempts is recorded per test and must lie under
the inbox. All data is synthetic.

The new flow with carried items (spec 047 T8.1, ADR-11): `test_the_new_flow_adds_only_what_spec_047_adds` runs
each kind through read → plan → the fixture digests and carryover (W13 and 2026-03 with `CARRY` items) → check →
the fixture proposer (`propose_from_inputs`) → write → approve → deliver, never writing a golden. The fingerprint
differs from the golden in exactly `top_lines` and, per part a carried item lands in, `counts.<part>`,
`marks.<part>` and `links.<part>` — always the dotted form, since `marks`, `counts` and `links` are dicts on both
sides — and those values are the golden's plus one empty entry per carried item: the fingerprint reads no
`carried_*` label as a mark and no link kind on a carried line (its label follows the link list), so the
carried lines themselves are asserted from the document's text. The user leaves `c3` (done) ticked, edits `c2`
(still open: its text and its mark) and unticks `c1` (not mentioned); every instruction file equals its golden
byte for byte once the delivered carried lines (`c3` as written, `c2` as edited) and, where a group had no item
before, that group's heading are inserted (`_expected_set`), timestamps and run ids masked as above.
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
from review_privacy_fixture import (  # noqa: E402
    CONFIG, PRP, QUARTER_CONFIG, condense_files, propose_from_inputs, proposals,
)
from review_doc_fingerprint import diff, fingerprint  # noqa: E402  (after the walk: it puts tomo/scripts on the path)

GOLDEN_DIR = TESTS_DIR / "fixtures" / "047-baseline"
WRITE_ENV = "TOMO_047_WRITE_BASELINE"
REGEN = f"{WRITE_ENV}=1 ./venv/bin/python -m pytest tests/test_047_baseline_e2e.py::test_baseline"
# Spec 047 T5.4 (owner 2026-11-24, the T8.1 mechanism brought forward): the previous-note lines are
# the one named difference; every other key and the instruction set stay strict.
ALLOWED: FrozenSet[str] = frozenset({"top_lines"})

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
    assert_baseline(kind, document, files, allowed=ALLOWED)


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



# ── the new flow with carried items (spec 047 T8.1) ──

CARRY = 3                        # carryover items in W13 and 2026-03: c1 not_mentioned, c2 still_open, c3 done
CARRIED_PARTS = ("done", "open")
TOP_LINES = {
    WEEK: ["> Previous review · week 2026-W12: found, 2 carried", "> Previous review · month 2026-02: found, 1 carried"],
    MONTH: ["> Previous review · month 2026-02: found, 3 carried",
            "> Previous review · quarter 2025-Q4: no note found for 2025-Q4"],
    QUARTER: ["> Previous review · quarter 2025-Q4: no note found for 2025-Q4"],
}
FIRST_DAY = {WEEK: "2026-03-23", MONTH: "2026-03-01"}
C2_NOTE = {WEEK: "2026-02", MONTH: "2026-02"}
C3_NOTE = {WEEK: "2026-W12", MONTH: "2026-02"}
C2_EDIT = ("still open (previous review)", "still open, ask again")
_CARRIED_LINE = re.compile(r"^- \[([ x])\] (carried c\d+ .*?)\s*%%t\d+%%$")


def _carried_lines(document: str) -> Dict[str, List[str]]:
    """``{part heading: [carried item line without its id]}`` of the document."""
    out: Dict[str, List[str]] = {}
    heading = None
    for line in document.split("\n"):
        if line.startswith("## "):
            heading = line[3:]
        elif (m := _CARRIED_LINE.match(line)):
            out.setdefault(heading, []).append(f"- [{m.group(1)}] {m.group(2)}")
    return out


def _expected_carried(kind: str) -> Dict[str, List[str]]:
    day, c1_note = FIRST_DAY[kind], ("2026-W12" if kind == WEEK else "2026-02")
    return {"Done": [f"- [x] carried c3 {PRP} ([[{C3_NOTE[kind]}]], [[{day}]]) · done (previous review)"],
            "Open": [f"- [x] carried c1 {PRP} ([[{c1_note}]]) · not mentioned again (previous review)",
                     f"- [x] carried c2 {PRP} ([[{C2_NOTE[kind]}]], [[{day}]]) · still open (previous review)"]}


def _delivered(kind: str) -> Tuple[str, str]:
    """The two carried lines Pass 2 delivers: ``c3`` as written, ``c2`` as the user edited it."""
    day = FIRST_DAY[kind]
    return (f"- carried c3 {PRP} ([[{C3_NOTE[kind]}]], [[{day}]]) · done (previous review)",
            f"- carried c2 {PRP} rewritten ([[{C2_NOTE[kind]}]], [[{day}]]) · {C2_EDIT[1]}")


def _user_edits(document: str) -> str:
    """Untick ``c1``; edit ``c2``'s text and its mark; leave ``c3`` ticked."""
    out = []
    for line in document.split("\n"):
        if line.startswith("- [x] carried c1 "):
            line = line.replace("- [x]", "- [ ]", 1)
        elif line.startswith("- [x] carried c2 "):
            line = line.replace(f"c2 {PRP} ", f"c2 {PRP} rewritten ", 1).replace(*C2_EDIT)
        out.append(line)
    return "\n".join(out)


def _item_ids(document: str) -> Dict[str, str]:
    """``{carried id: document item id}``."""
    return {m.group(1): m.group(2) for m in re.finditer(r"^- \[[ x]\] carried (c\d+) .*%%(t\d+)%%$", document, re.M)}


def run_new_flow(w: Walk, case: Case, carry: int) -> Tuple[str, Dict[str, str], dict]:
    """read → condense → fixture proposer → write → (user edits) → approve → deliver; ``(document as written,
    files deliver wrote, parse answer)``."""
    read = w.read(case.period, case.kind)
    assert read["status"] == "ok" and read["nothing_to_review"] is False, read
    out = w.write(case.stem, case.kind, case.proposals(), carry=carry, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["doc_path"] == case.doc and out["rejected"] == [], out
    document = w.doc(case.doc)
    if carry:
        w.edit_document(case.doc, _user_edits(document))
    w.approve(case.doc)
    parsed = w.parse(case.stem)
    assert parsed["approved"] is True and parsed["warnings"] == [], parsed
    assert w.preview(case.stem)["problems"] == []
    before = len(w.vault.recorded)
    delivered = w.deliver(case.stem)
    assert delivered["status"] == "delivered", delivered
    written = [p for p in w.vault.recorded[before:] if p != case.doc]
    assert written and all(p.startswith(INBOX) for p in written), written
    return document, {path: w.vault.text(path) for path in written}, parsed


def _escaped(line: str) -> str:
    return json.dumps(line, ensure_ascii=False)[1:-1]


def _expected_set(golden_set: dict, inserts: List[Tuple[str, List[str]]]) -> dict:
    """The golden files with ``lines`` inserted after each ``anchor`` line — as a line of a Markdown file and,
    escaped, inside the set JSON's ``content`` string; once per file, in at least one file."""
    out = copy.deepcopy(golden_set)
    for anchor, lines in inserts:
        hits = 0
        for path, file_lines in out.items():
            for index, line in enumerate(file_lines):
                if line == anchor:
                    file_lines[index + 1:index + 1] = lines
                    hits += 1
                    break
                needle = _escaped(anchor) + "\\n"
                if path.endswith(".json") and needle in line:
                    file_lines[index] = line.replace(needle, needle + "".join(_escaped(x) + "\\n" for x in lines), 1)
                    hits += 1
                    break
        assert hits >= 1, f"anchor {anchor!r} is in no golden file"
    return out


def _inserts(kind: str) -> List[Tuple[str, List[str]]]:
    c3, c2 = _delivered(kind)
    if kind == WEEK:
        return [(f"- Cleaned up {PRP} ([[2026-03-23]], [[2026-03-24]])", [c3]),
                (f"- Taxes {PRP} ([[2026-03-26]])", [c2])]
    return [(f"- March done {PRP} ([[2026-03-01]], [[2026-03-23]])", [c3, "### Open", c2])]   # Open had no item


@pytest.mark.parametrize("kind", list(CASES))
def test_the_new_flow_adds_only_what_spec_047_adds(kind, make_walk, monkeypatch):
    monkeypatch.delenv(WRITE_ENV, raising=False)          # a carried run never becomes the golden
    case = CASES[kind]
    carry = 0 if kind == QUARTER else CARRY
    document, files, parsed = run_new_flow(make_walk(case), case, carry)
    fp_path, set_path = golden_paths(kind)
    golden_fp, golden_set = _load(fp_path), _load(set_path)
    actual_fp = json.loads(_dump(fingerprint(document)))

    # the previous-note lines at the top, and the carried items with their marks (F2-AC1, F3-AC6, F5-AC2)
    top = document.split("- [ ] Approved")[0].split("\n")
    assert [line for line in top if line.startswith("> Previous review")] == TOP_LINES[kind]
    parts = list(CARRIED_PARTS) if carry else []
    expected_keys = sorted({"top_lines", *(f"{key}.{p}" for key in ("counts", "links", "marks") for p in parts)})
    # every other key equal — habits, callout (reading report), parts, groups, sections, the growth group and the
    # child marks (F2-AC1); the carried parts in the dotted form only, never the bare `marks`
    assert diff(golden_fp, actual_fp) == expected_keys
    assert actual_fp["top_lines"] == golden_fp["top_lines"] + len(TOP_LINES[kind])
    added = {"done": 1, "open": 2} if carry else {}
    for part, n in added.items():
        assert actual_fp["counts"][part] == golden_fp["counts"][part] + n
        assert actual_fp["marks"][part] == golden_fp["marks"][part] + [[]] * n
        assert actual_fp["links"][part] == golden_fp["links"][part] + [[]] * n
    assert _carried_lines(document) == (_expected_carried(kind) if carry else {})
    if not carry:
        assert "(previous review)" not in document

    # Pass 2: c3 kept, c2 kept, c1 absent (F5-AC4, F5-AC5, F2-AC2). `edited` is False for c2: parse sets it
    # only when an item's link stems change, so c2's text edit is checked through its delivered line
    # (`_delivered`, compared in the instruction files below), never through the `edited` flag
    if carry:
        ids = _item_ids(document)
        rows = {r["id"]: r for group in parsed["items"].values() for r in group}
        assert [(rows[ids[c]]["kept"], rows[ids[c]]["edited"]) for c in ("c1", "c2", "c3")] == \
            [(False, False), (True, False), (True, False)]
    expected = _expected_set(golden_set, _inserts(kind) if carry else [])
    actual = {path: mask(text) for path, text in files.items()}
    changed = _instruction_diff(expected, actual)
    assert changed == [], f"{set_path.name}: instruction files differ beyond the carried lines: {changed}"
    if carry:
        delivered = "\n".join(line for lines in actual.values() for line in lines)
        assert "carried c1" not in delivered


def test_a_quarter_day_reaches_the_proposer_with_the_material_of_a_week_read(make_walk):
    """F1-AC2: 2026-03-23 read in the quarter and in its week: the same day file, the same digester job
    material and that unit's digest among the proposer's inputs in both."""
    seen = {}
    for kind in (QUARTER, WEEK):
        case = CASES[kind]
        w = make_walk(case)
        assert w.read(case.period, kind)["status"] == "ok"
        plan = w.run("review-digest", "plan", "--stem", case.stem)
        job = next(j for r in plan["rounds"] for j in r if "2026-03-23" in j.get("days", []))
        files = condense_files(plan, w.stage(case.stem))
        check = w.condense(case.stem)
        stage = w.stage(case.stem)
        day = json.loads((stage / "days" / "2026-03-23.json").read_text(encoding="utf-8"))
        growth = [json.loads((stage / g).read_text(encoding="utf-8")) for g in job["growth_files"]]
        for doc in (day, *growth):
            doc.pop("read_id")
        digest = {k: v for k, v in files[job["out"]].items() if k != "read_id"}
        seen[kind] = (job["unit"], job["days"], job["day_files"], job["growth_files"], day, growth, digest)
        assert job["out"] in check["proposer"]["inputs"], check["proposer"]
    assert seen[QUARTER] == seen[WEEK]
    assert seen[WEEK][0] == "2026-W13" and "monday" in json.dumps(seen[WEEK][4])


MONTH_SECTION_ROW = {"id": "s1", "heading": "Theme", "level": 2, "parent": None, "occurrence": 1,
                     "description": "what the month's theme was", "placement": "under"}


def test_a_carried_section_item_shows_the_carried_mark_before_the_child_mark(make_walk):
    """F5-AC2: on a section item the carried label comes first, then the child mark — in the document and as
    delivered. Week and month are unmapped, so only a mapped month shows the two together."""
    def config() -> dict:
        out = copy.deepcopy(CONFIG)
        out["review"]["monthly"]["sections"] = {"t_month.md": [dict(MONTH_SECTION_ROW)]}
        return out

    case = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, False, config, lambda: proposals(MONTH))
    w = make_walk(case)
    assert w.read(case.period, MONTH)["status"] == "ok"
    w.condense(case.stem, carry=1)
    props = proposals(MONTH)
    props["sections"] = [{"key": "s1", "items": [
        {"text": f"theme carried {PRP}", "sources": ["2026-02", "2026-03-01"], "mark": "not_in_weekly",
         "carried": "still_open", "carried_ids": ["c1"]}]}]
    out = w.write(case.stem, MONTH, props, condense=False, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["rejected"] == [], out
    line = f"theme carried {PRP} ([[2026-02]], [[2026-03-01]]) · still open (previous review) · in no weekly review"
    assert re.search(rf"^- \[x\] {re.escape(line)} %%t\d+%%$", w.doc(case.doc), re.M), w.doc(case.doc)
    w.approve(case.doc)
    assert w.deliver(case.stem)["status"] == "delivered"
    assert f"- {line}" in w.vault.text(f"{INBOX}{MONTH_PERIOD}.md").split("\n")
