---
title: "Phase 1: Capture the declaration value"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Capture the declaration value

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1]`
- `[ref: SDD/Interface Specifications; Application Data Models]` — the `raw_value` semantics, incl. why it is `None` for inline
- `[ref: PRD/Feature 1]`, `[ref: PRD/Business rule 1]`
- Source to read: `tomo/scripts/lib/up_parse.py:43-47` (the dataclass), `:195-214` (both return sites), `:210` (`frontmatter.get(marker_word(parent_marker))` — the value is already read here); `tomo/scripts/moc-tree-builder.py:406` (`fm = parse_frontmatter`), `:410` (the call), `:415-425` (the cache entry)

**Key Decisions**:
- **ADR-1** — capture in `up_parse`, the declared SSoT. It already reads the value and already derives the property name.
- `raw_value` is `None` for an inline declaration — "not applicable", deliberately distinct from a frontmatter property that exists and holds nothing.

**Dependencies**: none. Nothing consumes the new field yet, so this phase is safe to land alone.

---

## Tasks

Widens what is captured about a note's parent declaration. No behaviour changes.

- [x] **T1.1 `UpParseResult.raw_value`** `[activity: domain-modeling]`

  1. **Prime**: Read `up_parse.py:43-47` and both return sites at `:206` and `:211`. Note that `:210` already fetches the whole property value before `_first_wikilink` discards all but the first link.
  2. **Test** (RED):
     - a frontmatter list `up: ["[[A]]", "[[B]]"]` → `raw_value == ["[[A]]", "[[B]]"]`, order preserved `[ref: PRD/Business rule 4]`
     - a frontmatter scalar `up: "[[A]]"` → `raw_value == "[[A]]"`, **not** wrapped in a list `[ref: SDD/Implementation Gotchas]`
     - an inline `up:: [[A]]` → `source == "inline"` and `raw_value is None` `[ref: SDD/Application Data Models]`
     - a note with **both** → inline still wins (unchanged precedence) and `raw_value is None`
     - no declaration → `target is None`, `source is None`, `raw_value is None`
     - a property that exists but is empty (`up:` / `up: []`) → `target is None` (unchanged) — record what `raw_value` is in this case and assert it, since it is the state the `_MISSING` sentinel later has to be distinguishable from
  3. **Implement**: add `raw_value: Any = None` to the dataclass; populate at the frontmatter return site.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_up_parse.py -q`; `ruff` clean; `# version:` bumped.
  5. **Success**:
     - [ ] The observed value is carried verbatim, shape and order intact `[ref: PRD/Business rule 4]`
     - [ ] Inline declarations carry no value `[ref: SDD/ADR-1]`

- [ ] **T1.2 Cache entry carries `up_value`** `[activity: data-architecture]`

  1. **Prime**: Read `moc-tree-builder.py:415-425`. `up_source` is already written at `:423`; this is the sibling field.
  2. **Test** (RED):
     - a frontmatter-declared note produces a cache entry whose `up_value` equals the property value
     - an inline-declared note produces an entry with `up_value` present and `None`
     - **the key is written for every entry** — its presence, not its value, is the freshness signal `[ref: SDD/ADR-3]`
     - `up_state`, `up_target` and `up_source` are unchanged for every existing fixture `[ref: CON-7]`
  3. **Implement**: add `"up_value": up.raw_value` to the entry dict.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**:
     - [ ] Every entry carries the key, so absence unambiguously means "old cache" `[ref: PRD/Feature 6]`
     - [ ] No additional Kado call is made — the value comes from `content` already in hand `[ref: CON-3]`

- [x] **T1.3 Second-consumer regression** `[activity: validate]` `[parallel: true]`

  1. **Prime**: `moc-discovery.py:63` and `:1399` also call `parse_up_from_content`.
  2. **Test** (RED): `moc-discovery`'s existing behaviour is unchanged by the wider dataclass — it reads `.target`/`.source` only.
  3. **Implement**: no production change expected. If one is needed, the dataclass change was not additive.
  4. **Validate**: the `moc-discovery` test suite passes untouched.
  5. **Success**: widening the shared result breaks no consumer `[ref: SDD/Implementation Boundaries]`

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Full suite green. Confirm a freshly built cache carries `up_value` on 100% of entries, matching how `up_source` behaves today. `ruff` clean.
