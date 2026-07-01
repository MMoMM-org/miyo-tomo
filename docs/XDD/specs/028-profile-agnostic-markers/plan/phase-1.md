---
title: "Phase 1: Foundation — Conventions resolver + profile keys"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Foundation — Conventions resolver + profile keys

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Interface Specifications; profile_conventions.py]`
- `[ref: SDD/Solution Strategy]` (DI value-object pattern)
- `[ref: SDD/Constraints; CON-4, CON-5]`

**Key Decisions**:
- ADR-2 `profiles_dir` caller-supplied. ADR-3 missing-key defaults (`up::`/`related::`/`""`).

**Dependencies**: none. This phase blocks Phases 2, 3, 4.

---

## Tasks

Establishes the single `Conventions` resolver and the profile data it reads.

- [ ] **T1.1 `lib/profile_conventions.py` resolver** `[activity: domain-modeling]`

  1. Prime: Read the resolver interface spec `[ref: SDD/Interface Specifications]` and `moc-discovery.py` `resolve_profile`/`_load_yaml` (298-320) as the pattern to generalize.
  2. Test (RED): `tests/test_profile_conventions.py` — resolves markers+suffix from a `profile_dict`; from a `profile_override` name; from a `config_path` (`profile:` key); missing `relationship_defaults.*.marker` → `up::`/`related::`; missing `map_note.name_suffix` → `""`; `profiles_dir` is a required kw-arg (calling without it raises).
  3. Implement (GREEN): Create `tomo/scripts/lib/profile_conventions.py` — frozen `Conventions{parent_marker, peer_marker, moc_suffix}` + `resolve_conventions(*, profiles_dir, profile_dict=None, config_path=None, profile_override=None)`. Resolution order per SDD. No `__file__`-derived path (ADR-2).
  4. Validate: `./venv/bin/python -m pytest tests/test_profile_conventions.py`; `./venv/bin/ruff check tomo/scripts/lib/profile_conventions.py`.
  5. Success:
     - [ ] Both bundled profiles resolve correct suffix (miyo `" (MOC)"`, lyt `""`) `[ref: PRD/AC F-55]`
     - [ ] Missing keys fall back to documented defaults, no crash `[ref: PRD/Config & fallback]`
     - [ ] `profiles_dir` required (ADR-2) `[ref: SDD/ADR-2]`

- [ ] **T1.2 Profile `name_suffix` keys + version bumps** `[activity: data-architecture]`

  1. Prime: Read `miyo.yaml` `map_note` (37-41) and `lyt.yaml` `map_note` block.
  2. Test (RED): extend `tests/test_profile_conventions.py` to load the *actual* bundled profiles and assert miyo→`" (MOC)"`, lyt→`""`.
  3. Implement (GREEN): add `map_note.name_suffix: " (MOC)"` to `miyo.yaml`, `map_note.name_suffix: ""` to `lyt.yaml`; bump each `# version:` (CON-5).
  4. Validate: pytest green; `git diff` shows only additive YAML + version bump.
  5. Success:
     - [ ] `map_note.name_suffix` present + consumed in both profiles `[ref: PRD/AC F-55/Feature 3]`
     - [ ] `# version:` bumped on both (else `update-tomo` ships nothing) `[ref: SDD/CON-5]`

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests + ruff. Confirm the resolver is importable and both profiles parse. No consumer wired yet — this phase adds capability only.
