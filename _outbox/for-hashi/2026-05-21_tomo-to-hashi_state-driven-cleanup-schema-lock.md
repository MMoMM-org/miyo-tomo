---
from: tomo
to: hashi
date: 2026-05-21
status: in-progress
status_note: Received. Step 2 iteration contract superseded by 2026-05-27 sources[] handoff. Combined cleanup contract acknowledged for future Hashi implementation.
subject: F-47 state-driven cleanup — schema lock + cleanup contract
priority: high
references:
  - docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md
  - docs/XDD/specs/017-tomo-lifecycle-tags/solution.md
  - tomo/schemas/doc-frontmatter.schema.json
supersedes: _outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md
target_version: "hashi >= 0.3.0 (suggested; Hashi team decides)"
requires_action: true
---

# F-47 State-Driven Cleanup — Schema Lock + Cleanup Contract

> **Schema-locked handoff.** F-47 (Tomo Lifecycle Tags, XDD spec 017) is fully
> implemented on the Tomo side (Phases 1–5 closed, 300 tests, 5 phase commits).
> This document supersedes the early-warning notice of 2026-05-20 and provides
> the finalised schema + authoritative cleanup contract. Implementation may begin
> immediately.

---

## 1. Context

F-47's vision: every Tomo-produced file in the inbox carries its lifecycle in a
single structured frontmatter field (`tomo.state`), so `/inbox` and `/moc-propose`
can discover pending work from one `byFrontmatter` lookup — no body-reads, no
filename-pattern matching, no scattered state logic.

**Hashi's role as consumer:** when Hashi successfully executes all actions in a
Tomo-produced `<ts>_instructions.md`, it flips `tomo.state` to `applied`, then
iterates every `source_*` key in the doc's `tomo:` block to trash upstream
source docs, and finally trashes the instructions doc itself. This makes the
lifecycle atomic: when the user sees the last action ticked, the input docs
are gone.

---

## 2. Schema (Verbatim)

The schema below is the Phase 1 deliverable, committed at
`tomo/schemas/doc-frontmatter.schema.json` (commit `2830817`).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://miyo.tomo/schemas/doc-frontmatter.schema.json",
  "title": "Tomo Doc Frontmatter",
  "description": "Schema for the 'tomo:' frontmatter block written by every Tomo producer. Validated at write-time in dev mode (TOMO_SCHEMA_STRICT=1). The root object is the full frontmatter dict; the 'tomo' property holds the lifecycle block.",
  "type": "object",
  "required": ["tomo"],
  "additionalProperties": true,
  "properties": {
    "tomo": {
      "type": "object",
      "required": ["doc_type", "state", "run_id", "updated_at"],
      "additionalProperties": false,
      "patternProperties": {
        "^source_[a-z_]+$": {
          "type": "string",
          "description": "Cross-reference to an upstream Tomo doc. Key pattern: source_<doc_type_snake_case> (e.g. source_suggestions, source_moc_proposal, source_suggestions_fan, source_garden_audit). Extensible for future F-44/45/46 doc-types without schema changes."
        }
      },
      "properties": {
        "doc_type": {
          "type": "string",
          "enum": ["source", "suggestions", "suggestions-fan", "moc-proposal", "instructions"],
          "description": "Type of Tomo-produced doc. Determines which state values are valid."
        },
        "state": {
          "type": "string",
          "description": "Current lifecycle state. Valid values are constrained per doc_type via oneOf branches."
        },
        "run_id": {
          "type": "string",
          "description": "Run-id that produced or last updated this doc. Format: YYYY-MM-DD-HHMMSS-<hash>."
        },
        "updated_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO-8601 UTC timestamp of the last write. Auto-set by build_tomo_block()."
        }
      },
      "oneOf": [
        {
          "description": "source — inbox items captured at Pass-1 dispatch",
          "properties": {
            "doc_type": {"const": "source"},
            "state": {"enum": ["captured"]}
          }
        },
        {
          "description": "suggestions — Pass-1 analysis output",
          "properties": {
            "doc_type": {"const": "suggestions"},
            "state": {"enum": ["pending-approval", "approved"]}
          }
        },
        {
          "description": "suggestions-fan — XDD-012 Force-Atomic-Resolve companion; same lifecycle as suggestions",
          "properties": {
            "doc_type": {"const": "suggestions-fan"},
            "state": {"enum": ["pending-approval", "approved"]}
          }
        },
        {
          "description": "moc-proposal — /moc-propose output; accepted after MOC-consumption",
          "properties": {
            "doc_type": {"const": "moc-proposal"},
            "state": {"enum": ["pending-accept", "accepted"]}
          }
        },
        {
          "description": "instructions — Pass-2 / MOC-consumption output; applied when Hashi is done",
          "properties": {
            "doc_type": {"const": "instructions"},
            "state": {"enum": ["pending-apply", "applied"]}
          }
        }
      ]
    }
  }
}
```

**Example instructions doc `tomo:` block at the point Hashi receives it:**

```yaml
tomo:
  doc_type: instructions
  state: pending-apply
  run_id: 2026-05-21-143022-a7f3c1
  updated_at: 2026-05-21T14:30:22Z
  source_suggestions: "100 Inbox/2026-05-21_1125_suggestions.md"
```

Or, when produced from a MOC-proposal acceptance path:

```yaml
tomo:
  doc_type: instructions
  state: pending-apply
  run_id: 2026-05-21-143022-a7f3c1
  updated_at: 2026-05-21T14:30:22Z
  source_moc_proposal: "100 Inbox/2026-05-21_1359_moc-proposal-notemaking.md"
