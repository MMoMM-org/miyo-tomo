# Open Items Backlog

> **Open work now lives in GitHub Issues** — [MMoMM-org/miyo-tomo/issues](https://github.com/MMoMM-org/miyo-tomo/issues).
> Migrated 2026-06-03 after a full code-vs-backlog verification sweep.
> This file is now a slim **index + archive**: the GH mapping, the backburner (not migrated),
> the Done-record, deliberate design decisions, and design-note appendices.
> Maintained as a living document — when new post-MVP items appear, prefer opening a GitHub issue
> and recording the mapping here only if it needs backlog-level context.

## Active roadmap tracks

For the **Obsidian-power track** sequencing (MOC-creation, garden-audit, weekly-review, tag-audit, suggestions UX), see [`roadmap-obsidian-power.md`](roadmap-obsidian-power.md). The work items themselves are GitHub epics **#16** (Obsidian-Power Skills) and **#19** (Suggestions Doc UX).

## Milestones (GitHub)

| Milestone | Theme | Epics |
|-----------|-------|-------|
| **MVP-Polish** | Harden the core `/inbox` flow | #17 MOC Intelligence · #18 Inbox Analysis Quality · #19 Suggestions UX · #22 Orchestration Robustness · #24 Performance & Cost |
| **Obsidian-Power** | Next-layer vault skills | #16 Obsidian-Power Skills · #20 Profile-Agnostic Pipeline · #21 Discovery/Cache Infra |
| **Post-Launch** | Lifecycle & cross-repo | #23 Install & Lifecycle Tooling · #26 Hashi Executor |
| **Tech-Debt** | Docs + refactors | #25 Documentation & Tech-Debt |

## Migrated items → GitHub (2026-06-03)

Must/Should items are standalone issues; **☐ #N** means the item is a Could-checkbox inside epic #N.

| backlog ID | GitHub | Disposition |
|-----------|--------|-------------|
| F-01 | **#26** | Must — Hashi executor epic (cross-repo, primary work in `miyo-tomo-hashi`) |
| F-02 | ☐ #16 | Periodic-notes infra (config present, rendering open) |
| F-04 | ☐ #23 | Profile switching post-install |
| F-05 | **#124** | Topic weighting in MOC matching (promoted to sub-issue 2026-07-03; spec 029) |
| F-07 | ☐ #20 | Configurable classification threshold |
| F-09 | ☐ #21 | Incremental cache refresh |
| F-10 | ☐ #22 | Automated applied-action detection |
| F-12 | ☐ #18 | Atomic note sub-types (LYT) |
| F-15 | ☐ #21 | Batch read / chunked search in Kado (external dep) |
| F-16 | **#34** | Relationship markers from config |
| F-17 | ☐ #17 | Callout full-line matching — *detail in Appendix A* |
| F-18 | ☐ #21 | Frontmatter sampling script |
| F-19 | ☐ #21 | Tag analysis script |
| F-20 | ☐ #21 | Orphan detection script |
| F-21 | **#36** | Cache staleness warning |
| F-28 | ☐ #23 | Profile→vault-config frontmatter copy at install |
| F-29 | ☐ #23 | Backup remainder (MVP shipped; nested-git warning + verification open) |
| F-30 | **#29** | LLM-driven insertion-point resolution for link_to_moc |
| F-32 | **#40** | Opus cost reduction (lever a shipped; measurement + b/c open) |
| F-34 | ~~#27~~ | **Superseded by spec 021** (2026-06-10) — Condition B retired from `/inbox`; capability moved to `/moc-propose`. GH #27 closed. *Historical detail in Appendix B.* |
| F-36 | **#28** | New-section proposal logic |
| F-37 | ☐ #22 | Daily-log date-source re-audit |
| F-39 | ☐ #20 | Profile-driven `daily_log.entry_time_format` |
| F-41 | **#32** | Multi-topic detection — **code-complete 2026-06-11** (XDD 016 shipped; see Done record) |
| F-42 | **#33** | Suggestions document UX pass |
| F-44 | **#30** | Knowledge-garden audit skill |
| F-45 | **#31** | Weekly/monthly review skill |
| F-46 | ☐ #16 | Tag-audit skill |
| F-48 | ☐ #16 | Incremental-discovery cache |
| F-50 | ☐ #22 | Stop-gate branch (iii) (branches i shipped) |
| F-51 | **#37** | Phase 0b stale-state detection |
| F-55 | **#35** | Profile-agnostic pipeline scripts |
| F-56 | **#38** | Tracker wizard deselect/ignore |
| D-01 | ☐ #25 | Tier-1 agent table outdated |
| D-02 | ☐ #25 | Broken cross-reference in template-system docs |
| D-03 | ☐ #25 | Broken cross-reference in workflow specs |
| D-04 | ☐ #25 | Daily-note detection config examples outdated |
| D-05 | ☑ #25 | Done 2026-06-30 — WHY-docs for 6 skills created at `docs/tomo/dot_claude/skills/` |
| D-06 | ☑ #25 | Done 2026-06-30 — post-018 deprecation banners added to 7 stale reference docs |
| D-07 | **#42** | `instruction-render.py` 1870 LOC refactor |
| D-08 | ☐ #25 | `suggestion-parser.py` 1397 LOC refactor |
| D-10 | **#41** | Documentation refresh (docs/ tree, coverage, screenshots) |
| D-11 | ~~#39~~ | **Done (2026-07-02)** — `cleanup-tomo.sh` v0.3 registry-aware: `registry-only` (deregister, you delete the folder) vs `--delete-disk --force`; interactive r/d/N; non-interactive defaults to registry-only; `--instance`/`--list`; hardened path guard. |
| D-12 | ☐ #23 | `move-tomo.sh` / instance-relocate helper |

**Operational follow-ups (from `docs/ai/memory/context.md`), also migrated:**

| context item | GitHub | Disposition |
|--------------|--------|-------------|
| #9 Audio classification post-transcription | → #33 | Resolved 2026-06-03: misclassification obsolete (audios partitioned out before dispatch); audio-as-deletable-source folded into the #33 source-model |
| #16 Suggestions checkbox layout (audio pairs) | → #33 | Folded into #33 2026-06-03: root cause is the origin/source terminology split + 3-file (m4a/transcript/note) ambiguity |
| Pass-2 happy-path `run-pass2.sh` | ☐ #24 | perf |
| Pass-1 token audit | ☐ #24 | perf |

## Backburner — Templates & Concepts (not migrated, stays here)

Deferred-by-nature Could items kept in the backlog as an idea store; promote to a GitHub issue when one becomes relevant.

| ID | Item | Priority | Notes |
|----|------|----------|-------|
| F-03 | Templater rendering by Tomo | Could | Eliminate user's manual Templater step; currently parked. Tomo resolves `{{tokens}}`; Templater syntax passes through unchanged. |
| F-14 | Additional PKM concepts (resource, reference, log, dashboard) | Could | Deferred until workflows require them. MVP concept set: inbox, atomic_note, map_note, calendar, project, area, source, template, asset. |
| F-22 | Document splitting for large batches | Could | Soft limit 30 items; no splitting logic. Batches are typically <10. |
| F-23 | Archive subdirectory for processed items | Could | Optional move to `+/archive/YYYY-MM/`. Tags-only suffices for MVP. |
| F-24 | Delete auxiliary files after cleanup | Could | Rendered notes/diffs stay in inbox after cleanup. Safer to leave for now. |
| F-05a | Typed-topic provenance at extraction (approach A) | Could | F-05 (#124) follow-on. Store extraction-time provenance in the cache instead of the title-token proxy. Only if #124's proxy proves insufficient. Heavy: cache schema bump + squelch-signature risk. |
| F-05b | Topic-match threshold re-derivation | Could | F-05 (#124) follow-on. Standalone data-driven re-tune of `JACCARD_DUP_THRESHOLD` / analyst keep-gate beyond #124's in-scope validation. Only if #124's placement-confidence check shows misseparation. |
| F-05c | Replay archived inbox as F-05 golden fixture | Could | F-05 (#124) follow-on. Recover the archived inbox that produced the original mis-match to build a real (not synthetic) regression fixture. Contingent on data recovery. |

## Done (historical record)

| ID | Item | Closed | Evidence |
|----|------|--------|----------|
| F-08 | Configurable MOC proposal minimum | 2026-06-03 | `MocProposalConfig.min_notes` config-driven (shared-ctx-builder.py:79-95) |
| F-11 | Callout-based tracker syntax | 2026-06-03 | `callout_body` in `TRACKER_SYNTAXES` (vault-config-writer.py:401); title-matching → F-17 |
| F-13 | Standalone MOC density scan | 2026-06-03 | Superseded by F-43 `/moc-propose` (no `/scan-mocs` needed) |
| F-25 | Default-doc template for undefined types | 2026-06-22 | `t_default_tomo.md` (tags + body) + `templates.mapping.default` role + `/tomo-setup` Phase 4 ask + `default-doc-writer` skill |
| F-26 | Voice memo transcription | 2026-04-21 | faster-whisper, XDD 009 (commits c7c9688…5d6aed7) |
| F-27 | Custom @-file picker | 2026-04-21 | `file-suggestion.sh` v0.5.0, spec 010 DONE |
| F-33 | Force Atomic Note via follow-up doc | 2026-04-23 | XDD 012 (commit 08a1f22) |
| F-35 | MSP Condition C — Placeholder MOC trigger | 2026-05-07 | Code-complete (commit 5b3a031); live-validation pending |
| F-38 | "Create daily note first" checkbox | 2026-06-03 | Emitted at suggestions-reducer.py:369 |
| F-41 | Multi-topic detection — N atomics per source | 2026-06-11 | XDD 016 (GH #32); Step 7.5 segmentation (inbox-analyst v0.16.0) + C1–C6 cardinality fixes (suggestions-reducer, suggestion-parser v0.10.0, instruction-render v0.21.0); live-validation pending |
| F-43 | MOC-creation skill | 2026-05-21 | `/moc-propose` + `moc-architect` shipped; F-47 blocker cleared; live-validation pending |
| F-47 | Tomo lifecycle state (frontmatter + byFrontmatter discovery) | 2026-05-21 | XDD 017 all 6 phases; 300 tests |
| F-49 | `resolve_stem_to_path`/`path_exists` latent bug | 2026-05-26 | Both added to KadoClient (commit f1600e5) |
| F-52 | Voice-transcriber dispatch optimization | 2026-05-21 | `voice-precheck.py` v0.1.0 (commit 602e5f4) |
| F-54 | Re-evaluate orchestrator dispatch-vs-impersonation | 2026-05-22 | Dispatch flip tested + reverted (commit 4f2b810); impersonation retained |
| D-09 | Shared `render-launcher` helper | 2026-05-30 | spec 020 Phase 1, `scripts/lib/render-launcher.sh` |
| B-01 | suggestion-parser.py dropped log entries for re-seen dates | 2026-04-18 | commit a963d73 |
| B-02 | instruction-render.py 404 on bare template stems | 2026-04-18 | commit a963d73 |

## Deliberate Design Decisions (YAGNI — not gaps)

Documented here so future sessions don't re-investigate these as "missing features".

| Decision | Rationale | Date |
|----------|-----------|------|
| No frontmatter baseline in profiles | Templates ARE the frontmatter definition. A separate profile baseline would duplicate the same info and risk drift. Users should define a template, not a schema. | 2026-04-19 |
| No tag taxonomy baseline in profiles | Tag taxonomy is already fully defined in `vault-config.yaml` under `tags.prefixes` with `known_values`, `wildcard`, `required_for`. `tomo.suggestions.proposable_tag_prefixes` and `excluded_tag_prefixes` provide additional control. Profile baseline would only be seed data for first-session wizard — not needed since wizard scans vault. | 2026-04-19 |
| Workflow documents use checkboxes, not tags | Frontmatter tags are not easily accessible in Obsidian. Suggestions use `[x] Approved` (global), instructions use `[x] Applied` (per action). Discovery by filename pattern. Source items still use tags (Tomo-managed). | 2026-04-19 |
| Section placement via LLM, not deterministic scoring | Spec describes a scoring algorithm (H2 matching, depth bonus, callout avoidance). Implementation uses LLM judgment. Works correctly; deterministic scoring is future optimization if drift becomes a problem. | 2026-04-19 |
| Classification matching via LLM, not weighted scoring | Spec describes weighted keyword scoring (exact=2, cache=1, substring=0.5). Implementation uses LLM keyword-overlap heuristic. Same reasoning as section placement. | 2026-04-19 |

---

## Appendix A — F-17 Detail: Callout Full-Line Matching (End-to-End)

> Reference design notes for GitHub **#17** (Could checkbox F-17). Kept here because the 4-layer plan predates the migration.

**Problem:** Same callout type can have different titles with different semantics:
- `>[!EXAMPLE]- New Notes Today` → editable (user content)
- `>[!EXAMPLE]- Modified Notes Today` → protected (DataviewJS output)

Matching on type alone (`EXAMPLE`) is unsafe. Need `type + full first line` as key.

**Current workaround:** instruction-builder reads the MOC at Pass 2 via `kado-read`
and extracts the callout first line. This works but is fragile — the builder gets
no guidance on which callouts are safe to edit.

**Proper implementation (4 layers):**

| Layer | Change | Why |
|-------|--------|-----|
| **vault-config.yaml** | Callout mapping keys become `type- title` (e.g. `"EXAMPLE- New Notes Today": "editable"`). Existing type-only keys (`blocks`, `shell`) remain as shorthand for callouts without titles. | Config is the source of truth for which callouts are safe |
| **moc-tree-builder.py** | When reading MOCs, extract callout signatures (type + full first line) per MOC. Store in `sections[]` alongside H2 headings. Format: `{"type": "callout", "callout_type": "blocks", "full_line": "> [!blocks]- Key Concepts", "editable": true}` | Cache knows the actual callout signatures per MOC |
| **shared-ctx-builder.py** | Include callout signatures in per-MOC data in shared-ctx. Subagent sees which sections are editable vs protected. | Subagent can emit the correct `section_name` with full callout info |
| **inbox-analyst.md** | `section_name` in `link_to_moc` action becomes the full callout line (e.g. `"> [!blocks]- Key Concepts"`) instead of just the type. | Reducer and instruction-builder get the exact target |

**Dependencies:** Requires vault-config callout mapping to support full-line keys first.
The current `callouts.editable` structure (`blocks: "Key Concepts section"`) would change to
include the title: `"blocks- Key Concepts": "Key Concepts section"` or a structured format.

**Validation:** After implementation, instruction-builder no longer needs to read the MOC
at Pass 2 to find the right callout — the information flows through the pipeline from
cache → shared-ctx → subagent → reducer → instruction-builder.

## Appendix B — F-34/F-35 Detail: Mental Squeeze Point Completion Plan

> Reference design notes for GitHub **#27** (F-34) and the shipped **F-35**.
> **⛔ F-34 Condition B is SUPERSEDED by spec 021 (2026-06-10).** Live validation proved it never fires; Condition B was retired from `/inbox` and the vault-wide accumulation → new-MOC capability now lives in `/moc-propose`. GH #27 closed. The notes below are historical context for the original F-34 design.

**Context.** Spec defines four MOC-creation triggers (Tier-3 New MOC
Proposal §2):
- **A — Batch Cluster** (≥3 items in a single /inbox run share a topic
  with no MOC). **Implemented** in `tomo/scripts/suggestions-reducer.py`
  (`topic_clusters` dict line 507, loop lines 594-606, render line 632+).
  Default threshold = 1 (every `needs_new_moc` surfaces).
- **B — Accumulation** (current item topics match existing notes
  with no MOC link / `up::` absent). **Shipped** — F-34 (XDD 015 / GH #27).
- **C — Placeholder Match** (item topics match a `placeholder_mocs[]`
  entry — a wikilink with no backing file). **Shipped** — F-35 (commit 5b3a031).
- **D — `/scan-mocs` manual command.** YAGNI per spec; superseded by F-43 `/moc-propose`.

**Constraint.** All F-34 changes are additive on hot paths (`inbox-analyst`,
`instruction-render`, `suggestions-reducer`, `shared-ctx-builder`). A run
with no accumulation index is byte-identical to pre-F-34 behaviour.

**F-34 architecture decision — RESOLVED.** Two options were evaluated:

| Option | Where Condition B logic lives | Pass-1 cost impact | Implementation effort |
|--------|-------------------------------|--------------------|-----------------------|
| **(a)** Add `kado-search` to `inbox-analyst` tool list | Per-item, in subagent (Step 8) | Adds N searches per Pass-1 batch | LOW (tool list + Step 8 logic) |
| **(b)** Pre-compute accumulation index in `shared-ctx-builder.py` | Once per run, in shared-ctx envelope | Zero Pass-1 subagent cost added | MEDIUM (new builder logic + index format) |

**Option (b) was chosen and implemented.** Cold-path pre-compute keeps Pass-1/subagent
cost profile unchanged and preserves the "no kado-search in subagent" invariant that
XDD-009 / XDD-012 designs rely on.

**F-34 shipped pipeline (XDD 015):**
- `tomo/scripts/atomic-note-indexer.py` (NEW) — scanner: `listNotes` bulk read + per-candidate `dataview-inline-field` for `up::` classification; emits `{topic: [unclassified stems]}` for clusters ≥ `min_cluster_size` (default 3)
- `tomo/scripts/cache-builder.py` (`--accumulation` arg) — persists to `discovery-cache.yaml.unclassified_topic_clusters`
- `tomo/scripts/shared-ctx-builder.py` (`build_accumulation_index()`) — surfaces to `shared-ctx.json.accumulation_index`, budget-trimmed (A4)
- `tomo/dot_claude/agents/inbox-analyst.md` Step 4 — Condition-B trigger: case-insensitive/whitespace-normalised topic match; Condition C wins on conflict (A7)

**Live-validation status (2026-06-05):** Run end-to-end against the real ~281-note vault
(`listNotes` available on Kado `feat/listnotes-search-op`). The cold-path pipeline produces
the cache + `unclassified_topic_clusters` field correctly. Two real-world defects surfaced by
the live run (fixtures could not) were fixed on `feat/f-34-msp-condition-b-accumulation`:

- **Topic-extraction quality** — first run gave 166 noise-dominated clusters. Fixed via
  `topic-extract.py` v0.4.0: drop level-2 headings (measured: genuine headings are freq-1 and
  never cluster, frequent ones are template sections); tags restricted to a configurable
  `topic/` prefix array (`tomo.accumulation.topic_tag_prefixes`, default `["topic/"]`); no
  title single-word split; date-shaped link targets filtered. Result: **166 → ~118 reliable,
  thematic clusters**, zero heading/bracket/date noise.
- **Kado rate-limiting** — per-candidate `up::` reads tripped HTTP 429; each was treated as
  "classified", silently dropping notes (44 in one run). Fixed via `kado_client.py` v0.7.0
  retry-with-backoff (429/503, `Retry-After`-aware). Result: **44 → 0** dropped reads;
  reliable cluster membership.

**Remaining for full T5.2 sign-off (in-container, user-run):** `/inbox` against an item
matching a known cluster to confirm a Proposed-MOC suggestion surfaces, and a Pass-1 token-cost
check vs the F-32 baseline (no regression — additive cold-path design). Open quality polish
(optional): tiny residue keys (`@` fragments, structural `i_*` tokens). Open SDD risk to confirm:
whether `dataview-inline-field` returns callout-embedded `up::` (SDD §Risks / A5).

## Spec 024 — `_count_kado_calls` undercounts handler frontmatter reads

`inbox-triage.py` `_count_kado_calls` does not include the per-source `read_frontmatter`
calls that `resolve_handlers` makes when a handler registry is active (one read per new source).
The `kado_calls` metric therefore undercounts on active-registry `/inbox` runs. **Byte-identity
(AC-5) is unaffected** — the empty-registry path makes zero handler reads, so a no-registry run
is byte-identical and its count is correct. Surfaced during T2.1 code review (2026-06-23).
Follow-up: thread a handler-read counter through `TriageState` and add it to the metric.

## ✅ RESOLVED — Pass-2 rendered staging notes re-ingested by `/inbox` before apply → [#108](https://github.com/MMoMM-org/miyo-tomo/issues/108)

Re-running `/inbox` **before Pass-2 output is applied** made Tomo re-ingest its own rendered staging
notes as fresh inbox items, because the renderer stamped a `tomo:` block only on the instructions
doc, not on the rendered atomic notes/MOCs it wrote into the inbox — so triage treated them as new
content. Surfaced during spec-027 live testing (`source_items` 4 → 9).

**Trigger** fixed separately: a PreToolUse hook (`block-inbox-selfschedule.sh`, PR #110) blocks the
model from self-scheduling `/inbox` via `ScheduleWakeup`, so the `/loop`-driven auto-re-run no longer
happens.

**Symptom** fixed via **Option A**: the renderer stamps `tomo: {doc_type: rendered-note,
state: pending-move}` on every rendered note/MOC (`instruction-render.py` +
`doc_frontmatter.merge_tomo_block_into_markdown`); triage adds a `tomo.state=pending-move` bucket and
excludes it from fresh sources (`inbox-triage.py::compute_new_sources`); Hashi's `stripTomoFrontmatter`
(895c0ac) already wipes the block on `move_note`/`create_moc` apply, so the moved note stays clean —
no cross-repo change. Fail-safe: a note whose frontmatter can't take the block is written unstamped
(worst case = pre-fix re-ingestion, never a corrupted note).

## OPEN — F-16 follow-up: `moc-proposal-parser.py` parent-checkbox marker hardcoded

Spec 028 (F-16) de-hardcoded relationship markers across the pipeline, but a Phase-4 seam grep
found `moc-proposal-parser.py:132` (`if "up::" in cb_text`) parsing an approved MOC proposal's
parent checkbox with a hardcoded `up::`. Deferred from 028 because it is **pure future-proofing**
(both bundled profiles use `up::`, so zero behavioral impact today) and the script has **no
`--config`/`--profile` channel** — threading it needs a delivery-channel design like the one
`suggestion-parser` got (read the marker from an upstream artifact's `conventions` block, or add a
flag). Pick up if/when a non-`up::` profile ships. Related: spec 028, epic #20.

## RESOLVED — F-57: `move_asset` for attachment moves (shipped 2026-09-01)

Hashi shipped `move_asset` in **0.20.1** (PR #120) for moving **attachments** (images, PDFs, audio)
inside the vault: `{id, action:"move_asset", source, destination, applied?}`,
`additionalProperties:false`, same idempotency matrix as `move_note`, routed through
`fileManager.renameFile` so embeds and links follow the file. It never calls `vault.process`, so
the bytes are never read. **`schema_version` stays `"2"`** — Hashi pins `const: "2"` and would
reject every instruction set if Tomo bumped it.

**Tomo emits it.** Present in BOTH `tomo/schemas/instructions.schema.json` (producer) and
`tomo/schemas/hashi-instructions.schema.json` (mirror), covered by
`tests/test_hashi_instructions_schema.py`.

The producer is **not** the deterministic renderer — `_build_move_note_actions`
(`lib/render_actions.py:559`) only ever moves Tomo-rendered `.md` notes, and `_dest_join` (`:498`)
hardcodes a `.md` suffix. `move_asset` comes from **session-composed instruction sets**: the
cross-vault import that surfaced the need wrote `tomo-tmp/rendered-hashi/instructions.json` by
hand, with 13 `move_note` + **8 `move_asset`** actions for `.jpg`/`.png` map images, moving
`100 Inbox/Images/*` → `Atlas/290 Assets/295 Attachments/*`.

**Correction — the mistake worth remembering.** PR #152 first added `move_asset` to the mirror
*only*, registered in `MIRROR_ONLY_ACTIONS` as "no Tomo emitter", on the strength of a
renderer-only audit. That audit was correct about the renderer and wrong about Tomo: a live
instruction set was already emitting the kind and failing validation against the producer schema
while applying cleanly in Hashi. **Auditing the deterministic pipeline is not the same as auditing
what Tomo emits** — session-composed instruction sets are a first-class producer with no code path
to grep. `tests/test_hashi_instructions_schema.py::test_move_asset_present_in_producer_schema_oneof`
is the regression guard.

Related: Hashi 0.20.1 also narrowed `move_note` to `.md`/`.canvas`/`.base` on **both** endpoints;
anything else now returns `failed` instead of silently corrupting the file via a UTF-8 round trip.
Documented in `docs/instructions-json.md`.
Source: `_inbox/from-hashi/2026-09-01_hashi-to-tomo_wire-sync-move-asset-and-replace-section.md`;
Hashi PRs #119 + #120, spec 002 decision log 2026-09-01. Tomo PRs #152 (mirror) + the correction.

**Update — the deterministic pipeline emits it too (spec 031).** The gap this entry describes —
"the producer is not the deterministic renderer" — is closed: spec 031 (Inbox attachment filing)
added `_build_move_asset_actions` (`lib/render_actions.py`), which reads `attachments[]` off each
manifest entry (populated by `inbox-triage.py`'s embed detection/resolution, `instruction-render.py`'s
manifest-entry threading) and emits `move_asset` for every unique resolved path, globally
deduplicated. Session-composed instruction sets remain a valid second producer for the same kind;
see `docs/instructions-json.md`'s "Who emits it" for `move_asset`.

## OPEN — Adopt Kado `kado-graph` navigation tool for MOC/related-note features (opportunity)

Kado shipped a read-only `kado-graph` navigation tool (PR #87, ~v0.17.0): per-note `backlinks` /
`outgoing` / `neighbors` (1-hop union) / `related` (2-hop, each node carries `via`) / `dangling` (a
source's unresolved link targets + `count`). Params `{operation, path(.md), limit?}` →
`{source, operation, nodes:[{path, relation, via?, count?}]}`; scope-filtered (resolved neighbours
outside the key's scope are silently omitted, so Tomo only ever sees paths it could already read).
**This is a DIFFERENT tool from `kado-graph-audit`** (vault-wide orphans + deadLinks), which Tomo
already consumes via garden-audit (spec 030). Not adopted — pure **opportunity** for future
MOC-accumulation / related-note discovery (returns *resolved* paths, vs `listNotes fields:['links']`'s
*raw unresolved* targets); `dangling` overlaps garden-audit's dead-link check but per-note instead of
vault-wide. From the same handoff, no action needed: `kado-search byContent` is now full-text ranked
(additive `score`/`snippets`) — **zero impact on Tomo** (`kado_client.search_by_content()` has no
callers); `_hints` responses are optional and currently ignored. Source:
`_inbox/from-kado/2026-06-24_kado-to-tomo_graph-tool-and-search-ranking.md`; Kado ADR-002 (disclosure
guard) / ADR-003 (`_hints` contract).

## OPEN — `garden-audit-render.py` is 1387 LOC, 2.8-4.6x over the constitution guideline

Flagged by the Phase 5 constitution check of spec 032-up-source-routing (2026-09-02); revisited
after spec 033-broken-up-cause-split Phase 4's constitution check (2026-09-04).

MiYo Constitution, Code Quality L2: *"Files implementing core behaviour … should remain small and
focused. When a file grows beyond ~300–500 LOC of dense logic, it should be refactored into smaller
modules along its natural seams."*

Measured: **1387 LOC**. It was **1059 LOC** at the spec-032 checkpoint above (1068 LOC once spec
033's own Phases 1-3 had also landed, +9 LOC registering the new `parent_not_moc` check). Phase 4
(T4.1-T4.6) then added **+319 LOC** on its own (338 insertions, 19 deletions against the pre-Phase-4
commit) — a ~30% increase, material rather than incidental, matching spec 032's own precedent above.
The growth bought: the per-check advisory message table and the once-per-run "Untagged parents"
grouping block that lets one MOC tag resolve several findings at once (T4.1); the reworded
`broken_up` wording that stops implying a target was found to be missing when the check cannot tell
missing from out-of-scope (T4.2); the per-situation "Flagged parents" counts, extended to a third
bucket after the fact (T4.3, corrected T4.5); the `cause-unknown` withholding path that reuses the
existing `_UNROUTABLE_REMEDY` mechanism rather than adding a parallel one (T4.4); and the fixes and
regression coverage the T4.5 prose read and T4.6 required to prove all of the above holds up as
rendered English, not just as passing assertions. L2 requires rationale on violation rather than a
hard block, so this did not gate either phase.

Natural seams observed while working in it:
- the three once-per-run summary renderers (`_render_summary`, `_render_unroutable_summary`,
  `_render_broken_up_split`) — the last two are structural twins sharing a
  classify → bucket → suppress-at-zero skeleton
- the withheld-finding surface: `_broken_up_withhold_reason`, `_render_withheld_block`,
  `_log_unroutable_findings`, plus the three parallel dicts `_UNROUTABLE_REMEDY`,
  `_UNROUTABLE_REASON_LABEL`, `_UNROUTABLE_SUMMARY_TEXT`

A code-quality reviewer recommended NOT extracting the twin renderers yet — two instances with
different render shapes make it a complexity wash — and named the trigger: **a third broken_up-scoped
summary line is the point to extract the shared skeleton.** Same judgment applies to the three
parallel dicts: a fourth unroutable reason would be the moment to collapse them into one dict of
records, since a reason currently needs an entry in all three and nothing enforces completeness.

**Both triggers arguably fired in Phase 4, unassessed.** T4.3 added `_render_flagged_parent_situations`
— a fourth once-per-run summary renderer sharing the same classify → bucket → suppress-at-zero
skeleton as the two already named (it is not `broken_up`-scoped alone, since it also counts
`parent_not_moc`, so it may or may not be the "third broken_up-scoped summary line" the original
trigger meant precisely — a judgment call for whoever picks this up, not decided here). T4.4 added a
fourth entry (`cause-unknown`) to all three parallel dicts, exactly the count the second trigger
named. Neither was extracted or collapsed during Phase 4 — flagging that the triggers exist, not
acting on them, since this entry's own scope is documentation, not refactoring.

Not spec-032 or spec-033 scope. Pick up when either trigger fires (now, arguably), or as a standalone
refactor.

## Decision record — the split line's "Broken parents:" label outlives its own precision

Spec 033 T4.5's prose read (2026-09-04) fixed the same defect — a `broken_up` finding's rendered
text asserting breakage it cannot confirm — at the per-finding heading, detail line, and Summary
levels for a cause-unknown finding (see `docs/tomo/scripts/garden-audit-render.md`'s T4.5 entry).
One instance survives, one level up. `_render_broken_up_split`'s section label ("Broken parents: N
findings — B in the note body, P in a note property…") still reads "Broken parents" even when N
includes a cause-unknown survivor. A reader who encounters this line in isolation — skipping the
Summary's own "Flagged parents" breakdown two lines above it, which DOES separate cause-unknown out
after T4.5's fix — sees "Broken parents: 1 finding" attached to a finding that may turn out to be
untagged-but-real rather than confirmed broken.

**Accepted, not fixed.** This is spec-032 verbatim-locked text (ADR-4, solution.md UI & UX,
"DO NOT PARAPHRASE" provenance); the check itself is named `broken_up` and this spec does not rename
it; and the trailing clause (T4.3/ADR-7) already scopes the count to declaration site rather than
asserting a cause. Rewording the label itself would mean reaching into 032-locked text and adding a
fourth sanctioned byte-identity difference to `test_032_t6_2_regression_inline_unchanged.py`'s
baseline comparison, for a residual the Summary line two lines above already resolves for a reader
who reads the whole Summary rather than one line of it in isolation.

Pick up if a future spec touches this line for an unrelated reason anyway, or if user feedback shows
readers land on the split line without reading the Summary above it.

## Decision record — `remove_up_link` stays unguarded; spec 032's routing is the alternative

Hashi's shipped `remove_up_link` executor has no guard against a note whose parent is declared in a
frontmatter `up:` property rather than an inline `up::` line — the action would find no line to
remove from and report `skipped-already` (a no-op that looks identical to "nothing to remove", not a
loud failure). Hashi raised this as a blind spot on 2026-09-01: a guard is technically possible
("fail only when the note has no inline `up::` line AND a frontmatter `up:` exists whose value
references the link; absent everywhere stays `skipped-already`"), but Tomo recommended **not**
building it — the durable fix is to stop *sending* `remove_up_link` for a frontmatter-declared parent
in the first place, which is exactly what this spec (032-up-source-routing) does by routing such
findings to `edit_frontmatter` instead. A guard on Hashi's side would fail honest no-ops in order to
absorb an action Tomo should never have sent.

Hashi accepted the reasoning and recorded the decision in their own spec — `spec-002
(instruction-executor)`, decision row 2026-09-01, PR **#128** (merged, commit `244cb45`) — including
the guard condition Tomo supplied, precisely because they are *not* implementing it: a future reader
finding `remove_up_link` unguarded next to two guarded siblings should find a written answer, not an
invitation to guess. Kokoro carries the same open-by-design note in ADR-028 §5, with an explicit
warning that the class must not be assumed swept clean. Hashi's `edit_frontmatter` (`operation:
"remove"` + `expected`) shipped in **0.22.0** and needs nothing new to receive this spec's output.
(Corrected 2026-09-03: the earlier **0.23.0** here named neither the release that added the kind nor
the one that added the `expected`/`expected_absent` split — that is 0.23.1. Tomo keeps 0.23.0 as a
stated floor deliberately, for its comment-preserving pre-check.)

Hashi is not tracking an issue on their side for this — there is nothing left for them to build. They
are waiting for Tomo to notify them once the routing ships (plan task **T6.6**), at which point the
frontmatter case stops being merely rare (measured: 1 of 29 live `broken_up` findings) and becomes
**unreachable** through `remove_up_link`, and the cross-repo record closes on both sides.

Source: `_inbox/from-hashi/2026-09-01_hashi-to-tomo_remove-up-link-acknowledged-unguarded.md`;
`_outbox/for-hashi/2026-09-01_tomo-to-hashi_remove-up-link-yes-it-can-occur.md`; spec
`032-up-source-routing` (this repo).

## OPEN — `broken_up` conflates three causes; the offered fix destroys valid links for two → [#157](https://github.com/MMoMM-org/miyo-tomo/issues/157)

`_resolve_up_state` (`tomo/scripts/moc-tree-builder.py:280`) returns `broken` for exactly one
condition — the `up::` target is not the stem of an **in-scope** MOC. Three unrelated vault states
land on that label, and `_check_broken_up` offers the same remedy to all three:

| actual state | is "repoint, or leave empty to remove" correct? |
|---|---|
| target does not exist | yes |
| target exists in scope, no MOC tag | no — the link is fine, the tag is missing |
| target exists outside `scope_paths` | no — the scanner is blind, not the vault |

Measured on the 2026-09-03 run (359 entries, scope `Atlas/200 Maps/` + `Atlas/202 Notes/`): 42
findings — **20** whose target sits in the cache as `kind: note`, **22** whose target is absent from
it. Cause 3 is confirmed rather than assumed: seven of those 22 name one target by bare stem while an
eighth records the same target as a full path under a folder outside `scope_paths`. The note exists;
it is never scanned.

Consequence is user-data, not code: nothing crashes and the emitted instruction is well-formed and
correctly guarded. Accepting the fix on causes 2 and 3 deletes a working parent link and flattens
deliberate hierarchy (notes parented to notes, or across a folder boundary).

Scope boundary worth keeping straight: spec 032 decides **where** a broken-parent fix is written
(`edit_frontmatter` vs. a body edit) and is unaffected by this. This issue is the separate question
of **whether** the fix should be offered.

Found while validating spec 032 — see `docs/XDD/specs/032-up-source-routing/live-validation.md`.

## OPEN — placeholder links carry no `section` (which H2 the link sits under)

`moc-indexing.md §6` specifies that placeholder output should record the **section** a
placeholder link appears under, so a later fix can put a created note back where it was
referenced. Today `moc-tree-builder.py` emits `placeholder_links` as `{target,
referenced_by}` only — the heading context is dropped at detection time in
`lib/placeholder_detect.py`.

Consequence: anything acting on a placeholder has to re-open the referencing MOC and
re-derive the heading, which is exactly the kind of second parse that
[spec 022's insertion-point work](specs/022-moc-insertion-point-intelligence/) exists to avoid.

Not urgent — no current consumer needs it. Recorded so the gap stays visible.

Provenance: filed during a 2026-04-12 drift check against `cache-generation.md` /
`structure-scan.md` / `moc-indexing.md`. That check listed seven spec-defined gaps; the
other six (orphan detection, cache post-write validation, classification coverage,
frontmatter sampling, per-tag counting, deep-nesting warning) have since shipped. This is
the last one, re-verified open on 2026-09-03 while retiring the memory file that carried
the list.

## RELEASE NOTE — spec 033 (`parent_not_moc`) may make excluded `broken_up` findings reappear

Spec 033 splits the `broken_up` garden-audit check: a link whose parent target exists but carries no
MOC tag now reports as a separate advisory check, `parent_not_moc`, instead of as `broken_up`. This
is correct (the two are different situations — see
[spec 033](specs/033-broken-up-cause-split/README.md)) but it silently changes what an existing
exclusion config suppresses (ADR-4 in `specs/033-broken-up-cause-split/solution.md`):

- An exclusion using `checks: all` for a path/note/tag keeps covering everything, `parent_not_moc`
  included. No action needed.
- An exclusion that names checks **explicitly** and lists `broken_up` does **not** automatically
  cover `parent_not_moc` — a finding on that path that used to be silent as `broken_up` can reappear,
  now labeled `parent_not_moc`, in the advisory tier.

Measured against this project's own live vault config
(`tomo-instance/config/garden-audit-exclusions.yaml`, spec 033 T3.3, 2026-09-03): 4 of 6 rules use
`checks: all` (unaffected); one rule (`Efforts/` → `[broken_up, dead_link, stale_moc]`) names
`broken_up` explicitly and will see reappearance the first time `/garden-audit` runs after this
ships. Confirmed by running the actual `GardenExclusions` loader against the file, not by reading the
YAML.

Action for anyone shipping this: mention it in the release note for spec 033 — "if you excluded
`broken_up` by name rather than with `checks: all`, you may see a few new advisory findings; this is
expected, not a regression" — and, for users who prefer silence, that adding `parent_not_moc` to the
explicit `checks` list restores it.

## OPEN — check-name knowledge is duplicated across six structures; it has already caused a real miss

Adding one garden-audit check requires editing **nine** separate registration sites, because no
single structure owns the set of check names. They are spread across:

- `tomo/scripts/garden-audit.py` — `_TIER` (name → tier), `_FIXABLE` (which names may carry a fix)
- `tomo/scripts/lib/garden_exclusions.py` — `ALL_CHECK_NAMES`
- `tomo/scripts/garden-audit-configure.py` — `_VALID_CHECKS`
- `tomo/scripts/garden-audit-render.py` — `_CHECK_LABEL`, plus two check-name tuples
- `tomo/scripts/garden-audit-stats.py` — `_CHECKS`, `_COL_LABEL`, **and a second, stats-local
  `_TIER`** that duplicates `garden-audit.py`'s
- `tomo/schemas/` — three separate check-name enums (`garden-audit-doc`, `garden-audit-wire`,
  `garden-audit-exclusions`), plus four prose descriptions that enumerate checks and validate
  nothing

**This is not hypothetical debt.** Spec 033's SDD first drafted the registration inventory at six
must-register sites. An independent audit found three more, all of them in `garden-audit-stats.py`
or the third schema enum — the surfaces furthest from the check that owns the name. The most severe
(`_CHECKS`, guarded by a module-scope `assert` at `garden-audit-stats.py:50`) would have raised
`AssertionError` at **import**, taking the stats tool down entirely, and the planned verification
walk would not have caught it: a walk over the inventory can only prove the sites named in it are
covered, never that no others exist. Spec 032 hit the same class of miss, and spec 031's
`move_asset` is still unregistered in three places for the same reason.

Spec 033 mitigated the symptom rather than the cause: it corrected the inventory to nine sites, and
rewrote its verification to include a completeness grep independent of the table (classify every
occurrence of an existing check name as either registered-or-deliberately-excluded). That grep is
reusable and should be the minimum bar for any future check — but it is a detector, not a fix.

The fix would be a single source of truth for check metadata (name, tier, fixable, label, column
label) with every other structure derived from it, leaving only the genuinely independent decisions
— the three sites where a name must deliberately NOT appear — as explicit opt-outs. The schema
enums could be generated rather than hand-maintained.

Worth doing before the next check is added, not after.

## RELEASE NOTE — spec 033: the first `/garden-audit` run after upgrading offers no broken-parent fixes

Spec 033 classifies *why* an `up::` parent link is flagged, using a new `up_broken_reason` field the
MOC-structure cache only gains once it is rebuilt. An index built before this change carries no such
field — and per PRD Feature 6, a report drawn from it must not claim a cause it cannot determine, nor
offer a fix that would be wrong for two of the three situations it cannot tell apart.

So on an unrefreshed index, every `broken_up` finding is **withheld**: no Apply checkbox, no
`Repoint to:` field, no Suggest opt-in. The block instead discloses that the index predates the
classifier and names the remedy — run `/explore-vault` to refresh the cache, then re-run the audit.

**This affects the first run for every existing user, not an edge case.** Measured on this project's
own vault (spec 033 T2.4, 2026-09-03): the live cache carried 359 entries and 42 `up_state=="broken"`
findings, and **0 of the 42** carried `up_broken_reason`. All 42 would be withheld on the first run
after this ships.

This is the designed behaviour, not a regression. Before spec 033 the audit offered one remedy —
*"repoint it to a MOC, or leave empty to remove"* — for three unrelated situations, and it was wrong
for two of them: it deleted links whose target was a real note that simply carried no MOC tag, and it
blamed the vault when the target merely sat outside the audited scope. Withholding until the index can
tell the cases apart is the honest behaviour; the spec's own Could-Have ("counting the saved
deletions") anticipates it.

Action for anyone shipping this: say so in the release note — *"the first audit after upgrading will
ask you to refresh the index before it offers broken-parent fixes; run `/explore-vault` once and the
fixes come back, now with the right one offered for each situation."* One refresh clears it
permanently.

### `link_to_moc` per-item coverage is title-keyed (spec 034 residual)

Found during spec 034 T2.7 review, 2026-09-06. `instructions-diff.py`'s `run_diff` uses
`source_key = info["title"]` (~`:752`) to look up `actual["links_by_source"]` for the
`link_to_moc` per-item coverage row. `title` falls back to the bare stem
(`:225,255,268`), so two confirmed items that both default their title to the same
filename merge in that coverage row — structurally identical to the `move_note` /
`delete_source` collapse that spec 034 T2.7 fixed, but for `link_to_moc`.

Not fixable within spec 034: `render_actions._build_link_to_moc_actions` (`:758-761`)
emits only `source_note_title` and carries no `source_path` or `item_key` traceability
field, so `instructions-diff.py` has nothing to key on. Closing it needs a renderer
schema change to add that field, plus title disambiguation on collision.

Narrower blast radius than the fixed case: needs two items sharing a filename *and*
neither title user-edited.

### `inbox_state.last_state_per_item_key` drops a key-less line silently (spec 034 residual)

Flagged by T2.5's review, 2026-09-06. `tomo/scripts/lib/inbox_state.py` fails open: an
unparseable or `item_key`-less line in `inbox-state.jsonl` is passed over rather than
aborting the run. An entry missing `item_key` therefore never reaches `done_keys`, is
never counted in the `declined` tally, and produces no per-item diagnostic — only the
generic "no done items to mark" if it was the sole entry.

Not reachable from a well-formed log: `item_key` is `required` + `minLength: 1` in
`state-entry.schema.json`, and `state-update.py` takes `--item-key` as a mandatory CLI
argument with no default. The fail-open is deliberate and inherited from the reducer's
prior tolerance.

Worth closing anyway on the same principle as T2.3's "a vanished item is now audible":
a truncated final line (disk full mid-write) is a real corruption shape, and the helper
should count skipped lines and let callers report them rather than swallowing them.
Small: a counter plus a stderr line in each of the two callers.

### Three more `listDir` consumers carry their own `type == "file"` check (spec 034 residual)

Found by T3.1, 2026-09-06, while unifying the two filters ADR-3 needs. Outside that ADR's
stated two-consumer scope, so deliberately left alone:

- `tomo/scripts/voice-precheck.py:52`
- `tomo/scripts/garden-audit.py:381`
- `tomo/scripts/shared-ctx-builder.py:204`
- `tomo/scripts/moc-discovery.py:422` (`_is_md_file`) — added by T3.1's reviewer
- `tomo/scripts/vault-scan.py:259` (root-scan folder check) — added by T3.1's reviewer

Each classifies Kado `listDir` entries independently. `tomo/scripts/lib/attachment_index.py`
now exposes `is_file_entry(item)` — case-insensitive, None-safe, non-dict-safe — which is what
`discover_files` and `build_inbox_index` share. The three above could route through it too.

Worth doing because T3.1 found the divergence was not merely cosmetic: the old
`discover_files` predicate **crashed** with `AttributeError` on a non-dict entry where
`build_inbox_index` returned `False`. Any consumer still on a hand-rolled check carries that
same latent fragility. Not urgent — Kado emits lowercase literals and well-formed dicts today.

Note on scope: all five consume **different** `listDir` calls, not the inbox listing ADR-3
shares, so none belonged in T3.1. T3.1 reported three; its reviewer found two more, so the
"grepped, zero remaining" framing was correct for the two named call sites but not literally
repo-exhaustive. Whoever picks this up should re-grep rather than work from this list.

### `test_mark_captured.py` shadows the real `lib.doc_frontmatter` for the whole process

Found 2026-09-06 during spec 034's inbox-state hardening; pre-existing, not introduced by it.
Confirmed by `git stash` before any edit.

`tests/test_mark_captured.py` registers a fake `lib.doc_frontmatter` module via
`sys.modules.setdefault(...)`. That fake is missing `body_after_frontmatter`. Because
`sys.modules` is process-global, the fake shadows the real module for anything that imports
it transitively **later in the same pytest process**.

The file fails when run in isolation. It only passes in the full suite because some earlier
test happens to import the real module first — so the suite's health depends on collection
order, and a future reordering or a new `-k` selection can surface it without warning.

Fix shape: register the fake with the real module's full surface, or scope it with a fixture
that restores `sys.modules` on teardown, rather than a process-global `setdefault`.

Worth doing because the failure mode is invisible: the suite stays green while a real module
is silently replaced for every later importer in that process.

### Dead shell tests still assert the retired `inbox-orchestrator` exists

Traced 2026-09-06 while closing spec 034's voice-path recursion. `inbox-orchestrator` was
deleted under spec 018 (agent-architecture-cleanup), retired in favour of
`suggestion-conductor` + `synthesis-conductor`. Three stale references survive:

- `tests/test-phase3.sh:141-144` — `check_file` asserts the file **exists**, then greps it for
  S-section format, the Classification Guard and the anti-parrot rule. Guaranteed to fail.
- `tests/test-004-phase3.sh:193,219` — feeds the missing path to a Python check and greps it
  for `mcp__kado__kado-write`. Guaranteed to fail.
- `tomo/dot_claude/agents/voice-transcriber.md:261` — a boundary line reading "You do NOT
  invoke `inbox-orchestrator`, `inbox-analyst`, or any other agent". Harmless but it is an
  LLM-loaded runtime file naming an agent that does not exist, which is exactly the noise CON-5
  exists to keep out. One-word removal; the sentence stays sound without it.

These two `.sh` scripts are not pytest-collected, which is why they have been failing silently
for some time — spec 034 repeatedly confirmed them as "pre-existing, unrelated" via `git stash`
without anyone identifying the cause. This is that cause.

Fix shape: either retarget the assertions at the agents that replaced it, or delete the dead
blocks. Deleting is likely right — the format rules those greps guard moved with the agent.

`docs/XDD/specs/005-daily-note-workflow/solution.md:12` also names it; that is a historical
spec and should be left as written.

### The Hashi wire-hygiene test skips silently when offline

Observed 2026-09-06 during spec 034: `tests/test_instruction_render_wire_hygiene.py:317`
skips with "upstream Hashi schema unreachable — offline". Across three consecutive full-suite
runs on a quiet tree it skipped once and ran twice — a transient network hiccup is enough.

Why it matters more than a typical skip: this test guards a **cross-repo contract**. CON-4 of
spec 034 states that what Hashi receives must not change, and Hashi is a separate repository —
so this is one of the few tests standing between a wire-shape change here and a break there.
A contract test that quietly opts out on a network blip can pass a drift through on exactly
the run where nobody is watching, and the suite still reports green.

The skip itself is reasonable (the alternative is a hard failure on every offline run). The
problem is that it is **invisible**: `pytest -q` reports only a count, so the difference
between "3435 passed, 1 skipped" and "3434 passed, 2 skipped" is easy to read past.

Fix shape, cheapest first: vendor a pinned copy of the upstream schema and test against that,
refreshing it deliberately — turning a network dependency into a reviewable diff. Failing that,
make the skip loud (a warning summary that names the contract left unverified), or gate it so
CI treats an offline skip as a failure while local runs stay tolerant.

### The clash surface has outgrown two files — `suggestions-reducer.py` and `render_actions.py`

Observed 2026-09-07 during spec 034 T5.2, raised by that task's code-quality review and
deliberately declined at the time.

The file is now 2388 lines. The MiYo Constitution's L2 code-quality rule says files of dense
logic should be refactored along their natural seams beyond roughly 300-500 LOC, so this is
not a near miss — and T5.2 added about 195 lines to it.

The seam is already visible. `resolve_destination_clashes` and `_clash_reason` are
self-contained pure functions whose only outside dependency is `_dest_join`, which is itself
imported from `lib/render_actions.py`. They would move into a `lib/` module without dragging
reducer-internal state behind them, and the move would put the Pass-1 proposal logic beside
the Pass-2 guard logic that T5.3 is about to write against the same `_dest_join`.

Why it was declined rather than done: T5.3 builds directly beside this code, so extracting it
mid-phase moves ground the next task is standing on. A refactor folded into a task about
destination clashes is also precisely the scope creep the review gates exist to catch — the
right call is to do it deliberately, as its own change, not as a rider.

Best done after Phase 5 closes, when T5.2, T5.3 and T5.4 have all landed and the final shape
of the clash logic is known. Doing it before then means refactoring code that is still moving.

**Updated 2026-09-07 after T5.3.** The entry above was written during T5.2 and named only
`suggestions-reducer.py`. T5.3 grew `tomo/scripts/lib/render_actions.py` from 1659 to 1854
lines, and T5.4 took it to 2046 — equally past the Constitution's L2 ~300-500 guidance, and from the same task family.
Naming it explicitly matters: a deferral that covers a second file only by inference from
"the whole clash surface" is a deferral someone will read as not covering it.

Two concrete seams now, not one:

- `resolve_destination_clashes` / `_clash_reason` in `suggestions-reducer.py` (Pass 1).
- `validate_destinations` in `render_actions.py` (Pass 2) — about 90 lines doing several
  jobs: grouping claims by folded destination, consulting the vault, building the clash
  record, computing drop and withdraw bookkeeping, and filtering the action list. Well
  documented and thoroughly tested, so this is legibility rather than correctness, but it
  splits cleanly along those named concerns.

And one duplication that should collapse when they move: `make_folder_listing`
(`render_actions.py`) is a near-verbatim copy of `_vault_folder_notes`
(`suggestions-reducer.py`), including identical comments. Both cache one
`list_dir(folder, depth=1)` per normalised destination folder, both deliberately avoid a
per-name probe because CON-7 forbids measuring Kado's case semantics. Two copies of a
decision is exactly the drift shape this spec hit in T5.0c, where an emitter moved and its
paired consumer did not. The shared module is the fix, and Pass 1 and Pass 2 already share
ground via `lib/` — `_dest_join` is imported across that boundary today.

**Condition met 2026-09-08 — Phase 5 is closed.** T5.4 was the last task moving this code,
and T5.5 added `lib/source_link.py`, which is the first piece of the shared ground this
extraction would land in. The blocker was never the work; it was that the code kept
moving underneath it. It has stopped.

### `state-update.py --stem` is unvalidated, and an LLM writes it

Found 2026-09-07 during spec 034 T5.0c, as the assumption that task's implementer could not
verify from its own diff.

`lib/inbox_state.display_stem` returns `entry["stem"]` verbatim when present — its basename
fallback only guards a *malformed* entry. So everything rests on what writes that field, and
there are two writers with different guarantees:

- `inbox-triage.py:659,772` writes `Path(note_path).stem`, which can never contain a slash.
- `state-update.py:93` writes `args.stem`, a `required=True` CLI argument with **no
  validation**, documented as "display only; not used for lookups".

That documentation was true until T5.0c widened a comparison. `_same_note_as_any` in
`instructions-diff.py` applies `_keys_match` in both directions, so a multi-segment
`source_stem` like `Places/Dresden` would collapse against `100 Inbox/Places/Dresden` — two
notes the emitter keeps distinct. The state-entry schema permits it: `stem` is
`{"type": "string", "minLength": 1}` with no pattern.

What makes it reachable rather than theoretical: `state-update.py`'s callers are
`tomo/dot_claude/agents/inbox-analyst.md` (four sites), an LLM-loaded runtime file where the
model substitutes `<stem>` itself, with no instruction that it must be a bare filename. And
recursion is what put subfolder notes in front of that agent — handling
`100 Inbox/Places/Dresden.md`, writing `Places/Dresden` is a plausible thing for a model to do.

Cheapest fix is a guard at the CLI boundary, where it is deterministic: reject a `/` in
`--stem`, or take its basename. A schema `pattern` would catch it a layer later. Worth doing
before the next live run over a subfolder-heavy inbox, since that is the first time the
analyst meets these paths at scale.

## Cross-run document join — a stale structured doc can bind a wrong anchor

**Found 2026-09-08** by T6.4a's implementer, as the assumption its diff could not verify.

`suggestion-parser.py` resolves both `_own_doc_path` and the companion `_resolve_doc` by falling
back to a **single cwd-relative filename** (`tomo-tmp/suggestions-doc.json`,
`tomo-tmp/suggestions-fan-doc.json`). Nothing checks that the `run_id` in the markdown being
parsed matches the `run_id` of the document it binds against.

**Reachable**: `suggest-handling/SKILL.md:30` clears only `tomo-tmp/items` and
`tomo-tmp/inbox-state.jsonl`. The structured documents are never cleared — a live instance was
observed holding `tomo-tmp/*.json` files from June and July.

**Consequence, and why it is asymmetric**: the *identity* join degrades safely, because
`bind_section_item_key`'s stem cross-check (`:1913`) rejects a mismatched entry and leaves the key
unset. The *anchor* join has **no such cross-check**, so a stale document with an overlapping
section id binds a **wrong placement anchor** silently — a MOC bullet lands under a heading from
another run.

**The naive fix is wrong.** A companion merge legitimately pairs two documents with *different*
`run_id`s — the primary from one run, the fan from the next (observed live:
`2026-09-08T17-07-05Z-807b53` and `...T18-06-09Z-afc46b`). Any check must be **pairwise** — each
markdown against its own structured doc — never equality across the pair.

Not caused by spec 034, but 034 introduced the doc-join mechanism that makes it reachable. Left
out of T6.4a deliberately: it is a distinct defect with its own fix, and T6.4a's scope was already
widened once.

## `suggestion-parser.py` loads its own structured doc four times

**Found 2026-09-08** by T6.4a's code-quality review.

T6.4a's companion path loads `_resolve_doc` once and reuses it for the item-key map, the anchor
map and the topic members. The **pre-existing primary path was not retrofitted**: `_own_doc_path`
is read from disk four separate times — inside `load_doc_anchor_map`, then `_load_json_doc` at
`:2278`, `:2383` and `:2421`. The `docs/tomo` mirror's claim that "the document is read once
instead of three times" is true only of the new half.

No correctness impact — small JSON, single-process invocation. But the two paths now do the
identical shape (resolve doc → key map → anchor map → member map) with separate variable names
and no shared helper. A `_load_doc_bundle(path) -> (item_keys, anchor_map, members)` would
collapse the duplication **and** the redundant reads in one move, and is a net LOC reduction in a
file the constitution already flags as too large.

Deliberately not done in T6.4a: it refactors a path that task did not break, on a task whose scope
had already widened once, while a live validation run was waiting on it.

## A destination clash leaves orphaned `pending-move` staging notes

**Found 2026-09-08** in the T6.4 live run.

Pass 2 renders each approved atomic into the inbox as a staging note
(`doc_type: rendered-note`, `state: pending-move`) **before** `validate_destinations` runs. When
the clash guard then withholds both claimants (T5.3), their staged files are already written and
stay in the inbox waiting for a move that will never be emitted.

Observed: two `2026-09-08_1813_elbe-schifffahrt-...` files, one per withheld claimant.

`pending-move` is excluded from fresh-source discovery, so they are not re-ingested — no loop, no
data loss. But nothing detects or removes them either: `detect_orphaned_state` covers *captured
source items whose downstream docs vanished*, a different case. The instruction set tells the user
to rename one item and re-run Pass 2, and that re-run renders a **new** pair, leaving the old pair
behind indefinitely.

Correctness is unaffected — the guard's own promise ("every source note below is untouched in the
inbox") holds. This is residue the user has to clear by hand, and it accumulates once per clash
per re-run.

Two possible closes: render after validation rather than before, or have the clash record carry
its withheld staging paths so something can clean or reuse them. The first is the larger change
and would also stop paying Kado writes for notes that are then withheld.

## ~~Link coverage fails for any title containing a sanitised character~~ — FIXED

**Fixed 2026-09-09** as spec 034 T6.4b: the field was split into `source_note_title`
(raw display text, on the wire) and `source_note_stem` (the vault key, Tomo-internal,
stripped before the wire). The same defect had a second victim —
`_subtract_unresolvable_links` joins the same two forms — now covered too. Kept below
for the diagnosis, in particular the entity theory that was wrong.

**Found 2026-09-08** in the T6.4 live run, by reading the container's own session transcript —
the instruction document alone did not show it.

`instructions-diff.py`'s link coverage matches exactly (`:634`,
`a.get("source_note_title") == stem`). The **emitter** puts the *sanitised* title into
`link_to_moc.source_note_title`, while `derive_expected` puts the *raw* title in. Any title
containing a character `sanitize_stem` replaces — `\ / : * ? " < > |` — therefore never matches,
and the audit hard-fails a run whose instruction set is correct.

Observed live:

| | value |
|---|---|
| emitted (`I07`) | `Elbe-Schifffahrt**-** Tschechischer Pegel bei Usti nad Labem …` |
| expected (`S01`) | `Elbe-Schifffahrt**:** Tschechischer Pegel bei Usti nad Labem …` |

The link itself was emitted correctly and points at the right MOC — only the audit's join fails.
Two sibling items in the same run passed solely because their titles carry no forbidden character.
**A colon in a title is not exotic**: the analyst produced this one unprompted, so this fires on
ordinary content.

**The likely correct fix is at the emitter, not the audit.** Under ADR-2 `source_note_title` is a
**display** field; carrying a sanitised *filename* in it is the category error. Making the audit
compare sanitised forms on both sides would hide that rather than fix it, and would also make the
field's meaning depend on who reads it.

Same class as T6.0d: an audit that hard-fails a correct run, so the user reads it as Tomo drifting
from its own instruction set.

**Note for whoever picks this up**: the container's orchestrator diagnosed this as an HTML-entity
mismatch (`&amp;` vs `&`) after seeing the MOC name `Elbsandstein & Tschechien 2026 (MOC)` in the
failure line. That was a rendering artefact of its own terminal — no `&amp;` exists anywhere in
the artefacts or the vault. Reproducing the audit directly is what showed the real cause.
