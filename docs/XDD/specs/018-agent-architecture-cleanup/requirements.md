---
title: "XDD 018 — Inbox Routing Redesign & Agent Decomposition"
status: draft
version: "0.2"
---

# Product Requirements Document

## 1. Problem

The current `/inbox` flow has three structural problems that compound:

**P1 — MOC-proposals are invisible to /inbox auto-discovery.**
`tomo/dot_claude/commands/inbox.md:90-101` scans the inbox for
`*_suggestions.md` and reads the top of each match for `[x] Approved`.
The glob matches `*_suggestions.md` and `*_suggestions-fan.md` but
**not** `*_moc-proposal-*.md` (renamed by F-55 on 2026-05-22). Result:
an accepted MOC proposal never triggers Pass 2; the user must either
wait for a downstream suggestion to ride alongside it or manually
force `/inbox --pass2`. This is the proximate bug observed in the
2026-05-24 live-run (`8208c52f` session) — `/inbox` reported "nothing
to do" while an approved moc-proposal sat in the inbox.

**P2 — Triage burns LLM context that a script could compute.**
Today's Pass-2 trigger requires reading the full body of every
workflow doc (`~7-15k tokens` per primary suggestions doc, `~5k` per
fan companion) into LLM context just to check whether the user ticked
one checkbox at the top. Pass-2 measured at 65k peak context on a
2026-05-23 run, with the suggestion-doc bytes contributing >25k
without ever being *reasoned about* — they only need to be *scanned
for status*.

**P3 — Monolithic agents force full-prompt loading for partial work.**
`inbox-orchestrator.md` (735 lines) and `instruction-builder.md` (375
lines) each pack 3+ jobs:
- inbox-orchestrator: transcription dispatch (Phase 0a) + discovery
  (Phase A) + suggestions fan-out (Phase B) + render (Phase C) +
  output (Phase D)
- instruction-builder: instructions (Step 3) + FAN sub-flow (Step 2.5)
  + moc-proposal merge (Step 2)

Every dispatch loads the full agent spec even when only one job
applies. The size also impedes future enhancements — adding a new
post-Pass-2 step today means editing a file that already contains
multiple unrelated responsibilities.

## 2. Solution Overview

Re-architect `/inbox` around three layers:

**Layer A — Deterministic triage.** A new `tomo/scripts/inbox-triage.py`
script becomes the single source of truth for "what work exists, what
is approved, what is already covered". It listDirs the inbox, fetches
frontmatter buckets via `kado-search byFrontmatter`, reads full bodies
of workflow docs (suggestions / fan / moc-proposal / instructions),
scans for `[x] Approved` and `[x] Force Atomic Note` checkboxes,
parses instruction `sources` fields for coverage, and emits a
`routing-plan.json` plus a local file cache (`tomo-tmp/inbox-cache/`).
The script materialises the docs it has already read so downstream
conductors don't re-fetch via Kado.

**Layer B — Two thin conductor agents.** `/inbox` consumes
`routing-plan.json` and impersonates one of:

- `suggestion-conductor` — handles fresh inputs (audio, untagged .md,
  captured-state notes) → produces suggestions doc, optional
  suggestions-fan companion, optional moc-proposal docs. Dispatches
  `voice-transcriber` for audio transcription and a per-item leaf
  agent for content analysis and suggestion generation (see OQ11 for
  naming).
- `synthesis-conductor` — handles approved inputs (approved
  suggestions, approved suggestions-fan, accepted moc-proposals,
  force-atomic items needing FAN resolve) → produces instructions doc
  + atomic note files + new MOC files. Dispatches per-item leaf agent
  for FAN Step 2.5 resolution.

Each conductor stays small — orchestration logic only, no inline
domain knowledge. Conductors are impersonated from the main session
(per F-54 empirical rule: subagents cannot use the `Agent` tool).

**Layer C — Lazy-loaded skills.** Cross-cutting knowledge moves into
`tomo/skills/` as small Skill files that conductors load only on the
branches that need them:

- `tomo-lifecycle-states` — STATE_MACHINE, transition rules,
  state-promoter invocation patterns
