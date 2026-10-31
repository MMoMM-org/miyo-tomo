"""test_043_grader_patterns.py — offline validation of the eval gate's regex graders (spec 043, T2.1).

Every regex pattern on `target: trace` is checked here before any paid run, against
the recorded spike traces and hand-edited variants of them (SDD ADR-5, Quality
Requirements/Reliability). This module reproduces the SDD's offline validation table
with one pytest command and checks that every grader regex in `evals/` parses, compiles
in Python and stays inside the Python/JS common subset.

How later tasks (T2.2-T2.4) extend it:
- add a grader to GRADERS: `inline(...)` while its file does not exist yet, then switch
  the entry to `from_file("evals/<case>/graders/<file>.md")` once it does;
- add an EXPECTATIONS row per (fixture, grader id) with the expected verdict;
- add a fixture to FIXTURES (file under the spec's fixtures/ directory) with its derivation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from grader_patterns import (
    FIXTURES_DIR,
    REPO,
    SPEC_DIR,
    Expect,
    _apply_match,
    evaluate,
    from_file,
    grader_files,
    grader_regexes,
    inline,
    js_subset_violations,
    last_message,
    load_fixture,
    load_grader,
    tool_uses,
)

SPIKE_REPORT_ONLY = SPEC_DIR / "spike" / "report-only-probe" / "graders"

# Fixture file → how it was derived. Every variant is the trimmed spike trace with ONE edit.
FIXTURES = {
    "pass1-spike.jsonl": "spike trace e-t7N3jn (Pass 1), trimmed, paths neutralised",
    "pass1-warn-before-dispatch.jsonl": "pass1-spike + an assistant text event relaying the WARN, "
    "inserted after the WARN tool_result and before the first Agent tool_use",
    "pass1-warn-after-dispatch.jsonl": "pass1-spike + the same assistant text event, "
    "inserted directly after the first Agent tool_use",
    "pass1-reducer-before-dispatch.jsonl": "pass1-spike with the reducer tool_use and its "
    "tool_result moved before the first Agent tool_use",
    "pass1-two-writes-same-stem.jsonl": "pass1-spike + a second kado-write-file call that "
    "publishes the .json under the same stem as the .md",
    "pass1-two-writes-different-stem.jsonl": "pass1-spike + a second kado-write-file call that "
    "publishes the .json under a different stem",
    "pass1-reducer-between-dispatches.jsonl": "pass1-spike with the reducer tool_use and its "
    "tool_result moved between the second and the third Agent tool_use",
    "pass1-dresden-key-flattened.jsonl": "pass1-spike with the Dresden dispatch's item_key "
    "flattened to 100 Inbox/Dresden.md (path unchanged)",
    "pass1-dresden-path-flattened.jsonl": "pass1-spike with the Dresden dispatch's path "
    "flattened to 100 Inbox/Dresden.md (item_key unchanged)",
    "pass2-spike.jsonl": "spike trace e-O6bppm (Pass 2, report-only probe), trimmed, paths neutralised",
    "pass2-status-sentence.jsonl": "pass2-spike with a status sentence before the first report line "
    "of the conductor's return",
    "pass2-duplicate-handback.jsonl": "pass2-spike with the hand-back tool_result event duplicated",
}

# Grader id → grader. `inline` rows carry the SDD-validated patterns until T2.2-T2.4 write
# the grader files; `from_file` rows load the real frontmatter.
GRADERS = {
    # SDD Complex Logic — relay grader 02.
    "warn-before-first-dispatch": inline(
        type="regex",
        target="trace",
        match="contains",
        pattern=r'^(?:(?![^\n]*"name":"Agent")[^\n]*\n)*?[^\n]*"type":"assistant"[^\n]*"type":"text","text":"[^\n]*active tracker field\(s\) have no keywords',
    ),
    # SDD Complex Logic — pipeline grader 09 (the violation shape; green when absent).
    "reduce-after-last-dispatch": inline(
        type="regex",
        target="trace",
        match="not_contains",
        pattern=r'"name":"Bash","input":\{"command":"python3? scripts/suggestions-reducer\.py[\s\S]*"name":"Agent","input":\{[^\n]*?"subagent_type":"tomo:inbox-analyst"',
    ),
    # SDD pipeline grader 04.
    "subfolder-path-and-key": inline(
        type="tool_used",
        tool="Agent",
        min=1,
        input_match=r'path\s*=\s*\\"100 Inbox/Places/Dresden\.md\\"[\s\S]*item_key\s*=\s*\\"100 Inbox/Places/Dresden\.md\\"',
    ),
    # SDD pipeline grader 10.
    "two-script-writes-same-stem": inline(
        type="regex",
        target="trace",
        match="contains",
        pattern=r'--vault \\"100 Inbox/(\d{4}-\d{2}-\d{2}_\d{4})_suggestions\.md\\"[\s\S]*--vault \\"100 Inbox/\1_suggestions\.json\\"',
    ),
    # SDD Report-only: the canary counts the frame the report-only grader reads.
    "handback-canary": inline(
        type="regex",
        target="trace",
        match="count:1",
        pattern=r"\[Subagent hand-back\][^\n]*The report follows:",
    ),
    # Spike grader files (report-only probe): pattern B is the SDD's report-only pattern.
    "spike-a-tool-use-result": from_file(
        SPIKE_REPORT_ONLY / "a-only-report-tool-use-result.md"
    ),
    "spike-b-handback-frame": from_file(
        SPIKE_REPORT_ONLY / "b-only-report-handback-frame.md"
    ),
    "spike-c-canary": from_file(SPIKE_REPORT_ONLY / "c-canary-return-visible.md"),
    # Controls: the UNANCHORED forms. They must misfire on the spike trace, which is what
    # proves the fixtures keep the prose lines (Skill expansion, WARN tool_result) that make
    # the anchoring necessary (SDD Implementation Gotchas).
    "control-unanchored-warn": inline(
        type="regex",
        target="trace",
        match="contains",
        pattern=r"active tracker field\(s\) have no keywords[\s\S]*\"name\":\"Agent\"",
    ),
    "control-unanchored-reducer": inline(
        type="regex",
        target="trace",
        match="not_contains",
        pattern=r'scripts/suggestions-reducer\.py[\s\S]*"subagent_type":"tomo:inbox-analyst"',
    ),
}

# (fixture, grader id) → expected verdict. `passed` is the grader's verdict (match AND
# match-mode applied); `count` is the number of regex matches / matching tool calls.
EXPECTATIONS = {
    # WARN before dispatch (SDD table rows 1-3).
    ("pass1-spike.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "spike: no relay before dispatch — red"
    ),
    ("pass1-warn-before-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        True, 1, "relay before the first Agent line"
    ),
    ("pass1-warn-after-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "relay after the first Agent line"
    ),
    # Reduce-after-dispatch violation (SDD table rows 4-5).
    ("pass1-spike.jsonl", "reduce-after-last-dispatch"): Expect(
        True, 0, "spike: violation absent — green"
    ),
    ("pass1-reducer-before-dispatch.jsonl", "reduce-after-last-dispatch"): Expect(
        False, 1, "violation present — red"
    ),
    ("pass1-reducer-between-dispatches.jsonl", "reduce-after-last-dispatch"): Expect(
        False, 1, "reducer before the LAST dispatch — red"
    ),
    # Subfolder path and key (SDD table row 6).
    ("pass1-spike.jsonl", "subfolder-path-and-key"): Expect(
        True, 1, "spike Agent inputs: 1 match"
    ),
    ("pass1-dresden-key-flattened.jsonl", "subfolder-path-and-key"): Expect(
        False, 0, "path right, item_key flattened — red"
    ),
    ("pass1-dresden-path-flattened.jsonl", "subfolder-path-and-key"): Expect(
        False, 0, "item_key right, path flattened — red"
    ),
    # Same-stem writes (SDD table row 7, plus the two edited variants).
    ("pass1-spike.jsonl", "two-script-writes-same-stem"): Expect(
        False, 0, "spike: 1 write only — no match"
    ),
    ("pass1-two-writes-same-stem.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, ".md and .json share the stem"
    ),
    ("pass1-two-writes-different-stem.jsonl", "two-script-writes-same-stem"): Expect(
        False, 0, "the backreference rejects a different stem"
    ),
    # Report-only (spike pattern B) and canaries.
    ("pass2-spike.jsonl", "spike-b-handback-frame"): Expect(
        True, 1, "spike pattern B green on e-O6bppm"
    ),
    ("pass2-status-sentence.jsonl", "spike-b-handback-frame"): Expect(
        False, 0, "a sentence before the report breaks B"
    ),
    ("pass2-duplicate-handback.jsonl", "spike-b-handback-frame"): Expect(
        True, 2, "contains: a duplicate still matches"
    ),
    ("pass2-spike.jsonl", "spike-a-tool-use-result"): Expect(
        False, 0, "pattern A red since 2.1.314 (format change)"
    ),
    ("pass2-spike.jsonl", "spike-c-canary"): Expect(True, 1, "spike canary c green"),
    ("pass2-spike.jsonl", "handback-canary"): Expect(
        True, 1, "exactly one hand-back frame"
    ),
    ("pass2-status-sentence.jsonl", "handback-canary"): Expect(
        True, 1, "the canary stays green under status-sentence-first"
    ),
    ("pass2-duplicate-handback.jsonl", "handback-canary"): Expect(
        False, 2, "a duplicated frame fails count:1"
    ),
    ("pass1-spike.jsonl", "handback-canary"): Expect(
        False, 0, "background dispatch: no hand-back frame"
    ),
    # Controls: the unanchored forms misfire on the spike.
    ("pass1-spike.jsonl", "control-unanchored-warn"): Expect(
        True, 1, "WARN tool_result satisfies an unanchored pattern"
    ),
    ("pass1-spike.jsonl", "control-unanchored-reducer"): Expect(
        False, 1, "skill text satisfies an unanchored reducer pattern"
    ),
}


@pytest.mark.parametrize(
    ("fixture", "grader_id"), sorted(EXPECTATIONS), ids=lambda v: v
)
def test_offline_validation_table(fixture, grader_id):
    expect = EXPECTATIONS[(fixture, grader_id)]
    outcome = evaluate(GRADERS[grader_id], load_fixture(fixture))
    assert (outcome.passed, outcome.count) == (expect.passed, expect.count), (
        f"{fixture} x {grader_id}: expected passed={expect.passed} count={expect.count} "
        f"({expect.why}), got passed={outcome.passed} count={outcome.count}"
    )


def test_every_fixture_and_grader_in_the_table_exists():
    assert {f for f, _ in EXPECTATIONS} == set(FIXTURES)
    assert {g for _, g in EXPECTATIONS} == set(GRADERS)
    on_disk = {p.name for p in FIXTURES_DIR.glob("*.jsonl")}
    assert on_disk == set(FIXTURES)


@pytest.mark.parametrize("fixture", sorted(FIXTURES))
def test_fixture_keeps_one_json_event_per_line(fixture):
    text = load_fixture(fixture)
    assert text.endswith("\n")
    for number, line in enumerate(text.splitlines()):
        event = json.loads(line)
        # The ordered patterns rely on the harness's compact encoding.
        assert json.dumps(event, ensure_ascii=False, separators=(",", ":")) == line, (
            number
        )


@pytest.mark.parametrize("fixture", sorted(FIXTURES))
def test_fixture_leaks_no_path_or_identity(fixture):
    text = load_fixture(fixture)
    leak = re.compile(
        r"/private/|/Volumes/|/Users/|/var/folders/|/tmp/|/home/|e-t7N3jn|e-O6bppm|marcus|@[a-z0-9-]+\.[a-z]"
    )
    assert not leak.search(text), leak.search(text).group(0)


def test_pass1_fixture_keeps_the_lines_the_ordered_patterns_rely_on():
    text = load_fixture("pass1-spike.jsonl")
    agents = [u for u in tool_uses(text) if u.name == "Agent"]
    assert len(agents) == 3
    assert all('"subagent_type":"tomo:inbox-analyst"' in u.input_json for u in agents)
    bash = [u.input_json for u in tool_uses(text) if u.name == "Bash"]
    assert sum("scripts/suggestions-reducer.py" in c for c in bash) == 1
    assert sum("scripts/kado-write-file.py" in c for c in bash) == 1
    lines = text.splitlines()
    first_agent = next(
        i for i, ln in enumerate(lines) if '"name":"Agent","input":{' in ln
    )
    # The Skill expansion names the reducer before the first dispatch (prose, not a call).
    assert any(
        "suggestions-reducer.py" in ln
        for ln in lines[:first_agent]
        if '"name":"Bash"' not in ln
    )
    # The WARN text sits in a tool_result before the first dispatch.
    assert any(
        "active tracker field(s) have no keywords" in ln
        and '"type":"tool_result"' in ln
        for ln in lines[:first_agent]
    )


def test_tool_uses_reads_parent_and_json_encoded_input():
    uses = tool_uses(load_fixture("pass1-spike.jsonl"))
    stubs = [u for u in uses if u.name == "Bash" and "analyst-stub.py" in u.input_json]
    assert len(stubs) == 3
    assert all(u.parent for u in stubs)
    assert all(
        u.input_json.startswith('{"command":"python3 scripts/analyst-stub.py \\"')
        for u in stubs
    )


# --- loader over the grader files in evals/ ------------------------------------------------


def test_grader_files_found():
    files = grader_files()
    assert files, "no grader files under evals/"
    assert all(p.suffix == ".md" for p in files)
    assert not any(p.name == "inbox-analyst.stub.md" for p in files)
    assert REPO / "evals" / "_lib" / "no-leak.md" in files


@pytest.mark.parametrize("path", grader_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_every_grader_file_parses_and_its_regexes_compile(path):
    grader = load_grader(path)
    assert grader.type in {"regex", "tool_used", "tool_order"}
    for regex in grader_regexes(grader):
        re.compile(regex)


@pytest.mark.parametrize("path", grader_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_every_grader_file_regex_is_js_compatible(path):
    for regex in grader_regexes(load_grader(path)):
        assert js_subset_violations(regex) == [], regex


@pytest.mark.parametrize("grader_id", sorted(GRADERS))
def test_every_table_regex_is_js_compatible(grader_id):
    for regex in grader_regexes(GRADERS[grader_id]):
        re.compile(regex)
        assert js_subset_violations(regex) == [], regex


@pytest.mark.parametrize(
    "pattern",
    [
        r"(?<=x)a",
        r"(?<!y)a",
        r"a*+",
        r"a++",
        r"a?+",
        r"a{2}+",
        r"(?>a)",
        r"(?i)a",
        r"(?s:a)",
        r"(?P<n>a)",
        r"\Aa",
        r"a\Z",
    ],
)
def test_js_subset_rejects(pattern):
    assert js_subset_violations(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"(?:(?<=\\n)|(?<![\w-]))tee\b",
        r"(?!\\n|(?<!\\)\")",
        r"\*+",
        r"[*+]",
        r"a+?",
        r"(a)\1",
        r"(?=x)(?!y)",
    ],
)
def test_js_subset_accepts(pattern):
    assert js_subset_violations(pattern) == []


def test_regex_target_last_message_reads_the_last_of_four_result_frames():
    # pass1-spike has four result frames; only the last starts with this sentence.
    grader = inline(
        type="regex",
        target="last_message",
        match="contains",
        pattern=r"^Pass 1 did not complete",
    )
    assert evaluate(grader, load_fixture("pass1-spike.jsonl")).passed


# --- evaluator semantics on synthetic traces -------------------------------------------------


def _trace(*events: dict) -> str:
    return "".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in events
    )


def _result(text: str) -> dict:
    return {"type": "result", "subtype": "success", "result": text}


def _tool_use(name: str, command: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "t",
                    "name": name,
                    "input": {"command": command},
                }
            ]
        },
    }


def _regex(pattern: str, target: str = "last_message", match: str = "contains"):
    return inline(type="regex", target=target, match=match, pattern=pattern)


def test_last_message_returns_the_last_result_frame():
    trace = _trace(_result("first"), _tool_use("Bash", "ls"), _result("second"))
    assert last_message(trace) == "second"


def test_last_message_ignores_non_result_lines_that_carry_the_result_text():
    decoy_string = _tool_use("Bash", 'echo \'"type":"result"\'')
    decoy_object = {
        "type": "assistant",
        "message": {"content": [{"type": "result", "result": "nested decoy"}]},
    }
    assert '"type":"result"' in json.dumps(decoy_object, separators=(",", ":"))
    trace = _trace(_result("real"), decoy_string, decoy_object)
    assert last_message(trace) == "real"


def test_last_message_without_a_result_frame_is_empty():
    assert last_message(_trace(_tool_use("Bash", "ls"))) == ""
    assert evaluate(_regex(r"^$"), _trace(_tool_use("Bash", "ls"))).passed


@pytest.mark.parametrize(
    ("pattern", "text", "matched"),
    [
        (r"x$", "x", True),
        (r"x$", "x\n", False),  # Python $ would also match before the trailing newline
        (r"x(?:\n|$)", "x\n", True),
        (r"x\s*$", "x\n", True),
        (r"a\$", "a$", True),  # escaped $ stays a literal
        (r"a[$]", "a$", True),  # $ inside a class stays a literal
        (r"^x", "y\nx", False),  # no multiline flag
    ],
)
def test_regex_anchors_follow_js_without_flags(pattern, text, matched):
    assert evaluate(_regex(pattern), _trace(_result(text))).passed is matched
    assert evaluate(_regex(pattern, target="trace"), text).passed is matched


@pytest.mark.parametrize(("count", "passed"), [(1, False), (2, True), (3, False)])
@pytest.mark.parametrize("mode", ["count:2", "count: 2"])
def test_apply_match_count_is_exact(mode, count, passed):
    assert _apply_match(mode, count) is passed


def test_apply_match_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="unknown match mode"):
        _apply_match("equals", 1)


def test_regex_rejects_an_unknown_target():
    with pytest.raises(ValueError, match="unknown target"):
        evaluate(_regex("x", target="first_message"), _trace(_result("x")))


@pytest.mark.parametrize(("present", "passed"), [(False, True), (True, False)])
def test_tool_used_min0_max0_passes_only_when_absent(present, passed):
    events = [_tool_use("Bash", "ls")] + ([_tool_use("Agent", "go")] if present else [])
    grader = inline(type="tool_used", tool="Agent", min=0, max=0)
    outcome = evaluate(grader, _trace(*events))
    assert (outcome.passed, outcome.count) == (passed, int(present))


@pytest.mark.parametrize(
    ("calls", "passed"), [(0, False), (1, True), (2, True), (3, False)]
)
def test_tool_used_min_defaults_to_one_and_max_bounds(calls, passed):
    trace = _trace(*[_tool_use("Bash", f"echo {i}") for i in range(calls)])
    grader = inline(type="tool_used", tool="Bash", max=2)
    assert evaluate(grader, trace).passed is passed


def test_tool_used_without_input_match_counts_every_call_of_the_tool():
    trace = _trace(
        _tool_use("Bash", "a"), _tool_use("Agent", "b"), _tool_use("Bash", "c")
    )
    outcome = evaluate(inline(type="tool_used", tool="Bash"), trace)
    assert (outcome.passed, outcome.count) == (True, 2)


# --- fixture builder ------------------------------------------------------------------------

BUILDER = FIXTURES_DIR / "build_fixtures.py"
SPIKES = {"pass1-spike.jsonl", "pass2-spike.jsonl"}


def test_builder_variants_regenerate_the_committed_fixtures(tmp_path):
    subprocess.run(
        [sys.executable, str(BUILDER), "variants", str(FIXTURES_DIR), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    built = {p.name for p in tmp_path.glob("*.jsonl")}
    assert built == set(FIXTURES) - SPIKES
    for name in sorted(built):
        assert (tmp_path / name).read_bytes() == (FIXTURES_DIR / name).read_bytes(), (
            name
        )


def test_builder_is_not_collected_by_pytest():
    assert not BUILDER.name.startswith("test")


def test_tool_order_is_left_for_t2_2():
    grader = inline(
        type="tool_order",
        before={"tool": "Bash", "input_match": "x"},
        after={"tool": "Bash", "input_match": "y"},
    )
    with pytest.raises(NotImplementedError):
        evaluate(grader, load_fixture("pass1-spike.jsonl"))
