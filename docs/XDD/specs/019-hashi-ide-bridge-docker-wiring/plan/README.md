---
title: "Hashi IDE Bridge Docker Wiring"
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

---

## Output Schema

### PLAN Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| phases | PhaseStatus[] | Yes | Status of each implementation phase |
| totalTasks | number | Yes | Total tasks across all phases |
| parallelTasks | number | Yes | Tasks marked `[parallel: true]` |
| specReferences | number | Yes | Count of `[ref: ...]` specification links |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |

### PhaseStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phase | number | Yes | Phase number |
| name | string | Yes | Phase name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| tasks | number | Yes | Task count in this phase |
| file | string | Yes | Path to phase file (phase-N.md) |
| detail | string | No | What needs clarification or what's in progress |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate (read the phase's Spec References)
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

**Pre-recorded deviation (carried into every phase):** the SDD lists "config mirrored to the instance" as part of the voice-pattern mirror (`begin-tomo.sh` reads the instance mirror for voice). For IDE Bridge **no instance mirror is created** — the runtime consumers already see the data they need: the entrypoint and the statusline read the **lock file** (in the bind-mounted `tomo-home/.claude/ide/`), and `begin-tomo.sh` reads `.ide_bridge` from the host's `tomo-install.json` directly. The lock file *is* the runtime mirror. This is a deliberate simplification of the voice pattern, consistent with ADR-1/ADR-2/ADR-3, and is called out where it bites (Phase 1 T1.2, Phase 3 T3.2).

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[ref: document/section; lines: X-Y]` - Links to specifications
- `[activity: type]` - Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/019-hashi-ide-bridge-docker-wiring/requirements.md` - Product Requirements (Features 1–7, ACs)
- `docs/XDD/specs/019-hashi-ide-bridge-docker-wiring/solution.md` - Solution Design (Feature-mirror architecture, ADR-1..5, interfaces)

**Pattern source to mirror** (read before touching anything — the whole feature copies this pattern):

- `scripts/lib/configure-voice.sh` - the wizard-lib template (`configure_*` + `write_*_config`)
- `tests/voice/test_configure_voice.py` - the subprocess test harness for a bash wizard lib
- `scripts/install-tomo.sh` (Step 6c, lines ~910–930; save-config block, lines ~1257–1298) - voice call-site + config persistence + instance mirror
- `scripts/update-tomo.sh` (lines ~424–469, 631–659) - voice update path (keep/update/disable) + persistence
- `scripts/lib/begin-tomo.sh.template` (lines ~236–314, 371–384) - voice drift-label rebuild + banner line
- `tomo/scripts/tomo-statusline.sh` (lines ~47–196) - Kado probe + render case block

**Key Design Decisions**:

- **ADR-1** (socat in base image): bake `socat` into the **base** Dockerfile layer, always present — NOT a conditional build ARG. Pre-socat images rebuild via an image-label drift check.
- **ADR-2** (unsupervised proxy): the **entrypoint** spawns `socat` in the background *only if a lock file is present*, before `exec "$@"`. No supervisor; a dead proxy is recovered by restarting the container.
- **ADR-3** (TCP-connect probe): reachability is a TCP-connect test to `127.0.0.1:<port>` (`/dev/tcp` or `nc -z`) — host-side in `begin-tomo.sh`, container-side (via the proxy) in the statusline. Not a WS handshake, not lock-file-presence.
- **ADR-4** (cleartext token): the auth token lives cleartext in `tomo-install.json` + the lock file; the `0600` requirement is dropped (host-only `127.0.0.1`, bind-mounted file).
- **ADR-5** (vault-path routing): a namespace-based routing rule in `tomo/CLAUDE.md.template` — vault-note paths (bridge active file, `[[wikilinks]]`, `@`-mentions, `kado-search` results) read via `kado-read` first; container-local files via local `Read`; ambiguous bare path tries `kado-read` first, falls back to `Read` on not-found/denied; fails closed. No protocol prefix.

**Hard constraints** (SDD Constraints):