- `kado-discovery-patterns` — listDir + byFrontmatter recipes
- `routing-plan-consumer` — how to read & branch on routing-plan.json
- `force-atomic-handling` — FAN sub-flow logic (today's Step 2.5)
- `suggestions-doc-format` — doc layout, approval-checkbox conventions
- `instructions-coverage` — sources field, coverage semantics

Skill set is the initial proposal; final granularity is OQ1.

**Layer D — Schema extension.** `instructions` doc-type
frontmatter gains a flat string array field:

```yaml
tomo:
  doc_type: instructions
  state: pending-apply
  sources:
    - "100 Inbox/2026-05-22_1432_suggestions.md"
    - "100 Inbox/2026-05-23_1328_suggestions-fan.md"
    - "100 Inbox/2026-05-22_1832_moc-proposal-board-games.md"
```

`inbox-triage.py` reads these to compute coverage:
`to_process = approved_set − union(all instructions.sources)`.

## 3. Personas

**P-1 — Marcus (operator).** Runs `/inbox` daily. Cares about: token
cost stays inside PRD §7 budgets, MOC-proposals get picked up
correctly, parallel-instructions warning fires only when it should,
state machine transitions happen reliably without manual cleanup.

**P-2 — Future contributor adding a new doc-type.** Wants to
extend Tomo with a new artifact (e.g. weekly-review summary). Cares
about: the new doc-type registers in one place (state machine, skill,
routing-plan bucket), conductors pick it up without spec edits, and
the skill-set documents how the new doc-type integrates.

## 4. Features (MoSCoW)

### Must

**F-1 — `inbox-triage.py` script (replaces `inbox-discovery.py`).**
Single deterministic entry point invoked once per `/inbox` run.
Outputs `tomo-tmp/routing-plan.json` + populates
`tomo-tmp/inbox-cache/` with full local copies of every workflow doc
it inspected. Scans approval checkboxes in body (no partial body
reads — Kado doesn't support them; we need full docs downstream
anyway). Detects force-atomic items per suggestion item. Computes
coverage from existing instructions `sources` field.

**F-2 — `/inbox` command becomes router.** Reads routing-plan,
impersonates one of `suggestion-conductor` / `synthesis-conductor` /
direct-transcribe / idle. Removes all in-command auto-discovery
markdown logic (currently 90-101). Keeps `--pass1` / `--pass2` /
`--recover` flags as overrides.

**F-3 — `suggestion-conductor` agent.** Replaces Phase 0a + Phase A +
Phase B + Phase C + Phase D of `inbox-orchestrator.md`.
Loads `routing-plan-consumer` + `suggestions-doc-format` skills always;
loads `force-atomic-handling` skill only when routing-plan has
force-atomic items.

**F-4 — `synthesis-conductor` agent.** Replaces all of
`instruction-builder.md`. Loads
`routing-plan-consumer` + `instructions-coverage` skills always;
loads `force-atomic-handling` skill only when FAN resolve items
exist.

**F-5 — moc-proposal Pass-2 trigger (Bug 1+2 fix).**
`inbox-triage.py` lists `*_moc-proposal-*.md`, reads approval
checkbox, classifies into `approved_moc_proposals` bucket.
synthesis-conductor consumes the bucket and merges proposed MOCs into
an existing instructions output or creates a new one if none exists.

**F-6 — Instructions coverage schema.**
`tomo/schemas/doc-frontmatter.schema.json` instructions doc-type gains
optional `sources: string[]` — a flat array of vault paths for all
input documents (suggestions, fan companions, moc-proposals).
`build_tomo_block()` accepts and emits this field.
`instruction-render.py` populates it at render time.

**F-7 — Skill scaffolding.** Initial six skills created in
`tomo/skills/<name>/SKILL.md` (granularity per OQ1). Skills define
how-to knowledge with concrete invocations, not prose rationale
(per `[[feedback_tell_how_not_what]]`).

**F-8 — Delete legacy agents.** `agents/inbox-orchestrator.md` and
`agents/instruction-builder.md` removed at end of implementation,
not retained as backups. Update-tomo.sh sync logic handles deletions.

### Should

**F-9 — F-50 (iii) skip-list integration.** When transcribed > 0 AND
manual `.md` notes also exist, triage emits a `skip_stems` array in
routing-plan; suggestion-conductor passes it to `inbox-discovery`
equivalent to filter newSources.

**F-10 — F-51 state-consistency check.** triage validates
`tomo-tmp/inbox-state.jsonl` against vault artefacts before allowing a
Resume; surfaces orphaned-state cases in `drift_indicators`.

**F-11 — F-56 phase C pipeline collapse.** A `suggestions-pipeline.py`
wrapper subsumes profile-lookup + reducer + render. suggestion-conductor
calls it as one Bash invocation.

**F-12 — F-32 model downgrade.** Conductors default `model: sonnet`
(no `inherit`, no `opus` without explicit rationale). Validate via
token-cost measurement after first live run.

**F-13 — Approval-state hint in routing-plan.** For docs with
`tomo.state=pending-approval` but no `[x] Approved` checkbox, surface
in `pending_approval[]` with friendly message — the user knows what
they have left to do.

### Could

**F-14 — F-53 parser default paths.** `suggestion-parser.py` defaults
`--file` and `--fan-resolve-file` to the local cache paths, so
synthesis-conductor calls it without explicit path args.

**F-15 — Triage timing metrics.** Triage writes timing breakdown
(listDir N ms, byFrontmatter N ms, body-reads N ms) to stderr for
performance regression tracking.

### Won't (this spec)

- F-30 (LLM-driven insertion-point resolution) — separate concern
- F-34 / F-35 (MSP B/C) — separate features
- F-41 (multi-topic detection) — separate
- F-58 (instruction cleanup) — handled by Hashi
- New Kado capabilities (e.g. partial body reads, frontmatter approval
  status) — out of scope, would shift the approval truth-source

## 5. Acceptance Criteria (Gherkin)

### Bug fixes (must pass)

**AC-1 — moc-proposal triggers Pass 2**
```
Given an inbox contains a *_moc-proposal-*.md with `- [x] Accept` ticked
And no approved suggestions or fan companion exist
When /inbox runs
Then synthesis-conductor is invoked
And the resulting instructions doc has sources listing the proposal's
vault path
```

**AC-2 — approved moc-proposal AND approved suggestions both trigger one Pass-2**
```
Given approved suggestions + approved moc-proposal both exist
When /inbox runs
Then a single synthesis-conductor invocation produces one instructions
doc covering both source documents
```

**AC-3 — unticked moc-proposal is invisible to routing**
```
Given a *_moc-proposal-*.md exists with `- [ ] Accept` (unticked)
And no other approved inputs exist
When /inbox runs
Then suggestion-conductor is invoked (not synthesis)
And the moc-proposal is surfaced in routing-plan.pending_approval[]
```

### Routing behaviour

**AC-4 — triage is the only routing computation**
```
Given /inbox is invoked
When the command runs
Then exactly one inbox-triage.py call occurs before any agent dispatch
And the command does no in-command markdown logic to derive action
```

**AC-5 — local cache prevents re-reads**
```
Given inbox-triage.py wrote tomo-tmp/inbox-cache/<doc>.md for an approved suggestion
When synthesis-conductor processes that document
Then synthesis-conductor reads from tomo-tmp/inbox-cache/, not via kado-read
```

**AC-6 — idle with explanation**
```
Given the inbox has captured-state docs but none meet routing criteria
(e.g. all are pending-approval, none ticked)
When /inbox runs
Then the command exits 0
And surfaces idle_reasons explaining what is waiting on user action
```

### Coverage

**AC-7 — covered docs are skipped on subsequent runs**
```
Given an instructions doc lists sources: ["X"] in frontmatter
And X.md still exists in the inbox with `- [x] Approved`
When /inbox runs again
Then routing-plan does not include X in approved_suggestions[] for processing
And the instructions doc is NOT regenerated for X
```

**AC-8 — partial coverage triggers partial processing**
```
Given approved suggestions A and B exist
And an instructions doc covers A only (sources: ["A"])
When /inbox runs
Then synthesis-conductor processes B (only)
```

### Agent decomposition

**AC-9 — conductors contain only orchestration content**
```
Given the redesigned suggestion-conductor.md and synthesis-conductor.md
When the files are inspected
Then each contains only orchestration logic (routing, dispatch, branching)
And domain knowledge, format specs, and reusable patterns live in skills
And no inline documentation or rationale is present (per AC-13)
```

**AC-10 — conductors do not contain force-atomic-handling prose**
```
Given the conductors are loaded
When force-atomic-handling logic is needed
Then it is loaded via the Skill mechanism, not inline
```

### Migration

**AC-11 — legacy agents are removed**
```
Given 018 implementation is complete
When `ls tomo/dot_claude/agents/` is run
Then inbox-orchestrator.md does NOT exist
And instruction-builder.md does NOT exist
```

**AC-12 — token cost regression bound**
```
Given the Privat-Test vault in its current state
When /inbox runs end-to-end
Then peak Pass-2 context is at most 40k tokens (target: 30k)
And the measurement is recorded via measure-inbox-pass-2-token-cost.py
```

### Runtime hygiene

**AC-13 — Runtime files contain only execution content**
```
Given suggestion-conductor.md, synthesis-conductor.md, the redesigned
/inbox command, and every new skill in tomo/dot_claude/skills/<name>/SKILL.md
When the files are inspected
Then they contain only imperatives, tool invocations, and branching logic
And they contain no descriptions of what called scripts do
   (the script's own --help is the source of truth)
And they contain no historical references — spec IDs (F-NN, ADR-N, XDD-NNN),
   dates (YYYY-MM-DD), or parenthetical citations ("per X", "see Y", "ref Z")
```

`Why:` in a STRICT block is added only when Claude Code needs the
reasoning to correctly execute the directive — not as a safeguard
against deletion or future editing. Safeguard rationale lives in
`docs/tomo/<mirrored-path>.md` (see AC-14).

**AC-14 — Rationale is preserved in docs/tomo before runtime strip**
```
Given any rationale-shaped content (script descriptions, design notes,
   platform-constraint explanations, decision history) exists in a
   pre-018 runtime file
When that content is removed during 018 implementation
Then the corresponding docs/tomo/dot_claude/<area>/<name>.md has been
   created OR updated to capture the WHY (decision context, alternatives
   considered, platform constraints) BEFORE the runtime strip is committed
And the docs/tomo entry uses WHY-shaped phrasing readable by a human
   maintainer ("we chose A over B because...", "subagents cannot use the
   Agent tool because Anthropic...")
```

## 6. Out of scope

- Changing the approval truth-source from body-checkbox to frontmatter
  (Obsidian UX anchor reasoning — body checkbox stays).
- Adding Kado partial-body reads (would shift the approval-scan, but
  costs a Kado release).
- Hashi-side changes (instructions consumption stays the same shape
  apart from the new optional `sources` field).
- Adding new doc-types (weekly-review, garden-audit etc.) — extension
  pattern is documented but specific types are separate specs.
- /moc-propose command rewrite — 013's moc-architect agent stays as-is;
  018 only adds the moc-proposal pickup path in /inbox.

## 7. Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| /inbox Pass-2 peak context | ≤ 30k tokens (was 65k) | `measure-inbox-pass-2-token-cost.py` |
| /inbox Pass-1 main-thread cost | ≤ 75% of pre-018 (F-32 lever) | `measure-inbox-phase-b-token-cost.py` |
| Conductor content fitness | Orchestration-only (no inline domain knowledge or docs) | Manual inspection per AC-9 |
| moc-proposal pickup rate | 100% (was 0%) | AC-1 / AC-2 manual run |
| Coverage false-negatives | 0 (no re-processing of covered docs) | AC-7 / AC-8 |

## 8. Open Questions before SDD

**OQ1 — Skill granularity.** Proposed six skills:
`tomo-lifecycle-states`, `kado-discovery-patterns`,
`routing-plan-consumer`, `force-atomic-handling`,
`suggestions-doc-format`, `instructions-coverage`. Are these the right
seams, or should some merge / split? **Lean: content-driven.** Use a
skill when the content is reusable across multiple agents/commands and
benefits from skill-loader capabilities; use an external readable file
when passive reference suffices. Final granularity decided in SDD
based on actual content.

**OQ2 — Conductor model.** Sonnet default for both? When (if ever)
does opus get justified? **Lean: sonnet default with opus override
mechanism.** Opus for tasks requiring deeper reasoning or larger
context windows (e.g. MOC path, investigational flows). Since the
Claude Code environment hardcodes sonnet, conductors need an explicit
override path to escalate to opus when needed.

**OQ3 — routing-plan.json schema strictness.** Strict typed schema
(`tomo/schemas/routing-plan.schema.json`) with `additionalProperties:
false` to prevent the F-47 force_atomic drift recurring, OR
lighter-weight document with just a top-level `action` enum?
**Decided: strict-typed** — we burned that lesson already (memory
`[[feedback_spec_schema_consumer_three_way_drift]]`).

**OQ4 — Drift / re-modified docs.** If a covered suggestions doc is
modified after instructions were rendered, today we'd silently miss
the change. **Decided: implement checksum-based drift detection.**
`inbox-triage.py` computes and stores checksums for processed docs;
on subsequent runs, compares current checksum against stored value.
Changed docs surface in `drift_indicators[]` with the checksum delta.
Gating behaviour (re-process vs. warn-only) deferred to SDD.

**OQ5 — Voice-transcriber hoist.** Today suggestion-conductor would
dispatch voice-transcriber. But voice-precheck.py already runs
deterministically; could inbox-triage.py call voice-transcriber
directly via Bash (no LLM dispatch), reducing one agent hop?
**Decided: keep dispatch in conductor** — voice-transcriber needs a
model call (Whisper or equivalent), so it stays an agent.

**OQ6 — FAN-resolve dispatch path.** synthesis-conductor dispatching
per-item leaf agent per force-atomic item — same impersonation rules as
today's instruction-builder Step 2.5? **Decided: yes, identical.**
The conductor is impersonated, dispatch from main session.

**OQ7 — F-43 (013) live validation gating.** Does 018 ship with 013's
operator-validation completed, or does 018 ship the routing fix and
013's validation is a separate user-led activity? **Decided:** 018's
AC-1/AC-2 include a manual operator-run that effectively validates
013's MOC pickup — 013 closes when 018 ships.

**OQ8 — Migration test order.** Big-bang means old agents are deleted.
Test sequence: (a) build new files, (b) write all unit/integration
tests against new files, (c) live-test on a copy of Privat-Test
vault, (d) delete old files in same PR? OR (a)(b)(d)(c) — delete then
live-test — to prove no fallback exists. **Decided: (a)(b)(c)(d)** —
keep the safety net during live test; deletion is the very last
commit on the branch.

**OQ9 — `inbox-discovery.py` fate.** Today's
`tomo/scripts/inbox-discovery.py` does Phase A byFrontmatter bucketing.
`inbox-triage.py` subsumes its function. Delete or keep as a thin
wrapper for backward compatibility (tomo-instance environments mid-
migration)? **Decided: delete** — big-bang implies no half-way.

**OQ10 — Skill format.** All skills use `<name>/SKILL.md` directory
format (per established convention). Content structure for each skill
(imperative how-to vs. reference lookup vs. coordination protocol)
determined in SDD based on how conductors consume them.
**Resolved: format is uniform; content structure follows usage.**

**OQ11 — Leaf agent naming.** Today's `inbox-analyst` does per-item
content analysis and suggestion generation. In the new architecture,
inbox-level triage moves to `inbox-triage.py`, so the leaf agent's
role is purely content analysis — not inbox analysis. Rename to
reflect its actual responsibility (e.g. `content-analyst`,
`suggestion-writer`)? **Lean: resolve in SDD** — functional
description takes precedence over name in PRD.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Conductor split misses a code path from today's monolith | Medium | High | Pilot-comparison: run both old and new on same vault state, diff outputs |
| Skill loading mechanism doesn't reduce token cost in practice | Medium | Medium | Measurement bound in AC-12; revisit skill granularity in SDD if not met |
| Big-bang migration leaves a broken state if AC-12 fails | Low | High | OQ8 lean (a)(b)(c)(d) keeps safety net |
| routing-plan.json schema drift bug recurs | Low | High | OQ3 = strict schema with `additionalProperties: false` |
| Body-read of all workflow docs at triage time is itself a token-cost regression on big inboxes | Low | Medium | Triage runs in Bash, not LLM — cost is wall-clock and Kado bytes, not LLM context. Measure |

## 10. Dependencies

- F-47 (017) shipped — STATE_MACHINE + doc-frontmatter.schema.json
  exist. ✅
- Kado 0.7.0+ — byFrontmatter, listDir filtering. ✅
- jsonschema in container — fixed per F-54 side-finding. ✅
- 013 (moc-creation-skill) code shipped — moc-architect.md, moc-exit
  discovery.py, /moc-propose command. ✅
- No new Kado releases required.
