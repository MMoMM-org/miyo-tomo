---
from: tomo
to: kado
date: 2026-05-26
topic: byFrontmatter nested dot-notation queries return 0 hits
status: done
status_note: Fixed in fix/byfrontmatter-nested-keys (808046f). Dot-notation added to byFrontmatter + shared filter.frontmatter helper. See for-tomo outbox reply 2026-05-26.
priority: high
requires_action: true
---

# byFrontmatter nested dot-notation broken

## What Changed

Tomo's F-47 lifecycle system writes a nested `tomo:` YAML block in frontmatter:

```yaml
tomo:
  doc_type: suggestions
  state: pending-approval
  run_id: 2026-05-26T15-56-32Z-61a5fd
  updated_at: '2026-05-26T16:04:32Z'
```

Querying this via `kado-search operation=byFrontmatter query=tomo.state=pending-approval` returns **0 hits**, even though `kado-read operation=frontmatter` on the same file returns the nested structure correctly.

Flat top-level keys work: `type=tomo-suggestions` → 1 hit. `tomo_version=0.1.0` → 1 hit.

## Why

This blocks the entire /inbox pipeline. `inbox-triage.py` discovers approved suggestions via `tomo.state=pending-approval` and `tomo.doc_type=suggestions` queries. With 0 hits, triage routes to `suggest` (fresh Pass 1) instead of `synthesize` (Pass 2), creating an infinite loop.

## Reproduction

```
kado-search { operation: "byFrontmatter", query: "tomo.state=pending-approval" }
→ items: []

kado-search { operation: "byFrontmatter", query: "type=tomo-suggestions" }
→ items: [{ path: "100 Inbox/2026-05-26_1604_suggestions.md", ... }]

kado-read { operation: "frontmatter", path: "100 Inbox/2026-05-26_1604_suggestions.md" }
→ content: { tomo: { state: "pending-approval", doc_type: "suggestions", ... } }
```

## Impact on Kado

The byFrontmatter operation needs to support dot-notation for nested YAML objects (`tomo.state` → traverse `frontmatter.tomo.state`). Obsidian's metadata cache stores nested objects — the question is whether Kado's query layer traverses them or only checks top-level keys.

## Action Required

1. Confirm: does byFrontmatter intentionally only query flat/top-level keys, or is nested dot-notation supposed to work?
2. If intentional limitation: document it, and Tomo will flatten the `tomo:` block to top-level keys (`tomo_state`, `tomo_doc_type`, etc.)
3. If bug: fix nested dot-notation traversal in the byFrontmatter handler.

## References

- Tomo F-47 lifecycle spec: `docs/XDD/specs/017-tomo-lifecycle-tags/`
- `tomo/scripts/lib/doc_frontmatter.py` — builds the nested `tomo:` block
- `tomo/scripts/inbox-triage.py:142-152` — the 4 byFrontmatter queries that fail
- Memory: `reference_kado_byfrontmatter_strict_equality` (documents strict equality, but doesn't mention nested key limitation)

