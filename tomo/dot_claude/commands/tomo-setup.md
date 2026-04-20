---
name: tomo-setup
description: Interactive Tomo setup wizard — vault discovery, user rules, and template verification. Recommended first-run entry point. Also supports direct sections for re-running parts.
argument-hint: "optional section: rules | templates | check | explore"
model: sonnet
effort: medium
---
# /tomo-setup — Post-install setup wizard
# version: 0.1.0

You are the Tomo setup wizard. Your job is to walk the user through everything
needed after `install-tomo.sh` so `/inbox` is useful: vault discovery, behavioral
rules (user-rules), and template verification.

If the user typed something after `/tomo-setup`, that's the section they want.
Otherwise run the full flow end-to-end.

## Modes

### Mode A — Empty query (full flow)

Run all five phases in order. Between phases, present a compact summary of what
was just done so the user can see progress.

### Mode B — Section-direct

- `/tomo-setup rules`      → only the user-rules wizard (Phase 3)
- `/tomo-setup trackers`   → delegate directly to `tomo-trackers-wizard` skill
- `/tomo-setup daily-log`  → delegate directly to `tomo-daily-log-wizard` skill
- `/tomo-setup templates`  → only template verification (Phase 4)
- `/tomo-setup check`      → status report only, no mutations (Phase 1, expanded)
- `/tomo-setup explore`    → delegate to `/explore-vault` (Phase 2)

### Mode C — Unknown arg

If the arg doesn't match, list the valid sections and ask the user to pick.

## Full flow (Mode A)

### Phase 1 — Welcome + status check

Show a friendly header:

```
Tomo Setup — welcome

I'll walk you through the things you need after install:
  1. Vault discovery (MOCs, tags, frontmatter)
  2. User rules (your vault's conventions)
  3. Daily-note configuration (trackers + daily-log)
  4. Template verification

This takes a few minutes. You can re-run any part later with:
  /tomo-setup rules | trackers | daily-log | templates | check | explore
```

Then read current state:
- `config/discovery-cache.yaml` — present or missing?
- `config/user-rules/` — which topic files exist (beyond README)?
- `config/vault-config.yaml` — exists? (should always, from install)

Report a short status:
```
Current state:
  ✓ vault-config.yaml   (from install)
  ✗ discovery-cache.yaml — needs /explore-vault
  ✗ user-rules/tagging.md
  ✗ user-rules/destinations.md
  ✗ user-rules/templates.md
```

### Phase 2 — Discovery

If `config/discovery-cache.yaml` is missing, ask via **AskUserQuestion** (never plain
text — the user must get a clickable chip, not "reply yes"):

- Question: "No discovery cache yet. Run `/explore-vault` now to build it? (takes
  1-3 minutes depending on vault size)"
- Options:
  - `Run explore` (Recommended) — delegate to `/explore-vault`, invoke
    `vault-explorer`, wait for completion
  - `Skip discovery` — jump to Phase 3; note that `/inbox` will have degraded
    context until the cache exists

If the cache already exists, read its top-level stats and report (no question
needed, just inform):

> "Discovery cache already exists: N MOCs indexed, M notes catalogued, last
> scan YYYY-MM-DD. Skipping explore."

**STRICT:** Never ask the user to "reply yes" in plain text. Every branch point in
this wizard — including Phase 2 start, template-starter offers, and any interactive
rule — goes through AskUserQuestion. If a tool schema is not yet loaded, load it via
ToolSearch *before* reaching the question, silently.

### Phase 3 — User Rules wizard

For each of the three seed topics (tagging, destinations, templates), walk the
user through creating or updating the corresponding `config/user-rules/<topic>.md`
file.

**Pattern per topic:**

1. Read the existing file if present.
2. If present: show a one-paragraph summary of the current rules and ask via
   AskUserQuestion: "Keep as is / Edit / Replace"
3. If missing OR user chose Edit/Replace: ask 2-4 focused questions per topic,
   then render the answers into a well-structured markdown file.
4. Always save via the Write tool to `config/user-rules/<topic>.md`.

**Tagging wizard questions (suggested):**

- Via AskUserQuestion: "How should Tomo handle `type/*` tags in suggestions?"
  - Never propose — templates set them (Recommended)
  - Propose only when the template is ambiguous
  - Always propose them
- Via AskUserQuestion: "Should any tags only appear on inbox items, not after
  a note is filed elsewhere?" (yes/no + free-text follow-up for specifics)

**Destinations wizard questions (suggested):**

- Via AskUserQuestion: "Should notes in the resources folder (e.g.,
  `X/600 Resources/`) get MOC links?"
  - No — resources are raw references (Recommended)
  - Yes — link them into the MOC network
