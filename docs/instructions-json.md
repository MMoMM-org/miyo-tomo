# instructions.json — Tomo Hashi Consumer Contract

**Audience:** Plugin authors building [Tomo Hashi](https://github.com/MMoMM-org)
(the Obsidian plugin that executes Tomo's Pass-2 instruction sets inside the
vault). This document is the authoritative consumer specification.

**Canonical schema:** [`tomo/schemas/instructions.schema.json`](../tomo/schemas/instructions.schema.json)
— JSON Schema Draft 2020-12, stricter than this prose (it has the final word
on required fields and enum values).

**Producer:** [`scripts/instruction-render.py`](../scripts/instruction-render.py)
inside this repo. Produced by the `instruction-builder` agent at the end of
Pass 2, written to the vault inbox via `kado-write operation="file"` (because
`operation="note"` only accepts `.md`).

**Companion human view:** the same instruction set is rendered as
`<date>_instructions.md` with per-action `- [ ] Applied` checkboxes. Tomo
Hashi should keep the checkbox states in sync with its execution state — it
is the user-visible contract for "what has been applied."

---

## Top-level structure

```json
{
  "schema_version": "1",
  "type": "tomo-instructions",
  "source_suggestions": "2026-04-21_0918_suggestions",
  "generated": "2026-04-21T11:13:18Z",
  "profile": "miyo",
  "tomo_version": "0.7.0",
  "action_count": 25,
  "actions": [ ... ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"1"` (const) | Bumps when the structure becomes incompatible. Reject with a clear error if you see a version you don't understand. |
| `type` | `"tomo-instructions"` (const) | Discriminator in case multiple JSON artefacts share the inbox folder. |
| `source_suggestions` | string \| null | Stem of the suggestions doc this set was derived from — traceability only. |
| `generated` | ISO-8601 UTC | Use this (not file mtime) when comparing action sets. |
| `profile` | string \| null | Active PKM profile (miyo / lyt / custom). Useful if your UI adapts to framework conventions. |
| `tomo_version` | string \| null | Tomo runtime version. Log it in case you need to debug a divergence. |
| `action_count` | integer | Length of `actions[]`. Mismatch → file corruption, abort. |
| `actions[]` | array | The executable payload. See below. |

---

## Action lifecycle

1. The user applies each action in the vault (manually, or via Tomo Hashi).
2. Tomo Hashi **must** treat the instruction set as a monotonic log — actions
   are applied or unapplied, never mutated in place. Don't rewrite the JSON.
3. The human-readable view (`*_instructions.md`) carries `- [ ] Applied`
   checkboxes per action. Tick them as you apply. Unticked checkboxes = not
   yet applied; the cleanup pass re-discovers partially-applied sets through
   these checkboxes.
4. `- [ ] Applied` at action index N corresponds to `actions[N-1]` in the
   JSON (IDs `I01`, `I02`, … align with the markdown's third-level headings).

---

## Execution order

The producer emits actions in dependency order. Tomo Hashi should apply
top-to-bottom by default — a cautious batched applier can re-order within
each block but MUST NOT move a `link_to_moc` before its `create_moc`.

```
1. create_moc        — new MOC files (must exist before link_to_moc hits them)
2. move_note         — atomic notes (move + rename)
3. link_to_moc       — add bullet lines into target MOCs
4. update_tracker    — daily note tracker fields
5. update_log_entry  — daily log prose lines
6. update_log_link   — daily log wikilink lines
7. delete_source     — remove leftover inbox items
8. skip              — informational only, no-op
```

Within each block, actions are ordered by assignment (monotonic `I01` … `INN`).

---

## Common invariants

- **All paths are vault-relative.** No leading slash, no URL encoding.
  (Example: `Atlas/202 Notes/Sapporo — Hauptstadt.md`.)
- **Wikilinks** in rendered content use **bare stems**: `[[Sapporo — Hauptstadt]]`
  — no folder prefix, no `.md` extension, Obsidian resolves by name.
- **Unicode** (emoji, umlauts, em-dashes) is preserved as-is in all strings.
  Don't normalise / re-encode filenames on write.
- **IDs** (`I01`, `I02`, …) are stable within a single instruction set but
  not across runs. Don't store them long-term.
- **`null` vs. missing** — the schema declares `null` where a field is
  defined but intentionally empty. Missing keys are never valid on required
  fields; treat that as a schema violation.

---

## Action kinds

Every action has `id` (`"I01"` …) and a `action` discriminator. Below: one
section per kind with fields, execution semantics, and idempotency.

### `create_moc` — create a new Map of Content

```json
{
  "id": "I01",
  "action": "create_moc",
  "source": "100 Inbox/2026-04-21_1113_brettspiele-moc.md",
  "destination": "Atlas/200 Maps/Brettspiele (MOC).md",
  "title": "Brettspiele (MOC)",
  "rendered_file": "2026-04-21_1113_brettspiele-moc.md",
  "parent_moc": "2700 - Art & Recreation",
  "template": "t_moc_tomo.md",
  "tags": ["type/others/moc", "topic/recreation/board-games"],
  "supporting_items": "S02, S06, S12"
}
```

| Field | Type | Notes |
|---|---|---|
| `source` | string | Current full path of the rendered MOC file in the inbox. This is the file to move. |
| `destination` | string | Target full path including filename (`.md`). Usually under `Atlas/200 Maps/`. |
| `title` | string | The MOC name (also the stem of `destination`). |
| `rendered_file` | string | Basename of `source` — redundant, for display. |
| `parent_moc` | string \| null | Up-link parent MOC. Emitted separately as a `link_to_moc` action; this field is metadata only. |
| `template` | string \| null | Template filename used at render time — traceability. |
| `tags` | string[] | Tags already applied to the rendered MOC body. |
| `supporting_items` | string \| null | Comma-separated suggestion IDs that justify the new MOC. The down-links from each supporting atomic note into this MOC are already emitted as `link_to_moc` actions elsewhere in the set — `supporting_items` is human context, not an executable pointer. |

**Execution algorithm:**

1. Verify `source` exists. If missing, the Pass-2 Kado write step may not have
   completed — surface the error; do not synthesize content.
2. Move + rename `source` → `destination`. Atomic if possible (FS-level rename
   within the vault).
3. (Obsidian) Ensure the new path is linked by index — Obsidian picks up file
   moves through its workspace watcher; no extra wiring needed.

**Idempotency:**

- If `destination` already exists and `source` does not: action was applied
  previously. Skip.
- If both `source` and `destination` exist: inconsistent state. Surface an
  error rather than overwriting.

---

### `move_note` — move + rename a rendered atomic note

```json
{
  "id": "I02",
  "action": "move_note",
  "source": "100 Inbox/2026-04-21_1113_asahikawa-zweitgroesste-stadt-hokkaidos.md",
  "destination": "Atlas/202 Notes/Asahikawa — zweitgrößte Stadt Hokkaidos.md",
  "title": "Asahikawa — zweitgrößte Stadt Hokkaidos",
  "rendered_file": "2026-04-21_1113_asahikawa-zweitgroesste-stadt-hokkaidos.md",
  "origin_inbox_item": "100 Inbox/Asahikawa.md",
  "parent_mocs": ["Japan (MOC)"],
  "tags": ["topic/japan/city", "topic/japan/hokkaido"]
}
```

| Field | Type | Notes |
|---|---|---|
| `source` | string | Current full path of the rendered atomic note in the inbox (what gets moved). |
| `destination` | string | Target full path including filename (`.md`). Usually under `Atlas/202 Notes/`. |
| `title` | string | Final note title — also the stem of `destination`. |
| `rendered_file` | string | Basename of `source`. |
| `origin_inbox_item` | string \| null | **Informational only.** Path of the original inbox item this note was derived from. Cleanup is handled by the separate `delete_source` action elsewhere in the set; do NOT delete this file as a side-effect of `move_note`. |
| `parent_mocs` | string[] | MOCs this note up-links to. Each is emitted as a separate `link_to_moc` action; these are metadata for display. |
| `tags` | string[] | Tags in the rendered note body — already present, not something to apply. |

**Execution algorithm:**

1. Verify `source` exists.
2. Move + rename `source` → `destination`.

**Idempotency:** same shape as `create_moc`.

**Templater coexistence:** rendered atomic notes may contain `<% ... %>`
Templater blocks that haven't yet resolved. Tomo's convention is that the
user (or Tomo Hashi) runs Obsidian's *Templater: Replace Templates in Active
File* after moving. If Tomo Hashi automates this, do it AFTER the move so
`tp.file.folder` etc. resolve to the correct location.

---

### `link_to_moc` — append a bullet line inside a MOC

```json
{
  "id": "I10",
  "action": "link_to_moc",
  "target_moc": "Japan (MOC)",
  "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
  "section_name": null,
  "line_to_add": "- [[Asahikawa — zweitgrößte Stadt Hokkaidos]]",
  "source_note_title": "Asahikawa — zweitgrößte Stadt Hokkaidos"
}
```

| Field | Type | Notes |
|---|---|---|
| `target_moc` | string | MOC stem (no path, no `.md`) — the name Obsidian resolves by. |
| `target_moc_path` | string \| null | Resolved vault-relative full path. See "Resolution rules" below. |
| `section_name` | string \| null | Hint for which section to write into. Usually null in current Pass-2 output; defer to the default "first editable callout" rule. |
| `line_to_add` | string | The exact bullet line to insert. Already formatted (`- [[stem]]`). |
| `source_note_title` | string \| null | Informational — which note's up-link this represents. |

**Resolution rules for `target_moc_path`:**

- Non-null: use it directly (faster, no search needed).
- Null: fall back to `target_moc` by name. Two legitimate reasons for null:
  1. The renderer couldn't find the MOC at Pass-2 time (Kado unreachable,
     no name match, or disambiguation needed).
  2. The target is itself being created by a `create_moc` in the same
     instruction set — the renderer attempts to synthesize the path from
     the sibling `create_moc.destination`, but this can fail if the sibling
     hasn't been located yet. Tomo Hashi can safely resolve the target at
     execute time.

**Execution algorithm:**

1. Open the target MOC file (using `target_moc_path` if set, else locate by
   name).
2. Find the insertion section (in priority order):
   a. If `section_name` is set and matches a heading or callout in the MOC,
      use that section.
   b. Otherwise, find the **first editable callout** in the MOC. Editable
      callouts are listed in `vault-config.yaml` under `callouts.editable`.
      Typical defaults: `connect`, `blocks`, `anchor`.
   c. If no editable callout exists, append to the end of the MOC body.
3. Insert `line_to_add` on a new line inside that section, preserving the
   `> ` line prefix if we're inside a callout.

**Idempotency:**

- If the target section already contains an exact match for `line_to_add`
  (byte-equal after trim), skip.
- Partial matches (e.g. the wikilink text is present but in a different
  bullet) are intentional duplicates — the user may have linked manually.
  Skip rather than deduplicate aggressively.

**Writing inside callouts:**

```markdown
> [!blocks]- Key Concepts
> - [[Asahikawa — zweitgrößte Stadt Hokkaidos]]     ← line_to_add, prefixed with "> "
> - [[previous existing line]]
```

Preserve the callout's fold state suffix (`[!name]-` = collapsed, `[!name]+`
= expanded). Don't change it on write.

