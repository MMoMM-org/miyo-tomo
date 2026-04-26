# instructions.json + instructions.md — Tomo Hashi Consumer Contract

> Last reviewed: 2026-04-26 (Path Shape Contract documented + renderer-side guard added in `instruction-render.py` v0.7.1; additive to v1).

**Audience:** Authors and integrators of [Tomo Hashi (友橋)](https://github.com/MMoMM-org)
— the Obsidian community plugin that reads Tomo's Pass-2 instruction set
and executes it inside the vault. This document is the authoritative
consumer specification for both companion artefacts.

**Canonical schema:** [`tomo/schemas/instructions.schema.json`](../tomo/schemas/instructions.schema.json)
— JSON Schema Draft 2020-12, stricter than this prose (it has the final
word on required fields and enum values).

**Producer:** [`scripts/instruction-render.py`](../scripts/instruction-render.py)
inside this repo. Produced by the `instruction-builder` agent at the end
of Pass 2, written to the vault inbox via `kado-write operation="file"`
(because `operation="note"` only accepts `.md`).

## Two files, one contract

Every Pass-2 run produces a matched pair in the inbox:

| File | Role | Who reads it |
|---|---|---|
| `<date>_instructions.json` | Canonical machine-readable contract. Every field and execution rule lives here. | **Tomo Hashi** (primary input) |
| `<date>_instructions.md` | Human-readable view of the same actions, with per-action `- [ ] Applied` checkboxes. | **User** (in Obsidian), **Tomo Hashi** (to sync checkbox state after each execution) |

Both files share a timestamped prefix. They're siblings, written in the
same Pass-2 invocation. If the `.json` is missing, Tomo Hashi must
refuse to execute the `.md` — markdown parsing is not a supported
fallback.

**Sync contract**: Tomo Hashi executes from the `.json`. After each
successful action apply, it ticks the matching `- [ ] Applied` checkbox
in the `.md` (action `I##` ↔ third-level heading `### I## — …`). On
failure, the checkbox is left empty and Tomo Hashi reports the error.
The user can also tick/untick checkboxes manually (e.g. "apply by hand,
then have Tomo Hashi skip"); Tomo Hashi honours the current state on
re-run.

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
  "md_peer": "2026-04-21_1113_instructions",
  "actions": [ ... ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"1"` (const) | Bumps when the structure becomes incompatible. Reject with a clear error if you see a version you don't understand. |
| `type` | `"tomo-instructions"` (const) | Discriminator in case multiple JSON artefacts share the inbox folder. |
| `source_suggestions` | string \| null | Stem(s) of the suggestions doc(s) this set was derived from — traceability only. A normal Pass-2 run produces a single stem. An XDD-012 Force-Atomic reconciliation run (primary doc + companion `*_suggestions-fan.md`) produces a comma-separated list: `"2026-04-21_0918_suggestions, 2026-04-21_1330_suggestions-fan"`. Tomo Hashi SHOULD treat this as opaque text; it's for human trace only and does not affect execution. |
| `generated` | ISO-8601 UTC | Use this (not file mtime) when comparing action sets. |
| `profile` | string \| null | Active PKM profile (miyo / lyt / custom). Useful if your UI adapts to framework conventions. |
| `tomo_version` | string \| null | Tomo runtime version. Log it in case you need to debug a divergence. |
| `action_count` | integer | Length of `actions[]`. Mismatch → file corruption, abort. |
| `md_peer` | string | Stem of the companion human-readable markdown, in the same folder (e.g. `2026-04-21_1113_instructions`). Added 2026-04-23 per Kokoro schema review: explicit linkage rather than inferring from `generated` timestamp + folder convention. Tomo Hashi SHOULD read `<md_peer>.md` alongside the JSON and SHOULD surface a clear error ("peer not found at recorded stem X") if the file is missing, rather than silently falling back to a convention-based search. Always populated by `instruction-render.py` v0.6.0+; older v0.5.x artefacts may lack it (not in the v1 required set — the field is additive). |
| `actions[]` | array | The executable payload. See below. |

---

## Action lifecycle

1. The user applies each action in the vault (manually, or via Tomo Hashi).
2. Tomo Hashi **must** treat the instruction set as a monotonic log — actions
   are applied or unapplied, never mutated in place.
3. **Applied-state lives on each action's `applied` boolean inside the JSON**
   (added 2026-04-25). Tomo emits `applied: false` on every action; Hashi
   flips it to `true` after a successful apply and saves the file atomically.
   The transition is monotonic — Hashi never writes `false`. Re-runs are
   additive.
4. The human-readable view (`*_instructions.md`) carries `- [ ] Applied`
   checkboxes per action. Hashi ticks them best-effort to mirror the JSON
   `applied` flag, but the **JSON is the source of truth**. Markdown
   checkboxes are an observation surface for humans, not an authoritative
   state. Hand-editing the JSON to flip an action's `applied` to `true`
   causes Hashi to skip that action on the next run — same semantics as a
   normal Hashi success.
5. Missing `applied` field is treated as `false` (graceful tolerance for
   v0.5.x artefacts produced before the field shipped).
6. `- [ ] Applied` at action index N corresponds to `actions[N-1]` in the
   JSON (IDs `I01`, `I02`, … align with the markdown's third-level headings).

### XDD 012 — Force-Atomic Resolve actions are indistinguishable

Actions that originated from an XDD-012 Force-Atomic resolve subflow
(i.e. the user ticked `Force Atomic Note` on a log entry whose inbox
item had no analyst-proposed atomic section, and Pass 2 synthesised a
follow-up suggestions doc) render identically to normal atomic-note
actions in `instructions.json`. There is no `force_atomic` flag, no
`from_resolve` marker, no extra execution rule — just the usual
`move_note` + `link_to_moc` pair for the atomic, plus any approved
daily-note actions linking to it. Tomo Hashi needs no special-case
handling. The `source_suggestions` string will list both docs when a
resolve reconciliation happened (see envelope table above).

---

## Companion markdown: `<date>_instructions.md`

The `.md` is a human-readable projection of the same instruction set.
It exists so the user can scan, edit-in-place, and tick Applied
checkboxes in Obsidian. Tomo Hashi uses it as the shared state surface
for applied/not-applied — but never as the source of truth for action
parameters (read those from JSON).

### File shape

```markdown
---
type: tomo-instructions
generated: 2026-04-21T11:13:18Z
tomo_version: "0.1.0"
source_suggestions: "2026-04-21_0918_suggestions"
profile: miyo
action_count: 25
tags:
  - MiYo-Tomo/instructions
---

# Tomo Instructions — 2026-04-21 11:13

Generated from: [[2026-04-21_0918_suggestions]]

## Summary
- 8 new atomic notes ready in inbox folder
- 1 new MOC ready in inbox folder
- 10 MOC link additions
- 1 daily note tracker update
- 2 daily log entries
- 3 source deletions

## Actions

### I01 — create_moc: Brettspiele (MOC)
- [ ] Applied
- **Source:** [[2026-04-21_1113_brettspiele-moc]]
- **Destination:** `Atlas/200 Maps/Brettspiele (MOC).md`
- **Tags:** `type/others/moc`, `topic/recreation/board-games`
- **Reason:** 3 atomic proposals about board-game strategy cluster under a missing MOC.

### I02 — move_note: Asahikawa — zweitgrößte Stadt Hokkaidos
- [ ] Applied
- **Source:** [[2026-04-21_1113_asahikawa-zweitgroesste-stadt-hokkaidos]]
- **Destination:** `Atlas/202 Notes/Asahikawa — zweitgrößte Stadt Hokkaidos.md`
- **Parent MOC(s):** [[Japan (MOC)]]

### … (one H3 per action through I25) …
```

### Layout rules Tomo Hashi depends on

| Rule | Detail |
|---|---|
| Frontmatter tag | `#MiYo-Tomo/instructions` on a fresh set; `#MiYo-Tomo/applied` after the user tags the set as fully done; `#MiYo-Tomo/archived` after cleanup. The lifecycle prefix (`MiYo-Tomo/`) comes from vault-config. |
| Action entries | Each is an H3 heading `### I##  — <action kind>: <title>`. The `I##` ID matches the JSON's `actions[N-1].id`. |
| Applied checkbox | The **first** bullet under each H3 is always `- [ ] Applied` (or `- [x] Applied` after the user ticks it). Tomo Hashi writes the tick after a successful apply; any other checkbox in the entry (if any) is decoration. |
| Action ordering | Identical to `instructions.json.actions[]`. Never re-order. |
| Wikilinks | Sources of rendered files use `[[<stem>]]` (no folder, no `.md`). Destinations are code-fenced full paths for clarity. |

### What NOT to parse out of the `.md`

Tomo Hashi **must not** derive action parameters (source path,
destination path, section name, tracker value, etc.) from the markdown.
Those come from the `.json`. The markdown may be edited by the user —
Tomo's internal model of "what to execute" stays pinned to the JSON.
If the markdown is lost or corrupted, Tomo Hashi can regenerate its
Applied state from vault inspection or from a tracked execution log;
the JSON is sufficient to replay.

### Cleanup contract

When `/inbox` runs the cleanup phase (`vault-executor`), it needs only
the `.md`'s frontmatter tag (`#MiYo-Tomo/applied`) and per-action
`- [x] Applied` checkboxes to decide which source inbox items to
transition from `captured` → `active`. The `.json` is not consulted
during cleanup. See
[tier-3 instruction-set-cleanup](XDD/reference/tier-3/inbox/instruction-set-cleanup.md)
for the full rules.

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
- **`applied` (boolean, optional, default `false`)** — present on every
  action kind. Tomo emits `false`; Hashi writes `true` after a successful
  apply. Missing field is tolerated as `false`. See "Action lifecycle"
  above for the round-trip contract.

---

## Path Shape Contract

Every path-typed field on every action kind conforms to a single canonical
shape. Tomo Hashi's path-safety pipeline (schema → normalize → vault-root
containment → deny-list → `fs.realpath` symlink-escape check → execute)
assumes paths are already in this form; non-conforming values fail closed
with non-actionable errors (`Path escapes vault root`, `path-symlink-escape`).
The renderer (`scripts/instruction-render.py` v0.7.1+, helper
`_validate_action_paths`) refuses to write `instructions.json` if any path
violates these rules — a Pass-2 run aborts with exit 2 and per-violation
diagnostics on stderr.

### The five rules

Every emitted path string is:

1. **Vault-relative** — no leading `/`, no `~`, no drive letter (`C:/...`).
2. **Absolute within the vault** — no `..` segments, no `./` prefix, no
   relative-to-something resolution required by the consumer.
3. **Plugin-alias free** — no `{{daily}}`, no Templater `<% ... %>` blocks,
   no `[[wikilink]]` shorthand. Wikilinks live only in `line_to_add` /
   `target_stem` payload fields, never in path fields.
4. **Forward-slash separated** — no backslashes (Tomo runs in a Linux
   container so this is automatic; the rule is stated for completeness).
5. **Control-char free** — no `\n`, `\r`, `\x00`, or other characters in the
   ranges `\x00-\x1f` / `\x7f`.

### Path field inventory

The complete list of path-typed fields, by action kind. Required fields
must be non-empty strings; nullable fields may be `null` (or absent on the
optional-but-not-required `move_note.origin_inbox_item`) but must conform
to the contract when set.

| Action kind         | Field                  | Required? | Notes |
|---------------------|------------------------|-----------|-------|
| `create_moc`        | `source`               | Required  | Vault path of the rendered MOC currently in the inbox. |
| `create_moc`        | `destination`          | Required  | Vault path of the final MOC location (under `Atlas/200 Maps/` by convention). |
| `move_note`         | `source`               | Required  | Vault path of the rendered atomic note in the inbox. |
| `move_note`         | `destination`          | Required  | Vault path of the final atomic-note location (under `Atlas/202 Notes/` by convention). |
| `move_note`         | `origin_inbox_item`    | Optional, nullable | Path of the original inbox item this note was derived from — informational. Cleanup is via `delete_source`, not this field. |
| `link_to_moc`       | `target_moc_path`      | Optional, nullable | Resolved vault path of the MOC. `null` is legitimate when the target doesn't exist yet (sibling `create_moc`) or Kado was unreachable at render time. Hashi falls back to `target_moc` (a stem, **not** a path). |
| `update_tracker`    | `daily_note_path`      | Required  | Vault path of the daily note. Tomo resolves the date-to-path mapping; Hashi receives the resolved value. |
| `update_log_entry`  | `daily_note_path`      | Required  | Same as above. |
| `update_log_link`   | `daily_note_path`      | Required  | Same as above. |
| `delete_source`     | `source_path`          | Required  | Vault path of the file to move to Obsidian's trash. |
| `skip`              | `source_path`          | Optional, nullable | Vault path of the inbox item the user chose to skip. |

`link_to_moc.target_moc`, `update_log_link.target_stem`, and the various
`*_stem` traceability fields are **stems** (no folders, no `.md`), not
paths — Obsidian resolves them by name. They are not subject to the path
contract.

### What stays out of path fields

- **No wikilink syntax.** `[[Some Note]]` belongs in `line_to_add`,
  `target_stem`, or `content` — never in a path field.
- **No Templater syntax.** `<% tp.file.title %>` is rendered into the body
  of an atomic note's content, never into a destination path.
- **No Daily Notes plugin aliases.** Tomo expands `{{daily}}` /
  date-formatted aliases into a concrete `daily_note_path` at Pass-2 time.
  Hashi has no resolver for these and will not gain one in v0.1.

### Renderer-side enforcement

`scripts/instruction-render.py` (v0.7.1+) runs `_validate_action_paths` over
the full action list immediately before serialising `instructions.json`.
Any violation aborts the run with exit code 2 and prints one diagnostic
line per offending field, naming the action ID, kind, field, value, and
which rule was broken. The check is defensive — production paths come from
config + suggestion data and should already conform — but it makes any
upstream regression visible inside Tomo rather than at Hashi execute time.

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
  "section_name": "[!blocks] Key Concepts",
  "line_to_add": "- [[Asahikawa — zweitgrößte Stadt Hokkaidos]]",
  "source_note_title": "Asahikawa — zweitgrößte Stadt Hokkaidos"
}
```

| Field | Type | Notes |
|---|---|---|
| `target_moc` | string | MOC stem (no path, no `.md`) — the name Obsidian resolves by. |
| `target_moc_path` | string \| null | Resolved vault-relative full path. See "Resolution rules" below. |
| `section_name` | string \| null | Callout/heading pointer — deterministically resolved at Pass-2 time. See "section_name resolution" below. |
| `line_to_add` | string | The exact bullet line to insert. Already formatted (`- [[stem]]`). |
| `source_note_title` | string \| null | Informational — which note's up-link this represents. |

**`section_name` resolution (current behaviour):**

- When set, the value is the full first line of a callout (leading `> `
  stripped for display), e.g. `[!blocks] Key Concepts` or
  `[!compass] Something to look at`. Tomo Hashi should match it against the
  MOC body by re-adding `> ` and scanning line-by-line.
- Pass-2 picks the target callout with a priority heuristic: prefer `blocks`
  (the conventional content callout in MiYo/LYT), then any other editable
  callout, then `connect` (navigation) as last resort. Editable callout names
  come from vault-config's `callouts.editable`.
- **Known limitation (backlog F-30):** the resolver only identifies the
  OUTER callout. For MOCs with H2/H3 sub-headers inside the callout that
  topic-group their children (e.g. Sport → Running / Stretching / Gym),
  the resolver cannot decide which sub-section a new link belongs under.
  Tomo Hashi can either (a) append at the end of the callout body (simple,
  works for flat MOCs), (b) surface the sub-structure in a UI so the user
  picks, or (c) defer to a post-MVP LLM-driven insertion-point step
  (planned; see backlog F-30).
- **`section_name` is `null`** when the target MOC doesn't exist in the
  vault yet (new MOC from a `create_moc` in the same instruction set),
  when Kado is unreachable during Pass-2, or when the MOC has no editable
  callout matching the config. Fall back to the first editable callout at
  execute time.

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
prose.

> **Why the asymmetry (`content` literal vs. `target_stem` structured)?**
> `update_log_entry.content` is a fully-formed line that Tomo Hashi
> inserts verbatim. `update_log_link.target_stem` is the bare wikilink
> target; Tomo Hashi formats the line as `- [[<target_stem>]]` and, when
> `position == "at_time"`, prefixes it with `HH:MM - `. The structured
> shape exists because the time-prefix case has to be rendered at
> execute time, not at generation time — the `HH:MM` is already in the
> `time` field, so baking it into a literal would duplicate data and
> invite drift if one got edited without the other. `update_log_entry`
> has no such composition need (its content is free-form prose), so it
> stays literal. Both kinds use the same `position` / `time` / `section`
> / `heading_level` fields.

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
