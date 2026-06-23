# SDD: Tag-Handler Framework (024)

> Builds on `requirements.md`. Resolves OQ-1/2/3 and surfaces a cross-repo dependency.

## 1. Architecture

Three layers, plugged into the existing 2-pass `/inbox` pipeline. **Additive-only**: with an empty
`config/tag-handlers/` directory every code path is a no-op and a run is byte-identical to today (AC-5).

```
config/tag-handlers/<feature>.json   ← pure data (authored by wizard)
            │
   tag-handler-resolve.py            ← deterministic: load registry, match tags, bind vars, resolve target
            │
 ┌──────────┼───────────────────────────────────────────────┐
 │ triage   │ Pass-1 (compose)            │ Pass-2 (render)   │
 │ mark     │ group by (handler,target)   │ emit instruction  │
 │ handled  │ LLM merges → status update  │ → apply (see §6)   │
 └──────────┴─────────────────────────────┴───────────────────┘
```

## 2. Handler config schema (`config/tag-handlers/<feature>.json`)

```jsonc
{
  "id": "tsukai",                              // unique; also the routing-plan marker
  "enabled": true,
  "match": {
    "tag_prefix": "MiYo/Tsukai/",              // required
    "capture_segments": ["repo"],              // names for suffix path segments after the prefix
    "read_fields": ["category"]                // frontmatter fields exposed to compose
  },
  "action": "insert_under_marker",             // one of the v1 registry (§4)
  "target": { "by": "repo", "map": { "Tomo": "Efforts/…/Tomo Dev Log.md" } },
  "marker": "## Captures",
  "placement": "inside",                       // inside | before | after (anchor semantics, §5)
  "compose": "Synthesize the batch's captures into one dated status update, grouped by category."
}
```

- `compose` is **either** a string (LLM directive) **or** an array of field names (mechanical template) —
  expressed as a JSON-Schema `oneOf` (string xor array of strings) so T1.2 is unambiguous.
- `enabled` (default `true`): a `false` handler is skipped exactly like an invalid one (not matched, not
  an error).
- `marker` → `anchor.value` transform: strip a leading run of `#` plus the following space and trim
  (`"## Captures"` → `"Captures"`); heading level is **not** significant for matching.
- `target.map` is the per-feature mapping the PRD prose calls `repo_note_map` — they are the same field
  (`target.map`, keyed by `target.by`). The PRD prose name is an alias, not a separate key.
- A JSON Schema `tomo/schemas/tag-handler.schema.json` validates each file at load; an invalid handler
  is skipped with a logged warning (never aborts the run — additive-safety).

## 3. Deterministic resolver — `tomo/scripts/tag-handler-resolve.py`

Pure, no LLM, no network beyond the registry read.

**Input:** an inbox item's `{path, tags[], frontmatter{}}` + the loaded registry.
**Output (per matched item):**
```json
{ "handler": "tsukai", "vars": { "repo": "Tomo" },
  "fields": { "category": "feature" },
  "target_path": "Efforts/…/Tomo Dev Log.md", "marker": "## Captures",
  "action": "insert_under_marker", "placement": "inside",
  "compose": "<directive or field-list>" }
```
- Matching: first registered handler whose `tag_prefix` is a prefix of any tag wins (deterministic order
  = lexical by `id`). Binds `capture_segments` from the remaining tag path; pulls `read_fields` from frontmatter.
- Target resolution: `target.map[ vars[target.by] ]`. Unmapped key → `target_path=null` (surfaced, not crashed).

## 4. Action registry (resolves OQ-2)

| Action | v1 status | place semantics |
|--------|-----------|-----------------|
| `insert_under_marker` | **shipped** | content under a `marker` heading anchor in a mapped note |
| `route_to_folder` | declared, **deferred** | move note to a folder (reuses `move_note`) |
| `link_to_moc` | declared, **deferred** | reuses existing `link_to_moc` instruction |
| `enrich_frontmatter` | declared, **deferred** | reuses `add_relationship`/frontmatter merge |

Decision: ship **`insert_under_marker` only** in v1; the other three are registry-declared so handler
JSON can name them, but the resolver rejects a deferred action with a clear "not yet implemented" message.
The registry table is the single extension point.

## 5. Pipeline integration (additive)

### Triage — `inbox-triage.py`
After `compute_new_sources`, run `tag-handler-resolve` over each new source's tags+frontmatter. A match
adds a `handled[]` entry to `routing-plan.json` (`{path, handler, vars, target_path, action, …}`) and the
item is **excluded** from the generic `suggest` lane. No match → unchanged.

