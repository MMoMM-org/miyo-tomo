# Knowledge-Garden Audit Skill (F-44 / #30) — Brainstorm Design

> Created: 2026-07-18 via `/brainstorm`.
> Roadmap item 2 (`docs/XDD/roadmap-obsidian-power.md`), P1-should, strict-sequenced.
> Predecessor shipped: MOC-creation track (`/moc-propose` + `moc-architect` + `vault-explorer`).
> This is the validated design contract for `/xdd`. Per-item detail flows into the XDD spec on pickup.

## Purpose

Turn Tomo from an inbox processor into a proactive vault-health assistant. A user-invoked,
whole-vault audit surfaces structural problems (disconnected notes, broken relations, dead
links, duplicates, stale MOCs), presents them in a prioritised review document, and — for the
fixable subset — applies fixes through the existing 2-pass / Hashi machinery. The report is
JSON-wire-backed (ADR-026) so Hashi can build an editor over it.

## Terminology (resolved in brainstorm)

Two distinct concepts that the existing `orphan_link.py` naming conflated:

- **Orphan** — a note with **no links at all** (no incoming backlinks, no outgoing links);
  completely disconnected from the graph. Needs the link graph to detect.
- **Unparented** — a note that **has links but no `up::`** (not filed under any MOC). This is
  what `orphan_link.py` currently detects (`up_state == "absent"`). NOT the same as an orphan.

## v1 Scope — six checks

| # | Check | Meaning | Data source | Fix action | Type |
|---|-------|---------|-------------|-----------|------|
| 1 | **Unparented** | has links, no `up::` | discovery cache (`orphan_link.py`, reuse) | `link_to_moc` (add `up::`) | 🔧 actionable |
| 2 | **Orphan** | no links at all | **new Kado bulk op** | `link_to_moc` or flag | 🔧 actionable |
| 3 | **Broken `up::`** | `up::` targets a non-existent MOC | cache / graph | fix or remove `up::` (modify) | 🔧 actionable |
| 4 | **Dead wikilink** | `[[X]]` target missing | **new Kado bulk op** | fix or remove link (modify) | 🔧 actionable |
| 5 | **Duplicate stems** | ≥2 notes share a filename stem | discovery cache (enumerate) | — (rename/merge needs human) | 📋 advisory |
| 6 | **Stale MOC** | MOC not edited > N months | `listDir` `modified` timestamps | — (review flag) | 📋 advisory |

**Advisory checks (5, 6) are report-only** — no Hashi apply. Rename/merge and MOC archival
need human judgment; the report surfaces them prioritised but does not auto-fix (v1).

## Data acquisition

Three sources, chosen by cost:

- **Discovery cache** (`moc_cache_loader` → `cache.entries`) — cheap. Provides per entry:
  `stem, path, kind (note/moc), up_state, topics, tags, title`. Covers checks 1, 3, 5.
- **`listDir` `modified` timestamps** — one call over the MOC folder(s). Covers check 6
  (stale MOCs). Cheap; no per-note read.
- **New Kado bulk graph operation** — covers checks 2, 4. See below.

### Link graph — new Kado bulk operation (cross-repo)

`kado-graph` today is **per-note** (`path` required): a whole-vault audit would be O(N) Kado
calls (429 risk on large vaults). Obsidian's `metadataCache` already holds `resolvedLinks` +
`unresolvedLinks` for the **whole vault in memory**, so Kado can expose a vault-wide operation
returning all unresolved links (dead wikilinks) and all orphans (no resolved links in/out) in
**one call** — O(N)→O(1).

**Decision:** request this bulk operation from Kado via the MiYo handoff protocol
(`_outbox/for-kado/`). Related to Kado issue #82 ("Adopt kado-graph"). The garden-audit spec
depends on it; the handoff is written as part of this work so the dependency lands quickly.
Key-scoping caveat: nodes outside the audit key's ACL are silently omitted (mirrors the
per-note `kado-graph` behaviour) — the audit reports only what the key can see.

## Output — two artifacts (ADR-026 parity)

