"""test_043_grader_patterns.py — offline validation of the eval gate's regex graders (spec 043, T2.1).

Every regex pattern on `target: trace` is checked here before any paid run, against
the recorded spike traces and hand-edited variants of them (SDD ADR-5, Quality
Requirements/Reliability). This module reproduces the SDD's offline validation table
with one pytest command and checks that every grader regex in `evals/` parses, compiles
in Python and stays inside the Python/JS common subset.

T2.2/T2.3 added the two Pass 1 cases' graders (every one loaded from its file), the
derived pass1-complete fixtures, `tool_order`, and the CLI's `last_message` semantics.

How later tasks (T2.4) extend it:
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
    parse_frontmatter,
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
    # Pass 1 completions the spike never reached (T2.2/T2.3). Every red variant below is
    # pass1-complete with ONE edit, the shape of the mutation that grader must catch.
    "pass1-complete.jsonl": "pass1-spike up to the .md write, then the .json write, "
    "mark-captured and the Pass 1 report (assistant text + final result frame)",
    "pass1-complete-relayed.jsonl": "pass1-complete + the WARN relay before the first "
    "dispatch, and a report that carries the duplicate line and the WARN line",
    "pass1-conductor-dispatched.jsonl": "pass1-complete + an Agent call to "
    "tomo:suggestion-conductor after the conductor Read",
    "pass1-analyst-name-not-type.jsonl": "pass1-complete with every analyst dispatch's "
    "subagent_type key renamed to name (value inbox-analyst)",
    "pass1-setup-twice.jsonl": "pass1-complete + run-id and shared-ctx-builder calls "
    "before the Skill call (setup done in the conductor)",
    "pass1-dispatch-before-setup.jsonl": "pass1-complete with the shared-ctx-builder call "
    "moved after the first Agent call",
    "pass1-render-before-reduce.jsonl": "pass1-complete with the render call moved before "
    "the reducer call",
    "pass1-write-tool-publish.jsonl": "pass1-complete with the .md publish done by the "
    "Write tool instead of kado-write-file",
    "pass1-mark-before-json-write.jsonl": "pass1-complete with mark-captured moved between "
    "the .md and the .json write",
    "pass1-inline-python.jsonl": "pass1-complete + a python3 -c read of the routing plan",
    "pass1-report-quoted.jsonl": "pass1-complete with the report line quoted inside a "
    "sentence instead of starting a line",
}

# Grader id → grader. `inline` rows carry the SDD-validated patterns until T2.2-T2.4 write
# the grader files; `from_file` rows load the real frontmatter.
PIPE = "evals/pass1-suggest-pipeline/graders/"
RELAY = "evals/pass1-warn-and-duplicates-relayed/graders/"

GRADERS = {
    # Case pass1-suggest-pipeline (SDD pipeline grader table, PRD F1).
    "conductor-not-dispatched": from_file(PIPE + "01-conductor-not-dispatched.md"),
    "analyst-dispatched-3x": from_file(PIPE + "02-analyst-dispatched-3x.md"),
    "no-general-purpose": from_file(PIPE + "03-no-general-purpose.md"),
    "subfolder-path-and-key": from_file(PIPE + "04-subfolder-path-and-key.md"),
    "shared-ctx-once": from_file(PIPE + "05-shared-ctx-once.md"),
    "run-id-once": from_file(PIPE + "06-run-id-once.md"),
    "setup-before-dispatch": from_file(PIPE + "07-setup-before-dispatch.md"),
    "reducer-before-render": from_file(PIPE + "08-reducer-before-render.md"),
    # SDD Complex Logic — the violation shape; green when absent.
    "reduce-after-last-dispatch": from_file(PIPE + "09-reduce-after-last-dispatch.md"),
    "two-script-writes-same-stem": from_file(
        PIPE + "10-two-script-writes-same-stem.md"
    ),
    "no-inline-vault-write": from_file(PIPE + "11-no-inline-vault-write.md"),
    "mark-captured-once": from_file(PIPE + "12a-mark-captured-once.md"),
    "mark-captured-after-json-write": from_file(
        PIPE + "12b-mark-captured-after-json-write.md"
    ),
    "no-inline-python": from_file(PIPE + "13-no-inline-python.md"),
    "report-line-anchored": from_file(PIPE + "14-report-line-anchored.md"),
    "no-duplicate-line": from_file(PIPE + "15-no-duplicate-line.md"),
    "no-leak": from_file("evals/_lib/no-leak.md"),
    # Case pass1-warn-and-duplicates-relayed (SDD relay grader table, PRD F2).
    "warn-in-reply": from_file(RELAY + "01-warn-in-reply.md"),
    # SDD Complex Logic.
    "warn-before-first-dispatch": from_file(RELAY + "02-warn-before-first-dispatch.md"),
    "duplicate-line": from_file(RELAY + "03-duplicate-line.md"),
    "relay-report-line-anchored": from_file(RELAY + "04-report-line-anchored.md"),
    # Control: the SDD's essence for grader 03. A dispatch whose subagent_type key was
    # renamed (mutation analyst-name-not-type) runs general-purpose without naming it,
    # so this pattern stays green on it; the shipped 03 counts dispatches without the key.
    "control-sdd-general-purpose": inline(
        type="tool_used", tool="Agent", min=0, max=0, input_match="general-purpose"
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
    # --- pass1-suggest-pipeline (T2.2). tool_order rows: count 1 = both sides found.
    ("pass1-complete.jsonl", "conductor-not-dispatched"): Expect(
        True, 0, "impersonated"
    ),
    ("pass1-spike.jsonl", "conductor-not-dispatched"): Expect(True, 0, "impersonated"),
    ("pass1-conductor-dispatched.jsonl", "conductor-not-dispatched"): Expect(
        False, 1, "conductor ran as a subagent"
    ),
    ("pass1-complete.jsonl", "analyst-dispatched-3x"): Expect(True, 3, "3 dispatches"),
    ("pass1-spike.jsonl", "analyst-dispatched-3x"): Expect(True, 3, "3 dispatches"),
    ("pass1-analyst-name-not-type.jsonl", "analyst-dispatched-3x"): Expect(
        False, 0, "no dispatch carries subagent_type"
    ),
    ("pass1-complete.jsonl", "no-general-purpose"): Expect(True, 0, "all typed"),
    ("pass1-conductor-dispatched.jsonl", "no-general-purpose"): Expect(
        True, 0, "a typed conductor dispatch is not general-purpose"
    ),
    ("pass1-analyst-name-not-type.jsonl", "no-general-purpose"): Expect(
        False, 3, "3 dispatches without subagent_type run general-purpose"
    ),
    ("pass1-analyst-name-not-type.jsonl", "control-sdd-general-purpose"): Expect(
        True, 0, "the SDD essence cannot see an untyped dispatch"
    ),
    ("pass1-complete.jsonl", "subfolder-path-and-key"): Expect(True, 1, "Dresden"),
    ("pass1-complete.jsonl", "shared-ctx-once"): Expect(True, 1, "built once"),
    ("pass1-setup-twice.jsonl", "shared-ctx-once"): Expect(False, 2, "built twice"),
    ("pass1-complete.jsonl", "run-id-once"): Expect(True, 1, "drawn once"),
    ("pass1-setup-twice.jsonl", "run-id-once"): Expect(False, 2, "drawn twice"),
    ("pass1-complete.jsonl", "setup-before-dispatch"): Expect(True, 1, "ctx first"),
    ("pass1-spike.jsonl", "setup-before-dispatch"): Expect(True, 1, "ctx first"),
    ("pass1-analyst-name-not-type.jsonl", "setup-before-dispatch"): Expect(
        True, 1, "any Agent call is a dispatch"
    ),
    ("pass1-dispatch-before-setup.jsonl", "setup-before-dispatch"): Expect(
        False, 1, "first dispatch before the ctx build"
    ),
    ("pass1-complete.jsonl", "reducer-before-render"): Expect(True, 1, "reduce first"),
    ("pass1-reducer-before-dispatch.jsonl", "reducer-before-render"): Expect(
        True, 1, "still before render (09 catches this one)"
    ),
    ("pass1-render-before-reduce.jsonl", "reducer-before-render"): Expect(
        False, 1, "render first"
    ),
    ("pass1-complete.jsonl", "reduce-after-last-dispatch"): Expect(True, 0, "absent"),
    ("pass1-complete.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, "both writes, one stem"
    ),
    ("pass1-write-tool-publish.jsonl", "two-script-writes-same-stem"): Expect(
        False, 0, ".md not published by the script"
    ),
    ("pass1-complete.jsonl", "no-inline-vault-write"): Expect(True, 0, "no Write"),
    ("pass1-write-tool-publish.jsonl", "no-inline-vault-write"): Expect(
        False, 1, "Write into 100 Inbox/"
    ),
    ("pass1-complete.jsonl", "mark-captured-once"): Expect(True, 1, "marked once"),
    ("pass1-spike.jsonl", "mark-captured-once"): Expect(False, 0, "never marked"),
    ("pass1-mark-before-json-write.jsonl", "mark-captured-once"): Expect(
        True, 1, "once, in the wrong place (12b catches it)"
    ),
    ("pass1-complete.jsonl", "mark-captured-after-json-write"): Expect(
        True, 1, "json write, then mark"
    ),
    ("pass1-spike.jsonl", "mark-captured-after-json-write"): Expect(
        False, 0, "no json write and no mark"
    ),
    ("pass1-mark-before-json-write.jsonl", "mark-captured-after-json-write"): Expect(
        False, 1, "mark before the json write"
    ),
    ("pass1-complete.jsonl", "no-inline-python"): Expect(True, 0, "none"),
    ("pass1-spike.jsonl", "no-inline-python"): Expect(True, 0, "none"),
    ("pass1-inline-python.jsonl", "no-inline-python"): Expect(False, 1, "python3 -c"),
    ("pass1-complete.jsonl", "report-line-anchored"): Expect(True, 1, "report line"),
    ("pass1-spike.jsonl", "report-line-anchored"): Expect(
        False, 0, "the spike says it did not report Pass 1 complete"
    ),
    ("pass1-report-quoted.jsonl", "report-line-anchored"): Expect(
        False, 0, "quoted mid-sentence, not at a line start"
    ),
    ("pass1-complete.jsonl", "no-duplicate-line"): Expect(True, 0, "absent"),
    ("pass1-spike.jsonl", "no-duplicate-line"): Expect(
        True, 0, "names the counter, not the line"
    ),
    ("pass1-complete-relayed.jsonl", "no-duplicate-line"): Expect(
        False, 1, "line present"
    ),
    ("pass1-complete.jsonl", "no-leak"): Expect(True, 0, "report leaks nothing"),
    ("pass1-complete-relayed.jsonl", "no-leak"): Expect(True, 0, "relay leaks nothing"),
    ("pass1-spike.jsonl", "no-leak"): Expect(
        False, 3, "the spike's apology names tomo-tmp/ three times"
    ),
    # --- pass1-warn-and-duplicates-relayed (T2.3).
    ("pass1-complete-relayed.jsonl", "warn-in-reply"): Expect(True, 1, "verbatim"),
    ("pass1-complete.jsonl", "warn-in-reply"): Expect(False, 0, "not relayed"),
    ("pass1-spike.jsonl", "warn-in-reply"): Expect(
        False,
        0,
        "the spike reply quotes the text WITHOUT its `WARN: ` prefix — not verbatim "
        "(plan T2.3 step 2 expected green; F2-AC1 says the line appears verbatim)",
    ),
    ("pass1-complete-relayed.jsonl", "warn-before-first-dispatch"): Expect(
        True, 1, "relayed before the first Agent line"
    ),
    ("pass1-complete.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "never relayed"
    ),
    ("pass1-complete-relayed.jsonl", "duplicate-line"): Expect(True, 1, "line present"),
    ("pass1-complete.jsonl", "duplicate-line"): Expect(False, 0, "absent"),
    ("pass1-spike.jsonl", "duplicate-line"): Expect(False, 0, "absent"),
    ("pass1-complete-relayed.jsonl", "relay-report-line-anchored"): Expect(
        True, 1, "report line"
    ),
    ("pass1-spike.jsonl", "relay-report-line-anchored"): Expect(False, 0, "no report"),
    ("pass1-report-quoted.jsonl", "relay-report-line-anchored"): Expect(
        False, 0, "quoted mid-sentence"
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


def test_regex_target_last_message_reads_the_spike_final_reply():
    # pass1-spike has four result frames and several interim texts; the final reply wins.
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


def _text(*texts: str, parent: str | None = None) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": t} for t in texts]},
        "parent_tool_use_id": parent,
    }


# `last_message` is the CLI's `lastAssistantText` (claude 2.1.314): the text blocks of the
# LAST assistant event that has any, joined with "\n". Result frames are not read.
def test_last_message_is_the_last_assistant_text_not_the_result_frame():
    trace = _trace(_text("first"), _result("frame text"), _text("second"))
    assert last_message(trace) == "second"
    trace = _trace(_text("reply"), _result("an older interim frame"))
    assert last_message(trace) == "reply"


def test_last_message_joins_the_text_blocks_of_one_event_with_newlines():
    assert last_message(_trace(_text("a", "b"))) == "a\nb"


def test_last_message_skips_assistant_events_without_text():
    trace = _trace(_text("reply"), _tool_use("Bash", "ls"), _result("x"))
    assert last_message(trace) == "reply"


def test_last_message_includes_subagent_text():
    # The CLI does not filter on parent_tool_use_id.
    trace = _trace(_text("main"), _text("done 100 Inbox/A.md", parent="toolu_x"))
    assert last_message(trace) == "done 100 Inbox/A.md"


def test_last_message_without_assistant_text_is_empty():
    assert last_message(_trace(_tool_use("Bash", "ls"), _result("frame"))) == ""
    assert evaluate(_regex(r"^$"), _trace(_tool_use("Bash", "ls"))).passed


def _texted(text: str) -> str:
    return _trace(_text(text))


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
    assert evaluate(_regex(pattern), _texted(text)).passed is matched
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
        evaluate(_regex("x", target="first_message"), _texted("x"))


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


# --- tool_order (claude 2.1.314: first `before` match index < first `after` match index) ----


def _order(before, after):
    return inline(type="tool_order", before=before, after=after)


B_X = {"tool": "Bash", "input_match": "x"}
B_Y = {"tool": "Bash", "input_match": "y"}


@pytest.mark.parametrize(
    ("commands", "passed", "count"),
    [
        (["x", "y"], True, 1),
        (["y", "x"], False, 1),
        (["x"], False, 0),  # "after" never called
        (["y"], False, 0),  # "before" never called
        ([], False, 0),
        (["x", "y", "x"], True, 1),  # first occurrences decide
        (["y", "x", "y"], False, 1),  # a later x before a later y does not help
        (["xy"], False, 1),  # one call matching both sides: index == index
    ],
)
def test_tool_order_compares_first_matching_indices(commands, passed, count):
    trace = _trace(*[_tool_use("Bash", c) for c in commands])
    outcome = evaluate(_order(B_X, B_Y), trace)
    assert (outcome.passed, outcome.count) == (passed, count)


def test_tool_order_matches_tool_name_and_input():
    trace = _trace(
        _tool_use("Agent", "x"), _tool_use("Bash", "y"), _tool_use("Bash", "x")
    )
    assert not evaluate(_order(B_X, B_Y), trace).passed  # Agent "x" is not Bash "x"
    assert evaluate(_order({"tool": "Agent"}, B_Y), trace).passed  # no input_match


def test_tool_order_accepts_a_bare_tool_name():
    trace = _trace(_tool_use("Agent", "go"), _tool_use("Bash", "y"))
    assert evaluate(_order("Agent", "Bash"), trace).passed
    assert not evaluate(_order("Bash", "Agent"), trace).passed


def test_tool_order_counts_subagent_calls_in_trace_order():
    sub = _tool_use("Bash", "x")
    sub["parent_tool_use_id"] = "toolu_parent"
    trace = _trace(sub, _tool_use("Bash", "y"))
    assert evaluate(_order(B_X, B_Y), trace).passed


# --- grader files: the CLI's strict frontmatter schema (claude 2.1.314) ------------------

CLI_KEYS = {
    "regex": {"type", "name", "target", "pattern", "flags", "match", "weight", "arm"},
    "tool_order": {"type", "name", "before", "after", "weight", "arm"},
    "tool_used": {"type", "name", "tool", "input_match", "min", "max", "weight", "arm"},
}


@pytest.mark.parametrize("path", grader_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_every_grader_file_uses_only_keys_the_cli_accepts(path):
    data = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert set(data) <= CLI_KEYS[data["type"]], set(data) - CLI_KEYS[data["type"]]
    for side in ("before", "after"):
        if isinstance(data.get(side), dict):
            assert set(data[side]) <= {"tool", "input_match"}, data[side]


# --- the two Pass 1 cases (T2.2, T2.3) --------------------------------------------------

PASS1_CASES = ("pass1-suggest-pipeline", "pass1-warn-and-duplicates-relayed")


def test_every_pass1_case_grader_is_validated_offline():
    in_table = {g.source for g in GRADERS.values() if g.source is not None}
    for case in PASS1_CASES:
        for path in sorted((REPO / "evals" / case / "graders").glob("*.md")):
            if path.name == "9-no-leak.md":
                continue
            assert path in in_table, f"{path.relative_to(REPO)} not in GRADERS"


def test_relay_report_grader_is_the_pipeline_report_grader():
    pipe = (REPO / PIPE / "14-report-line-anchored.md").read_bytes()
    assert (REPO / RELAY / "04-report-line-anchored.md").read_bytes() == pipe


def _skill_report_quotes() -> list[str]:
    """The `> "…"` blockquotes of suggest-handling's step 7, each joined to one line."""
    skill = REPO / "tomo" / "dot_claude" / "skills" / "suggest-handling" / "SKILL.md"
    step = skill.read_text(encoding="utf-8").split("### 7. Report", 1)[1]
    quotes, current = [], []
    for line in step.splitlines():
        if line.startswith("> "):
            current.append(line[2:])
        elif current:
            quotes.append(" ".join(current).strip('"'))
            current = []
    if current:
        quotes.append(" ".join(current).strip('"'))
    return quotes


def test_report_graders_match_the_skill_template_lines():
    report, duplicate = _skill_report_quotes()
    report = report.replace("{N}", "3").replace("<date>", "2026-10-30_0000")
    duplicate = duplicate.replace("{n}", "1")
    reply = _texted(f"{report}\n\n{duplicate}")
    for grader_id in (
        "report-line-anchored",
        "relay-report-line-anchored",
        "duplicate-line",
    ):
        assert evaluate(GRADERS[grader_id], reply).passed, grader_id
    assert not evaluate(GRADERS["no-duplicate-line"], reply).passed


def test_warn_grader_matches_the_kit_warn_line():
    from test_pass1_stub_kit import WARN_LINE

    assert evaluate(GRADERS["warn-in-reply"], _texted(WARN_LINE)).passed
    assert not evaluate(GRADERS["warn-in-reply"], _texted(WARN_LINE[6:])).passed
