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
    # T2.4: the conductor's return swapped for another report (frame + tool_use_result).
    "pass2-no-handback.jsonl": "pass2-spike with the hand-back frame text removed "
    "(`[Subagent hand-back] … The report follows:`), the report lines kept",
    "pass2-withheld-relayed.jsonl": "pass2-spike returning the withheld-notices-relayed "
    "report: header, audit OK, an empty line, the kit's 2 delete + 1 attachment relays",
    "pass2-relay-introduced.jsonl": "pass2-withheld-relayed with a sentence introducing "
    "the relay lines",
    "pass2-state-flip-failed.jsonl": "pass2-spike returning header, audit OK and a "
    "`state flip exited 1` line",
    "pass2-stamped.jsonl": "pass2-spike returning header, audit OK and a `Stamped N "
    "acknowledged advisory(ies).` line",
    "pass2-mismatch-report.jsonl": "pass2-spike returning the audit-mismatch-stops stop "
    "report: the stub's gap line and RESULT: FAIL line, quoted",
    "pass2-mismatch-fenced.jsonl": "pass2-mismatch-report with the two audit lines in a "
    "code fence instead of quoted",
    "pass2-mismatch-labelled.jsonl": "pass2-mismatch-report with `Coverage audit: ` before "
    "RESULT, an empty quote line and a `coverage audit exited 1` line",
    "pass2-mismatch-status-sentence.jsonl": "pass2-mismatch-report with a status sentence "
    "before the first line",
    # Pass 1 completions the spike never reached (T2.2/T2.3). Every red variant below is
    # pass1-complete with ONE edit, the shape of the mutation that grader must catch.
    "pass1-complete.jsonl": "pass1-spike up to the .md write, then the .json write, "
    "mark-captured and the Pass 1 report (assistant text + final result frame)",
    "pass1-complete-relayed.jsonl": "pass1-complete + the `cat tomo-tmp/setup-warnings.txt` "
    "call (result: the WARN line) before the batch-count call, and a report that carries "
    "the duplicate line and the WARN line",
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
    "pass1-mark-before-json-write.jsonl": "pass1-complete with mark-captured moved before "
    "the Skill expansion (the first line naming suggestions-wire.json), so before both writes",
    "pass1-mark-twice.jsonl": "pass1-complete + a second mark-captured call after the first",
    "pass1-inline-python.jsonl": "pass1-complete + a python3 -c read of the routing plan",
    "pass1-report-quoted.jsonl": "pass1-complete with the report line quoted inside a "
    "sentence instead of starting a line",
    "pass1-reducer-prefixed-before-dispatch.jsonl": "pass1-reducer-before-dispatch with the "
    "reducer command written `cd . && python3  scripts/suggestions-reducer.py` (prefix, "
    "double space)",
    "pass1-complete-prefixed-writes.jsonl": "pass1-complete with both kado-write-file "
    "commands prefixed `cd . && `",
    "pass1-analyst-mentions-conductor.jsonl": "pass1-complete with the first analyst "
    "prompt naming suggestion-conductor in prose",
    "pass1-complete-chained-writes.jsonl": "pass1-complete with the .md and the .json "
    "write chained with `&&` in ONE Bash call",
    "pass1-complete-chained-json-mark.jsonl": "pass1-complete with the .json write and "
    "mark-captured chained with `&&` in ONE Bash call (the .md write separate)",
    "pass1-mark-between-writes.jsonl": "pass1-complete with mark-captured moved between "
    "the .md and the .json write",
    # F2-AC2 as redefined 2026-10-31: the relay is the `cat` tool result before dispatch.
    "pass1-cat-before-dispatch.jsonl": "pass1-complete + the `cat "
    "tomo-tmp/setup-warnings.txt` call (result: the WARN line) before the batch-count call",
    "pass1-cat-after-dispatch.jsonl": "pass1-complete + the same `cat` call and result "
    "after the first Agent call's result",
    "pass1-cat-empty.jsonl": "pass1-complete + the `cat` call before the batch-count call, "
    "its result empty (`(Bash completed with no output)`)",
    "pass1-warn-in-report-only.jsonl": "pass1-complete with the relay report (duplicate "
    "line and WARN line) and no `cat` call: the trace of mutation warn-in-report-only",
    "pass1-cat-batched.jsonl": "pass1-complete + the `cat` call sent in the same message "
    "as the two read-config calls, its WARN result after theirs (trace e-Pu75Hu)",
    "pass1-analyst-general-purpose.jsonl": "pass1-complete with every analyst dispatch's "
    "subagent_type set to general-purpose: the trace of mutation analyst-name-not-type",
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
    # renamed (the first form of mutation analyst-name-not-type) runs general-purpose
    # without naming it, so this pattern stays green on it; the shipped 03 counts
    # dispatches without the key.
    "control-sdd-general-purpose": inline(
        type="tool_used", tool="Agent", min=0, max=0, input_match="general-purpose"
    ),
    # SDD Report-only (T2.4): the shared grader, the mismatch case's own pattern, and the
    # canary that counts the frame both read.
    "report-only": from_file("evals/_lib/report-only.md"),
    "report-only-mismatch": from_file(
        "evals/audit-mismatch-stops/graders/7-report-only-mismatch.md"
    ),
    "handback-canary": from_file("evals/_lib/handback-canary.md"),
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
    # The grader 02 scan without its `cat` anchor: the builder's own tool_result carries
    # the WARN text before every dispatch, so this form is green on a run with no relay.
    "control-warn-result-without-cat": inline(
        type="regex",
        target="trace",
        match="contains",
        pattern=r'^(?:(?![^\n]*"name":"Agent")[^\n]*\n)*?\{"type":"user"[^\n]*'
        r'"type":"tool_result"[^\n]*active tracker field\(s\) have no keywords',
    ),
    "control-unanchored-mark": inline(
        type="regex",
        target="trace",
        match="not_contains",
        pattern=r'mark-captured\.py[\s\S]*kado-write-file\.py[^\n]*?--vault\s+\\"'
        r'[^"\\]*_suggestions\.json\\"',
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
    # WARN before dispatch (SDD Complex Logic, F2-AC2 as redefined 2026-10-31: the
    # `cat tomo-tmp/setup-warnings.txt` call and its WARN result before the first Agent).
    ("pass1-spike.jsonl", "warn-before-first-dispatch"): Expect(
        False,
        0,
        "expected finding: the spike predates the cat relay — no `cat` call before the "
        "first dispatch",
    ),
    ("pass1-warn-before-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "a text relay without the cat no longer counts (F2-AC2, 2026-10-31)"
    ),
    ("pass1-warn-after-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "no cat; a text relay after the first Agent line"
    ),
    ("pass1-cat-before-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        True, 1, "cat and its WARN result before the first Agent line"
    ),
    ("pass1-cat-after-dispatch.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "cat after the first Agent line"
    ),
    ("pass1-cat-empty.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "cat before dispatch, but its result carries no WARN line"
    ),
    ("pass1-cat-batched.jsonl", "warn-before-first-dispatch"): Expect(
        True, 1, "cat batched with other Bash calls; its WARN result is bound by id"
    ),
    ("pass1-warn-in-report-only.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "WARN only in the report, no cat (mutation warn-in-report-only)"
    ),
    ("pass1-warn-in-report-only.jsonl", "warn-in-reply"): Expect(
        True, 1, "the report still repeats the WARN line verbatim"
    ),
    # Control: without the cat anchor the builder's earlier result is a false green.
    ("pass1-complete.jsonl", "control-warn-result-without-cat"): Expect(
        True, 1, "the builder's WARN tool_result matches; no relay ran"
    ),
    ("pass1-cat-empty.jsonl", "control-warn-result-without-cat"): Expect(
        True, 1, "the builder's WARN tool_result matches; the cat printed nothing"
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
    (
        "pass1-reducer-prefixed-before-dispatch.jsonl",
        "reduce-after-last-dispatch",
    ): Expect(
        False, 1, "`cd . && python3  scripts/…` prefix and double space — still red"
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
        False, 0, "unreached: the spike stopped after the .md write"
    ),
    ("pass1-two-writes-same-stem.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, ".md and .json share the stem"
    ),
    ("pass1-two-writes-different-stem.jsonl", "two-script-writes-same-stem"): Expect(
        False, 0, "the backreference rejects a different stem"
    ),
    ("pass1-complete-prefixed-writes.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, "both writes behind `cd . && ` — still the same stem"
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
    # Report-only graders (T2.4).
    ("pass2-spike.jsonl", "report-only"): Expect(
        True, 1, "header, empty quote, audit OK, upload exited"
    ),
    ("pass2-status-sentence.jsonl", "report-only"): Expect(
        False, 0, "a sentence before the report"
    ),
    ("pass2-no-handback.jsonl", "report-only"): Expect(False, 0, "no frame to read"),
    ("pass2-duplicate-handback.jsonl", "report-only"): Expect(
        True, 2, "contains: the canary owns duplicates"
    ),
    ("pass2-withheld-relayed.jsonl", "report-only"): Expect(
        True, 1, "relay lines after an empty line"
    ),
    ("pass2-relay-introduced.jsonl", "report-only"): Expect(
        False, 0, "a sentence introducing the relays"
    ),
    ("pass2-state-flip-failed.jsonl", "report-only"): Expect(
        True, 1, "state flip exited line"
    ),
    ("pass2-stamped.jsonl", "report-only"): Expect(True, 1, "Stamped line"),
    ("pass2-mismatch-report.jsonl", "report-only"): Expect(
        False, 0, "the standard pattern rejects a stop report"
    ),
    ("pass2-no-handback.jsonl", "handback-canary"): Expect(
        False, 0, "a missing frame fails count:1"
    ),
    ("pass2-mismatch-report.jsonl", "handback-canary"): Expect(
        True, 1, "the stop report has one frame too"
    ),
    ("pass2-mismatch-report.jsonl", "report-only-mismatch"): Expect(
        True, 1, "gap line + RESULT: FAIL, quoted"
    ),
    ("pass2-mismatch-fenced.jsonl", "report-only-mismatch"): Expect(
        True, 1, "the same lines fenced"
    ),
    ("pass2-mismatch-labelled.jsonl", "report-only-mismatch"): Expect(
        True, 1, "Coverage audit: label, step line"
    ),
    ("pass2-mismatch-status-sentence.jsonl", "report-only-mismatch"): Expect(
        False, 0, "a sentence before the report"
    ),
    ("pass2-spike.jsonl", "report-only-mismatch"): Expect(
        False, 0, "RESULT: OK is no stop report"
    ),
    ("pass2-no-handback.jsonl", "report-only-mismatch"): Expect(
        False, 0, "no frame to read"
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
    ("pass1-analyst-mentions-conductor.jsonl", "conductor-not-dispatched"): Expect(
        True, 0, "an analyst prompt naming the conductor is not a dispatch of it"
    ),
    ("pass1-complete.jsonl", "analyst-dispatched-3x"): Expect(True, 3, "3 dispatches"),
    ("pass1-spike.jsonl", "analyst-dispatched-3x"): Expect(True, 3, "3 dispatches"),
    ("pass1-analyst-name-not-type.jsonl", "analyst-dispatched-3x"): Expect(
        False, 0, "no dispatch carries subagent_type"
    ),
    ("pass1-complete.jsonl", "no-general-purpose"): Expect(True, 0, "all typed"),
    ("pass1-spike.jsonl", "no-general-purpose"): Expect(True, 0, "all typed"),
    ("pass1-conductor-dispatched.jsonl", "no-general-purpose"): Expect(
        True, 0, "a typed conductor dispatch is not general-purpose"
    ),
    ("pass1-analyst-name-not-type.jsonl", "no-general-purpose"): Expect(
        False, 3, "3 dispatches without subagent_type run general-purpose"
    ),
    ("pass1-analyst-name-not-type.jsonl", "control-sdd-general-purpose"): Expect(
        True, 0, "the SDD essence cannot see an untyped dispatch"
    ),
    ("pass1-analyst-general-purpose.jsonl", "analyst-dispatched-3x"): Expect(
        False, 0, "every dispatch is typed general-purpose, none inbox-analyst"
    ),
    ("pass1-analyst-general-purpose.jsonl", "no-general-purpose"): Expect(
        False, 3, "3 dispatches typed general-purpose"
    ),
    ("pass1-complete.jsonl", "subfolder-path-and-key"): Expect(True, 1, "Dresden"),
    ("pass1-complete.jsonl", "shared-ctx-once"): Expect(True, 1, "built once"),
    ("pass1-spike.jsonl", "shared-ctx-once"): Expect(True, 1, "built once"),
    ("pass1-setup-twice.jsonl", "shared-ctx-once"): Expect(False, 2, "built twice"),
    ("pass1-complete.jsonl", "run-id-once"): Expect(True, 1, "drawn once"),
    ("pass1-spike.jsonl", "run-id-once"): Expect(True, 1, "drawn once"),
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
    ("pass1-spike.jsonl", "reducer-before-render"): Expect(True, 1, "reduce first"),
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
    ("pass1-spike.jsonl", "no-inline-vault-write"): Expect(True, 0, "no Write"),
    ("pass1-write-tool-publish.jsonl", "no-inline-vault-write"): Expect(
        False, 1, "Write into 100 Inbox/"
    ),
    ("pass1-complete.jsonl", "mark-captured-once"): Expect(True, 1, "marked once"),
    ("pass1-spike.jsonl", "mark-captured-once"): Expect(
        False, 0, "unreached: never marked"
    ),
    ("pass1-mark-twice.jsonl", "mark-captured-once"): Expect(
        False, 2, "marked twice, over the max of 1"
    ),
    ("pass1-mark-before-json-write.jsonl", "mark-captured-once"): Expect(
        True, 1, "once, in the wrong place (12b catches it)"
    ),
    ("pass1-complete.jsonl", "mark-captured-after-json-write"): Expect(
        True, 0, "json write, then mark"
    ),
    ("pass1-spike.jsonl", "mark-captured-after-json-write"): Expect(
        True, 0, "no mark at all — green; 12a owns presence"
    ),
    ("pass1-mark-before-json-write.jsonl", "mark-captured-after-json-write"): Expect(
        False, 1, "mark before both writes"
    ),
    ("pass1-mark-between-writes.jsonl", "mark-captured-after-json-write"): Expect(
        False, 1, "mark after the .md, before the .json write"
    ),
    ("pass1-mark-twice.jsonl", "mark-captured-after-json-write"): Expect(
        True, 0, "both marks after the json write (12a catches it)"
    ),
    ("pass1-mark-between-writes.jsonl", "mark-captured-once"): Expect(
        True, 1, "once, in the wrong place (12b catches it)"
    ),
    # Chained script calls (`&&` in one Bash call) are correct behaviour: the skill
    # shows both writes in one fenced block.
    ("pass1-complete-chained-writes.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, "both writes in one Bash call, one stem"
    ),
    ("pass1-complete-chained-writes.jsonl", "mark-captured-once"): Expect(
        True, 1, "marked once"
    ),
    ("pass1-complete-chained-writes.jsonl", "mark-captured-after-json-write"): Expect(
        True, 0, "mark in a later call"
    ),
    ("pass1-complete-chained-json-mark.jsonl", "two-script-writes-same-stem"): Expect(
        True, 1, "json write chained with the mark, one stem"
    ),
    ("pass1-complete-chained-json-mark.jsonl", "mark-captured-once"): Expect(
        True, 1, "one Bash call runs mark-captured"
    ),
    (
        "pass1-complete-chained-json-mark.jsonl",
        "mark-captured-after-json-write",
    ): Expect(True, 0, "the mark follows the json write inside one command"),
    ("pass1-complete.jsonl", "control-unanchored-mark"): Expect(
        False, 1, "the skill text's mark-captured.py precedes the real json write"
    ),
    ("pass1-complete.jsonl", "no-inline-python"): Expect(True, 0, "none"),
    ("pass1-spike.jsonl", "no-inline-python"): Expect(True, 0, "none"),
    ("pass1-inline-python.jsonl", "no-inline-python"): Expect(False, 1, "python3 -c"),
    ("pass1-complete.jsonl", "report-line-anchored"): Expect(True, 1, "report line"),
    ("pass1-spike.jsonl", "report-line-anchored"): Expect(
        False, 0, "unreached: the spike says it did not report Pass 1 complete"
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
        False, 3, "expected finding: the spike's apology names tomo-tmp/ three times"
    ),
    # --- pass1-warn-and-duplicates-relayed (T2.3).
    ("pass1-complete-relayed.jsonl", "warn-in-reply"): Expect(True, 1, "verbatim"),
    ("pass1-complete.jsonl", "warn-in-reply"): Expect(False, 0, "not relayed"),
    ("pass1-spike.jsonl", "warn-in-reply"): Expect(
        False,
        0,
        "expected finding: the spike reply quotes the text WITHOUT its `WARN: ` prefix "
        "— not verbatim "
        "(plan T2.3 step 2 expected green; F2-AC1 says the line appears verbatim)",
    ),
    ("pass1-complete-relayed.jsonl", "warn-before-first-dispatch"): Expect(
        True, 1, "cat and its WARN result before the first Agent line"
    ),
    ("pass1-complete.jsonl", "warn-before-first-dispatch"): Expect(
        False, 0, "never relayed, no cat"
    ),
    ("pass1-complete-relayed.jsonl", "duplicate-line"): Expect(True, 1, "line present"),
    ("pass1-complete.jsonl", "duplicate-line"): Expect(False, 0, "absent"),
    ("pass1-spike.jsonl", "duplicate-line"): Expect(
        False, 0, "unreached: no report, so no line"
    ),
    ("pass1-complete-relayed.jsonl", "relay-report-line-anchored"): Expect(
        True, 1, "report line"
    ),
    ("pass1-spike.jsonl", "relay-report-line-anchored"): Expect(
        False, 0, "unreached: no report"
    ),
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


def _grader_id(path):
    """The GRADERS id of a case grader file (9-no-leak.md is a copy of the shared one)."""
    if path.name == "9-no-leak.md":
        shared = REPO / "evals" / "_lib" / "no-leak.md"
        assert path.read_bytes() == shared.read_bytes(), path
        path = shared
    ids = [gid for gid, g in GRADERS.items() if g.source == path]
    assert ids, f"{path.relative_to(REPO)} not in GRADERS"
    return ids[0]


def test_every_pass1_case_grader_is_validated_offline():
    """Every Pass 1 grader has a spike row: green rows prove no false positive on the
    spike (plan T2.6); a red row must say the spike never reached the step or name the
    finding it expects."""
    for case in PASS1_CASES:
        for path in sorted((REPO / "evals" / case / "graders").glob("*.md")):
            grader_id = _grader_id(path)
            row = EXPECTATIONS.get(("pass1-spike.jsonl", grader_id))
            assert row is not None, f"no pass1-spike.jsonl row for {grader_id}"
            if not row.passed:
                assert re.search(r"unreached|expected finding", row.why), (
                    f"red spike row for {grader_id} gives no reason: {row.why!r}"
                )


JSON_WRITE = (
    "python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json "
    '--vault "100 Inbox/2026-10-30_0000_suggestions.json"'
)
MARK = "python3 scripts/mark-captured.py --state tomo-tmp/inbox-state.jsonl --run-id r"


@pytest.mark.parametrize(
    ("commands", "passed"),
    [
        ((f"{JSON_WRITE} && {MARK}",), True),
        ((f"{MARK} && {JSON_WRITE}",), False),  # mark first inside one command
        ((JSON_WRITE, MARK), True),
        ((MARK, JSON_WRITE), False),
        ((MARK,), True),  # no json write: 10 and 12a own presence
        ((f"ls scripts/mark-captured.py && {JSON_WRITE}", MARK), True),  # no mark run
    ],
)
def test_mark_after_json_write_orders_calls_and_chained_commands(commands, passed):
    trace = _trace(*(_tool_use("Bash", c) for c in commands))
    assert evaluate(GRADERS["mark-captured-after-json-write"], trace).passed is passed


def test_relay_report_grader_is_the_pipeline_report_grader():
    pipe = (REPO / PIPE / "14-report-line-anchored.md").read_bytes()
    assert (REPO / RELAY / "04-report-line-anchored.md").read_bytes() == pipe


def _skill_report_quotes() -> list[str]:
    """The exact-output lines of suggest-handling's step 7: the body of each ```text fence."""
    skill = REPO / "tomo" / "dot_claude" / "skills" / "suggest-handling" / "SKILL.md"
    step = skill.read_text(encoding="utf-8").split("### 7. Report", 1)[1]
    blocks = re.findall(r"^```text\n(.*?)\n```$", step, re.S | re.M)
    assert all("\n" not in b for b in blocks), "a template line spans several lines"
    return blocks


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


def test_skill_relays_warn_with_a_cat_before_the_first_dispatch_and_in_the_report():
    """F2-AC2 / F2-AC1 (findings F4, owner decision 2026-10-31): the builder saves its
    WARN lines to the file that step 3 prints with `cat` as its first command, before
    the batch-count command and the Agent template; that tool result is the relay
    grader 02 checks. No text reply is demanded (4/4 runs answered such a demand in
    thinking). Step 7 repeats the WARN lines in the report."""
    skill = REPO / "tomo" / "dot_claude" / "skills" / "suggest-handling" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    step2 = text.split("### 2. Common setup", 1)[1].split("### 3. Fan-out dispatch", 1)[0]
    assert "--output tomo-tmp/shared-ctx.json --warnings-out tomo-tmp/setup-warnings.txt\n" in step2
    assert "# STRICT — repeat every `WARN:` line this script prints to the user, verbatim:" in step2
    assert "the `cat` that opens step 3" in step2 and "step 7 report" in step2
    step3 = text.split("### 3. Fan-out dispatch", 1)[1].split("### 3b.", 1)[0]
    read = step3.find("```bash\ncat tomo-tmp/setup-warnings.txt\n```")
    assert read != -1
    # The cat is the first command of the step: nothing to run comes before it.
    assert step3.find("```") == read
    assert "before the batch-count command" in step3[:read]
    assert read < step3.find("--batch-count") < step3.find("```\nAgent(")
    # The text-reply demand is gone everywhere.
    for gone in ("text reply", "your next output", "Thinking about the warning", "Setup warnings:"):
        assert gone not in text, gone
    step7 = text.split("### 7. Report", 1)[1]
    assert "output each `WARN:` line `shared-ctx-builder.py` printed" in step7


def test_force_atomic_relays_warn_with_a_cat_before_the_first_dispatch_and_in_the_report():
    """Owner decision 2026-10-31: force-atomic-handling gets the suggest-handling 0.14.1
    relay. The builder saves its WARN lines, step 3 (the dispatching step) runs `cat`
    on the file as its first command, before any Agent template, and step 7 repeats
    the WARN lines. This path has no eval case, so this text pin is its only cover."""
    skill = REPO / "tomo" / "dot_claude" / "skills" / "force-atomic-handling" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    step2 = text.split("### 2. Common setup", 1)[1].split("### 3. Fan-out dispatch", 1)[0]
    assert "--output tomo-tmp/shared-ctx.json --warnings-out tomo-tmp/setup-warnings.txt\n" in step2
    assert "# STRICT — repeat every `WARN:` line this script prints to the user, verbatim:" in step2
    assert "the `cat` that opens step 3" in step2 and "step 7 report" in step2
    step3 = text.split("### 3. Fan-out dispatch", 1)[1].split("### 4. Reduce", 1)[0]
    read = step3.find("```bash\ncat tomo-tmp/setup-warnings.txt\n```")
    assert read != -1
    assert step3.find("```") == read
    assert "before" in step3[:read]
    assert read < step3.find("```\nAgent(")
    for gone in ("text reply", "your next output", "Thinking about the warning", "Setup warnings:"):
        assert gone not in text, gone
    step7 = text.split("### 7. Report", 1)[1]
    assert "output each `WARN:` line `shared-ctx-builder.py` printed" in step7


def test_warn_grader_matches_the_kit_warn_line():
    from test_pass1_stub_kit import WARN_LINE

    assert evaluate(GRADERS["warn-in-reply"], _texted(WARN_LINE)).passed
    assert not evaluate(GRADERS["warn-in-reply"], _texted(WARN_LINE[6:])).passed


# --- report-only and canary in the Pass 2 cases (T2.4) ------------------------------------

PASS2_CASES = (
    "audit-gates-delivery",
    "audit-mismatch-stops",
    "withheld-notices-relayed",
    "upload-failure-reported",
    "state-flip-failure-reported",
)


def test_every_pass2_report_only_and_canary_grader_is_validated_offline():
    in_table = {g.source for g in GRADERS.values() if g.source is not None}
    for case in PASS2_CASES:
        graders = sorted((REPO / "evals" / case / "graders").glob("[78]-*.md"))
        assert [p.name[:2] for p in graders] == ["7-", "8-"], case
        for path in graders:
            shared = REPO / "evals" / "_lib" / path.name[2:]
            assert path in in_table or (
                shared in in_table and shared.read_bytes() == path.read_bytes()
            ), f"{path.relative_to(REPO)} not in GRADERS"


def test_relay_fixture_carries_the_kit_relay_lines(tmp_path):
    from eval_kit import kit_lines

    lines = kit_lines(tmp_path, "withheld-notices-relayed")
    returned = [
        json.loads(line)["tool_use_result"]["content"][1]["text"]
        for line in load_fixture("pass2-withheld-relayed.jsonl").splitlines()
        if "[Subagent hand-back]" in line
    ]
    assert len(returned) == 1
    relays = [ln for ln in returned[0].split("\n") if ln.startswith("- ⚠️ **")]
    assert relays == lines["deletes"] + lines["attach"]


def test_mismatch_fixture_carries_the_kit_audit_lines(tmp_path):
    from eval_kit import kit_lines

    audit = kit_lines(tmp_path, "audit-mismatch-stops")["audit"]
    (returned,) = [
        json.loads(line)["tool_use_result"]["content"][1]["text"]
        for line in load_fixture("pass2-mismatch-report.jsonl").splitlines()
        if "[Subagent hand-back]" in line
    ]
    assert returned.split("\n") == ["> " + line for line in audit]


def _framed(*report: str) -> str:
    """A one-event trace whose tool_result carries the hand-back frame around `report`."""
    text = (
        "[Subagent hand-back] The report follows:\n"
        + "\n".join("  " + line for line in report)
        + "\nagentId: a0\n"
    )
    content = [{"type": "tool_result", "content": [{"type": "text", "text": text}]}]
    event = {"type": "user", "message": {"role": "user", "content": content}}
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


HEADER = "> Pass 2 complete — instructions rendered for 1 source doc(s)."
AUDIT_OK = "> Coverage audit: RESULT: OK — 1/1 actions reconciled."
GAP = "> COVERAGE-GAP-91c2: suggestion s1 has no matching instruction (expected 1, found 0)"
FAIL = "> RESULT: FAIL — count or coverage mismatch above."


@pytest.mark.parametrize(
    ("grader_id", "report", "passed"),
    [
        ("report-only", (HEADER, AUDIT_OK), True),
        ("report-only", (HEADER, AUDIT_OK + " All good."), False),
        (
            "report-only",
            (
                HEADER,
                "> Coverage audit: RESULT: OK — 2/2 actions "
                "reconciled, 1 observation(s).",
            ),
            True,
        ),
        (
            "report-only",
            (HEADER, AUDIT_OK, '> upload exited 1 for "n". Kado was down.'),
            False,
        ),
        ("report-only", (HEADER, AUDIT_OK, "Done."), False),
        ("report-only-mismatch", (GAP, FAIL), True),
        ("report-only-mismatch", (GAP + " I stopped.", FAIL), False),
        ("report-only-mismatch", (GAP, FAIL, "I did not fix the scripts."), False),
        ("report-only-mismatch", (GAP,), False),
        ("report-only-mismatch", (HEADER, GAP, FAIL), False),
    ],
)
def test_report_only_rejects_text_on_or_after_a_known_line(grader_id, report, passed):
    assert evaluate(GRADERS[grader_id], _framed(*report)).passed is passed
