---
title: "Phase 1 — Config Foundation"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup
- [x] All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)`

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/specs/tier-1/pkm-intelligence-architecture.md` — Root architecture (4-layer stack, execution model)
- `docs/specs/tier-2/components/framework-profiles.md` — Profile schema and role
- `docs/specs/tier-2/components/user-config.md` — vault-config.yaml schema
- `docs/specs/tier-2/components/template-system.md` — Template rendering pipeline
- `docs/specs/tier-2/components/setup-wizard.md` — Two-phase setup design
- `docs/specs/tier-3/` — All Tier 3 detail specs (profiles, templates, wizard, config, inbox, discovery, etc.)

**Key Design Decisions**:

- **ADR-1**: Profiles = data, Skills = logic — profiles are pure YAML with no conditionals
- **ADR-2**: Layer precedence L3 > L2 > L1 — user config always wins over profile defaults
- **ADR-3**: MVP execution boundary — Tomo writes only to inbox folder; user applies everything else
- **ADR-4**: Template token syntax `{{token}}` — simple string replacement, Templater syntax preserved
- **ADR-5**: Two-phase setup — install script (host, no Kado) + first-session discovery (Docker, Kado live)

**Implementation Context**:

```bash
# Validation (shell scripts)
bash -n scripts/install-tomo.sh       # Syntax check
shellcheck scripts/install-tomo.sh    # Lint (if available)

# Validation (Python)
python3 -c "import yaml"             # YAML module available
python3 scripts/yaml-fixer.py --help  # Smoke test

# Validation (YAML)
python3 -c "import yaml; yaml.safe_load(open('tomo/profiles/miyo.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('tomo/profiles/lyt.yaml'))"

# Full validation
bash scripts/install-tomo.sh --help   # Verify non-interactive flags work
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Framework Profiles](phase-1.md)
- [x] [Phase 2: Reference Templates + Config Schema](phase-2.md)
- [x] [Phase 3: Install Script + YAML Fixer](phase-3.md)
- [x] [Phase 4: Integration Validation](phase-4.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | :white_check_mark: |
| Every task produces a verifiable deliverable | :white_check_mark: |
| All PRD acceptance criteria map to specific tasks | :white_check_mark: |
| All SDD components have implementation tasks | :white_check_mark: |
| Dependencies are explicit with no circular references | :white_check_mark: |
| Parallel opportunities are marked with `[parallel: true]` | :white_check_mark: |
| Each task has specification references `[ref: ...]` | :white_check_mark: |
| Project commands in Context Priming are accurate | :white_check_mark: |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | :white_check_mark: |
