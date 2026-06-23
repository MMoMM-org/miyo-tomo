---
title: "Phase 1: Hashi handoff (early/parallel) + resolver foundations"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Hashi handoff (early/parallel) + resolver foundations

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 2; lines: 22-50]` — handler config schema (match/action/target/marker/placement/compose)
- `[ref: SDD/Section 3; lines: 52-67]` — deterministic resolver contract (input/output, matching, target resolution)
- `[ref: SDD/Section 4; lines: 69-80]` — action registry (insert_under_marker shipped; other 3 declared-but-deferred)
- `[ref: SDD/Section 6; lines: 115-142]` — new `insert_under_marker` instruction + cross-repo contract
- `[ref: PRD/FR-1..FR-6; lines: 47-67]` — registry, match, action, compose, place

**Key Decisions**:
- Hashi handoff ships **first** (T1.1) so the executor lands in parallel — manual apply is fallback, not the planned interim (SDD §6).
- The Kokoro contract note (T1.1b) is part of T1's done-definition — the cross-repo contract must live in the authoritative repo before/alongside implementation (Constitution L2 Architecture).
- `compose` is a JSON-Schema `oneOf`: string (LLM directive) **xor** array of strings (mechanical template) (SDD §2).
- `enabled:false` handler is skipped exactly like an invalid one — not matched, not an error (SDD §2).
- Deterministic match order = lexical by `id`; unmapped target key → `target_path=null` (surfaced, not crashed) (SDD §3).
- Only `insert_under_marker` ships; deferred actions are registry-declared but resolver rejects them with a clear message (SDD §4).

**Dependencies**:
- None. This is the first phase; T1.1a/T1.1b (handoffs) and T1.2/T1.3 (code) are independent and may run in parallel.

---

## Tasks

Establishes the cross-repo contract (so Hashi can build in parallel) and the deterministic resolver foundation that every later phase consumes.

- [x] **T1.1a Hashi handoff: `insert_under_marker` action contract** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read the new-instruction contract `[ref: SDD/Section 6; lines: 115-142]` and the existing anchor/`link_to_moc`/`update_log_entry` vocab the handoff must contrast against.
  2. Test (acceptance): The handoff at `_outbox/for-hashi/insert-under-marker-action.md` specifies the full instruction contract (`target_path`, `anchor{type:heading,value}`, `placement`, `content`); explicitly flags that `inside`-on-a-heading is a **new executor semantic** (content beneath heading, above next same-or-higher heading) distinct from today's callout-only `inside`; states why existing vocab can't express it (target scoping, not line count); includes acceptance + test shape.
  3. Implement: Author `_outbox/for-hashi/insert-under-marker-action.md` per the MiYo handoff protocol (status `pending`).
  4. Validate: Contract is self-contained — a Hashi implementer could build the executor from it alone; every field in the SDD §6 JSON is covered.
  5. Success: Handoff sent, ships first so Hashi builds in parallel `[ref: SDD/Section 6; lines: 138-142]`.

- [x] **T1.1b Kokoro contract note (cross-repo, authoritative)** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read the cross-repo dependency rationale `[ref: SDD/Section 6; lines: 134-142]` and Constitution L2 Architecture (cross-component contract → Kokoro).
  2. Test (acceptance): A concrete ADR / design-note records the `insert_under_marker` instruction-set schema addition; routed via `_outbox/for-kokoro/`; lives in the authoritative repo before/alongside implementation (not folded into the Hashi handoff).
  3. Implement: Author the Kokoro design-note in `_outbox/for-kokoro/` describing the instruction-set schema change.
  4. Validate: Note matches the contract in T1.1a; references issue #47 and SDD §6.
  5. Success: Cross-repo contract reflected in Kokoro per Constitution L2 `[ref: SDD/Section 8; lines: 153]`.

- [x] **T1.2 `tomo/schemas/tag-handler.schema.json` — handler config JSON Schema** `[activity: data-architecture]`

  1. Prime: Read the handler config schema `[ref: SDD/Section 2; lines: 22-50]` and the Tsukai example `[ref: PRD/Section 6; lines: 88-103]`.
  2. Test (RED): valid Tsukai handler validates; `compose` as a string validates; `compose` as an array-of-strings validates; `compose` as a number/object fails (`oneOf`); missing `match.tag_prefix` fails; unknown `action` value fails; `enabled` defaults to `true`; deferred-action value (`route_to_folder`) is schema-valid (resolver rejects, not the schema).
  3. Implement: Create `tomo/schemas/tag-handler.schema.json` with match/action/target/marker/placement/compose and the `compose` `oneOf` (string xor string[]).
  4. Validate: `./venv/bin/python` schema unit tests pass; lint clean.
  5. Success: Invalid handler is detectable at load → skipped with logged warning, never aborts `[ref: SDD/Section 2; lines: 49-50]` `[ref: PRD/FR-1; lines: 48]`.

- [x] **T1.3 `tomo/scripts/tag-handler-resolve.py` — deterministic resolver** `[activity: backend-api]`

  1. Prime: Read the resolver contract `[ref: SDD/Section 3; lines: 52-67]` and the action registry `[ref: SDD/Section 4; lines: 69-80]`.
  2. Test (RED): match (tag_prefix prefix-of-tag binds `repo`, reads `category`); no-match (untagged item → no entry); prefix-collision resolves lexical-by-`id`; unmapped target → `target_path=null` (surfaced, no crash); invalid-handler-skip (logged warning, run continues); `enabled:false` skipped like invalid; deferred action (`route_to_folder`) → clear "not yet implemented" rejection.
  3. Implement: Create `tomo/scripts/tag-handler-resolve.py` (pure; no LLM/network beyond registry read) emitting the per-matched-item output shape in SDD §3.
  4. Validate: `./venv/bin/python` resolver tests pass; lint clean; types/contract match SDD §3 output JSON.
  5. Success: Resolver output drives triage/compose/render downstream `[ref: PRD/FR-2,FR-3,FR-6; lines: 49-67]` `[ref: SDD/Section 3; lines: 56-67]`.

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests under `./venv/bin/python`. Verify resolver match/no-match/collision/unmapped/invalid-skip paths against SDD §3 and the schema against SDD §2. Confirm both handoffs (`_outbox/for-hashi/`, `_outbox/for-kokoro/`) are sent. Lint clean. **Gate: resolver tests green.**
