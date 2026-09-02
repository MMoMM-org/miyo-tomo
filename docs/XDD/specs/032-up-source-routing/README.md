# Specification: 032-up-source-routing

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-01 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-01 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must features, 26 Gherkin criteria, 8 business rules, 8 edge cases |
| solution.md | completed | 6 ADRs (3 user-confirmed, 3 derived), two traced walkthroughs, 6 gotchas |
| plan/ | completed | 6 phases, 30 tasks, 126 spec refs, 7 parallel |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-01 | Spec scaffolded from a cross-repo exchange | Hashi's `edit_frontmatter` handoff asked *"wherever garden-audit decides a link needs repointing, it now needs to know whether the link sits in the body or in a property"*. Our answer: we already know, we just do not use it. Hashi acknowledged and **added no guard**, recording the decision in their spec-002 (PR #128) and explicitly awaiting this routing. Source: `_inbox/from-hashi/2026-09-01_hashi-to-tomo_resolve-dead-link-blindspot-was-live.md` §4. |
| 2026-09-01 | **Both fix paths are broken for a frontmatter-sourced `up`** — verified, not assumed | `broken_up` offers remove or repoint. Remove → `remove_up_link` → Hashi finds no `up::` line → *"nothing to remove"* → **silent success**. Repoint → `add_relationship` → `addRelationship.ts:21,70` returns `failed` with *"Marker not found"* → **loud failure**. One lies, the other refuses; in both cases the fix the user approved does not happen, because Tomo sent the wrong action kind. An earlier guess that repoint would silently add a duplicate `up::` line was checked and is **wrong** — Hashi fails instead. |
| 2026-09-01 | Population measured, not estimated | Live discovery cache (`tomo-instance/config/discovery-cache.yaml`): 64 entries carry `up_state`; **17 are frontmatter-sourced**, 18 inline, 29 have no `up`. Currently broken: **1, and it is inline**. So the defect is **latent with a real population**, not active — which sets urgency (low) without weakening the case. |
| 2026-09-01 | The discriminator already exists and is fully populated | `up_parse.py:43-47` exposes `source: "inline" \| "frontmatter" \| None`; `moc-tree-builder.py:423` writes it into the cache as `up_source`; **all 64 entries carry it**. `garden-audit.py:153-169` (`broken_up`) reads only `up_state`/`up_target` and never asks. Grepping `up_source` across the checker, parser, emitter and schemas returns nothing. **This is a threading gap, not a detection problem.** |
| 2026-09-01 | `expected` is sourceable at **zero** Kado cost — the framing of it as the hard question was wrong | Hashi requires `expected` and compares it **deep-equal against the whole property value**, while the cache holds only `up_target` (a stem). That looked like it would force a per-note read at audit time — the exact pattern **027 ADR-2** rejected on 429 grounds. It does not: `moc-tree-builder.py:406` has `fm = parse_frontmatter(content)` in scope at the cache-build site (`:415-425`), and `up_parse.py:210` already reads the full value via `frontmatter.get(marker_word(parent_marker))` before discarding everything but the first wikilink. The value is available twice over, for free, at the moment the cache is built. |
| 2026-09-01 | The `property` name is profile-agnostic for free | `marker_word(parent_marker)` derives `up` from the configured `up::` marker (`up_parse.py:210`), so `edit_frontmatter.property` needs no new config and does not hardcode `"up"`. Relevant because spec 028 made markers profile-driven. |
| 2026-09-01 | Same `instructions-diff` blind spot as spec 031 | `edit_frontmatter` is a new action kind, so `ACTION_ORDER` (`instructions-diff.py:429-433`) must gain it or the coverage audit passes green while the actions go unreconciled. Second spec in a row to hit this — a signal that adding a kind needs a checklist, not vigilance. |
| 2026-09-01 | ADRs confirmed by the user | **ADR-1** capture the observed value by extending `UpParseResult` with `raw_value` — `up_parse` already reads it (`:210`) and already derives the property name, so one place stays SSoT. **ADR-3** detect a stale cache by field *presence*, using a `_MISSING` sentinel rather than `None`, because `up_value: None` is a legitimate value (property exists, holds nothing) under Hashi's `expected`/`expected_absent` split. **ADR-4** surface the routing split in the report — accepted into scope; it is the observability whose absence let this defect class stay invisible. Derived: **ADR-2** branch in the parser not the check (the check describes reality, the parser maps a decision to an action — that mapping already lives at `garden-audit-parser.py:520-542`); **ADR-5** never fall back to the body action; **ADR-6** always derive the property name. |
| 2026-09-01 | Design finding: "remove" is usually `operation: "set"`, not `"remove"` | `remove` deletes the **whole property**, which is correct only when the broken link is its sole content. A property holding `["[[Alte MOC]]", "[[Reisen (MOC)]]"]` must be repaired by setting the surviving list, or a legitimate sibling parent is destroyed. The naming invites the wrong operation, so the SDD carries a traced walkthrough with all three rows. |
| 2026-09-01 | PRD acceptance criterion for `expected_absent` is **vacuously satisfied** | Every action this spec emits targets a property that exists — it is the source of the broken target. `expected_absent` is therefore never emitted, and the honest implementation is an assertion that it never happens rather than a code path producing it. Recorded rather than silently dropped, because a later spec emitting `edit_frontmatter` for a possibly-absent property makes the distinction live. |
| 2026-09-01 | PLAN completed → spec **Ready** | `plan/`: 6 phases, 30 tasks, 126 `[ref:]` links, 7 parallel. P1 capture (no consumers, safe alone) · P2 carry to the finding · P3 route + emit (the behavioural change) · P4 **the new-kind checklist as its own phase** · P5 report surface · P6 integration + live + notify Hashi. P4 depends on nothing and may run concurrently with P1–P3. Ready for /implement. |
| 2026-09-01 | P4 is a separate phase on purpose | Registration (producer schema, mirror, `instructions-diff`, `instructions-dryrun`, `render_md`, `_REQUIRED_PATH_FIELDS`) is not needed for the emitter to *work*, which is exactly why it gets folded into an emission task and forgotten. Spec 031 hit the identical trap one spec earlier. Two consecutive specs is a pattern, not coincidence — it argues for a standing checklist rather than vigilance. |