---

### `update_tracker` — set a tracker field on a daily note

```json
{
  "id": "I19",
  "action": "update_tracker",
  "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
  "date": "2026-03-26",
  "field": "Sport",
  "value": "true",
  "syntax": "inline_field",
  "section": "Tracker",
  "source_stem": "Sport",
  "reason": "Went running"
}
```

| Field | Type | Notes |
|---|---|---|
| `daily_note_path` | string | Full vault-relative path. Create the daily note first if missing. |
| `date` | `YYYY-MM-DD` | Redundant with the filename; use for display/sanity checks. |
| `field` | string | Tracker field name (e.g. `Sport`, `WaterIntake`). |
| `value` | string \| number \| boolean | The value to set. String form is canonical for display; coerce as needed for your storage. |
| `syntax` | `inline_field` \| `callout_body` \| `checkbox` | How to write it. See below. |
| `section` | string \| null | Hint for which section the tracker belongs under. |
| `source_stem` | string \| null | Inbox item the tracker was inferred from — informational. |
| `reason` | string \| null | LLM's classification reason — informational. |

**Syntax semantics:**

- `inline_field` — Obsidian Dataview style: `field:: value` on its own line,
  inside the named `section`.
- `callout_body` — write inside a named tracker callout: a line with
  `field:: value` prefixed by `> `.
