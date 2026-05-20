# Specification: 017-tomo-lifecycle-tags

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-20 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-05-20 (post-OQ-lock — 9 of 14 questions resolved, 2 still open) |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | Brainstorm-style PRD with open-questions section (OQ list) — user wants discovery-flow optimization explicitly discussed in doc, not pre-baked |
| solution.md | pending | Awaits PRD completion |
| plan/ | pending | Migration phased P1–P5 per backlog F-47 entry |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-20 | Spec ID = 017 (not 014 as initially mooted) | spec.py auto-increments from max existing (016); the 014 gap in the numbering is left as-is |
| 2026-05-20 | Workflow mode = full XDD (PRD → SDD → PLAN) | User signed off 2026-05-20; refactor touches 8+ scripts/agents + introduces new schema → too broad for thin-plan |
| 2026-05-20 | Pre-locked: `suggestions/converted` is the post-Pass-2 state name on a suggestions doc | User sign-off 2026-05-20. Alternative considered was `archived` — rejected because the file is not archived, only superseded by an instructions doc; "converted" reads naturally in the discovery log |
| 2026-05-20 | Pre-locked: State-promoter implementation = Option C (implicit body-read on pending-* docs) for v1 | User sign-off 2026-05-20. Cheaper than Option A (script run before every /inbox) and Option B (Hashi-plugin watcher), at the cost of one body-read per pending-state doc per `/inbox` run — still ~5% of today's token cost |
| 2026-05-20 | F-43 T6.2 + T6.4 marked blocked-by this spec | F-43 acceptance-flow cannot be live-validated without unified file-discovery; see `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 pause note |
| 2026-05-20 | Cross-repo: Tomo→Kado handoff for `kado-write operation=frontmatter` (same-day shipped) | OQ9 resolved BEFORE PRD draft. Tomo opened `_outbox/for-kado/2026-05-20_tomo-to-kado_kado-write-operation-frontmatter.md` (full-body round-trip eliminated, regex-YAML-edit bug class removed). Kado accepted design (merge default, arrays replace, body byte-identical, server normalises closing fence newline) and shipped in **Kado 0.9.6** (PR #49, commit 71ea690) the same day. Tomo replies archived in `_inbox/from-kado/2026-05-20_kado-to-tomo_kado-write-frontmatter-*.md`. **Consequence for F-47**: P1 scope adds a `kado_client.write_frontmatter(path, fm_dict, mode='merge', expected_modified=None)` wrapper; producer-side state writes use the new op from day one; the optional follow-up to migrate `tag-captured.py:96-184` away from regex YAML edit is now in-scope (removes the `feedback_frontmatter_newline_guard.md` failure mode at the Tomo layer too). No legacy fallback needed for the kado-write path. |
| 2026-05-20 | OQ batch-lock (9 of 14 closed) | User signed off on: OQ1 (hybrid byTag+listDir for fresh items), OQ2 (tag at Pass 1 dispatch), OQ3 (nested tag syntax), OQ4 (**no backward-compat — clean cut-over, Privat-Test reset**), OQ5 (filename rename going-forward only), OQ7 (configurable `tag_prefix` retained), OQ8 (accept byTag-pollution noise), OQ10 (replace tag-transition), OQ11 (suggestions 2-state, drop `converted`), OQ12 (moc-proposal 2-state, drop file-level `rejected`), OQ13 (Hashi auto-cleanup on instructions-applied + manual orphan-delete). Still open: OQ6 (MCP/tool-call layer optimizations — PRD section), OQ14 (PRD must include explicit flow diagrams for `/inbox` + `/moc-propose`). OQ4 is the biggest hebel — drops F-47.P5 entirely (no legacy fallback to remove). |

## Context

F-47 — Unified frontmatter + byTag discovery for all Tomo-produced docs. Replaces today's scattered detection model (filename-suffix in `state-init.py` SKIP_SUFFIXES + markdown-checkbox body-reads in `/inbox` Auto-Discovery + `#<tag_prefix>/captured` frontmatter tag on source items) with a single `#tomo/<doc-type>/<state>` hierarchical tag + `tomo:` frontmatter block on every Tomo-produced doc.

Surfaced from F-43 T6.2 live-validation findings (2026-05-20): `/inbox` Auto-Discovery does `listDir + 3× kado-read` of full file bodies to count `[x] Applied` / `[x] Approved` checkboxes; `tomo-moc-proposal-*` not in SKIP_SUFFIXES (filename uses prefix not suffix); state split across 3 mechanisms. F-43 acceptance-flow for proposal-docs has no discovery path — needs unified model first.

