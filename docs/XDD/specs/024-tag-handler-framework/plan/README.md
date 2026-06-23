# Implementation Plan: Tag-Handler Framework (024)

> Derived from `solution.md`. Strategy: the Hashi `insert_under_marker` ask ships **first** (T1) so the
> cross-repo executor lands in parallel — no manual-apply interim. Additive-only; empty registry = no-op.

## Phases

- [ ] [Phase 1: Hashi handoff (early/parallel) + resolver foundations](phase-1.md)
- [ ] [Phase 2: Triage detection](phase-2.md)
- [ ] [Phase 3: Pass-1 compose + suggestion](phase-3.md)
- [ ] [Phase 4: Pass-2 render + guards](phase-4.md)
- [ ] [Phase 5: Authoring wizard + Tsukai handler + docs](phase-5.md)
- [ ] [Phase 6: Integration & validation](phase-6.md)

## Phase index

| Phase | Theme | Gate |
|-------|-------|------|
| P1 | Hashi handoff (early/parallel) + resolver foundations | resolver tests green |
| P2 | Triage detection | empty-registry byte-identity (AC-5) |
| P3 | Pass-1 compose + suggestion | merged status update from a group (AC-3) |
| P4 | Pass-2 render + guards | instruction emitted; guards fire (AC-4) |
| P5 | Authoring wizard + Tsukai handler + docs | handler authorable end-to-end (AC-2, AC-6) |
| P6 | Integration & validation | E2E (AC-1..AC-5); wire Hashi apply when it lands |

## Task map

Full per-task TDD structure (Prime/Test/Implement/Validate/Success + refs) lives in each `phase-N.md`.

| Phase | Tasks |
|-------|-------|
| P1 | T1.1a Hashi handoff · T1.1b Kokoro contract note · T1.2 `tag-handler.schema.json` · T1.3 `tag-handler-resolve.py` · T1.4 validation |
| P2 | T2.0 extend `routing-plan.schema.json` · T2.1 `inbox-triage.py` detect/partition · T2.2 validation |
| P3 | T3.1 `tag-handler-interpreter` skill · T3.2 compose (LLM merge + field template) · T3.3 `suggestions-reducer.py` · T3.4 validation |
| P4 | T4.1 `instruction-render.py` → `insert_under_marker` · T4.2 guards · T4.3 validation |
| P5 | T5.1 `tomo-tag-handler-wizard` · T5.2 `tsukai.json` · T5.3 docs · T5.4 validation |
| P6 | T6.1 Tomo-side E2E (AC-1..AC-5) · T6.2 wire Hashi apply · T6.3 validation |

## Cross-repo dependency

T1.1 is the only externally-blocked item, and only for **automated apply** (T6.2). Everything T1.2–T6.1 is
Tomo-internal and proceeds regardless. If Hashi lands before T6, the manual-apply interim never happens.

## Constitution gates

- L1 Testing: resolver + triage + guard denial paths; AC-5 byte-identity.
- L1/L2 Architecture: T1.1 Hashi contract → Kokoro + `_outbox/for-hashi/` handoff.
- L2 Code Quality: logic in resolver/interpreter; handlers pure data.