1. **Markdown report doc** — the human review surface. Prioritised sections per finding
   category; fixable findings carry a checkbox + placement/action hint (mirrors the
   suggestions-doc pattern). Human-editable.
2. **JSON wire** (`garden-audit-wire.json`) — a complete structured mirror of the review
   surface, so Hashi can build a JSON-only editor over it (ADR-026, same pattern as the
   suggestions/fan wire). This is a hard requirement: the apply path must go to Hashi via JSON.

On approval, the fixable findings render into the **existing instruction-set format** via
`instruction-render` → the Hashi wire. Garden-audit builds **no new apply path** — it becomes a
new *source* feeding the shipped Pass-2 render/apply machinery. Unparented→`link_to_moc` maps
1:1 onto an existing Hashi action; broken-`up::` / dead-link map to modify actions.

## Prioritisation

Order findings by integrity impact:
integrity breaks (broken `up::`, dead links) > structure gaps (unparented, orphan) >
advisory (stale MOC, duplicate stems).

## New components

- `garden-audit.py` — scan script; orchestrates cache + Kado bulk op + `listDir`, emits findings.
- `garden-auditor.md` — agent; classifies/prioritises findings, applies LLM judgment on
  ambiguous cases (e.g. which MOC an orphan should link to — reuse `orphan_link.py` scoring).
- `/garden-audit` — command shim (mirrors `/moc-propose`), on-demand, whole-vault.
- **Kado handoff** (`_outbox/for-kado/`) — request the bulk graph operation.
- Reuse: `orphan_link.py`, `instruction-render`, the Hashi wire, `moc_cache_loader`.

## Sequencing / dependency

v1 = all six checks in one release, **blocking on the Kado bulk op** (cross-repo). The handoff
is authored alongside this spec so the new Kado version lands quickly (Marcus owns Kado too).

## Approaches considered

- **Output surface:** new report doc (chosen) vs. reuse `/moc-propose` surface vs. hybrid.
  Chosen because garden-audit findings are heterogeneous (orphans, dupes, dead links, stale
  MOCs) — the moc-proposal surface only fits unparented→link. A dedicated report handles all
  categories and advisory-only items cleanly, while still reusing the Pass-2 apply machinery.
- **Link graph:** bulk Kado op (chosen) vs. per-note O(N) `kado-graph` vs. bulk-with-fallback.
  Chosen because Obsidian's `metadataCache` makes the bulk op trivial for Kado (O(1)) and avoids
  the 429 risk of hundreds of per-note calls; the cross-repo turnaround is fast (same owner).

## Notes for the PLAN phase (from spec review)

- **Bulk-op response contract is an early, blocking task.** Checks 2 (orphan) and 4 (dead
  wikilink) both block on the new Kado operation, so PLAN must define its JSON response shape
  (field names / schema for the dead-links and orphans arrays) up front — inside the
  `_outbox/for-kado/` handoff artifact — before the consuming garden-audit code is written.
- **Pin the check-3 modify action.** Check 3 (broken `up::`) fixes via a Hashi *modify* action,
  but the exact existing action is not yet named (check 1 names `link_to_moc` explicitly). PLAN
  should pin which shipped Hashi modify action carries "fix or remove a broken `up::`", the same
  way check 1 is pinned.

## Parking lot (explicitly deferred — do NOT expand v1)

- **Auto-fix for advisory checks** — rename/merge for duplicate stems; archive-move for stale
  MOCs. Needs new Hashi action types + human-judgment UX. Revisit post-v1.
- **Periodic/scheduled invocation** — v1 is on-demand `/garden-audit` only. A scheduled
  cadence (weekly vault-health) can layer on later.
- **Per-note `kado-graph` fallback** — YAGNI given the bulk op is being requested and lands fast.
- **Incremental audit** (`filter.modifiedAfter`, F-48) — cheaper repeat-runs; separate epic-#16
  Could item.
- **Configurable stale threshold** (N months) — start with a sensible hardcoded default;
  config surface deferred (same pattern as other 0.6/thresholds in the pipeline).
