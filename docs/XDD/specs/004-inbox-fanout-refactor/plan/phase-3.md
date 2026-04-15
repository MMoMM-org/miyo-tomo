# Phase 3 — Fan-Out + Reducer (atomic-note only)

## Goal

Prove the full map-reduce loop end-to-end for the simplest action kind
(`create_atomic_note`). Orchestrator dispatches subagents in batches of 3-5,
each writes a result, reducer assembles the Suggestions document, orchestrator
writes it via `kado-write`.

## Acceptance Gate (from SDD)

- [ ] `WHILE Phase B is running, THE SYSTEM SHALL maintain between 1 and 5
  concurrent subagents`
- [ ] `WHEN a subagent starts processing item <stem>, THE SYSTEM SHALL
  transition the state-file entry to running`
- [ ] `WHEN a subagent completes successfully, THE SYSTEM SHALL produce
  tomo-tmp/items/<stem>.result.json and append a status: "done" line`
- [ ] `IF a subagent fails, THEN THE SYSTEM SHALL mark the item failed with
  an error object AND continue processing remaining items`
- [ ] `WHEN all Phase-B items have reached a terminal status, THE SYSTEM SHALL
  invoke the reducer to produce tomo-tmp/suggestions-doc.json`
- [ ] `WHEN the reducer detects 3+ items with the same normalised
  proposed_moc_topic, THE SYSTEM SHALL emit a corresponding Proposed MOC
  section`
- [ ] `WHEN the final Suggestions document is written to the vault, THE
  SYSTEM SHALL use mcp__kado__kado-write`
- [ ] `IF tomo-tmp/inbox-state.jsonl exists on /inbox entry, THEN THE
  SYSTEM SHALL prompt the user via AskUserQuestion`

## Tasks

### 3.1 Retrofit `inbox-analyst` for JSONL output

Changes to `tomo/.claude/agents/inbox-analyst.md`:
- Tighten tools list to `Read, Bash, mcp__kado__kado-read, Write` (drop
  `Glob, Grep, mcp__kado__kado-search` — not needed per-item)
- Change Step 11 (Produce Output): instead of narrative output, MUST write
  a single file `tomo-tmp/items/<stem>.result.json` matching the schema,
  then return a one-line confirmation
- Add Step 12 — Emit state update: MUST also call `state-update.py
  --stem <stem> --status done` (or `failed` with error) before returning
- For Phase 3, only `create_atomic_note` actions are emitted. The `actions[]`
  array always has exactly one element.
- Keep classification logic (Steps 4-9) — only the IO contract changes

### 3.2 `suggestions-reducer.py`

Inputs:
- `--state tomo-tmp/inbox-state.jsonl`
- `--items-dir tomo-tmp/items/`
- `--output tomo-tmp/suggestions-doc.json`

Logic:
1. Read state file, collect stems with `status: done`
2. For each stem, load `items/<stem>.result.json`, validate against schema
3. Build `sections[]`: one per item, with `actions[]` sub-array containing
   rendered markdown per action
4. Cluster `proposed_moc_topic` across items (per SDD algorithm)
5. Collect `failed` items into `needs_attention[]`
6. Validate output against `tomo/schemas/suggestions-doc.schema.json`
7. Write to `--output`

Rendering rules (replicated from retired `suggestion-builder`'s Step 4):
- `### SNN — <suggested_title>` heading
- `**Source:** [[<stem>]]` wikilink
- `**New tags to add:** <comma-separated>` (omit if empty)
- `**Link to MOC:**` with pre-checked boxes
- `**Why:**` 1-2 sentences
- `**Alternatives:**` list
- `**Decision:**` tri-state checkboxes (Approve / Skip / Delete source)
- When multiple actions per section: each action gets its own sub-block with
  its own Decision checkboxes

### 3.3 `inbox-orchestrator` agent body

Fill in `tomo/.claude/agents/inbox-orchestrator.md`:

- Phase 1: Detect resume state, run Phase A scripts
- Phase 2: Loop over pending items, dispatch subagents in batches of
  (default 5 from vault-config, min 3)
  - Uses Agent tool with `subagent_type: "inbox-analyst"` and a prompt that
    points to the item's stem + path, the shared-ctx location
  - After each batch, poll state-file; don't dispatch a new batch until prior
    batch items all terminal
- Phase 3: Invoke `suggestions-reducer.py`
- Phase 4: Render the final markdown from `suggestions-doc.json`, write via
  `kado-write` to `<inbox>/YYYY-MM-DD_HHMM_suggestions.md`
- Include all the Classification Guard, anti-parrot, wikilink rules (moved
  from `suggestion-builder.md`)

### 3.4 Wire `/inbox` command

Update `tomo/.claude/commands/inbox.md` Pass-1 flow to dispatch to
`inbox-orchestrator` instead of `inbox-analyst → suggestion-builder`. Pass-2
and cleanup unchanged.

### 3.5 Heredoc + Echo Discipline Tests

Add a pre-merge check (can live in `scripts/test-phase3.sh`):
- `grep -rn "cat <<" tomo/.claude/agents/inbox-orchestrator.md` → must return 0 matches
- `grep -rn "; echo \"EXIT:" tomo/.claude/agents/inbox-orchestrator.md` → 0 matches

### 3.6 Integration Test

Write `scripts/test-phase3.sh` (or extend existing):
- Against a fixture vault: 5 items in inbox, run orchestrator prompt end-to-end
  in a non-interactive mode (requires mock AskUserQuestion — use a flag like
  `--assume-fresh` for tests)
- Verify: 5 `result.json` files, valid state file with all `done`,
  one Suggestions doc written to the inbox

## Tests

- [ ] `bash scripts/test-phase3.sh` exits 0
- [ ] Running `/inbox` against the live instance with 3+ inbox items produces
  a valid Suggestions doc in the vault
- [ ] Peak subagent context < 80K tokens (log inspection)
- [ ] Introducing a deliberately broken inbox item (malformed YAML) does NOT
  abort the run; the item is marked `failed` and the doc still ships

## Hand-off to Phase 4

Phase 4 adds `update_daily` to `actions[]`. Phase 3 must handle `actions[]`
as a list, not a single object, even though in Phase 3 it always has length 1.