```

`source_*` values are **vault-relative paths** (no leading slash, no `vault://`
prefix) — the same format accepted by `kado-write` and `kado-read`. Exactly one
`source_*` key will be present on a standard instructions doc; future doc-types
(F-44/45/46) may add further `source_*` keys.

---

## 3. State-Driven Cleanup Contract

When Hashi successfully applies all actions in a Tomo-produced
`<ts>_instructions.md`, it MUST execute the following three steps in order:

```
When Hashi successfully applies all actions in a Tomo-produced <ts>_instructions.md:

1. Flip frontmatter via kado-write operation=frontmatter (mode=merge):
       { "tomo": { "state": "applied", "updated_at": <ISO-8601 now> } }
   This is the single signal Tomo and external tools watch for.

2. Iterate every key in the doc's tomo block matching the pattern ^source_[a-z_]+$:
   For each path value found, trash the file at that vault-relative path via
   Obsidian system trash (best-effort — log a warning if the path is missing,
   then proceed).

3. Trash the instructions doc itself LAST. The reason ordering matters:
   if step 2 partially succeeds, the instructions doc remains in the inbox
   as a recoverable cleanup target; the user can re-trigger the apply or
   manually trash the rest. Trashing the instructions doc first would
   strand uncollected source references.
```

**STRICT rules:**

- "Best-effort" means: log + continue, never raise on a missing source path.
- "system trash" — NOT `git rm`, NOT filesystem `rm` — MUST go through
  Obsidian's trash mechanism (`vault.trash(file, useSystemTrash: true)`) so
  the metadata cache is rebuilt cleanly and the user can recover via OS trash.
- Generic iteration over `source_*` keys means Hashi gets future Tomo doc-types
  (F-44 `source_garden_audit`, F-45 `source_weekly_review`, etc.) for free
  without Hashi code changes. MUST NOT use a hardcoded key list.
- If ANY action in the instructions set failed (Hashi's per-action result
  accounting), skip cleanup entirely: no state flip, no `source_*` trash, no
  instructions trash. The doc remains `pending-apply` for retry.

---

## 4. AC Mapping (PRD AC-4.x → Hashi Acceptance)

| Tomo AC | Hashi acceptance criterion |
|---------|---------------------------|
| AC-4.1 — Tomo emits contract; Hashi accepts state flip | Hashi's apply flow calls `kado-write operation=frontmatter mode=merge` with `tomo.state=applied` on the instructions doc AFTER all actions succeed. |
| AC-4.2 — missing source path → warning + proceed; instructions trashed last | Hashi catches FS-not-found on `source_*` paths, logs to its audit journal, proceeds with remaining keys; only AFTER iterating all `source_*` does it trash the instructions doc. |
| AC-4.3 — partial-applied count → no cleanup | If ANY action fails (Hashi's existing per-action result accounting), the entire cleanup step skips: no state flip, no `source_*` trash, no instructions trash. Doc remains `pending-apply`. |
| AC-4.4 — multiple pending-apply docs cleaned independently | Hashi applies + cleans up each instructions doc in its own transaction. Cleanup of one doc MUST NOT gate or affect cleanup of another. |
| AC-4.5 — generic `source_*` iteration (future doc-types) | Hashi MUST iterate the `^source_[a-z_]+$` pattern, NOT a hardcoded list of known key names. Future Tomo doc-types extend `source_*` without requiring Hashi code changes. |

---

## 5. F-47 Implementation Summary

All five Tomo producers now emit a `tomo:` block per the schema above:

| Producer | State emitted | Key `source_*` keys |
|----------|--------------|---------------------|
| `mark-captured.py` | `tomo.state=captured` on source items | — |
| `suggestions-render.py` (standard) | `pending-approval` on suggestions docs | — |
| `suggestions-render.py` (fan-resolve branch) | `pending-approval` on suggestions-fan docs | — |
| `instruction-render.py` | `pending-apply` on instructions docs | `source_suggestions` or `source_moc_proposal` |
| `suggestions-reducer.py --moc-proposal-mode` | `pending-accept` on moc-proposal docs | — |

Consumer side (`/inbox`): unified `byFrontmatter` discovery + sequential
state-promoter. No body-reads on non-pending docs. All frontmatter mutations
go through `KadoClient.write_frontmatter(mode="merge")` — Kado 0.11.0 API.
Regex YAML edits are eliminated.

F-47 ships behind feature branch `feat/017-tomo-lifecycle-tags`.
Phases 1–5 closed; Phase 6 (this handoff) is the final task.

---

## 6. Receipt Protocol

Per the MiYo handoff protocol:

- **On receipt:** Hashi flips frontmatter
  `status: pending → status: received` and adds:
  ```yaml
  received_by: hashi
  received_at: <ISO date>
  target_version: <hashi semver they plan to ship in>
  ```
- **On adoption:** Hashi flips frontmatter
  `status: received → status: done` and appends a `## Done` section at the
  bottom referencing the Hashi PR/commit that ships the cleanup.

---

## 7. References

- F-47 spec: `docs/XDD/specs/017-tomo-lifecycle-tags/` (in Tomo repo)
- Final implementation commit on `feat/017-tomo-lifecycle-tags`: `867b636`
- Schema file commit SHA: `2830817`
  (`feat(F-47): T1.2 doc-frontmatter schema + helper`)
- Early-warning notice (now superseded):
  `_outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md`
- Kado `kado-write operation=frontmatter` (mode=merge): Kado 0.11.0 API — the
  write primitive for the state flip in cleanup step 1.
