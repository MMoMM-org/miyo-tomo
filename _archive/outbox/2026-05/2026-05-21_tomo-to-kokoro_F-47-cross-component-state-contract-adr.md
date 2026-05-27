---
from: tomo
to: kokoro
status: done
status_note: Filed as ADR-018. Added § 6.6 Lifecycle State Contract to 06-miyo-tomo-hashi.md.
subject: F-47 cross-component state contract — ADR draft for Kokoro adoption
priority: normal
references:
  - docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md
  - docs/XDD/specs/017-tomo-lifecycle-tags/solution.md
  - tomo/schemas/doc-frontmatter.schema.json
adr_template: "ready-to-paste"
target_repo: miyo-kokoro
target_path: "<Kokoro session decides — likely global/decisions/ADR-018-tomo-cross-component-state-contract.md>"
---

This is a ready-to-paste ADR. Tomo F-47 introduces a cross-component schema (Tomo→Hashi) which under MiYo Constitution L2 Architecture requires Kokoro reflection. The next ADR number is whatever Kokoro's sequence dictates (ADR-018 as of 2026-05-21 — verify current sequence before filing). Tomo cannot commit on miyo-kouzou per `~/Kouzou/standards/general.md` — Kokoro session, please copy the ADR text below into the appropriate ADR file and commit.

---

## ADR text (ready to paste)

---

# ADR-018: F-47 — Cross-Component State Contract for Tomo Workflow Docs

*decisions/ADR-018-tomo-cross-component-state-contract.md*

**Author:** Marcus Breiden
**Date:** May 2026
**Status:** Accepted
**Supersedes:** —
**Related:** [06-miyo-tomo-hashi.md](../architecture/06-miyo-tomo-hashi.md) · [ADR-009](ADR-009-tomo-hashi-charter.md) · [ADR-016](ADR-016-tomo-hashi-action-contract.md) · [ADR-017](ADR-017-create-moc-collision-and-cascade.md) · MiYo Constitution §Architecture L2 · §Privacy & Security L1

---

## Context

MiYo is a multi-component PKM system. Two components — Tomo (AI workflow producer) and Hashi (Obsidian-side executor) — share the user's Obsidian vault as their communication medium. Tomo writes workflow docs into the vault inbox; Hashi reads and executes them; both treat the vault as the single source of truth. Under ADR-009 (Hashi charter), this producer/consumer split was the founding contract, but the contract left the *shape* of the shared state implicit.

Before F-47, Tomo's inbox docs carried state in four separate mechanisms: a frontmatter tag (`#<prefix>/captured`) on source items, body checkboxes (`[x] Approved`) on suggestions docs, body checkboxes (`[x] Applied`) on instructions docs, and nothing at all on proposal-docs. Each mechanism required a different consumer to detect a different signal. F-43 live-validation (2026-05-20) surfaced this as a concrete gap: `tomo-moc-proposal-*.md` docs had no state field at all, so `/inbox`'s discovery pass never found them and the acceptance flow was broken indefinitely.

F-47 introduces a unified `tomo:` frontmatter block on every Tomo-produced workflow doc. The block carries `doc_type`, `state`, `run_id`, `updated_at`, and `source_*` cross-references in a single structured location. Discovery shifts from body-reads and filename heuristics to a single server-side `kado-search operation=byFrontmatter` query. State transitions go through `kado-write operation=frontmatter mode=merge` — no more regex YAML edits (which had already caused production bugs: `feedback_frontmatter_newline_guard`).

Per MiYo Constitution L2 Architecture — *"Any change that affects interactions between MiYo components must be reflected in MiYo Kokoro as an updated design note or ADR"* — this cross-component schema requires a Kokoro pin. Tomo and Hashi evolve independently; a shared contract that lives only in Tomo's spec directory is not discoverable by Hashi maintainers (or future third components). This ADR is the system-level contract record.

## Decision

