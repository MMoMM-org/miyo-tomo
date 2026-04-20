---
title: "Phase 3: voice-transcriber agent (standalone)"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: voice-transcriber agent (standalone)

## Phase Context

**Dependencies**: Phase 2 (CLI must work). Phase 1 not strictly required if
testing in dev with manually-prepared model dir.

**Key files**:
- `tomo/dot_claude/agents/voice-transcriber.md` (new)
- Reference: existing agents `inbox-orchestrator.md`, `inbox-analyst.md`
  for frontmatter format and constraints style

**Out of scope this phase**: orchestrator integration. The agent runs
standalone via direct invocation; we wire it into Phase 0 of inbox-orchestrator
in Phase 4.

---

## Tasks

- [ ] **T3.1 Agent frontmatter and persona** `[activity: agent-design]`

  1. Prime: Read `tomo/dot_claude/agents/inbox-orchestrator.md` frontmatter
     and "Constraints" sections to match the in-house style. Note required
     fields: `name`, `description`, `model`, `tools`, `permissionMode`,
     optionally `skills`. Note version-comment convention.
  2. Implement: Create `tomo/dot_claude/agents/voice-transcriber.md` with:
     - `name: voice-transcriber`
     - `description: Transcribes audio files in the inbox via local faster-whisper. Discovers audio, checks for existing transcripts, invokes the CLI script, writes <basename>.md via kado-write. Skips silently if voice feature is disabled.`
     - `model: sonnet` (lightweight orchestration, no deep reasoning)
     - `tools: Read, Bash, mcp__kado__kado-search, mcp__kado__kado-read, mcp__kado__kado-write`
     - `permissionMode: acceptEdits`
     - `# version: 0.1.0` header
  3. Validate: Frontmatter parses (no YAML errors). Tools list matches actual usage.

- [ ] **T3.2 Workflow: discover + skip-or-transcribe loop** `[activity: agent-design]`

  1. Prime: Re-read solution.md § "Agent: voice-transcriber" for the exact
     responsibility list. Re-read inbox-orchestrator's "Constraints (strict)"
     block for guardrails to inherit (one Bash call, no inline python3 -c,
     no chained && or ;).
  2. Implement: Document the workflow in the agent body:
     - Step 1: Read `tomo-install.json` via `Read` tool. Parse `voice.enabled`.
       If false → return JSON summary `{"transcribed": 0, "skipped": 0, "errors": [], "reason": "disabled"}`.
     - Step 2: `kado-search` inbox for audio extensions (use `byPattern` or
       `listDir` per Kado API; verify exact param shape against existing usage in inbox-orchestrator).
     - Step 3: For each audio file:
       a. `kado-read` `<basename>.md`. If exists → skip, increment `skipped` counter.
       b. Otherwise: ONE Bash call: `python3 scripts/voice-transcribe.py "<path>"`.
       c. Capture stdout. On exit 0 → kado-write `<basename>.md` with stdout content.
       d. On non-zero exit → kado-write `<basename>.transcribe-error.md` with stderr content
          (also as plain text, not frontmatter).
     - Step 4: Return JSON summary for the orchestrator log.
  3. Validate: Workflow respects all "Constraints (strict)" rules.
     No Bash chaining. No heredocs. No inline Python.

- [ ] **T3.3 Error handling specifics** `[activity: agent-design]`

  1. Prime: Phase 2 CLI exit codes (0 success, 2 audio-not-found, 3 model-not-found, 4 transcription-error).
  2. Implement: Map exit codes to user-visible behaviour in the agent body:
     - Exit 3 (model missing): one-time warning to summary, abort entire
       voice phase (don't try other audios), return summary with error.
     - Exit 2/4: per-file error marker, continue to next audio.
     - Other exit codes: same as 4.
  3. Validate: Error path documented; user always sees what failed and where.

- [ ] **T3.4 Anti-parrot + format guardrails** `[activity: agent-design]`

  1. Prime: Memory `feedback_example_bleed_through.md` — examples in the
     agent body must use angle-bracket placeholders, not real-looking IDs.
  2. Implement: All examples in agent body use placeholders like
     `<basename>`, `<inbox_path>`, `<exit_code>`. Add a STRICT block:
     "NEVER write transcription content yourself — always pipe stdout from
     the CLI. NEVER skip the kado-read existence check."
  3. Validate: No example uses a real-looking concrete filename that
     could bleed into actual output.

- [ ] **T3.5 Sync agent into instance for testing** `[activity: tooling]`

  1. Prime: The agent file lives in `tomo/dot_claude/agents/`. To test in
     a running Tomo session, it must be copied to the instance via
     `update-tomo.sh` (or manually `cp` for dev).
  2. Implement: No code change — just procedural. After saving the agent
     file: run `bash scripts/update-tomo.sh` (or copy manually for dev
     iteration) and restart Claude in the instance to pick it up.
  3. Validate: Agent appears in the instance's Agent tool list.

- [ ] **T3.6 Standalone agent test** `[activity: validate]`

  Manual test in a Tomo session:
  - Pre-condition: voice enabled in `tomo-install.json`, tiny model installed,
    test vault has one short audio in inbox, no sibling .md.
  - Invoke the agent directly via `Agent` tool with subagent_type
    `voice-transcriber` and a prompt naming the inbox path.
  - Verify:
    - Sibling `.md` is created in the inbox via kado-write.
    - Markdown content matches PRD § F3 shape.
    - Re-invoking on the same inbox produces summary `{transcribed: 0, skipped: 1, errors: []}`
      and does NOT call the CLI a second time.
  - Disable voice in `tomo-install.json`, re-invoke. Summary returns
    `{reason: "disabled"}`, no Bash calls made.

- [ ] **T3.7 Phase Validation** `[activity: validate]`

  - Agent transcribes new audio files correctly.
  - Idempotent: pre-existing transcripts skipped without re-invoking the CLI.
  - Disabled state: returns immediately, zero side effects.
  - Errors surface as `.transcribe-error.md` files; agent does NOT abort the
    whole batch on per-file errors (except missing model).
