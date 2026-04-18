# Open Items Backlog

> Consolidated from tier specs, XDD specs, and implementation observations.
> Created: 2026-04-18 (XDD-006 spec consolidation).
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

## Documentation Debt

| ID | Item | Source | Priority | Notes |
|----|------|--------|----------|-------|
| D-01 | Tier 1 agent table outdated | reference/tier-1/pkm-intelligence-architecture.md §6 | Should | Still lists `suggestion-builder`; should reference orchestrator + subagent model (deviation noted but table not updated) |
| D-02 | Broken cross-reference in template-system | reference/tier-2/components/template-system.md | Should | Links to `../../references/tomo-lyt-knowledge-model-spec.md#8-parking-lot` — file doesn't exist at that path |
| D-03 | Broken cross-reference in workflow specs | reference/tier-2/workflows/inbox-processing.md, daily-note.md | Should | `> Related: [existing workflow doc](../../workflows/inbox-process.md)` — directory doesn't exist after migration |
| D-04 | Daily-note detection config examples outdated | reference/tier-3/daily-note/daily-note-detection.md | Could | Config YAML examples marked `(future)` but some are now implemented via XDD-005 |

## Known Issues

| ID | Item | Source | Priority | Notes |
|----|------|--------|----------|-------|
| B-01 | (none identified) | — | — | All known implementation issues addressed in XDD 001-005 |