## Context

**Problem.** garden-audit treats a broken `up` identically regardless of where it lives. For the 17
notes whose `up` is a YAML property rather than an inline `up::` line, both offered fixes fail — one
silently, one loudly — because Tomo emits a body-oriented action for a frontmatter-resident value.

**Why now.** Hashi shipped `edit_frontmatter` in 0.22.0 and, at our recommendation, deliberately left
`remove_up_link` unguarded on the grounds that the durable fix is Tomo-side routing. They are waiting
on it. Meanwhile the data needed to route has been in our discovery cache all along.

**Scope shape.** Two halves that must land together:

1. **Threading** — carry `up_source` (and the raw property value) from the cache into the
   `broken_up` finding and on to the action builder.
2. **Adoption** — `edit_frontmatter` as a new emitted kind: both schemas, emitter, `render_md`,
   `instructions-dryrun`, `_REQUIRED_PATH_FIELDS`, and `instructions-diff` reconciliation.

**Known constraints for the SDD:**
- `edit_frontmatter` requires `expected`; it is compared deep-equal, and **list order is
  significant**. A value reconstructed from a normalised cache field would fail on ordering noise —
  the stored value must be faithful.
- `expected_absent: true` and `expected: null` are a schema-enforced **exclusive pair** (Hashi
  0.23.0); `null` now means "holds a literal null", not "must not exist".
- A failed `edit_frontmatter` leaves the file **byte-identical** (Hashi pre-checks on a read-only
  path). Retry logic may rely on this.
- A **successful** `edit_frontmatter` drops YAML comments — Obsidian's serialiser, not a Hashi
  choice. This is a user-visible cost that belongs in the proposal surface, not a post-hoc note.
- Existing discovery caches predate any new field. The design must degrade rather than crash.

---
*This file is managed by the xdd-meta skill.*