- `checkbox` — a markdown task: `- [ ] field` or `- [x] field` depending on
  whether `value` is truthy.

**Execution algorithm:**

1. Open `daily_note_path`. If missing: create it (template-driven if the
   profile defines a daily template, else a minimal stub).
2. Find the `section`. If missing, create it at a reasonable position (below
   frontmatter, above the body).
3. Write `field` according to `syntax`. If the field already has a value,
   replace it (trackers are scalar).

**Idempotency:** re-applying with the same value is a no-op. Re-applying
with a different value overwrites — the user is explicit about what they
want; don't second-guess.

---

### `update_log_entry` — add a prose line to the daily log

```json
{
  "id": "I20",
  "action": "update_log_entry",
  "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
  "date": "2026-03-26",
  "section": "Daily Log",
  "heading_level": 2,
  "position": "after_last_line",
  "time": null,
  "content": "Viel Sport gemacht.",
  "source_stem": "Sport",
  "reason": "Notable activity"
}
```

| Field | Type | Notes |
|---|---|---|
| `daily_note_path` | string | Full vault-relative path. |
| `date` | `YYYY-MM-DD` | For display/consistency. |
| `section` | string | Heading text (e.g. `Daily Log`) — without leading `#`. |
| `heading_level` | integer (1–6) | Depth of the section heading. Combine with `section` to form the full marker (`## Daily Log`). |
| `position` | `after_last_line` \| `before_first_line` \| `at_time` | Placement within the section. |
| `time` | `HH:MM` \| null | Required when `position == "at_time"`. |
| `content` | string | The prose line to insert. |
| `source_stem` | string \| null | Informational. |
| `reason` | string \| null | Informational. |

