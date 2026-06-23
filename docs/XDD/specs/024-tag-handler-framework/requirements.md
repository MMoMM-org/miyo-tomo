# PRD: Tag-Handler Framework (024)

> Source of truth for the locked design: GitHub issue **#47** comment (2026-06-23 brainstorm).
> Status: PRD. Research phase skipped — design was resolved in the brainstorm, no open unknowns.

## 1. Problem

External MiYo tools write notes into the Obsidian vault inbox tagged `MiYo/<Feature>/…`.
**Tomo Tsukai** is the first: it captures coding events as inbox notes tagged `MiYo/Tsukai/<repo>`
with a `category` field, and explicitly delegates routing/enrichment to Tomo
(Tsukai spec `001-capture-insight-toolkit`; "Tomo owns downstream handling").

Today Tomo treats these as generic inbox items — it has no awareness of the tag and no way for the
user to say "notes tagged X should be handled like Y". The user wants a **general, extensible**
mechanism: per-feature handlers that define what Tomo does with a tagged note, authored by the
user themselves — but **skill-author is not installed in Tomo**, so handlers cannot be hand-written
skills.

## 2. Goals

- **G1** Recognize inbox notes carrying a registered `MiYo/<Feature>` tag during `/inbox` triage.
- **G2** Let the user define handler behavior as **pure data** (no skill authoring), via a wizard.
- **G3** One generic interpreter applies the matching handler in the existing 2-pass pipeline.
- **G4** For Tsukai (handler #1): merge a batch's captures per target note into **one** logical,
  LLM-composed status update inserted under a marker in a repo-mapped note.
- **G5** Extensible action registry — adding a handler or a new action type needs no pipeline rewrite.

## 3. Non-Goals (v1)

- **NG1** No new external surface; Tomo still only writes to the inbox at Pass-1 (instructions applied
  downstream by Hashi/manual, as today).
- **NG2** No deep tag hierarchy parsing beyond named suffix segments (Tsukai's tag is fixed 2-segment).
- **NG3** No per-repo handler *variants* in v1 — one handler per feature; per-repo differences are
  expressed as data inside the handler (`repo_note_map`), not as separate handlers.
- **NG4** Handlers do not create vault structure beyond the "create it first" guard (Hashi modifies,
  never creates).

## 4. Users & Context

- **Primary user:** Marcus (vault owner) — authors handlers and reviews suggestions.
- **Producers:** Tsukai (today) and future `MiYo/<Feature>` tools.
- **Pipeline:** `/inbox` 2-pass model — Pass-1 suggestions (user approves) → Pass-2 instructions
  (applied by Hashi/manual). All handler output flows through this existing review gate.

## 5. Functional Requirements

### Detection & registry
- **FR-1** A handler registry lives at `config/tag-handlers/<feature>.json` (synced to the instance).
- **FR-2** Each handler declares `match: { tag_prefix, capture_segments[], read_fields[] }`.
  Triage matches an inbox note's tags against every registered `tag_prefix`; on match it binds the
  named `capture_segments` from the tag suffix (e.g. `repo`) and reads the declared `read_fields`
  from frontmatter (e.g. `category`).
- **FR-3** Triage marks a matched item in `routing-plan.json` with its `handler` id and bound vars;
  unmatched items follow today's path unchanged.

### Actions
- **FR-4** A handler declares one `action` from the v1 registry: `insert_under_marker`,
  `route_to_folder`, `link_to_moc`, `enrich_frontmatter`.
- **FR-5** Each action has a **compose** step (either a mechanical field-template, e.g.
  `["created","Summary","link"]`, or an **LLM directive** string) and a **place** step
  (action-specific target resolution).
- **FR-6** `insert_under_marker` resolves a target note via `target: { by: <segment>, map: {…} }`,
  finds the configured `marker` heading, and inserts the composed content beneath it.

### Aggregation
- **FR-7** Within one `/inbox` batch, handled items are **grouped by (handler, resolved target)**.
- **FR-8** For an LLM-directive compose, the group's items are passed together so the model composes
  **one** status update with full context — never one output per source item.

### Pipeline integration
- **FR-9** Pass-1 surfaces each group as a reviewable suggestion (proposed update + target + marker)
  in the suggestions doc; the user approves as with any suggestion.
- **FR-10** Pass-2 renders an approved group into a Hashi `insert_under_marker` instruction
  (reusing the existing `log_entry`/anchor-insert capability).

### Guards
- **FR-11** Target note missing → surface a "create it first" checkbox (daily-note-existence pattern);
  the entry is skipped until the note exists.
- **FR-12** Marker missing in an existing target note → surface an error in the suggestion
  (do not silently append or relocate).

### Authoring
- **FR-13** A `tomo-tag-handler-wizard` skill walks the user through creating/editing a handler JSON
  via AskUserQuestion (mirrors `tomo-trackers-wizard` / `tomo-daily-log-wizard`); no skill authoring.
- **FR-14** Tomo ships a Tsukai reference handler so the feature works out-of-the-box once the user
  fills the `repo_note_map`.

## 6. Tsukai — Handler #1 (concrete)

```json
{
  "id": "tsukai",
  "enabled": true,
  "match": { "tag_prefix": "MiYo/Tsukai/", "capture_segments": ["repo"], "read_fields": ["category"] },
  "action": "insert_under_marker",
  "target": { "by": "repo", "map": { "Tomo": "Efforts/…/Tomo Dev Log.md" } },
  "marker": "## Captures",
  "placement": "inside",
  "compose": "Synthesize the batch's captures into one dated logical status update, grouped by category."
}
```

> `target.map` is the field FR-14/NG3 refer to in prose as `repo_note_map` — same field, keyed by `target.by`.

## 7. Acceptance Criteria

- [ ] **AC-1** Tomo identifies inbox notes carrying a registered Tsukai tag (`MiYo/Tsukai/` prefix).
- [ ] **AC-2** A user-authored handler JSON (via wizard) drives detection + handling for a global default.
- [ ] **AC-3** Three Tsukai captures for one repo in a batch produce **one** merged status update
  suggestion targeting the repo-mapped note under `## Captures`.
- [ ] **AC-4** Missing target note → "create it first" checkbox; missing marker → error.
- [ ] **AC-5** A `/inbox` run with **no** registered handlers is byte-identical to current behavior.
- [ ] **AC-6** Documented in Tomo's config/inbox docs.

## 8. Constraints

- **C1** Additive-only on hot paths (`inbox-triage`, `inbox-analyst`, `suggestions-reducer`,
  `instruction-render`); no behavior change when the registry is empty (AC-5).
- **C2** Handlers are pure data; all logic lives in scripts/skills (Tomo architecture principle).
- **C3** Privacy/MVP boundary unchanged: Pass-1 writes only to the inbox; Hashi/manual applies Pass-2.

## 9. Open Questions (deferred)

- **OQ-1** Per-repo handler variants vs single handler with `repo_note_map` (NG3 picks the latter for v1).
- **OQ-2** Whether `route_to_folder` / `link_to_moc` / `enrich_frontmatter` ship enabled in v1 or are
  registry-declared-but-stubbed (decide in SDD/PLAN).
- **OQ-3** Update cadence: append a new dated status block vs update-in-place under the marker
  (decide in SDD).

## References
- GitHub **miyo-tomo#47** — Tomo handling for Tsukai-tagged inbox notes (locked design in comment)
- Tsukai spec `001-capture-insight-toolkit` (PRD §Feature 7; note-shape.md)
- Kokoro **ADR-020** — Tomo Tsukai charter
