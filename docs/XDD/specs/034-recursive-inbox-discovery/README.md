# Specification: 034-recursive-inbox-discovery

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-05 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-09-06 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features (6 Must, 1 Should, 1 Could), 21 acceptance criteria, 6 business rules, 6 edge cases, 3 open questions |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-05 | **Scoped as a feature (recursive discovery), not as an enabler (path-derived item key)** | The path-safe item key is the necessary enabler, but shipping it alone would repeat the failure spec 031 recorded on this same date: five phases built against a field nothing populated, every task passing both review gates because each correctly implemented its own local contract. An enabler with no consumer cannot be live-validated. Framing the spec around the user-visible behaviour gives the key rework something that exercises it. |
| 2026-09-05 | **Agent Team mode for research** | The question crosses the analyst contract, fan-out cost, parser reconciliation, and the first run over a long-ignored subfolder backlog — perspectives that can contradict each other and are better reconciled between researchers than after the fact. |
| 2026-09-06 | **Item key becomes path-derived AND the field is renamed** | No schema change is strictly required — `stem` is an unconstrained `{"type": "string", "minLength": 1}` in every schema that carries it, so a path-derived value validates today. The rename is chosen anyway: a field named `stem` holding `places__dresden` misleads every future reader, and two separate defects this week (#162's dead renderer, #165's unreachable branch) cost time precisely because a name no longer matched reality. Cost accepted: a schema-version bump across `item-result`, `state-entry`, `suggestions-doc`, `suggestions-wire`, `routing-plan`, plus `validate-result.py`'s `REQUIRED_TOP` and the analyst's written contract. |
| 2026-09-06 | **No volume cap — measure instead** | The unbounded-batch behaviour already exists today for a flat inbox with many untriaged files; recursion does not create it, it makes a hidden backlog visible. Adding a cap would be new user-facing behaviour justified by no measurement: the largest clean run on record is 21 items at ~$0.61/item, and nothing above that has ever been exercised. The spec logs items and cost per run instead, so a future cap can be set from data rather than from a guess. |
| 2026-09-06 | **All subfolders discovered, no exclusion mechanism** | No inbox exclusion mechanism exists today (`garden-audit-exclusions.yaml` is bound to `/garden-audit` only, zero references in `inbox-triage.py`), so building one is net-new surface for a problem that does not exist yet: attachment folders hold no `.md` files. YAGNI. Revisit if a subfolder ever needs to be hidden from triage. |
| 2026-09-06 | **Hashi gets a handoff, not an ADR** | The wire contract does not change: `render_helpers._stem()` (`:12-18`) flattens every emitted `source_stem`/`target_stem` to a bare filename at the emission boundary (`render_actions.py:857,873,888`), so Tomo's internal key never crosses. But two same-stem items still produce indistinguishable values there, and Hashi joins on that field (`forceAtomicSync.ts:47`) and renders it as a note link (`DailyTab.ts:229`). That is a behavioural consequence in a sibling component, which Constitution L2 says must be made visible — a `_outbox/for-hashi/` handoff, not an ADR-gated redesign. |
| 2026-09-06 | **Correction: this is not a cross-repo contract change** | Recorded because it was asserted as one mid-research before being checked. The schema researcher read the schemas and marked Hashi's TypeScript consumer unverified; the orchestrator read the consumer and not the schemas. Each half alone supported a wrong conclusion — the consumer join looked like a contract dependency, the schema alone looked like a non-issue. Only the emission-boundary flattening, which neither had looked at, settles it. Lesson for the SDD: a boundary question needs the producer, the schema, and the consumer read together. |

## Context

Closes #163 and #164.

**The two halves of the inbox disagree about what it contains.** `discover_files`
(`tomo/scripts/inbox-triage.py:172`) calls `list_dir(inbox_path, depth=1)`, so only
inbox-root notes become sources. `resolve_inbox_attachments`, added by spec 031, uses
`list_notes(inbox_path, fields=["links"])`, which is recursive. A note in
`100 Inbox/Places/` therefore has its attachments resolved and is then never triaged —
the work is computed and discarded (#164).

Marcus confirmed on 2026-09-05 that he does put notes in inbox subfolders, so the
documents are right and the pipeline is too narrow. Spec 031's AC-F2.1 and SDD
walkthrough both use `100 Inbox/Places/Dresden.md` as a source note (#163).

**The blocker is the item key, not the depth.** `_stem_of`
(`tomo/scripts/suggestion-parser.py:1971`) is `src.rsplit("/", 1)[-1]`, `.md` stripped,
lowercased — the path is discarded. A flat inbox is a single namespace, so stems are
unique today by accident of layout rather than by construction. Recursing makes
`100 Inbox/Places/Dresden.md` and `100 Inbox/Reise/Dresden.md` the same key.

Consequences, worst first:

1. **The fan-out overwrites its own results.** Each analyst subagent writes
   `tomo-tmp/items/<stem>.result.json` (`inbox-analyst.md:37`, read back at
   `suggestions-reducer.py:1776`). Two same-stem notes means two subagents writing the
   same path in parallel — one silently clobbers the other. No error, no warning.
2. **Force-atomic and fan reconciliation collide.** `sections_by_stem`,
   `resolve_sections_by_stem`, `already_in`, `seen_pending`, `_stem_to_id` are all
   stem-keyed (21 sites in `suggestion-parser.py`). Same area as the livelock fixed in
   #165.
3. **Audio/transcript sibling matching** pairs by stem and would widen across folders.

The item key must become path-derived and threaded through the fan-out contract, the
per-item result filenames, the reducer, the parser's reconciliation, and the wire. The
analyst's written contract changes, so this is not purely deterministic-side work.

**Open questions for the PRD to settle**, not assumed here:

- What happens the first time a long-ignored subfolder backlog is triaged in one run.
  None of those notes carry `tomo.state`, so they all arrive as `new_sources` at once.
- Whether every subfolder is in scope, or whether some are structurally excluded
  (attachment folders such as `Images/`, `Scans/`, `assets/` hold no notes today, but
  an archive subfolder would be a different matter).
- How the standing "near MVP, additive only" constraint applies to an internal key
  change that is not additive.

---
*This file is managed by the xdd-meta skill.*

## Research findings (2026-09-06)

Four researchers: requirements, technical, performance, contracts. Every claim below was
re-verified against the source by the orchestrator before being recorded; anything that
could not be settled is marked **unverified** rather than smoothed over.

### Two independent blockers, not one

**B1 — the item key is a bare stem.** `_stem_of` (`suggestion-parser.py:1971`) is
`src.rsplit("/", 1)[-1]`, `.md` stripped, lowercased. A flat inbox makes stems unique by
accident of layout, not by construction.

**B2 — force-atomic reconstructs the note path from the stem.** A STRICT block in
`tomo/dot_claude/skills/force-atomic-handling/SKILL.md:55-60` mandates
`path = <inbox_path>/<stem>.md`. For `100 Inbox/Places/Dresden.md` that yields
`100 Inbox/Dresden.md`, which does not exist. **This breaks for a single subfolder note
with no name collision at all** — B2 is not a special case of B1. The STRICT block exists
because `source_path` there is the suggestions document, not the note; the stem was the
escape hatch, and it only works on a flat inbox.

### Blast radius of B1

| Site | What is keyed | Consequence of a collision |
|---|---|---|
| `suggestion-parser.py:1971` `_stem_of` | key derivation | root cause; all sites below inherit it |
| `suggestion-parser.py` × ~20 | `sections_by_stem`, `resolve_sections_by_stem`, `already_in`, `seen_pending`, `_stem_to_id` | two notes merge into one bucket; Force-Atomic promotes the wrong one; a MOC binds to the wrong source |
| `suggestions-reducer.py:1638→1715` | `items_dir / f"{stem}.result.json"` — a **filename** | two analyst subagents write the same path in parallel; one silently clobbers the other |
| `state-update.py:39,52,76,82` | `inbox-state.jsonl`, append-only, joined on `stem` | "last line wins" hides one item's real status |
| `mark-captured.py:44-49` → `:161` | `state[entry["stem"]] = entry`, then `client.write_frontmatter(...)` | **writes `tomo.state: captured` onto the wrong note in the vault** — the only consequence that mutates user data |
| `instructions-diff.py:105-111,281,397` | a locally duplicated `_stem()`, both sides of the coverage audit | both sides collapse identically, so the audit reports false *full coverage* rather than a mismatch |
| `inbox-triage.py:526-541` `check_audio` | `md_stems`, a flat set with no path component | an audio file is judged already-transcribed because an unrelated note elsewhere shares its stem |
| `validate-result.py:29` `REQUIRED_TOP` | validates `stem` present | second enforcement point for the same contract |

`mark-captured.py` is the one the key design must make impossible by construction, not
merely unlikely — everything else corrupts bookkeeping, that one corrupts the vault.

### Recursion is cheaper on discovery, not dearer

A recursive `list_dir` over the inbox **already runs in every pass**:
`build_attachment_index` (`inbox-triage.py:200-217`) calls `client.list_dir(inbox_path)`
with no depth, one call per run. `build_inbox_index`
(`lib/attachment_index.py:41-61`) consumes the same `[{path, type}]` shape that
`discover_files` partitions, so one listing could feed both — base Kado calls **3 → 2**.

Traced safe across every consumer of `discover_files`' output (`compute_new_sources`,
`check_audio`, `resolve_handlers`, `TriageState`). One thing to reconcile first: the two
file-type filters differ — `discover_files:178` is `(item.get("type") or "").lower()`
(case-insensitive, None-safe), `attachment_index.py:53` is exact-match. Kado emits
lowercase literals (`Kado/src/obsidian/search-adapter.ts:194,247`), so this is latent
robustness, not a live bug — but pick one filter before sharing a listing.

*Unverified:* whether the tag-handler registry's own matching makes any path-prefix
assumption. `resolve_handlers` matches on frontmatter, so this is low-risk, not confirmed.

### Cost

`_count_kado_calls` (`inbox-triage.py:1738-1778`) = 3 base + 7 byFrontmatter + per-item
reads. The `kado_calls=20` figure for spec 031's 4-item run is consistent with it.

The counter is **script-level only** — an analyst subagent's own `kado-read` (one per item,
`inbox-analyst.md:69`) is made over MCP by a different agent and is invisible to it. What
scales with recursion is fan-out, not discovery: one `Agent()` dispatch per item, batched
`tomo.suggestions.parallel` (default 5) concurrently, batches sequential. Measured
**$0.59–0.67 per item**; largest clean run on record 21 items at $0.61/item.

### No cap anywhere

`_search_all` (`kado_client.py:583-619`) follows every cursor page and merges them into one
unbounded in-memory list; `limit` is page size only. `determine_action` has no size branch.
`suggestions-render.py` has no size guard. The only throttle in the pipeline is
`tomo.suggestions.parallel`, which limits concurrency, not volume.

The eager merge is a consumer-side memory risk. It is **not** a Constitution L1 violation —
that rule binds the component *producing* a large result set, and Kado paginates correctly;
Tomo's client flattens it for its own convenience.

### Hashi

The wire never sees the internal key: `render_helpers._stem()` (`:12-18`) flattens every
emitted `source_stem`/`target_stem` to a bare filename at the emission boundary
(`render_actions.py:857,873,888`), and Hashi's schema types both as unconstrained strings
(`instructions.schema.json:170,189`). So no schema change and no contract change.

Two same-stem items nevertheless produce indistinguishable values there, and Hashi joins on
that field (`forceAtomicSync.ts:47`, whose own comment says "the wire has no other" key) and
renders it as a clickable note link (`DailyTab.ts:229`). Behavioural, sibling-component —
hence the handoff decision above.