**Schema change required (not pure-additive):** `routing-plan.schema.json` has `additionalProperties:false`,
so it must be **extended** with a `handled[]` property (and the `action` enum may gain a `handle` value).
To preserve AC-5, triage **omits the `handled` key entirely when the registry is empty / no item matched**
— an empty `handled:[]` would still validate after the schema change, but emitting nothing keeps an
empty-registry run byte-identical to today (and schema-valid before the extension lands).

### Pass-1 — interpreter skill + compose
A thin `tag-handler-interpreter` skill (loaded by the suggestion-conductor when `routing-plan.handled`
is non-empty) groups `handled[]` by `(handler, target_path)`. For each group it dispatches **one** compose:
- LLM directive → one analyst/compose call receives the **whole group** (all captures' title/category/
  Summary/body) and returns one merged status-update markdown block (FR-8).
- Field template → mechanical join, no LLM.
The reducer renders each group as a suggestion item (proposed block + target + marker + an `Approve` box),
reusing the suggestions-doc format.

### Pass-2 — `instruction-render.py`
An approved group renders to an `insert_under_marker` instruction (§6) reusing the existing `anchor`
machinery (`type:"heading", value:"<marker w/o ##>"` + `placement`). Guards:
- **target_path missing on disk** → emit a "create it first" checkbox (daily-note-existence pattern,
  reducer); no instruction until it exists (FR-11).
- **marker not found in an existing target** → emit an error item, no instruction (FR-12).

### Update cadence (resolves OQ-3)
**Append a new dated status block** beneath the marker (`placement:"inside"` at top, or `"after"` the
marker heading), never replace existing content — preserves history; idempotency is the user's review.

## 6. The new instruction + cross-repo dependency

`insert_under_marker` is **not** expressible with the current Hashi vocabulary: `link_to_moc` is
**MOC-stem-scoped** (targets a MOC by stem, not an arbitrary note path) and `update_log_entry` is
**daily-note-scoped**. (`link_to_moc.line_to_add` may itself be multi-line — the blocker is the *target
scoping*, not line count.) It needs a new instruction action:

```jsonc
{ "id": "...", "action": "insert_under_marker",
  "target_path": "Efforts/…/Tomo Dev Log.md",
  "anchor": { "type": "heading", "value": "Captures" },
  "placement": "inside",
  "content": "<multi-line composed status update>" }
```

Note: `placement:"inside"` is today defined **callout-only** in Hashi; `inside` relative to a *heading*
anchor (content beneath the heading, above the next same-or-higher heading) is a **new semantic the
executor must define** — called out in the handoff.

**This is a cross-repo contract change** (`miyo-tomo-hashi` must implement the executor side) and per the
MiYo Constitution (L2 Architecture) must be reflected in **Kokoro** (the authoritative repo) — a concrete
ADR/design-note routed via `_outbox/for-kokoro/`, not folded into the Hashi handoff (PLAN T1.1).

**Phasing decision (confirmed 2026-06-23):** the Hashi `insert_under_marker` ask ships **first**
(PLAN T1.1) so the executor lands in parallel with Tomo's side — manual apply is only the **fallback** if
Hashi is late, not the planned interim. Tomo's side (detect → compose → render the instruction) is
cross-repo-independent and proceeds regardless; the only externally-blocked step is the *automated* apply
(T6.2). The Kokoro contract note is part of T1.1's done-definition (before/alongside implementation, L2).

## 7. Authoring — `tomo-tag-handler-wizard`

A user-invocable skill mirroring `tomo-trackers-wizard`: AskUserQuestion for `tag_prefix`, segments,
fields, action, target map, marker, compose directive → validates against `tag-handler.schema.json` →
writes `config/tag-handlers/<feature>.json` via `vault-config-writer`-style atomic write. No skill authoring.

## 8. Constitution alignment

- **Privacy/MVP (L1):** Pass-1 writes only inbox; Phase-1 apply is manual; no new external surface.
- **Architecture (L1/L2):** the Hashi action (Phase 2) is a documented cross-repo contract → Kokoro + handoff.
- **Code Quality (L2):** logic in `tag-handler-resolve.py` + interpreter skill; handlers are pure data.
- **Testing (L1):** resolver match/no-match + denial paths; empty-registry byte-identity (AC-5);
  guard paths (missing target, missing marker).

## 9. Risks

- **R1** LLM merge quality across many captures — mitigate with a bounded group size + the user-review gate.
- **R2** Tag-prefix collisions between handlers — deterministic lexical-by-id ordering + load-time warning.
- **R3** Phase-1 manual apply friction — acceptable for v1; Phase-2 Hashi action removes it.
- **R4** Resolver running on every new source adds cold-path cost — bounded (pure, no I/O beyond registry).

## 10. Open for PLAN
- Test fixtures for resolver (match/no-match/collision/unmapped-target).
- Whether the interpreter compose reuses the analyst dispatch or a dedicated lean compose call.
- `tag-handler.schema.json` field-level validation rules.
