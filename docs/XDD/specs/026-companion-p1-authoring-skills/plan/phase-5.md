---
title: "Phase 5: Docs, Attribution, Ops & Integration"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Docs, Attribution, Ops & Integration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-8]` — kepano MIT attribution in README (+ docs/tomo mirrors)
- `[ref: SDD/Directory Map; Deployment View]` — evolution log, PRIVACY.md, Kokoro note, version-gated sync
- `[ref: SDD/Test Strategy]` — full suite green
- Constitution L2 (Dependencies/Operations/Architecture), L3 (Privacy PRIVACY.md)

**Key Decisions**:
- Companion mode warrants a lightweight Kokoro design note (not a full ADR): inbox-only write contract,
  `.base`/`.canvas` artifact type, the "no `/inbox` triage for these" policy (#93 boundary).

**Dependencies**: Phase 4 (all skills + scripts in place). This is the closing phase.

---

## Tasks

Delivers the documentation, governance, and integration evidence that close the spec.

- [x] **T5.1 kepano attribution + dependency note (README)** `[activity: docs]`

  1. Prime: `[ref: SDD/ADR-8; CON-5]`; kepano MIT license.
  2. Test: README contains a general MIT attribution + dependency note for kepano/obsidian-skills; no
     attribution text leaked into any runtime SKILL.md.
  3. Implement: add the attribution + dependency note to `README.md`; optional explicit note in the
     docs/tomo mirrors.
  4. Validate: `rg -l "kepano" tomo/dot_claude/skills` returns nothing (attribution not in runtime).
  5. Success: MIT obligation satisfied `[ref: SDD/ADR-8; Constitution L1/L2 Dependencies]`.

- [x] **T5.2 Evolution log entry** `[activity: docs]`

  1. Prime: `[ref: SDD/Directory Map]`; Constitution L2 Operations.
  2. Implement: `evolution/2026-06/companion-mode-p1.md` — what changed (5 skills, rename, 2 scripts,
     RETIRED_SKILLS_DIRS), when, traced to spec 026.
  3. Validate: entry is chronological + self-contained.
  4. Success: rollout reproducible from the log `[ref: Constitution L2 Operations]`.

- [x] **T5.3 PRIVACY.md companion paragraph** `[activity: docs]`

  1. Prime: Read `PRIVACY.md` "What vault content reaches the LLM".
  2. Implement: add a "Companion mode" paragraph (user-initiated; content read for compilations +
     template fetches reach the model; no new external surface).
  3. Validate: mirrors the `/inbox` paragraph; no new network surface claimed.
  4. Success: companion vault-read surface documented `[ref: Constitution L1 Privacy note]`.

- [x] **T5.4 Kokoro design-note handoff** `[activity: docs]`

  1. Prime: `[ref: SDD/Building Block View cross-repo note]`; MiYo handoff protocol.
  2. Implement: `_outbox/for-kokoro/2026-06-..._tomo-to-kokoro_companion-mode-write-contract.md` — a
     lightweight design note (inbox-only write contract; `.base`/`.canvas` artifact type now written by
     Tomo; #93 triage boundary). Not a full ADR.
  3. Validate: handoff frontmatter correct (`from: tomo`, `to: kokoro`, status `pending`).
  4. Success: L2 Architecture satisfied `[ref: Constitution L2 Architecture]`.

- [x] **T5.5 Integration: sync, suite, live walk** `[activity: validate]`

  *Done (deterministic half):* full suite 1771 pass + ruff clean; `update-tomo.sh --yolo` shipped all
  6 created / 4 updated / 1 retired files; instance copies version-match the repo; `default-doc-writer`
  retired from the instance. *User-delegated:* the per-format `.md`/`.base`/`.canvas` Compose-to-Inbox
  live walk against the live vault (needs the running container + Kado) — to be run by the user in their
  Tomo session (decision 2026-06-29). PRD live-walk acceptance tracked as the only open follow-up.

  1. Prime: version-gated sync caveat `[ref: SDD/Deployment View]`.
  2. Test: full suite green under `./venv/bin/python -m pytest tests/`; ruff clean.
  3. Implement/verify: `./scripts/update-tomo.sh --yolo` (sandbox-off for `.claude` dirs); grep the
     instance copies to confirm the version-gated sync shipped each skill/script; run an end-to-end
     Compose-to-Inbox walk per format family (`.md`, `.base`, `.canvas`) against a live vault
     (`tomo-privat` or test vault) — confirm correct skill auto-loads, artifact lands in inbox, parse-gate
     + collision behave.
  4. Validate: instance copies match repo versions; live walk produces valid artifacts in the inbox.
  5. Success: all 22 PRD ACs demonstrably met `[ref: PRD/Success Metrics; SDD/Acceptance Criteria]`.
