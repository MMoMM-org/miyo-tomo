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
| 2 | **Orphan** | no links at all | `kado-graph-audit` `orphans[]` | `link_to_moc` or flag | 🔧 actionable |
| 3 | **Broken `up::`** | `up::` targets a non-existent MOC | cache / graph | fix or remove `up::` (modify) | 🔧 actionable |
| 4 | **Dead wikilink** | `[[X]]` target missing | `kado-graph-audit` `deadLinks[]` | fix or remove link (modify) | 🔧 actionable |
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
- **`kado-graph-audit`** (Kado v1.2.0, shipped) — one vault-wide call returning all orphans +
  all dead wikilinks. Covers checks 2, 4. See below.

### Link graph — `kado-graph-audit` (SHIPPED, Kado v1.2.0)

`kado-graph` is **per-note** (`path` required): a whole-vault audit would be O(N) Kado calls
(429 risk on large vaults). We requested a vault-wide bulk operation; **Kado shipped it** as a
dedicated read-only tool **`kado-graph-audit`** in **v1.2.0** (Kado #98/PR #99), answered from
Obsidian's in-memory `metadataCache` (`resolvedLinks`/`unresolvedLinks`) — O(N)→O(1), no
per-note disk reads. The dependency is **satisfied** — garden-audit builds against the real tool.

**Input:** `{ include?: ("orphans"|"deadLinks")[], limit?, cursor? }` — both arrays in one call
by default; `include` narrows to one axis; `limit`/`cursor` paginate.

**Response contract (final, as shipped):**

```json
{
  "operation": "audit-graph",
  "orphans":    [ { "path": "Notes/Foo.md" } ],
  "deadLinks":  [ { "source": "Notes/Bar.md", "target": "Missing Note", "count": 2 } ],
  "total":      { "orphans": 12, "deadLinks": 47 },
  "cursor":     null,
  "truncated":  false
}
```

- `orphans[].path` — note with zero resolved links in AND out (= our **orphan**, check 2).
- `deadLinks[].source` — note containing the unresolved link; `.target` — raw unresolved link
  **text** (not a path, mirrors per-note `dangling`); `.count` — occurrences in that source
  (= our **dead wikilink**, check 4).
- `total` — post-ACL counts before pagination (denominator / progress).
- `cursor`/`truncated` — pagination; orphans emitted first then deadLinks; concatenate pages
  until `cursor` is `null`. A no-`limit` call returns everything in one page (normal vaults).

**ACL:** orphans gated on their own path, deadLinks on their `source` path; `total` is post-ACL.
Nodes outside the key's ACL are silently omitted — the audit reports only what the key can see.

**Index-lag caveat (inherited, by design):** the tool reads Obsidian's in-memory link maps, so
right after an Obsidian restart or a large *external* (outside-Obsidian) bulk change, a note may
transiently read as orphaned or a just-fixed link as still dead until reindex settles. No data
risk; steady-state in-Obsidian edits reflect promptly. Garden-audit should surface this as a
"results reflect the current index" note rather than treat a single run as ground truth.

Full schema + examples: Kado `docs/api-reference.md` → "Tool: kado-graph-audit".

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
- Reuse: `orphan_link.py`, `instruction-render`, the Hashi wire, `moc_cache_loader`,
  **`kado-graph-audit`** (Kado v1.2.0).

## Sequencing / dependency

v1 = all six checks in one release. The one cross-repo dependency (a vault-wide link-graph op)
is **already satisfied**: the `_outbox/for-kado/` handoff was authored alongside this spec, Kado
confirmed the contract and **shipped `kado-graph-audit` in v1.2.0** the same day (Kado #98/#99).
Nothing blocks the build — garden-audit calls the real tool.

## Approaches considered

- **Output surface:** new report doc (chosen) vs. reuse `/moc-propose` surface vs. hybrid.
  Chosen because garden-audit findings are heterogeneous (orphans, dupes, dead links, stale
  MOCs) — the moc-proposal surface only fits unparented→link. A dedicated report handles all
  categories and advisory-only items cleanly, while still reusing the Pass-2 apply machinery.
- **Link graph:** bulk Kado op (chosen) vs. per-note O(N) `kado-graph` vs. bulk-with-fallback.
  Chosen because Obsidian's `metadataCache` makes the bulk op trivial for Kado (O(1)) and avoids
  the 429 risk of hundreds of per-note calls; the cross-repo turnaround is fast (same owner).

## Notes for the PLAN phase (from spec review)

- **Bulk-op contract is DEFINED (no longer blocking).** Checks 2 (orphan) and 4 (dead wikilink)
  consume `kado-graph-audit` (Kado v1.2.0, shipped). The response shape is final — see the
  "Link graph" section above and Kado `docs/api-reference.md`. PLAN should add an early
  integration task to write a thin `kado_client` wrapper for the tool + fixtures from a real
  response, but there is no contract negotiation left. Watch the camelCase `deadLinks` field and
  the cursor-pagination (orphans-first-then-deadLinks) ordering.
- **Pin the check-3 modify action.** Check 3 (broken `up::`) fixes via a Hashi *modify* action,
  but the exact existing action is not yet named (check 1 names `link_to_moc` explicitly). PLAN
  should pin which shipped Hashi modify action carries "fix or remove a broken `up::`", the same
  way check 1 is pinned.

## Parking lot (explicitly deferred — do NOT expand v1)

- **Auto-fix for advisory checks** — rename/merge for duplicate stems; archive-move for stale
  MOCs. Needs new Hashi action types + human-judgment UX. Revisit post-v1.
- **Periodic/scheduled invocation** — v1 is on-demand `/garden-audit` only. A scheduled
  cadence (weekly vault-health) can layer on later.
- **Per-note `kado-graph` fallback** — YAGNI: the bulk `kado-graph-audit` shipped (Kado v1.2.0),
  so no O(N) per-note fallback is needed.
- **Incremental audit** (`filter.modifiedAfter`, F-48) — cheaper repeat-runs; separate epic-#16
  Could item.
- **Configurable stale threshold** (N months) — start with a sensible hardcoded default;
  config surface deferred (same pattern as other 0.6/thresholds in the pipeline).
