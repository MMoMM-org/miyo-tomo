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
| 007 | [Pipeline Tokens & Config Batch](specs/007-pipeline-tokens-and-config-batch/) | Completed | Direct implementation; no formal phase plan |
| 008 | [Deterministic Instruction Render](specs/008-deterministic-instruction-render/) | Completed | All phases shipped and live-validated 2026-04-21 |
| 009 | [Voice Memo Transcription](specs/009-voice-memo-transcription/) | Code-complete | Phases 1–5 merged; host validation (T5.1/T5.2) pending |
| 010 | [Custom File Picker](specs/010-custom-file-picker/) | Completed | Unified picker live; Phases 3–4 validated 2026-04-21 |
| 011 | [Instance Backup & Restore](specs/011-instance-backup-restore/) | Completed | Scripts shipped 2026-04-20; spec docs backfilled 2026-04-21 |
| 012 | [Force Atomic Synthesis](specs/012-force-atomic-synthesis/) | Completed | Shipped 2026-04-23 (commit `08a1f22`) |
| 013 | [MOC Creation Skill](specs/013-moc-creation-skill/) | Implemented | 6 phases, 29 tasks; implemented 2026-05-09 (feat/013-phase-4); live-vault validation pending (T6.2) |
| 015 | [MSP Condition B — Accumulation](specs/015-msp-condition-b-accumulation/) | Superseded | Shipped 2026-06-04 then **superseded by 021** (2026-06-10) — Condition B retired from `/inbox`, capability moved to `/moc-propose`; GH #27 closed |
| 016 | [Multi-Topic Atomic Notes](specs/016-multi-topic-atomic-notes/) | PRD-only | PRD drafted 2026-05-07; SDD + plan deferred pending stakeholder input (OQ1–OQ8) |
| 018 | [Agent Architecture Cleanup](specs/018-agent-architecture-cleanup/) | Live-validated | Review + live testing complete 2026-05-27. Conductors refactored to pure routers, skills own pipelines, synthesis-conductor dispatched on haiku, moc-proposal-parser added, related:: aggregation Tomo-side, inbox-triage state coverage extended. |

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
