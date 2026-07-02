---
title: "Phase 2: Suffix seams (F-55)"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Suffix seams (F-55)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; ensure_suffix/strip_suffix]`
- `[ref: PRD/Feature 2; Detailed Feature Specifications; business rules]`
- `[ref: SDD/Building Block View/Directory Map]`

**Key Decisions**: suffix apply-once; empty `""` = no-op append + no-op strip; strip case-insensitive (parity with existing regexes).

**Dependencies**: Phase 1 (needs `Conventions`). Independent of Phase 3 `[parallel: true]` at the phase level.

---

## Tasks

De-hardcodes the MOC title suffix across all four suffix seams. Every task keeps `miyo` output byte-identical.

- [x] **T2.1 moc-discovery suffix from profile** `[activity: backend]`

  1. Prime: Read `moc-discovery.py` `_PROFILE_TITLE_SUFFIX` (888-891) + `phase4_title` (933-944); it already holds `profile_dict`.
  2. Test (RED): title generation under miyo ends `" (MOC)"`; under lyt no suffix; apply-once when topic already ends in suffix.
  3. Implement (GREEN): replace `_PROFILE_TITLE_SUFFIX` dict with `resolve_conventions(profile_dict=..., profiles_dir=DEFAULT_PROFILES_DIR).moc_suffix`; apply via the shared apply-once rule.
  4. Validate: pytest + ruff; byte-identical miyo title regression fixture.
  5. Success:
     - [x] miyo titles unchanged `[ref: PRD/AC F-55]` — [ ] lyt titles plain `[ref: PRD/AC F-55]`

- [x] **T2.2 topic_clusters strip by param** `[activity: backend]` `[parallel: true]`

  1. Prime: Read `lib/topic_clusters.py` `strip_moc_marker` (32) + its callers.
  2. Test (RED): `strip_moc_marker(topic, suffix)` strips profile suffix case-insensitively; empty suffix = no-op; non-matching suffix left intact.
  3. Implement (GREEN): add `suffix` param, build regex from it; update callers to pass resolved suffix.
  4. Validate: pytest + ruff.
  5. Success: [ ] strip parity with old regex `[ref: SDD/Implementation Examples]`

- [x] **T2.3 reducer suffix + `conventions` block** `[activity: backend]`

  1. Prime: Read `suggestions-reducer.py` `_MOC_SUFFIX`/`_ensure_moc_suffix` (483-528), its `--profile` handling, and where it writes `suggestions-doc.json`.
  2. Test (RED): reducer applies profile suffix; output `suggestions-doc.json` contains additive `conventions{parent_marker,peer_marker,moc_suffix}`; existing wire fields unchanged.
  3. Implement (GREEN): `_ensure_moc_suffix` uses `resolve_conventions(profile_override=args.profile, profiles_dir=...).moc_suffix`; emit `conventions` block.
  4. Validate: pytest + ruff; schema/consumer of suggestions-doc.json still parses.
  5. Success:
     - [x] `conventions` block present (additive) `[ref: SDD/Modified wire]`
     - [x] miyo reducer output otherwise unchanged `[ref: PRD/AC regression]`

- [x] **T2.4 shared-ctx-builder `_MOC_NAME_RE` from suffix** `[activity: backend]` `[parallel: true]`

  1. Prime: Read `shared-ctx-builder.py` `_MOC_NAME_RE` (261) `_is_missing_moc_target`; it already loads the profile.
  2. Test (RED): placeholder-MOC detection uses resolved suffix; miyo behavior unchanged; empty-suffix profile still detects nothing spuriously.
  3. Implement (GREEN): build the detection regex from the resolved suffix. No change to shared-ctx *output* / schema.
  4. Validate: pytest + ruff.
  5. Success: [ ] detection parity under miyo `[ref: SDD/CON-2]`

- [x] **T2.5 Phase Validation** `[activity: validate]`

  - Run all suffix tests + ruff. Grep-confirm no residual `" (MOC)"` / `_MOC_SUFFIX` literals in the four seam sites. miyo regression fixtures green.