**State machines (locked 2026-05-20)**:

- **source**: `pending` (untagged in inbox) → `captured` (Pass 1 Phase C via `tag-captured.py`). Source items have no `#tomo/*` tag until Pass 1 dispatch — fresh-item discovery uses listDir (untagged = fresh).
- **suggestions**: `pending-approval` → `approved`. Pass 1 writes `pending-approval`. State-promoter Option C reads the body of `pending-approval` docs to detect `[x] Approved`; on hit, dispatches Pass 2 (instruction-builder); after Pass 2 success, flips suggestions tag to `approved`. The intermediate "user-ticked-but-Pass-2-not-yet-done" state is process-time only (seconds), not a file state.
- **moc-proposal**: `pending-accept` → `accepted`. `/moc-propose` writes `pending-accept`. State-promoter Option C reads body for any cluster `[x] Accept`; on hit, dispatches MOC-consumption; after success, flips tag to `accepted`. Per-cluster rejection (un-ticked clusters) handled as side-effect via existing squelch-persistence (`state/moc-squelch.json`) — no file-level `rejected` state.
- **instructions**: `pending-apply` → `applied`. Pass 2 / MOC-consumption writes `pending-apply`. Hashi flips per-action `[x] Applied` as it executes; when ALL actions applied, Hashi flips the file's `#<prefix>/instructions/applied` tag AND deletes/archives the linked input docs per cleanup contract (see below).

**Cleanup pattern (locked 2026-05-20)**:

- **Instructions-done auto-cleanup** — when Hashi reaches `applied` (last action done), it auto-deletes (Obsidian trash) the instructions doc + its linked source docs. Hashi reads `tomo:` frontmatter references (`source_suggestions: <path>`, `source_moc_proposal: <path>` — added in F-47 producer-side writes) to know what to delete alongside. Cross-repo handoff to Hashi tracked in `_outbox/for-hashi/` once F-47 ships P1.
- **Orphan cleanup** — manual via Obsidian (right-click → delete). Examples: a `pending-approval` suggestion the user abandons; a `pending-accept` moc-proposal the user closes without accepting clusters. Tomo does not auto-archive these; inbox volume doesn't justify a script. State-promoter ignores them (they sit as `pending-*` until user deletes or finally ticks an approve box).

**Locked questions (close 2026-05-20 — move to Decisions Log when PRD picks them up)**:

- **OQ1** (byTag-only vs hybrid byTag+listDir for fresh source items) → **hybrid**. Implied by OQ2: fresh items are untagged, only listDir finds them; byTag finds the rest.
- **OQ2** (source-item tagging boundary) → **tag at Pass 1 dispatch**. No on-arrival watcher.
- **OQ3** (tag hierarchy syntax) → **nested** `#tomo/<doc-type>/<state>`.
- **OQ4** (backward-compat duration) → **none**. Solo-developer Tomo today; clean cut-over, no legacy fallback in state-init/orchestrator. Privat-Test gets reset as part of F-47 rollout.
- **OQ5** (filename rename strategy) → **going-forward only**. No bulk-rename of existing `tomo-moc-proposal-*.md` files; Privat-Test reset removes the few that exist.
- **OQ7** (tag namespace) → **configurable**. Keep `tag_prefix` (default `MiYo-Tomo`) → `#<prefix>/<doc-type>/<state>`. Matches prior-art on `#<prefix>/captured`.
- **OQ8** (byTag-pollution mitigation) → **accept noise**. No client-side inbox-path filter on byTag results. If a user manually applies `#<prefix>/...` outside inbox it's harmless; we don't defend against self-inflicted misuse.
- **OQ10** (tag transition semantics) → **replace**. Old state-tag removed when new one is set. Matches Kado 0.9.6 `mode=merge` `tags` array-replace semantics naturally.
- **OQ9** (Kado frontmatter patch-op) → **RESOLVED 2026-05-20** before PRD draft. Kado shipped `kado-write operation=frontmatter` in Kado 0.9.6 same-day after Tomo handoff. F-47.P1 uses `write_frontmatter` directly.
- **OQ11** (suggestions state-machine simplification) → **2-state**: `pending-approval → approved`. `converted` dropped — state-promoter runs Pass 2 immediately on `[x] Approved` detection, no intermediate "user-ticked-but-Pass-2-pending" file state.
- **OQ12** (moc-proposal state-machine simplification) → **2-state**: `pending-accept → accepted`. No file-level `rejected`. Per-cluster rejection handled via squelch-persistence (existing F-43 mechanism).
- **OQ13** (cleanup pattern) → **Hashi auto-deletes on instructions-applied** (instructions + linked source-suggestions + linked source-moc-proposal via `tomo:` frontmatter refs). **Manual delete for orphans** (abandoned `pending-*` docs). No Tomo-side cleanup script.

