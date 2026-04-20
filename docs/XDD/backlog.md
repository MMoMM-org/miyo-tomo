# Open Items Backlog

> Consolidated from tier specs, XDD specs, and implementation observations.
> Created: 2026-04-18 (XDD-006 spec consolidation).
> Updated: 2026-04-19 (spec-vs-IST audit, profile gap analysis).
> Maintained as a living document — update when new items are identified or items are completed.

## Features (Post-MVP)

| ID | Item | Source | Priority | Notes |
|----|------|--------|----------|-------|
| F-01 | Seigyo execution via locked scripts | reference/tier-1/pkm-intelligence-architecture.md §7 | Must | Replaces user-applied workflow with deterministic script execution + dual vetting |
| F-02 | Periodic notes beyond daily (weekly, monthly, quarterly, yearly) | reference/tier-2/workflows/daily-note.md §7 | Should | Requires synthesis (LLM judgment), periodic-note config surface, learning from MVP usage first |
| F-03 | Templater rendering by Tomo | reference/tier-2/components/template-system.md §3 | Should | Eliminate user's manual Templater step; currently parked |
| F-04 | Profile switching post-install | reference/tier-2/components/framework-profiles.md | Could | Migration path between profiles (e.g., LYT → MiYo); out of scope for MVP |
| F-05 | Topic weighting in MOC matching | reference/tier-3/vault-exploration/topic-extraction.md | Could | Title/heading topics should score higher than content keywords; MVP treats equally |
| F-06 | Configurable confidence thresholds | reference/tier-3/lyt-moc/moc-matching.md | Could | `confidence_threshold` and `max_results` currently hardcoded; future vault-config fields |
| F-07 | Configurable classification threshold | reference/tier-3/discovery/classification-matching.md | Could | `classification.confidence_threshold` in vault-config |
| F-08 | Configurable MOC proposal minimum | reference/tier-3/lyt-moc/new-moc-proposal.md | Could | `moc_proposal.min_notes` in vault-config (default: 3) |
| F-09 | Incremental cache refresh | reference/tier-3/discovery/moc-indexing.md §8 | Could | Currently full rebuild on every `/explore-vault`; delta refresh for performance |
| F-10 | Automated applied-action detection | reference/tier-3/inbox/instruction-set-cleanup.md §5 | Could | Auto-detect whether user applied actions without manual tag change |
| F-11 | Callout-based tracker syntax | reference/tier-2/workflows/daily-note.md §5 | Could | Custom plugin tracker syntaxes beyond inline_field, task_checkbox, frontmatter |
| F-12 | Atomic note sub-types (LYT) | reference/tier-3/profiles/lyt-profile.md | Could | Classify atomic notes into sub-types during inbox processing; MVP treats as flat |
| F-13 | Standalone MOC density scan | reference/tier-2/workflows/lyt-moc-linking.md §8 | Should | `/scan-mocs` command for vault-wide clustering (not just inbox batch) |
| F-14 | Additional PKM concepts | reference/tier-2/components/universal-pkm-concepts.md | Could | resource, reference, log, dashboard — deferred until workflows require them |
| F-15 | Batch read / chunked search in Kado | reference/tier-2/workflows/vault-exploration.md | Could | If Kado adds these, vault-explorer benefits automatically |
| F-16 | Relationship marker from config (not hardcoded) | reference/tier-3/config/relationship-config.md, moc-tree-builder.py | Should | `moc-tree-builder.py` hardcodes `up::` and `related::` regexes. Should read markers from profile/config. Also support finding markers in frontmatter (`up: [[Parent]]` as YAML key) and inside callouts (`> up:: [[Parent]]`). Important for reading; writing already uses templates. |
| F-17 | Callout full-line matching end-to-end | reference/tier-3/config/callout-mapping.md, vault-example.yaml | Should | See details below |
| F-18 | Frontmatter sampling script | reference/tier-3/config/cache-generation.md §3.5 | Could | Phase 4 deferred. `cache-builder.py` accepts `--frontmatter` input but no script generates it. Cache works without |
| F-19 | Tag analysis script | reference/tier-3/config/cache-generation.md §3.6 | Could | Phase 4 deferred. `cache-builder.py` accepts `--tags` input but no script generates it. Cache works without |
| F-20 | Orphan detection script | reference/tier-3/config/cache-generation.md §3.7 | Could | Phase 4 deferred. `cache-builder.py` accepts `--orphans` input but no script generates it. Cache works without |
| F-21 | Cache staleness warning | reference/tier-3/discovery/staleness-policy.md | Should | No code checks `last_scan` timestamp at session/run start. User doesn't know when cache is outdated (>7 days) |
| F-22 | Document splitting for large batches | reference/tier-3/inbox/suggestions-document.md §9 | Could | Soft limit 30 items. No splitting logic in reducer/renderer. Batches are typically <10 |
| F-23 | Archive subdirectory for processed items | reference/tier-3/inbox/instruction-set-cleanup.md §9 | Could | Optional move to `+/archive/YYYY-MM/`. Tags-only suffices for MVP |
| F-24 | Delete auxiliary files after cleanup | reference/tier-3/inbox/instruction-set-cleanup.md §10 | Could | Rendered notes and diffs stay in inbox after cleanup. Safer to leave for now |
| F-25 | Inbox-note template definition | XDD 009 spec discussion 2026-04-20 | Should | Tomo has atomic-note templates only; inbox-note structure is undefined (user's inbox is zettelkasten-lean). Define explicit template — frontmatter? Lifecycle tags? — so future features (incl. voice transcripts per XDD 009) can inherit it |
| F-26 | Voice memo transcription | XDD 009 spec | Should | Local whisper transcription of audio files in inbox → markdown with timestamped callouts. See `docs/XDD/specs/009-voice-memo-transcription/` |
| F-27 | Custom @-file picker (open notes / inbox / vault) | XDD 010 spec | Should | Replace built-in `@` picker with vault-aware variant: default = open Obsidian notes via `kado-open-notes`; `/inbox` and `/vault` as scope prefixes. Cache-backed for typing-rate latency. See `docs/XDD/specs/010-custom-file-picker/` |
| F-28 | Profile→vault-config copy at install time | vault-explorer cleanup 2026-04-20 | Could | When install-tomo.sh writes vault-config.yaml, copy the selected profile's `frontmatter_defaults:` into the vault-config as `frontmatter:` so `token-render.py` finds defaults without an /explore-vault step. Today users must populate it manually since vault-explorer Step 3 was retired |

### F-17 Detail: Callout Full-Line Matching (End-to-End)

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

## Documentation Debt

| ID | Item | Source | Priority | Notes |
|----|------|--------|----------|-------|
| D-01 | Tier 1 agent table outdated | reference/tier-1/pkm-intelligence-architecture.md §6 | Should | Still lists `suggestion-builder`; should reference orchestrator + subagent model (deviation noted but table not updated) |
| D-02 | Broken cross-reference in template-system | reference/tier-2/components/template-system.md | Should | Links to `../../references/tomo-lyt-knowledge-model-spec.md#8-parking-lot` — file doesn't exist at that path |
| D-03 | Broken cross-reference in workflow specs | reference/tier-2/workflows/inbox-processing.md, daily-note.md | Should | `> Related: [existing workflow doc](../../workflows/inbox-process.md)` — directory doesn't exist after migration |
| D-04 | Daily-note detection config examples outdated | reference/tier-3/daily-note/daily-note-detection.md | Could | Config YAML examples marked `(future)` but some are now implemented via XDD-005 |

## Deliberate Design Decisions (YAGNI — not gaps)

Documented here so future sessions don't re-investigate these as "missing features".

| Decision | Rationale | Date |
|----------|-----------|------|
| No frontmatter baseline in profiles | Templates ARE the frontmatter definition. A separate profile baseline would duplicate the same info and risk drift. Users should define a template, not a schema. | 2026-04-19 |
| No tag taxonomy baseline in profiles | Tag taxonomy is already fully defined in `vault-config.yaml` under `tags.prefixes` with `known_values`, `wildcard`, `required_for`. `tomo.suggestions.proposable_tag_prefixes` and `excluded_tag_prefixes` provide additional control. Profile baseline would only be seed data for first-session wizard — not needed since wizard scans vault. | 2026-04-19 |
| Workflow documents use checkboxes, not tags | Frontmatter tags are not easily accessible in Obsidian. Suggestions use `[x] Approved` (global), instructions use `[x] Applied` (per action). Discovery by filename pattern. Source items still use tags (Tomo-managed). | 2026-04-19 |
| Section placement via LLM, not deterministic scoring | Spec describes a scoring algorithm (H2 matching, depth bonus, callout avoidance). Implementation uses LLM judgment. Works correctly; deterministic scoring is future optimization if drift becomes a problem. | 2026-04-19 |
| Classification matching via LLM, not weighted scoring | Spec describes weighted keyword scoring (exact=2, cache=1, substring=0.5). Implementation uses LLM keyword-overlap heuristic. Same reasoning as section placement. | 2026-04-19 |

## Known Issues

| ID | Item | Source | Priority | Notes |
|----|------|--------|----------|-------|
| B-01 | suggestion-parser.py dropped log entries for re-seen dates | scripts/suggestion-parser.py | Fixed | Fixed 2026-04-18 (commit a963d73) |
| B-02 | instruction-render.py 404 on bare template stems | scripts/instruction-render.py | Fixed | Fixed 2026-04-18 (commit a963d73) — resolves via kado search_by_name |
