---
title: "Phase 6: Agents, skill dispatch and STRICT rules"
status: pending
version: "1.1"
phase: 6
---

# Phase 6: Agents, skill dispatch and STRICT rules

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View; lines: 376, 384-386]` — the skill's and the three agents' responsibilities (SDD cites the write rule as SKILL.md:11 and the STRICT as :237; the current file has the Rules at 13-25 and the STRICT at 238)
- `[ref: SDD/Integration Points; lines: 681-689]` — prompt contents (paths, ids, dates, language only) and the one-line reply
- `[ref: SDD/Primary Flow; lines: 900-937]`; `[ref: SDD/Error Handling; lines: 955-962]` — rewrite once, `condense-incomplete`, `read-stale`, Pass 1 abort, self-started helpers, throttling
- `[ref: SDD/Architecture Decisions; ADR-7, ADR-8, ADR-10 (Pass 1 abort); lines: 1201-1210, 1217]`
- `[ref: SDD/Implementation Gotchas; lines: 1301, 1307]` — `review-digest.py` named in the skill's WHY doc; the one-line reply
- `tomo/dot_claude/commands/inbox.md:57-69` and `tomo/dot_claude/skills/suggest-handling/SKILL.md:86-112` (read only — eval-gated, never edited)

**Key Decisions**:
- Agents: `review-digester` (`haiku`), `review-carryover` (`sonnet`), `review-proposer` (`opus`); each `permissionMode: acceptEdits`, `tools: Read, Write`, no Bash, no MCP, no skills; each reads stage files only, writes exactly its `out` path, replies one line (ADR-7).
- The proposal rules of SKILL.md step 5 move into `review-proposer.md`: themes over all days, open judged against later weeks, one place per finding, carried items matched to the days and marked, child marks over the whole period, item text in the review language (ADR-8).
- Skill: `allowed-tools: Read, Write, Bash, Agent`; step 4 continue or `--fresh`; step 5 `plan` → one message per round → `check` → retry once → proposer → `write` → rewrite once. STRICT blocks only for observed deviations, each with a one-line `Why:` (one-message batch, `subagent_type`, `run_in_background: false`, never read stage files or grep day files in the main session and never start an agent `plan` did not list) (ADR-8).
- Pass 1 abort after step 4 runs `review-doc.py replace --stem <stem> --abort` and nothing else (ADR-10).
- `settings.json` is not changed (CON-6); T1.4 proved the writes.

**Dependencies**: Phase 5 (and T1.4's outcome). T6.1 → T6.2 → T6.3 → T6.4. T6.3 waits for T6.2: T6.2 owns `tests/test_047_agents.py` including the proposal pins moved out of the old skill tests, and T6.3 only removes those pins from the skill tests.

---

## Tasks

Puts the three agents in place and makes the skill drive them, with the main session never reading the period itself.

- [ ] **T6.1 WHY layer for the agents and the new step 4/5** `[activity: technical-writing]`

  1. Prime: `docs/tomo/dot_claude/skills/periodic-review.md`, `docs/tomo/dot_claude/agents/*.md` (existing mirror style), the current SKILL.md Rules (13-25, incl. line 21), step 4 (118-127), step 5 (129-165), STRICT (238); spec 046 close-out (grep fallback, four self-started helpers for $2.83) `[ref: SDD/ADR-7, ADR-8]` `[ref: SDD/Directory Map/Documentation; lines: 464-467]`
  2. Test: `test_review_why_docs.py` (extended in this task for agents) finds a mirror for each of the three agent files before they exist; the skill mirror names `review-digest.py`, `plan` and `check` (gotcha); every rationale now in SKILL.md step 5 that moves to the proposer has a home in `docs/tomo/dot_claude/agents/review-proposer.md` (checked by listing each moved rule against the doc in the commit message).
  3. Implement: `docs/tomo/dot_claude/agents/review-digester.md` (haiku, one unit, no judgement, the cap), `review-carryover.md` (sonnet, no setup marker, text as it stands now), `review-proposer.md` (opus rationale, whole-period rules, carried rules, the moved step-5 rationale); `docs/tomo/dot_claude/skills/periodic-review.md` (step 4/5 WHY, dispatch, each STRICT's failure mode, Pass 1 abort, continued read, the observed deviations).
  4. Validate: `test_review_why_docs.py` green; no runtime file changed yet.
  5. Success: every decision baked into the agents and the new steps is persisted before the runtime text `[ref: CLAUDE.md WHY-persistence rule; SDD/ADR-7, ADR-8]`

- [ ] **T6.2 The three review agents** `[activity: prompt-engineering]`

  1. Prime: T6.1 docs; `tomo/dot_claude/agents/inbox-analyst.md:1-12` (frontmatter); T4.1/T5.1 schemas; `review-digest.py plan` job fields; use `tcs-helper:agent-author` `[ref: SDD/ADR-7]` `[ref: SDD/Application Data Models; lines: 641-662]`
  2. Test: `tests/test_047_agents.py` — each file has `# version: 0.1.0`, the right `model`, `permissionMode: acceptEdits`, `test_tools_are_read_and_write_only` (no Bash, no `mcp__*`, no Agent, no skills; F7-AC5); each names its one output path from the prompt, the one-line reply format, and never Kado or the vault; the digester covers every day file and every growth file of its unit and the weekly note as `child_notes` source, writes the unit's created notes as `growth` candidates with their creation days as sources and the note paths in `notes`, stays under `cap_bytes`; the carryover takes open items, intentions/goals and themes from the user's text and Tomo blocks alike with no setup marker (F4-AC1), writes text in the review language; the proposer pins (one assertion per rule, phrased as an imperative, no examples that could bleed through): themes counted over all days of the period (F1-AC3), open judged against later weeks (F1-AC4), one item per finding across weeks with all sources (F1-AC5), each carryover id exactly once with its mark per F4-AC2 and F4-AC3 (a theme never done), placement into the best-fitting mapped section else the group of its mark (F4-AC4), carried again with the same mark and no age (F4-AC8), item text in the review language (F4-AC11), child marks over the whole period (F2-AC3), the "Vault growth" group built from the digests' growth candidates and `context.json`'s growth counts and MOC lists with the candidates' creation days as sources, never reading `manifest.json`, `carried: false` from `plan` means no item carries `carried`; each pin RED-proven by deleting its line; the step-5 proposal pins that today sit in `tests/test_review_skill*.py`, `tests/test_046_t4_4_skill_sections.py` and `tests/test_046_t4_5_skill_quarter.py` are re-created here against `review-proposer.md` (listed one to one in the commit message).
  3. Implement: `tomo/dot_claude/agents/review-digester.md`, `review-carryover.md`, `review-proposer.md` — imperatives only, no rationale (it lives in T6.1's docs).
  4. Validate: `test_047_agents.py` green; `update-tomo.sh` agent glob (`agents/*.md`, :374-377) covers them (read only); ruff clean.
  5. Success: three agents with the owner's models, no vault access, and the proposal rules over the whole period `[ref: PRD/F1-AC3, F1-AC4, F1-AC5, F4-AC1, F4-AC2, F4-AC3, F4-AC4, F4-AC8, F4-AC11, F7-AC5]`

- [ ] **T6.3 Skill step 4 and step 5: continue, dispatch, check, propose, abort** `[activity: prompt-engineering]`

  1. Prime: T6.1 docs; `tomo/dot_claude/skills/periodic-review/SKILL.md` (frontmatter 5; Rules 13-25 incl. the write rule and line 21 "Never quote `read*.json` …"; step 4 118-127; step 5 129-165 with `read_path` at 131 and `read.json` at 139, 141, 143 through 160; STRICT at 238); `tests/test_review_skill*.py`, `tests/test_046_t4_4_skill_sections.py`, `tests/test_046_t4_5_skill_quarter.py`, `tests/review_skill_helpers.py`; `review-read.py` / `review-digest.py` / `review-doc.py` outputs; use `tcs-helper:skill-author` `[ref: SDD/ADR-8, ADR-10]` `[ref: SDD/Error Handling; lines: 943-962]`
  2. Test: `tests/test_047_skill_contract.py` — `allowed-tools` adds `Agent`; the write rule and the STRICT name the agents' files as the only exceptions and the skill writes only `confirmed-<kind>.json`; step 4 passes `--fresh` on every Start-over route and on `read-stale`, and `test_continued_read_line` (one line with the read's time on `continued: true`; F6-AC4); step 5 order `plan` → one message per round with `subagent_type`, `run_in_background: false` and the exact prompt template (stem, unit, read_id, files, out, cap, language — no note text) → `check` → retry jobs in one message → `check` → proposer with `proposer.inputs` → `write` → on `proposals-invalid` one re-dispatch with the errors verbatim, a second shown and no document (F6-AC3); `condense-incomplete` reruns step 5 from `plan` once; `stopped nothing-condensed` stops naming every week (F6-AC8 wording); the four STRICT blocks with one-line `Why:`; the Pass 1 abort runs only `review-doc.py replace --stem <stem> --abort` (F6-AC6); the run report repeats the previous-note lines (F3-AC6) and names not-condensed weeks and a failed carry; `test_step4_5_ask_no_new_question` (no setup question for a previous kind, F3-AC8); line 21 no longer names `read*.json` and instead forbids quoting any stage file; no line of SKILL.md names `read_path`, `read.json` or `read*.json` (untruncated `rg` over the file); the old step-5 proposal-prose pins are removed from the skill tests (T6.2 already re-created them in `test_047_agents.py`); this task does not edit `tests/test_047_agents.py`.
  3. Implement: SKILL.md → 0.3.0 (a further bump if T2.4 already bumped it), imperatives only: Rules 13-25 (write rule naming the agents' files as the only exceptions, line 21 rewritten), step 4 118-127, step 5 129-165 (every `read_path` / `read.json` reference at 131-160 replaced by the `plan` / `check` / proposer flow), the STRICT at 238; `commands/review.md` only if its text names the old read files (version bump).
  4. Validate: skill tests green; full suite green; ruff clean; `settings.json` and every eval-gated file byte-identical.
  5. Success: the skill continues or reads anew, dispatches every job from the main session, and aborts Pass 1 cleanly `[ref: PRD/F6-AC3, F6-AC6]`

  - **Carry-over from the T2.4 review (2026-11-23):** SKILL.md's refused-problems list (~164) does not name `read-stale`; add it with the step 4/5 rewrite.

  - **Carry-over from the T4.3 review (2026-11-23):** `review-digest.py plan` resets every failed unit (and a whole-file failed carryover) to pending on each call, because it cannot tell a continued read from a repeat call; retries stay bounded only if the skill runs `plan` once per run, then `check` at most twice. Step 5 says so as an imperative (STRICT only if a live run shows a second `plan`), and the WHY doc says a unit that fails twice stays failed until the next session.

- [ ] **T6.4 Plugin eval case `review-no-stage-read`** `[activity: testing]`

  1. Prime: `evals/README.md` (adding a case, graders' limits), an existing case folder (`evals/pass1-suggest-pipeline/`), memory notes on plugin eval (sees subagent calls; no AskUserQuestion; traces and `input_match`) `[ref: SDD/Quality Requirements/Performance (hard); lines: 1234]` `[ref: SDD/Error Handling; lines: 961]`
  2. Test: graders — 0 Read/Grep/Bash calls on `tomo-tmp/review/<stem>/days|growth|children|previous|context*` in the main session; the proposer reads no `manifest.json`, `days/` or `growth/` file; every `Agent()` call has a `subagent_type` from `plan` and `run_in_background: false`; the digester and carryover calls of a round sit in one message; no agent outside `plan`'s list; each agent reply is one line. RED proofs by named mutations (a skill copy that reads one day file; one that dispatches the round in two messages); controls marked.
  3. Implement: the case under `evals/review-no-stage-read/` with a stubbed small stage; no change to `scripts/run-evals.sh` semantics or to gated files. The paid run happens only on the owner's go (T9.1); it is not a merge gate for these files.
  4. Validate: the case's offline/grader unit tests (as the README describes) green; ruff clean.
  5. Success: the main session's no-read rule and the batch dispatch are machine-checked `[ref: SDD/ADR-8; SDD/Quality Requirements]`

- [ ] **T6.5 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean. Trace F1-AC3, F1-AC4, F1-AC5, F4-AC1 … F4-AC4, F4-AC8, F4-AC11, F6-AC3, F6-AC6, F7-AC5 to node ids (model-behaviour parts marked for the T9.2 live-walk rows). Audit the three agents and the skill after the edits (`tcs-helper:agent-author` / `skill-author` audit): imperatives only, no rationale, no STRICT without an observed deviation. Git log: T6.1 docs before T6.2/T6.3. `settings.json` and every eval-gated file byte-identical.