**Still open — PRD must work these through**:

- **OQ6** (MCP / tool-call layer optimizations beyond byTag + read_frontmatter) — needs ruhig diskutiert im PRD. Candidates to evaluate:
  - `kado-search byTag` with server-side `path-prefix` filter (avoid client-side filtering of unrelated `#<prefix>/...` matches if we later care about pollution)
  - Batched `read_frontmatter` — paths[] → frontmatters[] in one call (currently 1 call per file)
  - Combined `kado-list-by-tag` op returning path + frontmatter + tags in one round-trip (skip the byTag → read_frontmatter chain)
  - Each candidate is a potential Kado-side handoff (separate spec). PRD evaluates value/cost.
- **OQ14** (PRD shape requirement — surfaced 2026-05-20): PRD must include **explicit flow diagrams** showing files × tags × phases end-to-end for **`/inbox`** (Pass 1 + Pass 2 + state-promoter) and **`/moc-propose`** (discovery + acceptance + MOC-consumption). Implicit until now; locked as a PRD section.

**Migration phases (locked 2026-05-20 — revised after OQ4 = no backward-compat lock)**:

| Phase | Scope | Risk |
|---|---|---|
| F-47.P1 | Schema (`tomo/schemas/doc-frontmatter.schema.json`) + producer-side writes — all scripts emit `#<prefix>/<doc-type>/<state>` tag + `tomo:` frontmatter block (with `source_suggestions` / `source_moc_proposal` refs where applicable) via new `kado_client.write_frontmatter()` wrapper (Kado 0.9.6 op). Also: migrate `tag-captured.py:96-184` away from regex YAML edit to use the wrapper (removes `feedback_frontmatter_newline_guard.md` failure mode). | low — additive |
| F-47.P2 | Consumer **clean cut-over**: state-init + Auto-Discovery + orchestrator Phase A switched to byTag + read_frontmatter. **No legacy fallback** (OQ4 lock). Privat-Test gets reset as prereq. | mid — discovery logic + test-vault reset |
| F-47.P3 | Filename rename (`tomo-moc-proposal-YYYYMMDD-HHMM-<slug>.md` → `YYYY-MM-DD_HHMM_moc-proposal-<slug>.md`) + `-diff.md` → `_instructions-diff.md`. **Going-forward only** (OQ5 lock — no bulk migration). | low — file naming |
| F-47.P4 | MOC-consumption flow (moc-proposal/accepted → instructions/pending-apply via instruction-builder MOC-branch). Closes F-43 acceptance-gap (T6.2 + T6.4 unblock). | high — new workflow branch |
| ~~P5~~ | ~~Legacy-fallback removal~~ — **dropped**. OQ4 locked no fallback in P2; nothing to remove. |  |

**Cross-repo handoffs**:

- **Kado** — `kado-write operation=frontmatter` (OQ9). ✅ Shipped Kado 0.9.6 same-day (`_outbox/for-kado/2026-05-20_tomo-to-kado_kado-write-operation-frontmatter.md`).
- **Hashi** — auto-cleanup-on-applied behaviour. Hashi reads `tomo: source_suggestions` / `source_moc_proposal` refs from the instructions doc's frontmatter; when last action `[x] Applied`, deletes (Obsidian trash) the instructions doc + linked sources. Handoff to be opened during F-47.P1 once the frontmatter ref shape stabilises (PRD locks the schema field names).

**Hard blocker for**: F-43 T6.2 + T6.4 (proposal-doc acceptance live-validation). Inherited by F-44/F-45/F-46 — they'll use the unified model from day one.

**Touch points** (preliminary, to be confirmed in SDD): `state-init.py`, `inbox.md`, `inbox-orchestrator.md` Phase A, `suggestions-render.py`, `instruction-render.py`, `suggestions-reducer.py` (--moc-proposal-mode), `tag-captured.py`, `vault-executor`, `suggestion-parser._is_moc_proposal_doc`, new `tomo/schemas/doc-frontmatter.schema.json`.

---
*This file is managed by the xdd-meta skill.*
