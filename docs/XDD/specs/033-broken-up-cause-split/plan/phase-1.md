---
title: "Phase 1: Resolve and record the cause"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Resolve and record the cause

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-3]`
- `[ref: SDD/Interface Specifications; Cache entry]`
- `[ref: PRD/Feature 1]`, `[ref: PRD/Feature 6]`
- Source to read: `tomo/scripts/moc-tree-builder.py:280-290` (`_resolve_up_state`), `:367-372`
  (`moc_stem_set` construction and the path loop that already holds the note paths), `:405-425`
  (the call site and the cache entry); `tomo/scripts/lib/moc_scan.py:44-55` (`ScanResult`, which
  already carries `in_scope_note_paths`)

**Key Decisions**:
- **ADR-2** — add a field, do not extend `up_state`'s enum. Three consumers test `== "absent"` /
  `== "broken"`; new enum values would make each silently wrong.
- **ADR-3** — write the field on **every** entry, `null` where it does not apply, so its *absence*
  means "cache predates this spec".

**Dependencies**: none. Nothing consumes the field yet, so this phase is safe to land alone.

---

## Tasks

Widens what the cache records about a broken parent. No behaviour changes; the audit still produces
exactly the findings it produces today.

- [x] **T1.1 `_resolve_up_state` reports why** `[activity: domain-modeling]`

  1. **Prime**: Read `moc-tree-builder.py:280-290`. Note that the caller at `:367` builds
     `moc_stem_set` from `scan_result.moc_paths`, and that the same `ScanResult` carries
     `in_scope_note_paths` — the note-stem set is derivable at the same site, from data already
     loaded. `[ref: SDD/Code Context]`
  2. **Test** (RED):
     - target is a MOC stem → `("valid", None)` `[ref: PRD/F1 criterion 3]`
     - target is an in-scope **note** stem → `("broken", "not-a-moc")` `[ref: PRD/F1 criterion 1]`
     - target is in **neither** set → `("broken", "unresolved")` `[ref: PRD/F1 criterion 2]`
     - target is `None` → `("absent", None)` — unchanged
     - a stem present in **both** sets (a MOC also listed as a note) → resolves `valid`; the MOC set
       wins. Assert it rather than assume the sets are disjoint.
  3. **Implement**: extend the signature with the note-stem set and return the pair. Keep the
     existing precedence: MOC first, then note, then unresolved.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_moc_tree_builder.py -q`
  5. **Success**: the three broken/valid distinctions are decided in one place, from sets the caller
     already holds, with no vault access added `[ref: PRD/F1 criterion 4]`.

- [x] **T1.2 The cache entry carries `up_broken_reason`** `[activity: data-architecture]`

  1. **Prime**: Read `moc-tree-builder.py:405-425`. Note how spec 032 added `up_source` and
     `up_value` at this site, and that `up_value` is written **unconditionally** precisely so its
     presence is the freshness signal.
  2. **Test** (RED):
     - a broken-with-note-target entry → `up_broken_reason == "not-a-moc"`
     - a broken-with-unknown-target entry → `up_broken_reason == "unresolved"`
     - a **valid** entry → the key is **present** and its value is `None`
       `[ref: SDD/ADR-3]`
     - an **absent** entry → the key is **present** and its value is `None`
     - over a whole built cache → **every** entry carries the key. Assert on the count, not on a
       hand-picked entry; a per-entry test passes while a conditional write is still shipping.
  3. **Implement**: one added key in the entry dict, written unconditionally.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_moc_tree_builder.py tests/test_moc_cache_loader.py -q`
  5. **Success**: presence is universal, so absence is unambiguous `[ref: PRD/F6]`.

- [ ] **T1.3 Absence semantics are stated for the next reader** `[activity: documentation]`

  1. **Prime**: this task's original text told the implementer to find the schema that validates
     `moc-structure-cache.yaml` entries. **No such schema exists.** Verified: `tomo/schemas/`
     contains no `moc-structure-cache.schema.json` and no file there mentions `up_state` at all;
     `tomo/scripts/lib/moc_cache_loader.py` reads the cache with a bare `yaml.safe_load` and performs
     no schema validation of any kind — only staleness and structural checks. A JSON schema for this
     cache was considered and rejected as out of scope for this spec; CON-6 ("schema and its mirror
     stay bytewise identical") does not apply because nothing here is a mirrored schema — there is no
     schema to begin with. Do not re-open this question; the absence was confirmed by direct
     inspection, not by a failed search.
  2. **Test**: none — there is no schema to add a RED assertion against. The success criterion this
     task serves (the absence semantics are stated, not left to be inferred from the sentinel) is a
     documentation deliverable, not a validated one.
  3. **Implement**: document `up_broken_reason`'s three values (`null` / `"not-a-moc"` /
     `"unresolved"`) and its absence semantics (missing key = pre-033 cache, per ADR-3) in
     `docs/tomo/scripts/moc-tree-builder.md` — this repo's WHY-persistence layer for
     `tomo/scripts/moc-tree-builder.py`, per the root CLAUDE.md rule that runtime rationale lives
     there, not in the runtime file itself. Include a short note that a JSON schema was looked for and
     does not exist, so a future reader does not re-litigate this search.
  4. **Validate**: read the added section back; confirm it states all three values, the `null`
     meaning, and the absence-means-pre-033-cache rule without requiring the reader to re-derive it
     from `_MISSING`-sentinel code.
  5. **Success**: `docs/tomo/scripts/moc-tree-builder.md` states the absence semantics, so the next
     reader does not have to infer them from the sentinel — the same success bar the original task
     set, met by the artifact that actually governs this field.

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Rebuild the cache from the live vault fixture and confirm every entry carries the key.
  - Confirm no consumer reads it yet: grep `up_broken_reason` outside `moc-tree-builder.py`, its
    tests, and `docs/tomo/scripts/moc-tree-builder.md`. A hit means this phase is not standalone
    after all.
