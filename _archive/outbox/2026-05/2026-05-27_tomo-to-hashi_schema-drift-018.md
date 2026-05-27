---
from: tomo
to: hashi
date: 2026-05-27
topic: Schema drift from 018 — add_relationship.mode + supporting_items type
requires_action: true
status: done
status_note: supporting_items type widened in cf855d8 on fix/schema-supporting-items-type
---

# Schema Drift: instructions.schema.json vs instruction-render.py output

Found during spec 018 (agent architecture cleanup) live validation.

## 1. ~~`add_relationship.mode`~~ — RESOLVED

Removed `mode` field from instruction-render v0.18.0. Per contract
(instructions-json.md §882-886), related:: aggregation is done Tomo-side.
instruction-render now reads existing related:: from vault, merges with
new links, and emits one action per target with the combined `line`.
Hashi always does replace — no change needed.

## 2. `create_moc.supporting_items` — type mismatch

Schema says: `type: ["string", "null"]` (e.g. `"S02, S06, S12"`)
MOC-proposal-parser emits: `type: array` (e.g. `["Thought Collisions", "The 7 C's of Notemaking"]`)

Suggestion-parser still emits strings (SNN IDs). Both formats coexist.

**Fix needed in schema:** widen type to accept both:
```json
"supporting_items": {
  "oneOf": [
    {"type": "string"},
    {"type": "array", "items": {"type": "string"}},
    {"type": "null"}
  ]
}
```

**Hashi impact:** `supporting_items` is display-only for Hashi (link_to_moc actions are the operational signal). No executor change needed — just schema alignment.
