---
title: "Phase 3: Agent Artifacts"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Agent Artifacts

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/specs/tier-3/wizard/first-session-discovery.md` — /explore-vault 10-step flow
- `docs/specs/tier-3/lyt-moc/moc-matching.md` — MOC matching algorithm
- `docs/specs/tier-3/lyt-moc/section-placement.md` — where to place links in MOCs
- `docs/specs/tier-3/lyt-moc/new-moc-proposal.md` — Mental Squeeze Point detection
- `docs/specs/tier-3/config/frontmatter-schema.md` — frontmatter detection
- `docs/specs/tier-3/config/relationship-config.md` — relationship detection
- `docs/specs/tier-3/config/tag-taxonomy.md` — tag detection
- `docs/specs/tier-3/config/callout-mapping.md` — callout detection

**Key Decisions**:
- Agent artifacts are Claude Code markdown files (agents, commands, skills)
- They live in tomo/ source and get copied to instance by install script
- vault-explorer agent orchestrates the /explore-vault flow and delegates to Python scripts
- Skills encode reusable knowledge patterns (LYT, Obsidian fields)

**Dependencies**:
- Phase 1 + 2 (Python scripts must exist so agents know what to call)

---

## Tasks

Creates the Claude Code agent, command, and skill definitions that orchestrate vault exploration.

- [ ] **T3.1 Vault Explorer Agent** `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/wizard/first-session-discovery.md]` for the 10-step flow and `[ref: docs/specs/tier-2/workflows/vault-exploration.md]` for the 7-step workflow
  2. Test: Agent definition includes: persona, constraints, 10-step workflow (connect → structure scan → frontmatter → tags → relationships → callouts → trackers → templates → MOC indexing + cache → summary); delegates to Python scripts via bash; presents findings and gets user confirmation per section; handles first-run vs subsequent (--confirm flag); writes confirmed config; calls cache-builder for final output
  3. Implement: Create `tomo/.claude/agents/vault-explorer.md` — Claude Code agent definition following the Tomo agent pattern. Include version comment.
  4. Validate: Agent file is valid markdown; references correct script paths; workflow matches spec
  5. Success: Agent covers all 10 discovery steps; delegates deterministic work to scripts; handles user interaction for confirmations

- [ ] **T3.2 Explore Vault Command** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read existing command files in `tomo/.claude/commands/` for pattern reference
  2. Test: Command triggers vault-explorer agent; supports --confirm flag for re-running detection; provides clear user instructions
  3. Implement: Create `tomo/.claude/commands/explore-vault.md` — Claude Code command that invokes the vault-explorer agent
  4. Validate: Command file follows Claude Code command format
  5. Success: `/explore-vault` triggers the vault-explorer agent correctly

- [ ] **T3.3 LYT Patterns Skill** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/lyt-moc/moc-matching.md]`, `[ref: docs/specs/tier-3/lyt-moc/section-placement.md]`, `[ref: docs/specs/tier-3/lyt-moc/new-moc-proposal.md]`
  2. Test: Skill defines MOC matching algorithm (overlap scoring, depth bonus, size penalty); section placement rules (where to add links in MOCs); Mental Squeeze Point detection (3+ items share topics, no MOC match → propose new MOC); confidence thresholds
  3. Implement: Create `tomo/.claude/skills/lyt-patterns.md` — Claude Code skill encoding LYT/MOC knowledge patterns
  4. Validate: Skill file is valid markdown; scoring algorithm matches spec; thresholds match
  5. Success: Skill provides complete MOC matching, placement, and new-MOC proposal knowledge

- [ ] **T3.4 Obsidian Fields Skill** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/config/frontmatter-schema.md]`, `[ref: docs/specs/tier-3/config/relationship-config.md]`, `[ref: docs/specs/tier-3/config/callout-mapping.md]`, `[ref: docs/specs/tier-3/config/tag-taxonomy.md]`
  2. Test: Skill defines frontmatter handling (required/optional fields, validation, generation); relationship markers (reading/writing up::, related:: in various positions); callout classification (editable/protected/ignore boundaries); tag taxonomy (prefix structure, wildcard behavior, assignment logic)
  3. Implement: Create `tomo/.claude/skills/obsidian-fields.md` — Claude Code skill encoding Obsidian field handling patterns
  4. Validate: Skill file is valid markdown; covers all 4 config domains
  5. Success: Skill provides complete Obsidian field knowledge for agents

- [ ] **T3.5 Phase Validation** `[activity: validate]`

  - All agent/command/skill files exist in tomo/.claude/. vault-explorer agent references correct script paths. Command invokes correct agent. Skills cover all spec-defined patterns. Version comments present on all files.