- **CON-1**: all shell runs on **bash 3.2** (macOS `/bin/bash`) — no `declare -A`, no bash 4+ features.
- **CON-3**: **no exposed ports** in `docker run` — the proxy is container-localhost only.
- **CON-4**: **Kado is the sole vault surface** — introduce no alternative vault-read path; the bridge carries editor context only.
- **CON-6**: changes are **additive** — must not regress the voice wizard, the launch banner, or the current Kado statusline.
- **Test-isolation rule** (memory `feedback_test_scripts_must_never_touch_real_install`): any test that runs `install-tomo.sh` MUST pass `--instance-location <TMPDIR> --instance-name <iso> --home-dir <TMPDIR>/home --config-file <TMPDIR>/cfg.json`. Never run install/update at the default path in a test.
- **Version bumps** (memory `feedback_bump_version_on_managed_file_edit`): every edited file carrying `# version:` MUST get its number bumped, or `update-tomo.sh` ships nothing. Number only, no parenthetical.

**Implementation Context**:

```bash
# Unit / integration tests (host-only Python; drives bash libs via subprocess)
pytest tests/                          # full suite — must stay green (CON-6)
pytest tests/ide_bridge/ -v            # this feature's tests

# bash 3.2 syntax gate (macOS /bin/bash IS 3.2 — this is the CON-1 check)
/bin/bash -n scripts/lib/configure-ide-bridge.sh
/bin/bash -n docker/entrypoint.sh
/bin/bash -n scripts/lib/begin-tomo.sh.template
/bin/bash -n tomo/scripts/tomo-statusline.sh

# Isolated install smoke (NEVER omit the isolation flags)
scripts/install-tomo.sh --vault <vault> --non-interactive \
  --instance-location "$TMPDIR" --instance-name iso \
  --home-dir "$TMPDIR/home" --config-file "$TMPDIR/cfg.json"
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Wizard Lib & Lock File](phase-1.md)
- [x] [Phase 2: Container Runtime Wiring](phase-2.md)
- [ ] [Phase 3: Launch & Status Surfaces](phase-3.md)
- [ ] [Phase 4: Integration & Validation](phase-4.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

### PRD Acceptance-Criteria → Task Traceability

| PRD | Acceptance criterion (abbrev.) | Task |
|-----|-------------------------------|------|
| F1-AC1 | lock at `tomo-home/.claude/ide/<port>.lock`, correct JSON | T1.1, T1.2 |
| F1-AC2 | update-tomo creates lock without reinstall | T1.2 |
| F1-AC3 | update token → lock regenerated | T1.1, T1.2 |
| F1-AC4 | lock JSON has pid/workspaceFolders/ideName/transport/authToken | T1.1 |
| F2-AC1 | lock present → socat forwards `127.0.0.1:<port>`→host | T2.2 |
| F2-AC2 | no lock → no proxy, no error | T2.2 |
| F2-AC3 | connection reaches Hashi on host | T4.1 (live) |
| F3-AC1 | socat in every fresh image | T2.1 |
| F3-AC2 | pre-socat image rebuilds (drift) | T3.1 |
| F4-AC1 | install asks enable / token / port | T1.1, T1.2 |
| F4-AC2 | `--non-interactive` skips, preserves state | T1.1, T1.2 |
| F4-AC3 | update shows status, keep / update / disable | T1.1, T1.2 |
| F4-AC4 | non-UUID token rejected with clear error | T1.1 |
| F4-AC5 | port default 23027, non-numeric/out-of-range rejected | T1.1 |
| F5-AC1 | selection used without a Kado read | T3.3 |
| F5-AC2 | active-file vault path read via `kado-read`, not local FS | T3.3 |
| F5-AC3 | ambiguous bare path → `kado-read` first, fall back on not-found/denied; true vault path fails closed | T3.3 |
| F6-AC1 | banner "IDE: bridge active" when configured + lock present | T3.1 |
| F6-AC2 | banner "IDE: not configured" when absent (dimmed) | T3.1 |
| F6-AC3 | configured but Hashi unreachable → non-blocking warning | T3.1 |
| F7-AC1 | Kado `門:<port>` with green/red/yellow + Tags sub-state | T3.2 |
| F7-AC2 | Hashi `橋:<port>` green/red/yellow, no Tags sub-state | T3.2 |
| F7-AC3 | color retained (not replaced by symbols) | T3.2 |
