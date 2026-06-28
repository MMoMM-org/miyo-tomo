---
title: "Phase 3: Write-Side Helper Skill"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Write-Side Helper Skill

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — one write-side skill `kado-write-patterns`, symmetric to `kado-discovery-patterns`
- `[ref: SDD/Deliverable 5; kado-write-patterns frontmatter contract]`
- `[ref: SDD/kado-discovery-patterns vs kado-toolkit Boundary]` (from technical research)
- `[ref: PRD/Feature 5]`
- `[ref: tomo/dot_claude/skills/kado-discovery-patterns/SKILL.md]` — read-side sibling

**Key Decisions**:
- Write-side ONLY: `kado-write-file.py` (`.md`→note, non-`.md`→file, `--no-overwrite`),
  `write_frontmatter`, `read-config-field.py`, `token-render.py`, `validate-json.py`, `sanitize_stem`.
  Read/query stays in `kado-discovery-patterns`. Both descriptions state the split.

**Dependencies**: Phase 1 (references `validate-json.py` + `--no-overwrite`). Independent of Phase 2.

---

## Tasks

Delivers the write-side Kado helper catalog the companion + Tomo use for all vault writes.

- [x] **T3.1 kado-write-patterns skill (new)** `[activity: docs-skill]`

  1. Prime: Read `kado-discovery-patterns` (to mirror shape + state the boundary), the helper scripts
     `[ref: tomo/scripts/{kado-write-file.py,read-config-field.py,token-render.py,validate-json.py}]`,
     and `kado_client` write methods `[ref: tomo/scripts/lib/kado_client.py; lines: 298,322,352]`.
  2. Test (audit): `/skill-author` audit passes; description states write/compose scope and directs
     read/query tasks to `kado-discovery-patterns`; body contains invocations (HOW), no WHAT-prose, no
     duplication of read-side patterns.
  3. Implement via `/skill-author`: `tomo/dot_claude/skills/kado-write-patterns/SKILL.md` with the
     write-side invocations. `# version: 0.1.0`. WHY + read/write boundary rationale →
     `docs/tomo/dot_claude/skills/kado-write-patterns.md`. If needed, add one line to
     `kado-discovery-patterns`'s description naming the write-side counterpart (bump its version).
  4. Validate: audit clean; no read-side duplication; boundary explicit in both descriptions.
  5. Success: write-side invocations correct; read tasks routed to discovery-patterns `[ref: PRD/Feature 5 AC]`.

- [x] **T3.2 Phase Validation** `[activity: validate]`

  - `/skill-author` audit. Confirm the read/write split is unambiguous and the skill references the
    Phase 1 scripts (`validate-json.py`, `kado-write-file.py --no-overwrite`).
