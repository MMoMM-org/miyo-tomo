---
title: "Phase 4: End-to-end test + docs"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: End-to-end test + docs

## Phase Context

**Dependencies**: Phases 1-3 complete and merged.

**Key files**:
- `README.md` (root — feature mention)
- `docs/XDD/reference/tier-2/` (any reference doc that mentions `@`)
- `tomo/dot_claude/rules/project-context.md` (capability note)
- `_inbox/from-kado/2026-04-20_*` (mark done)
- `docs/XDD/backlog.md` (update if applicable)

---

## Tasks

- [ ] **T4.1 Live UX walkthrough** `[activity: validate]`

  1. Prime: Real vault, real Obsidian session with several notes open.
  2. Implement: Open a Tomo session. Walk through:
     - `@` (no query) → confirm open notes appear, active first
     - `@<partial>` → confirm filter on open notes works
     - `@/inbox` → confirm inbox files appear
     - `@/inbox <q>` → confirm fuzzy match works
     - `@/vault <topic>` → confirm fuzzy match returns relevant matches
     - Select an item → confirm `@<path>` is inserted AND Claude resolves the file
  3. Validate: All flows feel native; no obvious latency stutter.

- [ ] **T4.2 Latency measurement** `[activity: validate]`

  1. Prime: SDD targets — open notes ≤200ms, cached ≤50ms, vault cold ≤500ms.
  2. Implement: For each scope, run 10 invocations with `time bash file-suggestion.sh < <input>`.
     Capture median + p95.
  3. Validate: Compare to targets. Document actual numbers in spec README's
     Completion Summary. Investigate if any scope is >2x target.

- [ ] **T4.3 FORBIDDEN graceful behaviour** `[activity: validate]`

  1. Prime: Kado has feature-gate; user can disable `allowActiveNote`.
  2. Implement: In Kado settings, disable `allowActiveNote` and
     `allowOtherNotes` for the Tomo key. Type `@`.
  3. Validate: Picker shows zero open-notes results — no error, no crash.
     `@/inbox` and `@/vault` still work. Re-enable → next `@` works.

- [ ] **T4.4 Update docs** `[activity: docs]`

  1. Prime: Read root README.md and project-context.md.
  2. Implement:
     - README: under features, add "Custom file picker (open notes / inbox / vault)".
     - project-context.md: bump version, mention picker scopes (`@`, `@/inbox`, `@/vault`).
     - Add a tier-2 reference doc `docs/XDD/reference/tier-2/components/file-picker.md`
       describing the three scopes and cache mechanics. Link from
       `docs/XDD/README.md` index.
  3. Validate: Docs accurately reflect implementation.

- [ ] **T4.5 Mark inbox handoff done** `[activity: tooling]`

  1. Prime: `_inbox/from-kado/2026-04-20_kado-to-tomo_2026-04-20-kado-open-notes-available.md`
     was set to in-progress when this spec started.
  2. Implement: Run `~/.claude/skills/miyo-inbox/inbox-set-status.sh
     _inbox/from-kado/2026-04-20_kado-to-tomo_2026-04-20-kado-open-notes-available.md
     done "Implemented as XDD 010 — file picker uses kado-open-notes for default scope"`.
  3. Validate: Status updated in handoff frontmatter.

- [ ] **T4.6 Spec status flip** `[activity: docs]`

  1. Prime: spec README currently in PLAN phase.
  2. Implement: Set Current Phase = `DONE`, Status = `ready`. All phase
     READMEs marked `done`. Add Completion Summary listing what shipped,
     latency numbers, known limits.
  3. Validate: Status fields consistent.

- [ ] **T4.7 Phase Validation** `[activity: validate]`

  - All three scopes work in real session against real vault.
  - Latency targets met (or documented).
  - FORBIDDEN scenario gracefully handled.
  - Inbox handoff marked done.
  - Spec marked done.
  - Branch ready to merge.