We adopt `tomo/schemas/doc-frontmatter.schema.json` (Draft-07 JSON Schema, maintained in the Tomo repo) as the canonical cross-component contract for Tomo workflow doc lifecycle state.

### 1. The `tomo:` block is the single source of truth for lifecycle state

Every Tomo-produced workflow doc carries a `tomo:` frontmatter block:

```yaml
tomo:
  doc_type: <suggestions | suggestions-fan | moc-proposal | instructions | source>
  state:    <see per-doc-type state machine below>
  run_id:   <string — production run that wrote this doc, format YYYY-MM-DD-HHMMSS-<hash>>
  updated_at: <ISO-8601 UTC timestamp of last state write>
  # Cross-references (instructions docs only):
  source_suggestions:     "<vault-relative path>"   # when instructions came from a suggestions doc
  source_suggestions_fan: "<vault-relative path>"   # when instructions came from a fan-resolve doc (XDD 012)
  source_moc_proposal:    "<vault-relative path>"   # when instructions came from an accepted proposal-doc
  # Extensible: F-44/45/46 will add source_garden_audit, source_weekly_review, etc.
```

`tomo.state` is the single canonical state field. The tag-based capture mechanism (`#<prefix>/captured`) and body-checkbox-derived state detection are eliminated; all lifecycle state lives in the `tomo:` block.

### 2. State machines per doc-type

```
suggestions (and suggestions-fan):
  null → pending-approval (trigger: producer write)
  pending-approval → approved (trigger: state-promoter after Pass-2 success)
  terminal: approved

moc-proposal:
  null → pending-accept (trigger: moc-architect write)
  pending-accept → accepted (trigger: state-promoter after MOC Pass-2 success)
  terminal: accepted

instructions:
  null → pending-apply (trigger: instruction-builder write)
  pending-apply → applied (trigger: Hashi after last [x] Applied confirmed)
  terminal: applied

source:
  null → captured (trigger: mark-captured at Pass-1 dispatch)
  terminal: captured
```

Only listed transitions are valid. Any other transition MUST be rejected by the consumer with a logged `lifecycle.transition_rejected` event and no vault write.

### 3. All state mutations go through `kado-write operation=frontmatter mode=merge`

No consumer may mutate the `tomo:` block via regex string-edit, full-note overwrite (`operation=note`), or direct filesystem write. The required call path is:

```
kado-write operation=frontmatter mode=merge
  path: <doc path>
  frontmatter: {"tomo": {"state": <new-state>, "updated_at": <iso8601>}}
  expectedModified: <unix-ms from last read>   # optimistic concurrency
```

`mode=merge` semantics: arrays replace, scalars replace, unrelated keys preserved. A partial `tomo:` block write (only `state` + `updated_at`) preserves `doc_type`, `run_id`, and all `source_*` keys unchanged.

### 4. Hashi cleanup is state-driven via generic `source_*` iteration

When Hashi flips the last `[x] Applied` checkbox on an instructions doc, it MUST:

1. Write `tomo.state=applied` via `kado-write operation=frontmatter mode=merge` on the instructions doc.
2. Collect every frontmatter key matching the pattern `source_*` from the `tomo:` block.
3. Trash (to Obsidian system trash) each path referenced by a `source_*` key.
4. Trash the instructions doc itself (last).

Hashi MUST iterate `source_*` keys generically — it must NOT enumerate a hardcoded list of known doc-types. This ensures that future doc-types (F-44 garden-audit, F-45 weekly-review, F-46 tag-audit) produce instructions docs whose `source_garden_audit: <path>` keys are cleaned up by Hashi without any Hashi code change.

If a path under a `source_*` key is already missing at cleanup time (e.g. deleted manually by the user), Hashi MUST log a warning and continue — best-effort cleanup.

### 5. Schema is Tomo-owned; consumers embed or pin by commit SHA

`tomo/schemas/doc-frontmatter.schema.json` is the master copy. Tomo validates every `tomo:` block at write time (CI gate + dev-mode runtime assert via Python `jsonschema`). Consumers (Hashi, future components) SHOULD embed the schema verbatim in their repo OR reference by commit SHA at integration time — they MUST NOT maintain a divergent copy.

