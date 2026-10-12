# Specification: 039-attachment-conflict-hardening

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-11 |
| **Current Phase** | PLAN |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.0, 51 acceptance criteria (F1–F6 Must, S1, C1); names four superseded prior criteria in CON-5 |
| solution.md | completed | v1.0, 10 ADRs all confirmed; 3 new components, 11 modified; CON-2 = Kokoro handoff before implementation |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-11 | Spec opened | Three inputs share one subject — what happens to an attachment between the owner's decision and the vault: Hashi's request for an editable target folder (`_inbox/from-hashi/2026-10-11_hashi-to-tomo_attachment-conflicts-need-an-editable-target-folder.md`), #185 (two input classes pass `check_typed_name`) and #186 (a failed `move_asset` does not stop its origin's delete). Research while answering Hashi found a fourth: Pass 2's vault-occupancy guard does not cover `move_asset`. |
| 2026-10-11 | Accept `proposed_dir`, released as a required-nullable field under wire `schema_version` 4 | Owner. Hashi's preferred shape (matches `proposed_name`); the change is coordinated either way because `attachment_conflicts[]` items are `additionalProperties: false` on their side. The markdown gets an editable folder counterpart and the inventory a new row. |
| 2026-10-11 | Pass 2 validates `move_asset` destinations against the vault | Owner, after the finding that `validate_destinations` claims only `move_note` and `create_moc` (`render_actions.py:1306`): an owner-typed name onto an occupied file reaches the wire unchecked, fails at apply, and — through #186 — still deletes its origin. |
| 2026-10-11 | Path-qualified embed only when the final basename is not unique in the vault | Owner, choosing this over "Hashi measures first" and "path whenever a folder was picked". Bare basename stays the default (owner ruling 2026-09-27). Requires a vault-wide basename check through Kado; Obsidian's resolution of an ambiguous basename is not measured by Tomo. |
| 2026-10-11 | #185: one new refusal reason covering both whitespace padding and `# ^ [ ]` | Owner. `FORBIDDEN_CHARS` is not widened (it also feeds `sanitize_stem`) and `forbidden_character` is not reused (its prose is false for these four characters). |
| 2026-10-11 | #186: option 1 — an origin's `delete_source` depends on its `move_asset` actions too | Owner. The executor's existing `skipped-dependency` cascade does the rest with no Hashi change. The proposal then goes to Kokoro, which owes ADR-029's open item a position once Tomo proposes one. |
| 2026-10-11 | Research done — four perspectives, kept in full in `research.md` | Technical, integration, performance/Kado, requirements. Forced four owner decisions (below) and surfaced five pre-existing gaps. |
| 2026-10-11 | The folder gets its own editable markdown line | Owner. Keeps the 2026-10-02 ruling intact: a folder typed into the rename line's backticks still refuses `separator_present`. Costs one new parser literal, carried by the new inventory row's `parser_label`. |
| 2026-10-11 | `ignore` stays exempt from Pass 2's vault check | Owner. Its move is still sent unchanged (037 F3-AC3 preserved); with #186 in place a failed apply now keeps the origin note instead of deleting it. |
| 2026-10-11 | A `move_asset` dropped by the vault check holds its owning notes | Owner. Same treatment as a refused typed name (038 ADR-6): nothing of that item is filed, the owner is told. |
| 2026-10-11 | When Kado cannot be consulted: path-qualify the embed, report the target as unchecked, still emit the move | Owner, choosing the cautious direction over 037 F1-AC5's silent degrade. A path-qualified embed resolves whatever else is in the vault; #186 protects the origin if the unchecked move then fails. |
| 2026-10-11 | Defaults accepted without objection | Folder refusal classes (`..`, leading `/`, `\\`, `~`, `./`, empty segment, segment-edge whitespace, forbidden characters, trailing `/`, the inbox or below) refuse, never repair; a non-existent folder is allowed and reported as "will be created"; the path-qualified embed rule covers every attachment the run files; Keep in inbox is unchanged; the vendored consumer suggestions schema is refreshed to v3 first; empty typed name, fan-wire conflicts, edited-wire schema validation and the Force Atomic bypass stay in the backlog. |
| 2026-10-11 | A folder with an empty name on the "no free name" line is refused as blank | Owner, over the consumer's implied reading that a folder alone resolves the conflict. 038's no-substitution contract wins; typing the original name back in remains valid (F1-AC10). PRD F1-AC11. |
| 2026-10-11 | PRD approved | 51 criteria. Phase moves to SDD. |
| 2026-10-12 | SDD approved — all 10 ADRs confirmed | Central choice ADR-1: one attachment plan decided before the render loop, with the embed rewrite and the move builder as its readers — closes `backlog.md:1917` and `:1956` on the way. ADR-10 changes C1, so the Kokoro design-time handoff (CON-2) precedes implementation. |

## Context

Verified before opening (2026-10-11):

- `proposed_name` is consumed only when `remedy` is `rename` (`render_actions.py:849/886`, `embed_rewrite.py:136`) — Hashi's §4 question.
- The markdown shows the target folder but does not let the owner change it: only the prefix Tomo printed is stripped, any other folder is refused `separator_present` (`suggestion-parser.py:2530`, owner ruling 2026-10-02).
- Pass 1's free-name search consults only the asset folder's listing (`suggestions-reducer.py:698`), never the vault.

---
*This file is managed by the xdd-meta skill.*
