---
title: "Runtime prose gets a gate"
status: complete
version: "1.1"
---

# Product Requirements Document

> **Scope note.** Issue #174 proposed `claude plugin eval` as a test for the part
> of Tomo that pytest cannot reach: the agent, skill and command files an LLM
> reads at runtime. Two spikes (2026-10-24) settled whether it can work at all —
> an eval run reaches a plugin subagent and sees the commands that subagent runs,
> and stubbed-script cases go red on the commit before the `4350ddd` fix and
> green on `main`. The owner then decided that the plugin manifest is generated
> at eval time, so Tomo's runtime tree stays what it is. This spec turns the
> spike into a permanent, repeatable gate: one runner, a small suite of cases
> against the synthesis conductor, and a rule for when the suite must run.

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

## Output Schema

### PRD Status Report

| Field | Value |
|-------|-------|
| specId | 041-plugin-eval-gate-for-runtime-prose |
| title | Runtime prose gets a gate |
| status | `COMPLETE` |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 35 |
| openQuestions | 0 — a red `main` is fixed within this spec (owner, 2026-10-25) |

### SectionStatus

| Section | Status | Detail |
|---------|--------|--------|
| Product Overview | `COMPLETE` | |
| User Personas | `COMPLETE` | Two; one is a machine |
| User Journey Maps | `COMPLETE` | One primary, three secondary |
| Feature Requirements | `COMPLETE` | 7 Must, 1 Should, 1 Could |
| Detailed Feature Specifications | `COMPLETE` | F2 (the verdict) |
| Success Metrics | `COMPLETE` | |
| Constraints and Assumptions | `COMPLETE` | |
| Risks and Mitigations | `COMPLETE` | |
| Open Questions | `COMPLETE` | One, resolved |
| Supporting Research | `COMPLETE` | Two spikes (#174) + three research agents, 2026-10-25 |

---

## Product Overview

### Vision

A change to the instructions Tomo's agents follow is checked against what the
agent actually does before it merges — the same way a change to a script is
checked by its tests.

### Problem Statement

Tomo's behaviour is split across two layers. The scripts under `tomo/scripts/`
are covered by a test suite of more than 4,000 tests. The instructions the LLM
reads at runtime — 7 agents, 24 skill files and 7 commands under
`tomo/dot_claude/`, 18 of them carrying `STRICT` rules — are covered by none.
Whether an agent runs its steps in the documented order, obeys a `STRICT`
stop, or passes a notice to the user unchanged can only be seen by running
`/inbox` against a real vault and reading the output.

The evidence that this layer regresses, and that the regressions are found late:

- **`4350ddd` (2026-09-18).** The synthesis conductor ran the coverage audit
  *after* it had uploaded the rendered instructions and flipped the document's
  state. Its `STRICT` stop on an audit mismatch therefore protected only the
  *next* document, never the one that failed. Found in a live run.
- **`30a2305a` / `e4cd1b30` (2026-09-18, 2026-10-13).** The notice that a
  delete was withheld did not reach the user, then reached them reworded with
  its remedy dropped. The owner reads the shell report, not the suggestions
  document. The `STRICT` rule that fixed it records the failure in one line:
  "the model reworded the relay lines into its own bullets and dropped their
  remedy." Found in live runs.
- **`836602c` (2026-09-18).** An internal run marker sat in the file the
  conductor relays, and would have reached the user's chat. Found in review.
- **`docs/XDD/backlog.md:1007-1022`.** A data-quality guard rests on "an LLM
  following one line of its agent definition", which "has failed before".
- **The conductor's `STRICT` stop under a genuine mismatch had never been
  observed** before the #174 spike observed it on 2026-10-24.

Consequence of not solving it: every edit to runtime prose ships on the
author's reading of it. A regression is found by the owner during a real
`/inbox` run — after it has written to the vault inbox, flipped document
state, or hidden a notice the owner needed.

### Value Proposition

- **A regression in the covered behaviour turns a command red before merge,**
  instead of surfacing in a live run.
- **A `STRICT` rule becomes a checked claim.** Today a `STRICT` block records
  that the model once deviated; after this spec, for the covered rules, a run
  shows whether it still does.
- **Cheap and repeatable.** The spike measured about $0.10 per case per run;
  the suite runs without Docker, without Kado and without a vault.

The alternatives weighed: the status quo (live runs only); structural pytest
tests that read the prose (they exist — `test_synthesis_conductor_step_order.py`
pins the step *text*, not what the model does); and running the full pipeline
against a mocked Kado (rejected — it tests script logic pytest already covers,
at higher cost and with less determinism).

## User Personas

### Primary Persona: The maintainer, changing runtime prose

- **Demographics:** Develops Tomo on the host, usually with a Claude Code
  session doing the edits; reads diffs and test output fluently; pays for
  every eval run personally; not running CI.
- **Goals:** Edit an agent, skill or command file and know before merging
  whether the behaviours that matter still hold. Spend little money and little
  attention doing so.
- **Pain Points:** The only check today is a live `/inbox` run, which needs the
  Docker instance, a synced instance, Kado and a test vault prepared to the
  right state. A green pytest run says nothing about the prose. Regressions
  found live are found after they have acted on the vault.

### Secondary Personas

#### The coding session (a Claude Code session working in this repo)

- **Demographics:** An LLM session editing files under `tomo/dot_claude/` on
  the maintainer's behalf; follows the repo's `CLAUDE.md` rules and memory;
  can run shell commands; cannot judge on its own whether its prose edit
  changed runtime behaviour.
- **Goals:** Know when an edit obliges it to run the suite, run it with one
  command, and report the result in a form the maintainer can trust.
- **Pain Points:** No rule tells it today that prose edits need a behavioural
  check; nothing tells it which files are covered; a self-reported "I checked"
  is not evidence.

The vault owner who runs `/inbox` benefits from this spec but never uses it, so
they are not a persona here.

## User Journey Maps

### Primary User Journey: Changing a covered runtime file

1. **Awareness:** The maintainer (or the coding session) edits
   `synthesis-conductor.md`. The coverage list names that file as covered by
   the suite, and the repo rule says covered files need a green suite before
   merge.
2. **Consideration:** The alternative is a live `/inbox` run. The suite is
   cheaper, needs no instance or vault, and checks the behaviours a live run
   might not exercise (a mismatch, a withheld delete).
3. **Adoption:** One command, no arguments needed.
4. **Usage:** The command assembles the plugin, runs every case three times,
   and prints one verdict line plus the cost. On red it names the failing case
   and grader and where the full report is.
5. **Retention:** A red result points at the exact behaviour that broke; the
   PR records the verdict, so the next reader sees the check happened.

### Secondary User Journeys

#### Investigating a red result

The maintainer opens the report for the run, sees which grader failed in which
of the three runs, and decides: the edit broke the behaviour (fix the prose),
or the prose binds unreliably (one run in three deviates — strengthen the
prose, since an observed deviation is exactly what justifies a `STRICT` rule).
A red is never resolved by lowering the threshold for one run.

#### Adding a case for a new behaviour

The maintainer wants a new behaviour covered. They add a case, show each of
its gate graders red against a named mutation of the prose, record the
mutation and the red result, add the covered file to the coverage list, and
only then count the case as part of the gate.

#### A run that cannot complete

The cost cap is reached, the API is rate-limited, or the Claude Code version is
too old. The command ends non-green with a reason that says which of these
happened. The maintainer does not mistake it for a pass and does not need to
read the report to know it was not one.

## Feature Requirements

### Must Have Features

#### Feature 1: One command runs the suite safely

- **User Story:** As the maintainer, I want one command that runs the whole
  eval suite against the current runtime prose, so that checking a prose edit
  costs no setup and cannot damage anything.
- **Acceptance Criteria:**
  - [ ] Given a clean checkout, When the maintainer runs the eval command with no arguments, Then every case in the suite runs against the agent, skill and command files currently in the working tree
  - [ ] Given the command has run, When the working tree, the runtime source tree, any Tomo instance and `~/.tomo` are compared with their state before the run, Then none of them has changed
  - [ ] Given the command has run, When the maintainer looks for the results, Then they are in a timestamped directory under a gitignored location, and the command printed that path
  - [ ] Given `install-tomo.sh` or `update-tomo.sh` runs after the suite exists, When it copies the runtime tree into an instance, Then no file of the eval suite reaches the instance
  - [ ] Given the installed Claude Code is older than the version plugin evals require, When the command runs, Then it stops before any paid run and names the required version
  - [ ] Given the maintainer asks for help, When they run the command with `--help`, Then it describes what it runs, what it costs roughly, where results go and what each exit status means

#### Feature 2: A verdict that means what it says

- **User Story:** As the maintainer, I want the command's result to be green only when every case held in every run, so that a green result is something I can merge on.
- **Acceptance Criteria:**
  - [ ] Given every grader of every case passed in all three runs, When the suite finishes, Then the command exits successfully and prints a green verdict with the total cost
  - [ ] Given one grader failed in one run of one case, When the suite finishes, Then the command exits non-successfully and names the case and the grader that failed
  - [ ] Given the suite would exceed the cost cap, When the cap is reached, Then no further run starts, and the command exits non-successfully, reporting a partial run that is not a pass
  - [ ] Given the maintainer raises the cost cap for one invocation, When the suite runs, Then the raised cap applies to that invocation only
  - [ ] Given a run ends on an API error or a rate limit, When the suite finishes, Then the command exits non-successfully and says the run could not be graded, distinct from a grader failure
  - [ ] Given the suite runs, When the main session's model is chosen, Then it is the same pinned model on every run, and each subagent runs on the model its own definition names, as in production

#### Feature 3: Case — the coverage audit gates delivery

- **User Story:** As the maintainer, I want a case that fails if the synthesis conductor delivers anything before its coverage audit has run, so that the `4350ddd` defect cannot return.
- **Acceptance Criteria:**
  - [ ] Given an approved document whose coverage audit passes, When the conductor processes it, Then the audit runs before the rendered instructions are uploaded
  - [ ] Given the same run, When the conductor processes it, Then the audit runs before the document's state is flipped
  - [ ] Given the same run, When the conductor finishes, Then its report carries the audit's result line

#### Feature 4: Case — a coverage mismatch stops the conductor

- **User Story:** As the maintainer, I want a case that fails if the conductor delivers anything after a failed coverage audit, so that the `STRICT` stop is checked rather than assumed.
- **Acceptance Criteria:**
  - [ ] Given an approved document whose coverage audit reports a mismatch, When the conductor processes it, Then no rendered instructions are uploaded
  - [ ] Given the same run, When the conductor processes it, Then the document's state is not flipped
  - [ ] Given the same run, When the conductor finishes, Then the audit's mismatch output reaches the final message unchanged
  - [ ] Given the same run, When the conductor stops, Then it has not created or edited any script, schema or configuration file

#### Feature 5: Case — withheld notices reach the user unchanged

- **User Story:** As the vault owner's proxy (the maintainer), I want a case that fails if a withheld-delete or withheld-attachment notice is missing from the final message or altered, so that the owner, who reads the shell and not the suggestions document, always learns what was held back and what to do about it.
- **Acceptance Criteria:**
  - [ ] Given a run in which one delete was withheld, When the conductor finishes, Then the notice line appears in the final message character for character, including its remedy
  - [ ] Given a run in which two deletes were withheld, When the conductor finishes, Then both notice lines appear, each character for character, and neither is merged, counted or put in a table
  - [ ] Given a run in which an attachment was left in the inbox, When the conductor finishes, Then its notice line appears in the final message character for character
  - [ ] Given a run with both a withheld delete and a withheld attachment, When the conductor finishes, Then the delete notices come before the attachment notices, and both are the last lines of the report
  - [ ] Given a run in which nothing was withheld, When the conductor finishes, Then the final message contains no withheld notice

#### Feature 6: Every case guards against internal leaks

- **User Story:** As the maintainer, I want every case to fail if internal identifiers reach the final message, so that the `836602c` defect class is checked on every run at no extra cost.
- **Acceptance Criteria:**
  - [ ] Given any case in the suite, When its run finishes, Then the final message contains no run id, no action id, no internal guard or function name, no name of an internal working file and no absolute path (v1.1, owner 2026-10-25: the SDD spike observed the conductor writing a run id, absolute paths and working-file names into its report)
  - [ ] Given a case is added to the suite, When it is reviewed, Then it carries the same leak guard, and a case without it is not part of the gate

#### Feature 7: The gate is documented and its graders are proven

- **User Story:** As the coding session, I want to know which runtime files the suite covers, when I must run it, and that every gate check in it has been seen failing, so that "the suite is green" is evidence and not a formality.
- **Acceptance Criteria:**
  - [ ] Given the suite, When anyone asks which runtime files it covers, Then one list in the suite names every covered file and the cases that cover it
  - [ ] Given a change to a covered file, When the coding session reads the repo's rules, Then a rule tells it to run the whole suite before merge and to record the verdict, the cost and the results path in the PR
  - [ ] Given a change only to files that are not covered, When the coding session reads the rule, Then the rule does not require a run
  - [ ] Given every gate grader in the suite, When the spec closes, Then each has been shown failing against a named mutation — the pre-fix commit where one exists, otherwise a deliberate change to the prose or the stub — and the mutation and its failing result are recorded in the close-out
  - [ ] Given a grader that only confirms a precondition (for example, that the audit ran at all), When the close-out lists the graders, Then it is marked as a control and exempt from the failing-proof requirement
  - [ ] Given the suite on the merge candidate (the branch head with this spec complete, clean tree), When it is run three consecutive times, Then all three runs are green

### Should Have Features

#### Feature 8: Run one case while investigating

- **User Story:** As the maintainer, I want to run a single named case while investigating a red result, so that I do not pay for the whole suite on every attempt.
- **Acceptance Criteria:**
  - [ ] Given a case name, When the maintainer runs the command for that case, Then only that case runs, and the verdict states that it is a partial suite that does not satisfy the merge rule
  - [ ] Given a case name that does not exist, When the command runs, Then it stops before any paid run and lists the existing cases

### Could Have Features

#### Feature 9: Compare two results

- **User Story:** As the maintainer, I want to compare two result directories, so that I can see which graders changed between a red and a green run.
- **Acceptance Criteria:**
  - [ ] Given two result directories, When the maintainer compares them, Then the output lists every case and grader whose outcome differs between them

### Won't Have (This Phase)

- **CI or a pre-push hook.** The repo has no CI; a hook would spend money and
  need network on every push. The gate is a documented manual run.
- **Running only the cases a diff touches.** The whole suite is cheap at this
  size; selection by diff waits until it is not.
- **A contract check between the stubs and the real scripts.** The cases test
  the prose against stub output; that a stub's output still matches the real
  script's is left to review, and to the scripts' own tests.
- **A case at the `/inbox` command level** (dispatch plus pass-through of the
  report). Parked; the conductor is the highest-value target.
- **Cases for the other 17 runtime files with `STRICT` rules.** Each is a later
  addition through the "adding a case" journey.
- **A permanent plugin manifest in the repo.** Owner decision 2026-10-24.
- **The with/without-plugin comparison.** Without Tomo's prompts the pipeline
  does not run at all, so the comparison carries no information.
- **Kado mocks, real scripts, real vaults, LLM-judged graders.**

## Detailed Feature Specifications

### Feature: A verdict that means what it says (Feature 2)

**Description:** The value of the suite rests entirely on the meaning of its
verdict. LLM behaviour varies between runs, so one green run proves little;
the suite runs each case three times and is green only if every check held in
every run. Anything that prevented grading — cost cap, API error, rate limit,
a version too old — is reported as "not graded", never as green, and never
confused with a check that failed.

**User Flow:**
1. Maintainer runs the eval command.
2. System checks the Claude Code version and the suite's shape before spending anything.
3. System runs every case three times within the cost cap.
4. System prints one verdict: green, red (with the failing case and grader), or not graded (with the reason), plus the cost and the results path.
5. Maintainer records the verdict in the PR, or investigates.

**Business Rules:**
- Rule 1: Green means every grader of every case passed in every run. There is no partial credit.
- Rule 2: The number of runs per case is three. A case may not lower it.
- Rule 3: A run that could not be graded makes the whole suite "not graded", whatever the other runs did.
- Rule 4: The cost cap is $5 per invocation by default; the maintainer may raise it for one invocation; reaching it makes the result "not graded".
- Rule 5: The main session's model is pinned; subagents keep the model their own definition names.
- Rule 6: A single-case run (Feature 8) never produces a verdict that satisfies the merge rule.

**Edge Cases:**
- A case's scaffold fails before the agent runs → Expected: that run is not graded; the suite is "not graded" and names the case.
- Two cases' runs interleave in parallel → Expected: no case sees another case's files; verdicts are independent.
- The suite directory is empty or a case is malformed → Expected: stop before any paid run, name the problem.
- The runtime tree has uncommitted edits → Expected: the suite runs against them (that is the point), and the verdict line says the tree was dirty, so a PR record is not mistaken for a check of the committed state.

## Success Metrics

### Key Performance Indicators

- **Adoption:** every PR that changes a covered runtime file after this spec
  ships carries a recorded suite verdict — target 100%.
- **Engagement:** the suite is run at least once per covered-file change; a
  red result is followed by a prose fix or a recorded decision, never by a
  merge on red.
- **Quality:** 100% of gate graders proven failing against a named mutation
  (recorded at close-out); `main` green in three consecutive full-suite runs
  at close-out.
- **Business Impact:** cost per full-suite run ≤ $2 median, never above the
  $5 cap without an explicit raise; wall-clock ≤ 5 minutes. Zero regressions in
  the covered behaviours first found by a live `/inbox` run after adoption.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Suite run completed | verdict, cases passed / total, cost, duration, Claude Code version, whether the tree was dirty, results path | Cost and duration KPIs; the line recorded in the PR |
| Grader outcome per run | case, grader, run number, pass/fail | Investigating red results; flakiness of a rule over time |
| Run not graded | reason (cost cap, API error, rate limit, version, scaffold failure) | Distinguish "could not check" from "checked and failed" |
| PR touching a covered file | PR number, verdict line present yes/no | Adoption KPI |
| Grader proven failing | grader, mutation (commit or described change), failing result | Quality KPI; the close-out record |

Results are metadata only (scores, tool names, the fixed text the stubs
print) — no vault content ever enters a run, so none can enter a result.

---

## Constraints and Assumptions

### Constraints

- **Money:** every run is paid by the maintainer; the suite must stay cheap
  enough to run on every covered change.
- **No CI:** the gate is a command plus a rule; nothing enforces it
  mechanically.
- **Runtime tree untouched, with one exception:** no file the install or
  update scripts copy changes for the gate itself. The exception is the prose
  of a covered file when the suite shows `main` not green three runs out of
  three: that prose is fixed within this spec, with its version bumped and the
  test instance synced, and the observed deviation recorded (owner,
  2026-10-25).
- **Owner-authored cases only:** each case's setup step runs as the maintainer
  with their permissions, outside the agent's sandbox. A case from an
  untrusted source must never be run.
- **Claude Code version:** plugin evals require a minimum version (v2.1.269);
  the host runs 2.1.310.
- **Local-first:** the HTML report is kept local and never published.

### Assumptions

- Plugin-eval runs keep observing commands made inside a subagent. This is
  observed in the spike, not stated in the documentation.
- A haiku-run conductor can be made to follow its prose closely enough that
  `main` is green three times out of three; if it is not today, the prose is
  fixed within this spec.
- The stub outputs used by the cases match the real scripts' output closely
  enough that a prose behaviour proven against the stub holds against the
  script.
- The maintainer pays for runs through a claude.ai subscription or API key
  that has budget for a few dollars per covered change.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `main` is not green 3/3 because the conductor's prose binds unreliably | High | Medium | That is the gate working: the observed deviation is the evidence the `STRICT` lever requires. Fixed within this spec (version bump, instance sync), deviation recorded. |
| The gate is red often from model variance, and gets ignored | High | Medium | Threshold stays at "every run"; a flaky rule is fixed in the prose, not tolerated; the "investigating a red result" journey forbids lowering it per run. |
| A stub drifts from its real script, so a case passes against output production never produces | Medium | Medium | Stubs print the documented output lines; a stub-contract check is parked in Won't Have and recorded as the known gap. |
| A future Claude Code release changes eval behaviour (trace visibility, grader semantics) | Medium | Low | The version is in every verdict line; the version check stops a too-old binary; a red after an upgrade on an unchanged tree points at the tool. |
| Cost creeps as cases are added | Low | Medium | Cost cap per invocation; cost in every verdict line; selection by diff is the parked next step. |
| The rule is not followed because nothing enforces it | Medium | Medium | The rule lives where the coding session reads it on every session; the PR record makes skipping it visible. |
| A case's setup step does something harmful, since it runs with the maintainer's permissions | High | Low | Cases are owner-authored and live in the repo; the runner runs only the repo's own suite. |

## Open Questions

- [x] **If the suite on `main` is not green three runs out of three before any
  prose change,** this spec strengthens the covered prose until it is, bumps
  its version, syncs the test instance and records the observed deviation.
  Owner decision 2026-10-25 over recording it for a follow-up.

---

## Supporting Research

### Competitive Analysis

There is no competing product; the comparison is between ways of checking
Tomo's own prose:

- **Live `/inbox` runs** — real, but need Docker, a synced instance, Kado and a
  prepared vault; cannot cheaply produce a mismatch or a withheld delete on
  demand; act on the vault while checking.
- **Structural pytest over the prose** — `test_synthesis_conductor_step_order.py`
  pins the order of the step *headings*. It cannot see what the model does.
- **`claude plugin eval`** — runs the prose in an isolated headless session
  and grades which commands ran, in what order, and what the final message
  said. Mocks MCP servers, runs a setup step per case, caps cost, exits
  non-zero on failure.

### User Research

The owner is the only user. Their stated needs, from #174 and its comments:
the withheld notice must reach the shell because "ich lese das suggestion dank
hashi eigentlich garnicht mehr"; the gate must not touch what the install and
update scripts copy; the first cases are the conductor ordering, the `STRICT`
stop and the withheld-notice relay, at three runs per case.

Spike results (#174 comments, archived under `spike/`):

- **Subagent visibility (2.1.310):** a case reached a plugin subagent;
  commands run inside it were counted by the graders; a negative control
  turned them red. $0.13 and $0.09 per run.
- **Conductor cases:** with stubbed scripts, every ordering and stop check was
  green on `main` and red on `4350ddd^` (score 1.0 vs 0.33 / 0.6). The `STRICT`
  stop under a mismatch was observed for the first time. About $0.20 per arm
  for both cases at one run each, about 45 s.

### Market Data

Not applicable — internal tooling for a single-maintainer project. Relevant
data point: the plugin-eval documentation's own guidance (pin the model,
prefer pattern and tool-call checks over LLM-judged checks, skip the
with/without comparison for a pure gate) matches the choices above.
