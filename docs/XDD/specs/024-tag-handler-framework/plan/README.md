# Implementation Plan: Tag-Handler Framework (024)

> Derived from `solution.md`. Strategy: the Hashi `insert_under_marker` ask ships **first** (T1) so the
> cross-repo executor lands in parallel — no manual-apply interim. Additive-only; empty registry = no-op.

## Phase index

| Phase | Theme | Gate |
|-------|-------|------|
| P1 | Hashi handoff (early/parallel) + resolver foundations | resolver tests green |
| P2 | Triage detection | empty-registry byte-identity (AC-5) |
| P3 | Pass-1 compose + suggestion | merged status update from a group (AC-3) |
| P4 | Pass-2 render + guards | instruction emitted; guards fire (AC-4) |
| P5 | Authoring wizard + Tsukai handler + docs | handler authorable end-to-end (AC-2, AC-6) |
| P6 | Integration & validation | E2E (AC-1..AC-5); wire Hashi apply when it lands |

## Tasks

### P1 — Handoff + foundations
- **T1.1a** Draft + send the **Hashi handoff** (`_outbox/for-hashi/insert-under-marker-action.md`): the new
  `insert_under_marker` instruction contract (`target_path`, `anchor{type:heading,value}`, `placement`,
  `content`), reusing Hashi's existing `anchor` resolution; flags that `inside`-on-heading is a new
  executor semantic; acceptance + test shape. **Ships first** so Hashi builds in parallel.
- **T1.1b** **Kokoro contract note** (constitution L2, Architecture): a concrete ADR / design-note in
  miyo-kokoro recording the `insert_under_marker` instruction-set schema addition, routed via
  `_outbox/for-kokoro/`. Part of T1's done-definition — the contract must live in the authoritative repo
  before/alongside implementation, not folded into the Hashi handoff.
- **T1.2** `tomo/schemas/tag-handler.schema.json` — handler config JSON Schema (match/action/target/marker/
  placement/compose). Invalid handler → skipped with logged warning.
- **T1.3** `tomo/scripts/tag-handler-resolve.py` — deterministic resolver (load registry, match tag_prefix,
  bind capture_segments, read fields, resolve target_path). Tests: match, no-match, prefix-collision
  (lexical-by-id), unmapped-target (`target_path=null`), invalid-handler-skip.

### P2 — Triage detection
- **T2.0** Extend `tomo/schemas/routing-plan.schema.json` (it is `additionalProperties:false`): add the
  `handled[]` property (and a `handle` action value if needed). **Prereq for T2.1.**
- **T2.1** `inbox-triage.py`: after `compute_new_sources`, run resolver; add `handled[]` to
  `routing-plan.json`; exclude handled items from the `suggest` lane. **Omit the `handled` key entirely
  when empty → byte-identical run (AC-5).** Tests: handled-item partition; empty-registry identity (no
  `handled` key, schema-valid); mixed batch.

### P3 — Pass-1 compose + suggestion
- **T3.1** `tag-handler-interpreter` skill — loaded by suggestion-conductor when `routing-plan.handled`
  non-empty; groups by `(handler, target_path)`.
- **T3.2** Compose: LLM directive → one call per group receives all captures → one merged status-update
  block (FR-8); field-template → mechanical join (no LLM).
- **T3.3** `suggestions-reducer.py`: render each group as a suggestion item (proposed block + target +
  marker + `Approve`). Tests: one group → one suggestion; multi-capture merge cardinality.

### P4 — Pass-2 render + guards
- **T4.1** `instruction-render.py`: approved group → `insert_under_marker` instruction reusing the
  `anchor` machinery (`type:heading`, `value:<marker w/o ##>`, `placement`).
- **T4.2** Guards: target-missing → "create it first" checkbox (daily-note pattern, reducer); marker-missing
  → error item, no instruction. Tests: both guard paths (Constitution L1 denial-path coverage), incl. a
  **fake-vault read** for the marker-existence check (FR-12 is a filesystem-access path, not pre-supplied input).

### P5 — Authoring + Tsukai + docs
- **T5.1** `tomo-tag-handler-wizard` skill (AskUserQuestion → writes `config/tag-handlers/<feature>.json`,
  validated against the schema). Mirrors `tomo-trackers-wizard`.
- **T5.2** Ship `config/tag-handlers/tsukai.json` reference handler (match `MiYo/Tsukai/`, segment `repo`,
  field `category`, action `insert_under_marker`, marker `## Captures`, compose directive). User fills `repo_note_map`.
- **T5.3** Docs: config/inbox docs + `docs/tomo/` WHY-docs for the resolver, interpreter skill, wizard.

### P6 — Integration & validation
- **T6.1** E2E (Tomo-side): 3 Tsukai captures for one repo → one merged status-update suggestion →
  approved → `insert_under_marker` instruction. Validates AC-1..AC-5.
- **T6.2** When the Hashi action lands (T1.1 handoff done): wire the automated apply + cross-repo E2E.

## Cross-repo dependency
T1.1 is the only externally-blocked item, and only for **automated apply** (T6.2). Everything T1.2–T6.1 is
Tomo-internal and proceeds regardless. If Hashi lands before T6, the manual-apply interim never happens.

## Constitution gates
- L1 Testing: resolver + triage + guard denial paths; AC-5 byte-identity.
- L1/L2 Architecture: T1.1 Hashi contract → Kokoro + `_outbox/for-hashi/` handoff.
- L2 Code Quality: logic in resolver/interpreter; handlers pure data.
