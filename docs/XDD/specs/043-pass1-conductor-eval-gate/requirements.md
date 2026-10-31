---
title: "Eval gate for the Pass 1 conductor"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

When someone edits the text that runs `/inbox` Pass 1, they find out before merging whether the model still follows it, in the same way spec 041 already did for Pass 2.

### Problem Statement

Pass 1 of `/inbox` (the suggestion conductor and the skill it loads) is runtime prose that a model reads and follows. When an edit breaks it, nothing tells you: pytest cannot see what a model does with a sentence. Those breaks have only ever been found by live runs on the owner's vault, after the change had shipped.

- **Regression history.** Since 2026-09-01, `suggestion-conductor.md`, `suggest-handling` and `force-atomic-handling` have taken 6 + 5 + 1 fix commits, more than any runtime file outside the existing gate (#207). Each one was found by reading a live transcript:
  - every dispatch ran general-purpose instead of `inbox-analyst` (6ce79da4);
  - the setup ran twice, which drew a second run id and sent a second vault walk into HTTP 429 (f3b478b9);
  - 15 unusable tracker fields were warned on stderr and reported to nobody (f3b478b9);
  - 11,055 characters of rendered markdown were relayed through the model's own tokens instead of a script (811a0230);
  - a `#` line inside a dispatch template never reached the subagent (a0f08626);
  - `python3 -c` kept being used, because the text named no sanctioned alternative (7e53ad6f);
  - Force Atomic was broken for every note in a subfolder (4cc992d4).
- **The gap the gate leaves.** The existing eval gate (spec 041) covers only `synthesis-conductor.md`, `inbox.md` and `settings.json`. An edit to the Pass 1 text needs no evidence before merge.
- **A second gap, in the gate itself.** No grader checks that the Pass 2 conductor's reply is *only* the report. On conductor 0.24.1, 1 run in 6 wrapped the report in a status sentence of its own, and every grader stayed green (#205, `evals/README.md` Known gaps).

### Value Proposition

- A Pass 1 regression is caught in about 2 minutes for about $1.50 (measured in the spike), instead of in a live run on a real vault followed by a transcript audit.
- The gate already exists, with its runner, its verdict, its merge rule and its RED-proof discipline. This spec extends it; it does not build a second one.
- The rules that broke before (dispatch type, the path of a subfolder note, setup order, WARN relay, script-only publishing, mark-captured after the write) are each defended by a grader that has been proven able to go red.

## User Personas

### Primary Persona: The maintainer who changes runtime prose

- **Demographics:** The repo owner, or a Claude Code session working for them. Expert in Tomo's pipeline. Edits `tomo/dot_claude/` text often, usually as part of a fix.
- **Goals:** Merge a change to the Pass 1 text knowing that the model still runs the pipeline in order, dispatches the right agent with the right path, publishes through scripts, and tells the user what the scripts warned about.
- **Pain Points:** Today the only check is a live `/inbox` run on a vault: slow, it costs real tokens, it touches real notes, and a deviation is visible only by auditing the transcript call by call.

### Secondary Personas

#### The reviewer of a runtime-prose PR

- **Demographics:** The owner reviewing a PR, or a review agent.
- **Goals:** See in the PR whether a change to a covered file passed the gate, with the verdict, the cost and the results path.
- **Pain Points:** For Pass 1 files the PR has no such evidence today, so a review comes down to reading the prose.

## User Journey Maps

### Primary User Journey: Change the Pass 1 text and merge it

1. **Awareness:** The maintainer edits `suggestion-conductor.md`, or the `suggest-handling` skill it loads. The root `CLAUDE.md` rule and the coverage table in `evals/README.md` say that this file is gated.
2. **Consideration:** Run the full suite (`scripts/run-evals.sh`), or skip it and risk an unnoticed regression.
3. **Adoption:** The full suite costs about $3 and takes about 2–3 minutes. That is cheaper than one live `/inbox` run on the owner's vault.
4. **Usage:** The maintainer runs the suite from a terminal and reads the verdict. If it is RED, stderr names the case, the grader and the run. They re-run with `--keep-temp`, read the trace, and fix either the prose or (if the prose is right) the case.
5. **Retention:** Every merge of a covered file needs a GREEN. Each new live-run finding becomes a grader with a RED proof.

### Secondary User Journeys

#### Review a PR that touches a gated file

1. The reviewer opens the PR. It names a covered file.
2. The PR body carries the verdict line, the cost and the results path from a full-suite run.
3. A PR without that evidence, or with only a `--case` run, does not merge.

#### Recover when the harness format changes

1. After a `claude` update, a trace grader goes red with no prose change.
2. Its canary is red too, which says the trace frame it reads has moved, not that the model deviated.
3. The maintainer reads a kept trace and updates the grader. The prose stays as it is.

## Feature Requirements

### Must Have Features

#### Feature 1: A Pass 1 pipeline case

- **User Story:** As the maintainer, I want one case that runs `/inbox` on a fresh inbox and grades every step of Pass 1, so that a change that breaks the order, the dispatch or the publishing goes red.
- **Acceptance Criteria:**
  - [ ] Given an instance with 3 fresh inbox notes, one of them in a subfolder, and a batch size of 2, When the case runs `/tomo:inbox`, Then the main session itself runs Pass 1: it dispatches no `suggestion-conductor` subagent.
  - [ ] Given the same run, When the analysts are dispatched, Then there are exactly 3 dispatches, every one names the Tomo `inbox-analyst` agent, and none runs as general-purpose.
  - [ ] Given the subfolder note, When it is dispatched, Then its full inbox path, folder included, is passed as both the item's path and its key.
  - [ ] Given the run, When the shared context is built, Then it is built exactly once, before the first dispatch, and the run id is drawn exactly once.
  - [ ] Given the run, When the analysts have finished, Then the reducer runs before the renderer, and both run after the last dispatch.
  - [ ] Given the run, When the suggestions are published, Then both artefacts (the note and its JSON) are written through the publishing script, and nothing is written to the vault by passing content through the model.
  - [ ] Given a successful vault write, When the run continues, Then sources are marked captured exactly once, after both writes.
  - [ ] Given the whole run, When any value is read from a file, Then no inline `python3 -c` is used.
  - [ ] Given the run, When it reports, Then the reply begins with the Pass 1 completion line naming 3 analysed items and the suggestions note, and it carries the leak guard that every case carries.
  - [ ] Given the reducer reports no duplicate proposals, When the run reports, Then the "already existed" line is absent.

#### Feature 2: A Pass 1 relay case

- **User Story:** As the maintainer, I want a case in which the scripts warn and the reducer converts a duplicate proposal, so that a change that swallows what the user must be told goes red.
- **Acceptance Criteria:**
  - [ ] Given the shared-context build prints a `WARN:` line, When the run continues, Then that line appears verbatim in the user-facing reply.
  - [ ] Given the same `WARN:` line, When the run dispatches, Then the line is shown to the user before the first dispatch, not only in the final report: a `cat tomo-tmp/setup-warnings.txt` tool call whose result carries the line runs before the first `Agent` call. (Changed 2026-10-31, owner decision: a tool result counts as shown, because Claude Code displays Bash output. Before, it was read as an assistant text message, which 4 of 4 paid runs never wrote.)
  - [ ] Given the reducer reports one converted duplicate proposal, When the run reports, Then the reply carries the line saying 1 proposed MOC already existed and is offered as an unticked link.
  - [ ] Given the run, When it reports, Then it still carries the Pass 1 completion line and the leak guard.

#### Feature 3: Stubs that let a case reach the end of Pass 1

- **User Story:** As the maintainer, I want the stand-ins for the analyst and the scripts to leave plausible results behind, so that the conductor runs to the end instead of stopping on inconsistent input.
- **Acceptance Criteria:**
  - [ ] Given the stand-in analyst runs for an item, When it finishes, Then a result for that item exists where the pipeline expects it, and the stand-in costs no Kado access.
  - [ ] Given the stand-in reducer and renderer, When they run, Then their outputs are consistent with the counts they print (3 sections, the proposed MOC count) and are large enough to pass the conductor's own sanity check.
  - [ ] Given a stub is called in a way that no Pass 1 step calls it, When the case runs, Then the stub fails loudly instead of returning plausible output.
  - [ ] Given any Pass 1 case, When it runs, Then nothing outside its own temporary workspace is read or written: no instance, no `~/.tomo`, no vault, no Kado.

#### Feature 4: A "reply is only the report" grader for the Pass 2 conductor

- **User Story:** As the maintainer, I want the gate to fail when the synthesis conductor wraps its report in prose of its own, so that the 1-in-6 deviation from #205 can no longer pass unnoticed.
- **Acceptance Criteria:**
  - [ ] Given a Pass 2 case, When the conductor returns, Then a grader checks the conductor's own return, not the main session's relay, and passes only if that return consists of report lines alone.
  - [ ] Given the conductor writes a status sentence before its report, When the grader runs, Then it is red.
  - [ ] Given the trace frame the grader reads is missing or appears more than once, When the case is graded, Then a canary grader is red, so that a harness format change cannot read as a pass.
  - [ ] Given each Pass 2 case, When its report has a case-specific shape (for example a coverage-audit mismatch that stops the run), Then that case's grader accepts exactly that shape.

#### Feature 5: Every new grader is proven able to go red

- **User Story:** As the maintainer, I want each new gate grader to have been red at least once under a named change, so that a green gate means something.
- **Acceptance Criteria:**
  - [ ] Given each new non-control grader, When the suite runs with its named mutation (or against a named older revision), Then that grader is red in 3 of 3 runs.
  - [ ] Given a "never" grader that the model refuses to break on request, When it is RED-proven, Then the proof uses a neutral prose change that makes the forbidden step plausible.
  - [ ] Given a grader that only confirms a precondition, When it is listed, Then it is marked as a control and is not required to have a mutation.
  - [ ] Given the RED proofs, When they are recorded, Then each one names its mutation, its grader, the 3 verdicts and the results path.

#### Feature 6: The gate covers the Pass 1 files

- **User Story:** As the reviewer, I want the merge rule and the coverage table to name the Pass 1 files, so that a PR touching them must carry a full-suite GREEN.
- **Acceptance Criteria:**
  - [ ] Given the coverage table in `evals/README.md`, When it is read, Then it lists `suggestion-conductor.md` and `suggest-handling` with the cases that cover them, and the docs test fails if a case or a path is missing.
  - [ ] Given the root `CLAUDE.md` gate rule, When it is read, Then it names the Pass 1 files as gated.
  - [ ] Given the merge candidate of this spec, When the full suite runs 3 times, Then all 3 runs are GREEN, with the median cost and the maximum duration recorded.
  - [ ] Given the full suite, When it runs at its default cap, Then it finishes under the $5 cap.

### Should Have Features

#### Feature 7: The known limits are written down

- **User Story:** As the maintainer, I want the gate's documentation to say what the Pass 1 cases cannot see, so that I don't read GREEN as more than it is.
- **Acceptance Criteria:**
  - [ ] Given `evals/README.md`, When it is read, Then it names the limits found in the spike:
    - analysts run in the background, so one case produces several result frames;
    - the trace format the report-only grader depends on, and the `claude` version it was validated on;
    - the analyst's own behaviour is not covered.

### Could Have Features

- A third Pass 1 case for the Force Atomic path (`force-atomic-handling`: the real path of a subfolder note in fan-resolve). It would cost about $0.75 more per gate run.
- A case checking that tag-handler groups are built before the reduce step.

### Won't Have (This Phase)

- **Gating `force-atomic-handling`.** It has no case in this phase, so the gate rule does not list it. Its fix history (1 commit) is the smallest of the three.
- **The analyst's own behaviour.** `inbox-analyst` reads the vault directly through Kado MCP. It gets its own spec; this one stands it in with a stub agent.
- **Kado mocks of any kind.**
- **Live runs, or any run against an instance or a vault.**
- **A change to the gate's runner, verdict, exit codes or cost cap**, beyond adding cases and documentation.

## Detailed Feature Specifications

### Feature: A Pass 1 pipeline case (Feature 1)

**Description:** The case starts `/tomo:inbox` in a throwaway workspace. In that workspace, triage yields a routing plan with action `suggest` and 3 fresh notes. Every script Pass 1 calls is a stand-in with the real output format, and the analyst is a stand-in agent. The main session reads the conductor's text, loads `suggest-handling` and runs the pipeline. Graders read the trace and the final reply.

**User Flow:**
1. The maintainer runs the full suite.
2. The system stages the workspace and starts `/tomo:inbox`.
3. The model runs triage, reads the conductor, loads the skill, builds the shared context, dispatches the analysts batch by batch, reduces, renders, publishes, marks captured and reports.
4. The system grades the trace and the reply, and prints one verdict for the whole suite.

**Business Rules:**
- Rule 1: Pass 1 is impersonated. A case in which the conductor runs as a subagent is RED, because that is not how `/inbox` runs Pass 1.
- Rule 2: The dispatch count equals the number of fresh notes. Batches respect the batch size, and the next batch starts only after the previous one has finished.
- Rule 3: The path the analyst receives is the note's real inbox path, never one rebuilt from its stem.
- Rule 4: The shared context is built once per run, before any dispatch.
- Rule 5: Both published artefacts go through the publishing script, under the same timestamped name.
- Rule 6: Marking sources captured follows a successful write. When the write fails, the sources stay uncaptured.
- Rule 7: Report graders anchor at the start of a line, so that a sentence quoting the report line cannot satisfy them.

**Edge Cases:**
- The conductor detects inconsistent stand-in output and stops early → the stubs are wrong, not the prose: the case must not be made green by loosening graders (Feature 3).
- The analysts run in the background, so the main session ends its turn while it waits → the case is graded on the last reply, and dispatch graders read the dispatch, not the completed result.
- A grader passes only because the model quotes the expected line inside an apology → anchored patterns (Rule 7).

## Success Metrics

### Key Performance Indicators

- **Adoption:** Every PR that touches a gated Pass 1 file after the merge carries a full-suite GREEN (verdict line, cost, results path).
- **Engagement:** Each live-run finding on Pass 1 after the merge becomes a grader with a RED proof, or a written reason why it cannot be graded.
- **Quality:**
  - every new non-control grader is red in 3/3 under its mutation;
  - the merge candidate is GREEN in 3/3 full-suite runs;
  - no grader is a false positive on the recorded traces.
- **Business Impact:**
  - a full gate run stays at or below about $3.10 median and under the $5 cap;
  - the Pass 1 cases add at most about $1.60 median per gate run;
  - a full gate run takes at most 6 minutes (changed from 4 minutes on 2026-10-31 by owner decision: measured 298–344 s).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Full-suite run | verdict, cost, duration, results path, `claude` version | Merge evidence; cost and duration KPIs |
| Grader result per run | case, grader, pass/fail, explanation | Locate a regression; false-positive check |
| RED proof | mutation or revision, grader, 3 verdicts, results path | Quality KPI: every grader can fail |
| Canary result | case, frame count | Distinguish a harness format change from a model deviation |

---

## Constraints and Assumptions

### Constraints

- **Cost.** The owner accepted about +$1.50 per gate run for 2 Pass 1 cases, measured in the spike at $0.21 per Pass 1 run. The $5 cap stays.
- **Where the harness runs.** `claude plugin eval` cannot run in Claude Code's sandbox, so the owner runs every paid run from a terminal.
- **No paid run while files change.** The gate's tree-change guard makes such a run NOT GRADED.
- **Runtime prose stays imperative.** Explanations go to `docs/tomo/` first, and every edit to a managed file bumps its version.
- **No contact with live data.** Cases must never touch tomo-instance, tomo-privat, `~/.tomo` or a vault.
- **No Kado mocks.**

### Assumptions

- The impersonation path (`inbox.md` → main session reads the conductor → `Skill` loads `suggest-handling`) behaves in the gate as it did in the spike on `claude` 2.1.314.
- The Tomo `inbox-analyst` name resolves to the plugin's stand-in agent in every case, as it did in the spike.
- Subagent tool calls stay visible in the trace. This is observed, not documented, as for spec 041.
- One Pass 1 run that reaches the end costs at most about $0.27.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A `claude` update moves the trace frame a grader reads (it already happened once, between 2.1.310 and 2.1.314) | High | Medium | A canary per trace grader; the dependency is named in the Known limits |
| The stand-ins drift from the real scripts' output, and the gate grades a pipeline that no longer exists | High | Medium | Stand-in formats are copied from the real scripts; a stub fails loudly on an unknown call (Feature 3) |
| A grader is red on the current prose (a real regression) | Medium | Medium | Treat it as a finding: fix the prose in this spec and record it. Never loosen the grader to get green |
| Background dispatch makes runs flaky (a case ends before the last notification) | Medium | Low | 3 runs per case, which the merge rule already requires; record any NOT GRADED |
| Pass 1 cost rises beyond the measurement | Low | Low | The cost KPI is recorded on every merge-candidate run; the cap catches the outlier |

## Open Questions

- [x] How many Pass 1 cases? 2. Owner decision, 2026-10-30.
- [x] Does the conductor need a real analyst? No: a stand-in agent. Owner decision.
- [x] Which trace frame does the report-only grader read? The hand-back frame, plus a canary. Spike Q5.
- [ ] Does the relay case need its own workspace, or can it reuse the pipeline case's with different stand-in outputs? This is an SDD question; it does not change any criterion.

---

## Supporting Research

### Competitive Analysis

Not applicable: this is internal test infrastructure. The comparable is spec 041's gate for Pass 2, which this spec extends. The method is the same (stubbed scripts, trace graders, mutation-proven RED); only the subject changes.

### User Research

- **Live-run audits 2026-09-12 to 2026-09-14** (the fix commits cited in the Problem Statement). Every Pass 1 defect was found by auditing each tool call in a transcript. Comparing artefacts would not have found them.
- **Research for this spec**, 3 agents (Decisions Log, 2026-10-30):
  - the Pass 1 conductor is impersonated;
  - 7 scripts need stand-ins;
  - the analyst cannot be stood in by a script stub;
  - a report-only grader is feasible on the trace.
- **The spike** (`spike/write-up.md`, $0.296) confirmed or corrected each of these points:
  - impersonation and skill loading work;
  - the analyst stand-in resolves;
  - analysts run in the background;
  - stand-ins that are too thin make the conductor stop early;
  - a report grader can be fooled by a quoted line;
  - the report-only grader must read the hand-back frame on 2.1.314.

### Market Data

Measured costs:

| Run | Cost |
|---|---|
| Pass 1 run (sonnet main session, haiku stand-in analysts) | $0.21 |
| Pass 2 run in the spike | $0.089 |
| Existing gate, 5 cases × 3 runs | about $1.00 (`evals/README.md`) |
| Projected full gate with 2 Pass 1 cases | about $2.50–3.10 |