### 6. Breaking vs. non-breaking schema changes

- **Non-breaking** (no cross-component coordination required): adding a new `doc_type` enum value, adding a new optional `source_<x>` key.
- **Breaking** (requires coordinated Tomo + Hashi release + ADR supersession or peer ADR): removing or renaming an existing `doc_type` or `state` value, removing an existing `source_*` key, changing `mode=merge` semantics, changing the `source_*` iteration contract.

A breaking change MUST be reflected in Kokoro before or alongside implementation.

## Reasoning

**Frontmatter as the single state surface, not tags.** The user's UX model is: frontmatter is hidden in the editor and not browsed via the tag pane. A tag on a workflow doc is pure machine metadata that the user never interacts with directly — but it is visible noise in tag searches and auto-complete. Frontmatter carries the same data invisibly and is the canonical Obsidian metadata surface. One state field, one place, no drift.

**Sidecar state file rejected.** A per-doc `.tomo-state.json` sidecar file avoids frontmatter mutation but doubles the read cost per doc (two Kado calls to know a doc's state), leaks orphan files on doc deletion, and breaks under Obsidian Sync (frontmatter syncs, sibling files may not). Vault-as-SoT discipline argues strongly for keeping all state inside the vault file itself.

**SQLite state index rejected.** A Tomo-owned SQLite index would enable fast queries and eliminate per-doc frontmatter reads, but it introduces a single point of failure (Hashi reads instructions docs when Tomo may not be running), requires migrations, and breaks the "state lives in the vault" principle that makes the user's vault self-describing. Local-first PKM should keep all state in vault files.

**Mirrored lifecycle tag rejected (PRD v1.2 drop).** An earlier design (PRD v1.1) included a `#<prefix>/<doc-type>/<state>` tag mirrored to `tomo.state` for tag-search discoverability. Dropped in v1.2 because: (a) the user doesn't browse workflow docs via tag pane, (b) two state fields create drift risk, (c) the tag write adds per-transition overhead without UX benefit. Reversible if requirements change — the renderer can re-add a mirrored tag write in one place.

**Generic `source_*` iteration is the forward-compatibility key.** Without it, every new Tomo doc-type (F-44, F-45, F-46) would require a Hashi release to add the new doc-type to a hardcoded list. With the `source_*` pattern, Hashi's cleanup logic is doc-type-agnostic forever. This is the same principle as the `outcome` enum in ADR-014 and the action schema in ADR-016: explicit extensibility points prevent accidental coupling.

**Merge semantics for state flips are a user-data safety guard.** If state flips used `mode=replace`, a Tomo bug that emits an incomplete `tomo:` block would silently wipe the user's other frontmatter (tags, `up::`, `related::`). Merge mode ensures only the explicitly supplied keys change; user-added frontmatter is always preserved.

## Consequences

### Positive

- **Single SoT for lifecycle state.** Every component can answer "what is this doc's state?" with one frontmatter read — no body parse, no filename heuristic.
- **Unified discovery.** `kado-search operation=byFrontmatter query="tomo.state=pending-*"` returns all pending workflow docs in one server-side call. Token cost for discovery drops from ~4,850 to ~1,000 per `/inbox` run (steady state).
- **F-43 acceptance-flow unblocked.** Proposal-docs now carry `tomo.state=pending-accept`; the state-promoter discovers them in the same query as suggestions docs.
- **Future doc-types are free.** F-44 garden-audit, F-45 weekly-review, F-46 tag-audit can all emit `tomo:` blocks and participate in the cleanup contract without changing Hashi.
- **Regex YAML edit bug class eliminated.** The `feedback_frontmatter_newline_guard` bug (malformed YAML from string-join without trailing newline) cannot occur when all frontmatter mutations go through `kado-write operation=frontmatter`.
- **`run_id` propagates as correlation ID.** Tomo and Hashi can use `tomo.run_id` to correlate their respective log entries for a workflow execution.

### Negative

- **Tomo and Hashi must coordinate schema version bumps.** A breaking schema change without Hashi adoption creates a period where pending-apply docs accumulate but Hashi cannot correctly iterate `source_*` keys. Each breaking change requires a cross-repo handoff (via `_outbox/for-hashi/`) and a coordinated release window.
- **Hashi adoption is asynchronous (Tomo ships first).** After Tomo F-47.P4 ships, a window exists where instructions docs carry the new `tomo:` block but Hashi may not yet consume it. During this window, Hashi cleanup remains filename-driven (pre-F-47 behaviour). The window closes when Hashi releases its state-driven cleanup implementation.
- **Frontmatter mutation path is gated on Kado.** Any component mutating `tomo.state` must have a live Kado MCP connection. Direct vault writes (bypassing Kado) are architecturally forbidden and would undermine the concurrent-write safety (`expectedModified`) contract.

### Neutral

- **Schema lives in Tomo repo.** This is consistent with Tomo being the sole producer of `tomo:` blocks today. If a future component other than Tomo needs to produce `tomo:` blocks (e.g. Hakobi landing files with pre-set state), a Kokoro ADR will re-examine ownership.
- **Constitution alignment checked.** Privacy L1 (no PKM body content, no credentials in `tomo:` block — workflow metadata only). Local-first L1 (state in vault, no external state store). Architecture L2 (this ADR is the cross-component documentation). Operations L1 (feature branches, not main). No new constitutional questions raised.

## Propagation

- **Kokoro (this repo):** ADR-018 (this file). `global/architecture/06-miyo-tomo-hashi.md` gains a `§ Lifecycle State Contract` subsection pointing at this ADR and summarising the `tomo:` block shape.
- **Tomo:** F-47 implementation (`feat/017-tomo-lifecycle-tags` branch). Schema at `tomo/schemas/doc-frontmatter.schema.json`. Handoff to Hashi at F-47.P4 merge: `_outbox/for-hashi/2026-05-21_tomo-to-hashi_state-driven-cleanup-schema-lock.md`.
- **Hashi:** Receives the schema-lock handoff after F-47.P4 ships. Hashi implements state-driven cleanup (generic `source_*` iteration, `tomo.state=applied` flip on last action) in its next release cycle. The exact Hashi branch and timeline are Hashi's to decide.
- **Future MiYo components producing workflow docs:** Must emit a `tomo:` block per this contract. Must validate against `tomo/schemas/doc-frontmatter.schema.json`.

## References

- Triggering handoff: `Tomo/_outbox/for-kokoro/2026-05-21_tomo-to-kokoro_F-47-cross-component-state-contract-adr.md`
- F-47 PRD: `Tomo/docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md`
- F-47 SDD: `Tomo/docs/XDD/specs/017-tomo-lifecycle-tags/solution.md`
- Schema: `Tomo/tomo/schemas/doc-frontmatter.schema.json` (created in F-47.P1)
- Hashi schema-lock handoff: `Tomo/_outbox/for-hashi/2026-05-21_tomo-to-hashi_state-driven-cleanup-schema-lock.md`
- Memory entry `feedback_frontmatter_newline_guard` (Tomo) — the regex-YAML-edit bug class this contract eliminates.
- Memory entry `user_marcus_tomo_ux_model` (Tomo) — rationale for dropping the mirrored lifecycle tag (v1.2 decision).
- MiYo Constitution L2 Architecture: `~/Kouzou/projects/miyo/miyo-constitution.md`
- F-43 MOC creation spec: `Tomo/docs/XDD/specs/013-moc-creation-skill/`
- Hashi charter: [ADR-009](ADR-009-tomo-hashi-charter.md)
- Action contract: [ADR-016](ADR-016-tomo-hashi-action-contract.md)

---

*Part of MiYo Kokoro — [README](../../README.md)*
