---
title: "Multi-instance first-class install + lifecycle tag-prefix cleanup"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section complete
- [x] All phases defined with linked phase files
- [x] Dependencies between phases clear (no circular dependencies)
- [x] Parallel work tagged with `[parallel: true]`
- [x] Activity hints provided
- [x] Every phase references SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests in the final phase
- [x] Project commands match actual setup

---

## Specification Compliance Guidelines

1. **Before each phase:** read the referenced PRD/SDD sections (Context Priming gate).
2. **During implementation:** reference SDD ADRs / PRD ACs per task.
3. **After each task:** run the per-task tests + `bash -n` (shell) / `ruff` (python).
4. **Phase completion:** all phase tests pass; version bumps applied; spec-compliance verified.

### Deviation Protocol
Document any deviation with rationale in the spec README Decisions Log; obtain approval before proceeding; update the SDD if the deviation improves the design.

## Metadata Reference
- `[parallel: true]` — concurrent-safe tasks
- `[ref: doc/section]` — specification link
- `[activity: type]` — specialist hint

---

## Context Priming

*GATE: Read these before any implementation.*

**Specification:**
- `docs/XDD/specs/020-multi-instance-install/requirements.md` — PRD (F1–F6 + ACs)
- `docs/XDD/specs/020-multi-instance-install/solution.md` — SDD (ADR-1..ADR-7, layout, registry schema, flows)
- `docs/XDD/backlog.md` — D-09 (shared render-launcher, closed by ADR-7)

**Key Design Decisions:**
- **ADR-1** — Self-contained `<parent>/<name>/{begin-tomo.sh, tomo-install.json, instance/, home/}`; default parent `~/MiYo/Tomo/`.
- **ADR-2** — `~/.tomo/instances.json` rebuildable index; `instance-registry.sh` helper (atomic jq); instance config is SoT.
- **ADR-3** — Identity via `-e TOMO_INSTANCE_NAME=<raw>` + sanitized `--hostname`; statusline reads env (basename fallback).
- **ADR-4** — Non-fatal launcher update-check (installed vs repo `# version:`); never block launch.
- **ADR-6** — Remove lifecycle tag prefix; repoint statusline probe to `byFrontmatter tomo.state`.
- **ADR-7** — Shared `render-launcher.sh` (closes D-09).

**Implementation Context (commands):**
```bash
# Tests (host)
python3 -m pytest tests/ -q              # python unit/integration tests
python3 -m pytest tests/<file> -q        # targeted
bash -n <script.sh>                      # shell syntax check (bash 3.2 target)
ruff check <python-files>                # python lint

# NEVER run install/update against the default path in tests — always pass
#   --instance-location <TMPDIR> --instance-name <iso> --home-dir <TMPDIR> --config-file <TMPDIR>/x.json
# (memory: feedback_test_scripts_must_never_touch_real_install)
```

---

## Implementation Phases

Each phase is a separate file. Tasks follow red-green-refactor: **Prime → Test → Implement → Validate**.

- [x] [Phase 1: Foundation libraries (registry + render-launcher)](phase-1.md)
- [x] [Phase 2: Install multi-instance flow](phase-2.md)
- [x] [Phase 3: Per-instance update + launcher identity & update-check](phase-3.md)
- [ ] [Phase 4: Lifecycle tag-prefix cleanup (Part B)](phase-4.md)
- [ ] [Phase 5: Docs sweep + finalize](phase-5.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities marked | ✅ |
| Each task has specification references | ✅ |
| Project commands accurate | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |
