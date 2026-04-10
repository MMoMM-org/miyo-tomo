# Tomo Specifications — Pyramid Index

> How Tomo encodes, stores, and uses PKM intelligence to work with Obsidian vaults.
> Brainstorm spec: `tomo/references/tomo-lyt-knowledge-model-spec.md`

## Structure

Specs are organized in tiers. Each tier traces upward to its parent. Implementation can start at any tier.

- **Tier 1** — Framework: the architectural vision and core patterns
- **Tier 2** — Components (WHAT exists) and Workflows (HOW they interact)
- **Tier 3** — Details: implementable units with clear scope and acceptance criteria

## Pyramid

```
Tier 1 (Framework)
└── PKM Intelligence Architecture
    ├── 4-Layer Knowledge Stack + Precedence
    ├── Decision Flow Pattern
    ├── Two-Phase Setup Flow
    ├── Execution Model
    │   ├── MVP: Tomo writes inbox-only, User Applies outside
    │   └── Post-MVP: Seigyo locked scripts with dual vetting
    └── Inbox 2-Pass Model
        ├── Pass 1: Action Suggestions (user picks direction)
        └── Pass 2: Instruction Set (user applies details)
```

## Critical Architectural Boundary (MVP)

**Tomo writes only to the inbox folder.** All vault content changes outside the inbox are applied **manually by the user** during MVP. This is a deliberate constraint to keep execution deterministic — even with Kado as a safe access layer, AI-driven execution introduces variance that the inbox-only boundary eliminates.

Post-MVP introduces **Seigyo** (Obsidian control plugin) as the deterministic executor for outside-inbox changes, using locked scripts after dual vetting (action proposals + script proposals).

See [Tier 1 §7 Execution Model](tier-1/pkm-intelligence-architecture.md#7-execution-model) for full rationale.

### Tier 2 — Components

| Spec | Status | Description |
|------|--------|-------------|
| [Universal PKM Concepts](tier-2/components/universal-pkm-concepts.md) | Draft | Framework-agnostic vocabulary: concepts, relationships, lifecycle |
| [Framework Profiles](tier-2/components/framework-profiles.md) | Draft | Profile schema, planned profiles (MiYo, LYT, PARA) |
| [User Config](tier-2/components/user-config.md) | Draft | vault-config.yaml schema, precedence, validation |
| [Discovery Cache](tier-2/components/discovery-cache.md) | Draft | Semantic index, staleness policy, degraded operation |
| [Template System](tier-2/components/template-system.md) | Draft | Token vocabulary, rendering pipeline, note type mapping |
| [Setup Wizard](tier-2/components/setup-wizard.md) | Draft | Two-phase onboarding: install script + first-session discovery |

### Tier 2 — Workflows

| Spec | Status | Description |
|------|--------|-------------|
| [Inbox Processing](tier-2/workflows/inbox-processing.md) | Draft | **2-Pass model:** Pass 1 Suggestions → user confirms direction → Pass 2 Instruction Set → user applies → cleanup |
| [Daily Note](tier-2/workflows/daily-note.md) | Draft | Daily note tracker updates (multi-syntax), content injection. Weekly+ post-MVP. |
| [LYT/MOC Linking](tier-2/workflows/lyt-moc-linking.md) | Draft | MOC tree (all levels), classification, section placement, new MOC proposals, standalone density scan |
| [Vault Exploration](tier-2/workflows/vault-exploration.md) | Draft | Structure scan, topic extraction, MOC tree discovery (path + tag), cache generation |

### Tier 3 — Details

| Parent | Spec | Status | Description |
|--------|------|--------|-------------|
| Profiles | [MiYo Profile](tier-3/profiles/miyo-profile.md) | Draft | Development target, Marcus's vault conventions |
| Profiles | [LYT Profile](tier-3/profiles/lyt-profile.md) | Draft | Validation target, standard Ideaverse conventions |
| Config | [Frontmatter Schema](tier-3/config/frontmatter-schema.md) | Draft | Required/optional fields, formats, validation |
| Config | [Relationship Config](tier-3/config/relationship-config.md) | Draft | Marker-based patterns, position rules |
| Config | [Tag Taxonomy](tier-3/config/tag-taxonomy.md) | Draft | Prefix system, assignment rules |
| Config | [Callout Mapping](tier-3/config/callout-mapping.md) | Draft | Editable vs protected, section semantics |
| Discovery | [MOC Indexing](tier-3/discovery/moc-indexing.md) | Draft | MOC tree building (path+tag discovery), placeholder detection, level assignment |
| Discovery | [Classification Matching](tier-3/discovery/classification-matching.md) | Draft | Keyword scoring algorithm, profile+cache enrichment, fallback mechanism |
| Discovery | [Staleness Policy](tier-3/discovery/staleness-policy.md) | Draft | Age thresholds, degraded operation modes, on-demand fallback |
| Templates | [Token Vocabulary](tier-3/templates/token-vocabulary.md) | Draft | Built-in + user-defined tokens, resolution order, YAML list formatting |
| Templates | [Template Files](tier-3/templates/template-files.md) | Draft | Reference templates per note type, Templater coexistence, fallback |
| Wizard | [Install Script](tier-3/wizard/install-script.md) | Draft | Phase 1: 10-step host-side flow, concept mapping UX, non-interactive mode |
| Wizard | [First-Session Discovery](tier-3/wizard/first-session-discovery.md) | Draft | Phase 2: 10-step Kado scan, detection + confirmation per config section |
| Inbox | [Inbox Analysis](tier-3/inbox/inbox-analysis.md) | Draft | inbox-analyst agent, classification with alternatives, MOC matching with confidence |
| Inbox | [Suggestions Document (Pass 1)](tier-3/inbox/suggestions-document.md) | Draft | suggestion-builder agent, suggestions format with alternatives |
| Inbox | [Instruction Set Generation (Pass 2)](tier-3/inbox/instruction-set-generation.md) | Draft | instruction-builder agent, detailed action format |
| Inbox | [Instruction Set Apply (User)](tier-3/inbox/instruction-set-apply.md) | Draft | MVP: user manually applies approved actions in Obsidian |
| Inbox | [Instruction Set Cleanup](tier-3/inbox/instruction-set-cleanup.md) | Draft | vault-executor (inbox-side only): tagging, archiving processed inbox items |
| Inbox | [State Tag Lifecycle](tier-3/inbox/state-tag-lifecycle.md) | Draft | captured → proposed → confirmed → instructions → applied → active/archived |
| Daily Note | [Daily Note Detection](tier-3/daily-note/daily-note-detection.md) | Draft | Path computation, missing note policy (skip/suggest/create), multi-day coverage |
| Daily Note | [Tracker Field Handling](tier-3/daily-note/tracker-field-handling.md) | Draft | 3 syntaxes (inline/checkbox/frontmatter), 5 value types, trigger keywords, read-before-write |
| LYT/MOC | [MOC Matching](tier-3/lyt-moc/moc-matching.md) | Draft | Topic overlap scoring, depth bonus, size penalty, confidence ranking |
| LYT/MOC | [Section Placement](tier-3/lyt-moc/section-placement.md) | Draft | H2 section matching, protected zone avoidance, link format detection |
| LYT/MOC | [New MOC Proposal](tier-3/lyt-moc/new-moc-proposal.md) | Draft | Mental Squeeze Point (4 triggers), placeholder resolution, /scan-mocs command |
| Exploration | [Structure Scan](tier-3/vault-exploration/structure-scan.md) | Draft | Concept folder mapping, subdirectory detection, unmapped folder handling |
| Exploration | [Topic Extraction](tier-3/vault-exploration/topic-extraction.md) | Draft | 5 extraction methods (title, H2, links, LLM, tags), normalization |
| Exploration | [Cache Generation](tier-3/vault-exploration/cache-generation.md) | Draft | Assembly order, section schemas, validation, progress reporting |

## Status Legend

| Status | Meaning |
|--------|---------|
| — | Not started |
| Draft | Spec written, not reviewed |
| Review | Under review |
| Approved | Ready for implementation |
| In Progress | Implementation started |
| Done | Implemented and verified |

## Cross-References

- Brainstorm research: `tomo/references/lyt-obsidian-knowledge-model.md`
- External research: `tomo/references/tomo-external-research.md`
- Brainstorm spec: `tomo/references/tomo-lyt-knowledge-model-spec.md`
- Tomo architecture: `global/architecture/04-miyo-tomo.md`
- Kado API contract: `global/references/kado-v1-api-contract.md`
