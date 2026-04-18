# Tomo Documentation Index

> Single entry point for all Tomo specifications and architecture reference.

## Implementation Specs

| ID | Name | Phase | Status |
|----|------|-------|--------|
| 001 | [Config Foundation](specs/001-phase-1-config-foundation/) | Ready | Plan complete (28/28 tests) |
| 002 | [Vault Explorer](specs/002-phase-2-vault-explorer/) | Ready | Plan complete (34/34 tests) |
| 003 | [Inbox Processing](specs/003-phase-3-inbox-processing/) | Ready | Plan complete (40/40 tests) |
| 004 | [Inbox Fan-Out Refactor](specs/004-inbox-fanout-refactor/) | Completed | Full suite (PRD + SDD + Plan, 21/21 tests) |
| 005 | [Daily Note Workflow](specs/005-daily-note-workflow/) | Completed | Full suite (PRD + SDD + Plan) |
| 006 | [Spec Consolidation](specs/006-spec-consolidation/) | Ready | Full suite (PRD + SDD + Plan) |

## Architecture Reference

Migrated from `docs/specs/` (2026-04-18, XDD-006). Kokoro (`~/Kouzou/projects/miyo/`) is the architectural authority. These docs reflect Tomo's implementation with inline deviation annotations where applicable.

### Tier 1 — Framework
- [PKM Intelligence Architecture](reference/tier-1/pkm-intelligence-architecture.md)

### Tier 2 — Components
- [Universal PKM Concepts](reference/tier-2/components/universal-pkm-concepts.md)
- [Framework Profiles](reference/tier-2/components/framework-profiles.md)
- [User Config](reference/tier-2/components/user-config.md)
- [Discovery Cache](reference/tier-2/components/discovery-cache.md)
- [Template System](reference/tier-2/components/template-system.md)
- [Setup Wizard](reference/tier-2/components/setup-wizard.md)

### Tier 2 — Workflows
- [Inbox Processing](reference/tier-2/workflows/inbox-processing.md) -- deviations (XDD-004)
- [Daily Note](reference/tier-2/workflows/daily-note.md) -- deviations (XDD-005)
- [LYT/MOC Linking](reference/tier-2/workflows/lyt-moc-linking.md)
- [Vault Exploration](reference/tier-2/workflows/vault-exploration.md)

### Tier 3 — Details
- **Config**: [Frontmatter Schema](reference/tier-3/config/frontmatter-schema.md) | [Relationship Config](reference/tier-3/config/relationship-config.md) | [Tag Taxonomy](reference/tier-3/config/tag-taxonomy.md) | [Callout Mapping](reference/tier-3/config/callout-mapping.md)
- **Discovery**: [MOC Indexing](reference/tier-3/discovery/moc-indexing.md) | [Classification Matching](reference/tier-3/discovery/classification-matching.md) | [Staleness Policy](reference/tier-3/discovery/staleness-policy.md)
- **Daily Note**: [Detection](reference/tier-3/daily-note/daily-note-detection.md) -- deviations (XDD-005) | [Tracker Field Handling](reference/tier-3/daily-note/tracker-field-handling.md) -- deviations (XDD-005)
- **Inbox**: [Analysis](reference/tier-3/inbox/inbox-analysis.md) -- deviations (XDD-004) | [Suggestions Document](reference/tier-3/inbox/suggestions-document.md) -- deviations (XDD-004) | [Instruction Set Generation](reference/tier-3/inbox/instruction-set-generation.md) | [Instruction Set Apply](reference/tier-3/inbox/instruction-set-apply.md) | [Instruction Set Cleanup](reference/tier-3/inbox/instruction-set-cleanup.md) | [State Tag Lifecycle](reference/tier-3/inbox/state-tag-lifecycle.md)
- **LYT/MOC**: [MOC Matching](reference/tier-3/lyt-moc/moc-matching.md) | [Section Placement](reference/tier-3/lyt-moc/section-placement.md) | [New MOC Proposal](reference/tier-3/lyt-moc/new-moc-proposal.md)
- **Profiles**: [MiYo Profile](reference/tier-3/profiles/miyo-profile.md) | [LYT Profile](reference/tier-3/profiles/lyt-profile.md)
- **Templates**: [Token Vocabulary](reference/tier-3/templates/token-vocabulary.md) | [Template Files](reference/tier-3/templates/template-files.md)
- **Vault Exploration**: [Structure Scan](reference/tier-3/vault-exploration/structure-scan.md) | [Topic Extraction](reference/tier-3/vault-exploration/topic-extraction.md) | [Cache Generation](reference/tier-3/vault-exploration/cache-generation.md)
- **Wizard**: [Install Script](reference/tier-3/wizard/install-script.md) | [First-Session Discovery](reference/tier-3/wizard/first-session-discovery.md)

## Open Items

See [backlog.md](backlog.md) — 15 features, 4 doc-debt items.
