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

## OPEN — `garden-audit-render.py` is 1059 LOC, 2-3.5x over the constitution guideline

Flagged by the Phase 5 constitution check of spec 032-up-source-routing (2026-09-02).

MiYo Constitution, Code Quality L2: *"Files implementing core behaviour … should remain small and
focused. When a file grows beyond ~300–500 LOC of dense logic, it should be refactored into smaller
modules along its natural seams."*

Measured: **1059 LOC**. It was already **775 LOC** before spec 032 touched it — so the breach is
pre-existing, but spec 032 added roughly **+284 LOC**, a material contribution rather than pure
inheritance. L2 requires rationale on violation rather than a hard block, so this did not gate the
phase.

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

Not spec-032 scope. Pick up when either trigger fires, or as a standalone refactor.

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
