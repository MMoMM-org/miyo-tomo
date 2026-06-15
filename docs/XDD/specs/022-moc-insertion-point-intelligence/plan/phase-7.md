---
title: "Phase 7: Cross-repo + live walk"
status: in_progress
version: "1.0"
phase: 7
---

# Phase 7: Cross-repo + live walk

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/ADR-7]` — Kokoro ADR + Hashi handoff
- `[ref: requirements.md/Feature 6; AC-14, AC-15]` — live walk
- `[ref: research-synthesis.md/Hashi contract]` — existing shapes, real-walk obligation
- `[ref: solution.md/System-Wide Patterns — Logging]` — metadata-only (L2 Privacy)

**Key Decisions**:
- No new Hashi wire shape — but the new Pass-1 emission must be real-walked (standing
  "real walks > synthetic fixtures" rule; #28 owes one).
- Constitution L2: the Pass-2→Pass-1 relocation is documented in Kokoro.
- Tracking events stay metadata-only (paths/tiers/counts) — no note content / full heading text.

**Dependencies**: Phases 1–6 complete (the full pipeline must emit + render correctly).

---

## Tasks

Closes governance + proves the redesign end-to-end against the real vault.

- [ ] **T7.1 Tracking events (metadata-only)** `[activity: backend]`

  1. Prime: Review the PRD tracking table + L2 Privacy `[ref: requirements.md/Tracking Requirements; solution.md/System-Wide Patterns]`.
  2. Test (red): emitted lifecycle.discovery events carry tier-fired / MOC-path / counts only — assert NO note content or full heading text is logged.
  3. Implement (green): emit the events on the existing lifecycle.discovery channel.
  4. Validate: log-content assertion passes (metadata-only).
  5. Success: [ ] metadata-only logging `[ref: Constitution L2 Privacy]`

- [ ] **T7.2 Cross-repo artifacts** `[cross-repo]` `[needs-hashi]` `[activity: documentation]`

  1. Prime: Read the prior handoffs `[ref: _outbox/for-hashi/2026-06-13_*; _inbox/from-hashi/*]` and the Kokoro ADR location.
  2. Test (red): n/a (docs) — checklist: Kokoro ADR exists describing the Pass-2→Pass-1 relocation; `_outbox/for-hashi/` handoff states the new emission uses existing shapes and requests the real walk.
  3. Implement (green): write the Kokoro ADR/design-note (Constitution L2); write the `_outbox/for-hashi/` handoff (status pending). Note: Tomo session edits Kokoro file but does NOT git-commit Kokoro (single-owner rule) — leave for the Kokoro session.
  4. Validate: handoff + ADR reference the spec ID and the existing-shapes claim.
  5. Success: [ ] L2 reflection + handoff filed `[ref: solution.md/ADR-7]`

- [ ] **T7.3 Live-validation walk** `[cross-repo]` `[needs-hashi]` `[activity: validate]`

  1. Prime: Confirm the test note `100 Inbox/First Principles Thinking.md` exists and pick a target MOC where no H2 fits `[ref: requirements.md/AC-14]`. Use host-vs-live-Kado (sandbox off; URL+token from `tomo-instance/.mcp.json`).
  2. Test (red): run `/inbox` Pass-1 → a new H2 section is proposed, its name appears in the suggestions doc, and it is renamable (AC-14).
  3. Implement (green): execute the walk; confirm Pass-2 renders the new section and (through Hashi) it lands before the footer with correct spacing and the link under it (AC-15). Log the run cost to `docs/evolution/inbox-cost-log.md`.
  4. Validate: vault state diff matches the emitted `instructions.json`; #28 fired on a real MOC (not a fixture).
  5. Success:
     - [ ] #28 fires + reviewable + renamable `[ref: AC-14]`
     - [ ] applies before footer, correct spacing `[ref: AC-15]`

- [ ] **T7.4 Phase Validation + full regression** `[activity: validate]`

  - Run the full `./venv/bin/python -m pytest tests/` suite (true baseline ~840 pass; only known failures are the 8 pre-existing `tests/ide_bridge`). Confirm no new regressions. Verify `update-tomo` synced every edited managed file (grep instance versions).
