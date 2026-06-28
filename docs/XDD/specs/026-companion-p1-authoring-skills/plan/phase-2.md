---
title: "Phase 2: Format-Knowledge Skills"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Format-Knowledge Skills

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View; Skill frontmatter contracts]` — differentiated descriptions
- `[ref: SDD/ADR-6]` — access-agnostic, differentiated triggers, no cross-format co-load
- `[ref: SDD/ADR-8]` — kepano attribution in README + docs/tomo mirror, never in SKILL.md
- `[ref: PRD/Features 1-3]`
- kepano source: `github.com/kepano/obsidian-skills` (obsidian-markdown / obsidian-bases / json-canvas)

**Key Decisions**:
- Format skills are pure knowledge — they never mention Kado. Descriptions anchor to ONE artifact type
  to avoid cross-format co-load and the `obsidian-fields` "callout" collision.
- Every skill authored/audited via `/skill-author`. Runtime SKILL.md = imperatives only; WHY →
  `docs/tomo/`. Author the docs/tomo mirror BEFORE stripping rationale from runtime.

**Dependencies**: none (independent of Phase 1). The three tasks are mutually parallel.

---

## Tasks

Delivers the three format-knowledge skills the companion uses to author correct artifacts.

- [ ] **T2.1 obsidian-markdown upgrade** `[activity: docs-skill] [parallel: true]`

  1. Prime: Read the existing skill `[ref: tomo/dot_claude/skills/obsidian-markdown/SKILL.md]`, the
     moc-architect load `[ref: tomo/dot_claude/agents/moc-architect.md; lines: 8-10]`, kepano
     obsidian-markdown, and `obsidian-fields` description (to differentiate).
  2. Test (manual/audit, no unit test for prose): `/skill-author` audit passes; a callout task does NOT
     co-load obsidian-fields; moc-architect still resolves obsidian-markdown by `skills:` frontmatter.
  3. Implement via `/skill-author`: flip `user-invocable: true`; broaden + differentiate description
     (syntax verbs, not metadata/classification); remove the "Lazy-loaded … not user-invocable" body
     line; audit/expand content vs kepano (add tables, task lists, fenced code w/ language, footnotes,
     properties/frontmatter YAML, math, Mermaid, comments, highlight). Bump `# version`. Update
     `docs/tomo/dot_claude/skills/obsidian-markdown.md` (WHY).
  4. Validate: `/skill-author` audit clean; description disjoint from obsidian-fields; moc-architect
     compatibility confirmed.
  5. Success: user-invocable + auto-triggers on OFM syntax, no obsidian-fields co-load, no moc-architect
     regression `[ref: PRD/Feature 1 AC]`.

- [ ] **T2.2 obsidian-bases skill (new)** `[activity: docs-skill] [parallel: true]`

  1. Prime: Read kepano `obsidian-bases` (SKILL + FUNCTIONS_REFERENCE) and ADR-6/ADR-8.
  2. Test (audit): `/skill-author` audit passes; description triggers on `.base` only (no co-load on
     `.canvas`/`.md`); body mentions no Kado.
  3. Implement via `/skill-author`: `tomo/dot_claude/skills/obsidian-bases/SKILL.md` (+ optional
     `references/`) with adapted Bases knowledge (filters, formulas, properties, views, summaries,
     troubleshooting). `# version: 0.1.0`. WHY + kepano attribution → `docs/tomo/.../obsidian-bases.md`.
  4. Validate: audit clean; access-agnostic; trigger anchored to `.base`.
  5. Success: produces valid `.base` knowledge; no cross-format co-load `[ref: PRD/Feature 2 AC]`.

- [ ] **T2.3 obsidian-canvas skill (new)** `[activity: docs-skill] [parallel: true]`

  1. Prime: Read kepano `json-canvas` (SKILL + EXAMPLES), JSON Canvas 1.0 spec (jsoncanvas.org), ADR-6/8.
  2. Test (audit): `/skill-author` audit passes; description triggers on `.canvas` only; body mentions
     no Kado.
  3. Implement via `/skill-author`: `tomo/dot_claude/skills/obsidian-canvas/SKILL.md` (+ optional
     `references/`) — node/edge/group structure, color system, ID rules, the 8-item validation
     checklist. `# version: 0.1.0`. WHY + attribution → `docs/tomo/.../obsidian-canvas.md`.
  4. Validate: audit clean; access-agnostic; trigger anchored to `.canvas`.
  5. Success: produces valid JSON Canvas knowledge; no cross-format co-load `[ref: PRD/Feature 3 AC]`.

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Run `/skill-author` audit across all three. Confirm: each triggers only on its artifact type;
    none mention Kado; obsidian-fields callout boundary intact; moc-architect unaffected.