**Position semantics:**

- `after_last_line` — append to the end of the section (most common).
- `before_first_line` — prepend to the top of the section.
- `at_time` — insert in chronological order within the section, using `time`
  as the sort key. Other entries in the section are assumed to have
  leading `HH:MM` prefixes too; if not, fall back to `after_last_line`.

**Execution algorithm:**

1. Open `daily_note_path` (create if missing, same rules as `update_tracker`).
2. Find `section` at `heading_level`. Create it if missing.
3. Insert `content` according to `position`.

**Idempotency:** exact-content deduplication. If the section already
contains `content` on its own line, skip.

---

### `update_log_link` — add a wikilink line to the daily log

Same shape as `update_log_entry`, but the payload is a wikilink instead of
prose:

```json
{
  "id": "I21",
  "action": "update_log_link",
  "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
  "date": "2026-03-26",
  "section": "Daily Log",
  "heading_level": 2,
  "position": "after_last_line",
  "time": null,
  "target_stem": "Asahikawa — zweitgrößte Stadt Hokkaidos",
  "reason": "Cross-reference to related note"
}
```

| Field | Type | Notes |
|---|---|---|
| `target_stem` | string | Bare note stem to link to (no `.md`, no path). |

The line Tomo Hashi writes is `- [[<target_stem>]]` (optionally prefixed by
`HH:MM - ` when `position == "at_time"`). All other fields mirror
`update_log_entry` — same execution, same idempotency rules.

---

### `delete_source` — remove a source file from the inbox

```json
{
  "id": "I22",
  "action": "delete_source",
  "source_path": "100 Inbox/Sport.md",
  "reason": "Content fully captured in daily note."
}
```

| Field | Type | Notes |
|---|---|---|
| `source_path` | string | Full vault-relative path of the file to delete. |
| `reason` | string | Human-readable justification — surface in the UI when confirming. |

**Execution algorithm:**

- Move the file to Obsidian's trash (respects the user's trash-folder
  setting). **Do not hard-delete.**
- If the file is already gone: treat as a no-op (previous apply).

**Emitted in two cases:**

1. The user ticked `[ ] Delete source` on an atomic-note suggestion without
   accepting it — explicit intent.
2. Daily-only inference: the source item's content landed entirely in a
   daily note (tracker / log entry / log link) with no atomic note
   created. The renderer infers deletion from `source_stem` cross-checks
   between the suggestions doc's confirmed items and daily-update items.

The `reason` field distinguishes the two.

---

### `skip` — informational no-op

