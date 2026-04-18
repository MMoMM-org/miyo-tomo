---
title: "Phase 2 — Vault Explorer"
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
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup
- [x] All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)`

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/reference/tier-1/pkm-intelligence-architecture.md` — Root architecture
- `docs/XDD/reference/tier-2/workflows/vault-exploration.md` — Vault exploration workflow
- `docs/XDD/reference/tier-2/components/discovery-cache.md` — Discovery cache component
- `docs/XDD/reference/tier-3/vault-exploration/` — Structure scan, topic extraction, cache generation
- `docs/XDD/reference/tier-3/discovery/moc-indexing.md` — MOC tree building
- `docs/XDD/reference/tier-3/wizard/first-session-discovery.md` — /explore-vault flow
- `docs/XDD/reference/tier-3/lyt-moc/` — MOC matching, section placement
- `docs/XDD/reference/tier-3/config/` — Frontmatter, relationship, tag, callout detection

**Key Design Decisions**:

- **ADR-1**: Python scripts call Kado HTTP API directly, return compact JSON to agents
- **ADR-2**: Scripts handle deterministic data processing; agents handle user interaction
- **ADR-3**: Discovery cache overwrites on each scan (no merge) to prevent stale data
- **ADR-4**: Cache is advisory — Tomo degrades gracefully without it
- **ADR-5**: First run = full scan + user confirmation; subsequent = silent cache rebuild

**Implementation Context**:

```bash
# Python scripts
python3 scripts/vault-scan.py --help
python3 scripts/topic-extract.py --help
python3 scripts/moc-tree-builder.py --help
python3 scripts/cache-builder.py --help

# Validation
bash scripts/test-phase1.sh              # Phase 1 still passes
python3 -c "import yaml"                 # PyYAML available in container
```

---

## Implementation Phases

Each phase is defined in a separate file.

- [x] [Phase 1: Scan Scripts](phase-1.md)
- [x] [Phase 2: MOC Discovery + Cache Assembly](phase-2.md)
- [x] [Phase 3: Agent Artifacts](phase-3.md)
- [x] [Phase 4: Integration Validation](phase-4.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | :white_check_mark: |
| Every task produces a verifiable deliverable | :white_check_mark: |
| Dependencies are explicit with no circular references | :white_check_mark: |
| Parallel opportunities are marked with `[parallel: true]` | :white_check_mark: |
| Each task has specification references `[ref: ...]` | :white_check_mark: |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | :white_check_mark: |
