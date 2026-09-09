# Specification: 035-wire-schema-versioning

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-09 |
| **Current Phase** | Initialization |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-09-09 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-09 | **Scoped as a versioning mechanism, not as a one-off schema fix** | Re-vendoring the two drifted fields closes the incident; it does not stop the third one. Two specs walked past the version gate without noticing, and the mechanism that should have caught them exists and is correct on the consumer's side. The spec is about when `schema_version` moves and how the consumer learns of it. |
| 2026-09-09 | **The consumer is consulted on the mechanism before it is picked** | Hashi vendors our schema and enforces it with `additionalProperties: false`. Any scheme that assumes they can read a field before they have re-vendored it is a scheme that breaks them again. The handoff of 2026-09-09 asks for their opinion rather than announcing a decision. |

## Context

### What happened

Tomo's Pass-1 suggestions wire (`tomo/schemas/suggestions-wire.schema.json`) gained two fields in
`suggestions[]` across two specs, while `schema_version` stayed `"1"`:

| Field | Added by | Commit |
|---|---|---|
| `attachments` | spec 031 — file inbox attachments alongside the notes that embed them | `9847829` |
| `item_key` (in `required`) | spec 034 — schemas carry required item_key | `2a5c6d9` |

Hashi vendors its own copy of that schema and compiles it with ajv
(`src/schema/suggestions-validator.ts:9`). Every object in it is `additionalProperties: false`.

**Measured on 2026-09-09**, running Hashi's vendored schema and ajv options against a real
`_suggestions.json` from the 2026-09-08 run: eight validation errors, two per suggestion,
`item_key` and `attachments`. `validate()` returns `{ok: false}`, so `SuggestionsDoc` never builds
an `EditModel` and the Suggestions Editor registered at Hashi's `main.ts:628` cannot open any run
Tomo currently produces.

The drift is bounded: a property-set diff of the two schemas shows those two fields in
`suggestions[]` and **nothing else** — root, `proposed_mocs[]`, `daily_updates[]` and
`tag_handler_groups[]` are all in sync. The Pass-2 instruction schema
(`hashi-instructions.schema.json` vs Hashi's `instructions.schema.json`) is fully in sync too:
root plus all 20 `$defs`, no field drift, no required drift.

### Why the existing gate did not fire

Hashi's schema pins `"schema_version": {"const": "1"}` and its validator has prescribed wording for
a mismatch — `"Schema version mismatch — expected X, got Y"` — specifically to drive an "upgrade
Hashi" prompt. That path never ran, because the version never moved. The gate is built correctly
on the consumer side; the producer walked around it twice.

### The question this spec answers

Under `additionalProperties: false`, **an added field is not additive for the consumer.** So:

1. When does `schema_version` move — on any shape change, or only on a change that breaks a
   consumer? (The incident says those are the same thing here, but that should be stated, not
   assumed.)
2. How does a consumer learn a bump is coming, given they vendor the schema and ship on their own
   cadence? A bump with no lead time turns a silent break into a loud one — better, but still a
   break.
3. Is there a compatibility window, and what does Tomo emit during it?
4. Does the same rule apply to the Pass-2 instruction schema, which is in sync today and has more
   consumers-in-waiting? And to the garden-audit wire?
5. What stops the next spec from adding a field without noticing — a test, a checklist item in the
   XDD gates, or something that reads both schemas and fails?

Question 5 is the one that decides whether this spec is worth building. A rule nobody enforces is
what we already had.

### Scope boundary

This spec does **not** re-vendor Hashi's schema — that is Hashi's file and their release. The
handoff `_outbox/for-hashi/2026-09-09_tomo-to-hashi_suggestions-wire-schema-two-specs-behind.md`
asks for it and offers to hold the wire steady until this spec lands.

### Prior art in this repo

- `docs/XDD/specs/034-recursive-inbox-discovery/README.md`, decisions of 2026-09-06 — two
  corrections in a row about which wire Hashi actually joins on. The lesson recorded there ("a
  boundary question needs the producer, the schema, and the consumer read together") is the same
  lesson this incident teaches, one level up: it also needs the consumer's *vendored copy*.
- MiYo Constitution, Architecture L2: "Public interfaces between MiYo components … Breaking
  changes require explicit review for backward compatibility and a documented migration path in
  Kokoro."

---
*This file is managed by the xdd-meta skill.*