```json
{
  "id": "I25",
  "action": "skip",
  "source_path": "100 Inbox/Evergreen Notes.md",
  "reason": "Skipped by user (kept in inbox)."
}
```

| Field | Type | Notes |
|---|---|---|
| `source_path` | string \| null | Path of the source item the user chose to skip. |
| `reason` | string \| null | Human-readable. |

**Execution:** nothing. Tomo Hashi may still surface it in the UI as
"skipped" for transparency, but it's not an executable action.

---

## Worked example (abridged)

A Pass-2 run with 9 confirmed items (8 atomic + 1 new MOC), 2 daily updates,
2 skipped items produces 25 actions. The envelope looks like:

```json
{
  "schema_version": "1",
  "type": "tomo-instructions",
  "source_suggestions": "2026-04-21_0918_suggestions",
  "generated": "2026-04-21T11:13:18Z",
  "profile": "miyo",
  "tomo_version": "0.7.0",
  "action_count": 25,
  "actions": [
    { "id": "I01", "action": "create_moc",   "title": "Brettspiele (MOC)", ... },
    { "id": "I02", "action": "move_note",    "title": "Asahikawa — ...",    ... },
    { "id": "I03", "action": "move_note",    ... },
    ...
    { "id": "I09", "action": "move_note",    ... },
    { "id": "I10", "action": "link_to_moc",  "target_moc": "Japan (MOC)",   ... },
    { "id": "I11", "action": "link_to_moc",  "target_moc": "Brettspiele (MOC)", ... },
    ...
    { "id": "I19", "action": "update_tracker", ... },
    { "id": "I20", "action": "update_log_entry", ... },
    { "id": "I21", "action": "update_log_entry", ... },
    { "id": "I22", "action": "delete_source",  ... },
    { "id": "I23", "action": "delete_source",  ... },
    { "id": "I24", "action": "delete_source",  ... },
    { "id": "I25", "action": "skip",            ... }
  ]
}
```

---

## Recommended Tomo Hashi implementation shape

A minimal plugin maps 1:1 onto the action kinds:

```ts
// Pseudocode — adapt to your plugin's Obsidian API surface
interface ExecResult { applied: boolean; skipped?: string; error?: Error }

async function apply(action: Action, vault: Vault): Promise<ExecResult> {
  switch (action.action) {
    case "create_moc":
    case "move_note":       return moveFile(action.source, action.destination, vault)
    case "link_to_moc":     return appendLineToSection(action, vault)
    case "update_tracker":  return writeTrackerField(action, vault)
    case "update_log_entry":
    case "update_log_link": return insertIntoDailyLog(action, vault)
    case "delete_source":   return trashFile(action.source_path, vault)
    case "skip":            return { applied: false, skipped: "no-op" }
  }
}
```

**Run loop:**

1. Read `instructions.json` + `instructions.md` from the inbox.
2. For each action in JSON order, check the corresponding `- [ ] Applied`
   checkbox in the MD. If ticked, skip.
3. Apply. On success, tick the checkbox (write back to the MD). On failure,
   leave unchecked and report.
4. When every action has been ticked, the set is complete — `/inbox`
   cleanup will archive it on the next Tomo run.

---

## Validating a JSON payload before execution

Use the bundled dry-run:

```bash
python3 scripts/instructions-dryrun.py <path/to/instructions.json>
```

Exit 0 = every action has its required fields and a known `action` type.
Exit 1 = schema violation (surfaces which action and which field). Use this
in CI if you generate JSONs during plugin tests.

A thorough consumer can also run the producer's own unit suite to verify a
round-trip:

```bash
python3 tests/test-instructions-diff.py
```

---

## Schema and version evolution

- `schema_version` is a monotonically increasing string. v1 is the current
  contract.
- Breaking changes (field removal, type change, new required field) bump
  the version. Tomo Hashi **must** reject unknown versions explicitly.
- Additive changes (new optional field, new action kind) are v1-compatible;
  Tomo Hashi should ignore unknown fields on known kinds, and surface
  unknown action kinds rather than assume a fallback.

When in doubt, compare against the live JSON Schema:
[`tomo/schemas/instructions.schema.json`](../tomo/schemas/instructions.schema.json)
has the final say on required fields, enum values, and type constraints.