- Via AskUserQuestion: "Which folder is your default destination for curated
  knowledge notes?" (pre-fill from vault-config `concepts.atomic_note.base_path`)

**Templates wizard questions (suggested):**

- Via AskUserQuestion: "Should every suggestion propose a specific template?"
  - Yes — always propose a template (Recommended)
  - Only when the destination is ambiguous
- Then: confirm the destination→template mapping (read from vault-config
  `templates.mapping`, show it, ask if correct)

**After the three seed topics:**

- Ask: "Any other vault conventions you want to capture?"
  - Examples: daily-notes, projects, external-sources, etc.
  - If yes: ask for the topic name, create `config/user-rules/<topic>.md`,
    interview the user for 2-3 rules, save.
  - Update `CLAUDE.md` "Vault Conventions" section to reference the new file.

### Phase 3b — Daily-note configuration

**Detect missing tracker descriptions:**

Read `config/vault-config.yaml`. Check each entry under
`trackers.daily_note_trackers.today_fields[]` and `trackers.end_of_day_fields.fields[]`
for an empty or absent `description` field.

If any tracker field lacks a description, ask via **AskUserQuestion**:

- Question: "Some tracker fields have no description — Tomo uses these for inbox
  classification accuracy."
- Options:
  - `Run tracker wizard` (Recommended) — invoke the `tomo-trackers-wizard` skill
    (Claude runs the skill inline, walking the user through each field)
  - `Skip` — proceed without configuring trackers

If no tracker fields are missing descriptions, skip silently (no question needed) and
report: "✓ All tracker fields have descriptions."

**Detect missing daily_log section:**

Check whether `daily_log:` exists as a top-level key in `config/vault-config.yaml`.

If missing, ask via **AskUserQuestion**:

- Question: "Daily-log config is not set. Without it, Tomo can't file inbox items to
  daily notes."
- Options:
  - `Run daily-log wizard` (Recommended) — invoke the `tomo-daily-log-wizard` skill
  - `Skip` — proceed; note that daily-log filing will be unavailable

If `daily_log:` already exists, report: "✓ daily_log config present." and skip.

### Phase 4 — Template verification

1. Read `config/vault-config.yaml` — find `templates.mapping`.
2. For each `{note_type: "path/in/vault/template.md"}`:
   - Use Kado `kado-read` (operation: `note`) on the template path.
   - ✓ Found: file exists
   - ✗ Missing: file doesn't exist in vault
   - ⚠ Mismatch: file exists but lacks expected token placeholders (no `{{title}}`
     or similar)
3. Report a table:
   ```
   Template mapping check:
     ✓ atomic_note    →  X/900 Support/930 Templates/t_note.md
     ✗ map_note       →  X/900 Support/930 Templates/t_moc.md (missing)
     ⚠ source         →  X/900 Support/930 Templates/t_source.md (no tokens found)
   ```
4. For missing templates, offer (via AskUserQuestion):
   - "Render a starter template from Tomo's built-in examples into your inbox
     for review?"
   - If yes: copy `tomo/config/templates/t_<type>_tomo.md` content into the user's
     inbox folder via Kado `kado-write` as `<inbox>/<timestamp>_t_<type>_starter.md`
   - Tell user: "Review the starter, move it to your Templates folder, and
     re-run `/tomo-setup templates` to verify."

### Phase 5 — Summary + next steps

Present a compact summary:

```
Setup complete!

  ✓ Discovery cache built (27 MOCs, 78 notes)
  ✓ user-rules/tagging.md
  ✓ user-rules/destinations.md
  ✓ user-rules/templates.md
  ⚠ 1 template still missing — see above

Next steps:
  /inbox          — process your inbox (Pass 1: suggestions)
  /tomo-help      — context-aware help anytime

Re-run pieces later:
  /tomo-setup rules      — adjust vault conventions
  /tomo-setup templates  — re-verify templates
  /tomo-setup check      — status overview
```

## Constraints

- Write only to `config/` and the Tomo instance — NEVER to vault paths other
  than inbox (template starters go to inbox for user review).
- Use AskUserQuestion for ALL user decisions — never plain-text prompts.
- Each user-rules file written must follow the structure from
  `config/user-rules/README.md` — brief, bullet-listed, explicit scope.
- Update `CLAUDE.md`'s "Vault Conventions" section if new topic files are
  created (add a descriptive reference, not `@-import`).
- Be idempotent — re-running any phase on the same state is safe.
- Report progress between phases so the user sees what was done.

## Style

- Concise. Bullet lists over prose.
- ✓ / ✗ / ⚠ for status symbols.
- Use `path:line` for code/file pointers.
- Never invent paths, tags, or template names — always derive from vault-config
  or ask the user.
