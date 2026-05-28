---
title: "Phase 4: Integration & Validation"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Integration & Validation

Proves the six touch points work together end-to-end, runs the live transport check that unit tests can't cover, and closes the doc-cleanup item. This is the release gate for spec 019.

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 2; AC3]` — connection reaches Hashi's WS server on the host (live, can't be unit-tested)
- `[ref: PRD/User Journey → First-Time IDE Bridge Setup]` and `[ref: PRD/Secondary Journey → Post-Install Addition]`
- `[ref: SDD/Runtime View → Launch + connect; lines: 220-244]`
- `[ref: SDD/Quality Requirements; lines: 300-305]`
- `[ref: SDD/Acceptance Criteria (EARS); lines: 307-335]`

**Key Decisions**:
- **Test scope** (memory `feedback_test_scope_personal_vault`): pre-launch QA = MiYo architecture + Marcus's real vault + real Hashi. No synthetic test vault, no exhaustive sub-mode matrix.
- **Live-validation caveat** (memory `feedback_llm_improvisation_masks_arch_gaps`): "worked once" is weak evidence — verify the mount/port/lock wiring against the actual running container, not just a green log line.

**Dependencies**: Phases 1, 2, 3 complete.

---

## Tasks

- [ ] **T4.1 End-to-end install → launch → connect (live, personal vault)** `[activity: integration-test]`

  1. **Prime**: Re-read SDD Runtime View "Launch + connect" sequence (lines 220-244) so you know the expected chain: install writes lock → begin-tomo probes + builds (drift) → entrypoint spawns socat → Claude Code reads lock + connects `ws://127.0.0.1:<port>` → socat forwards to host Hashi.
  2. **Test**:
     - **Isolated install smoke** (automated, safe): run `install-tomo.sh --non-interactive` with all four isolation flags into a `tmp` location; assert `tomo-install.json` has the `.ide_bridge` block and (when enabled via a scripted config) the lock file exists at `<home>/.claude/ide/<port>.lock` with the correct JSON `[ref: SDD/EARS lock-file; PRD/F1-AC1]`. NEVER run against the default path (memory `feedback_test_scripts_must_never_touch_real_install`).
     - **Live end-to-end** (manual, real instance + Obsidian/Hashi running): enable IDE Bridge via the real `update-tomo.sh`, paste the real Hashi auth token + port, launch `begin-tomo.sh`. Confirm: banner shows "IDE: bridge active"; statusline shows `橋:<port> ✓` and `門:<port> ✓`; inside Claude Code, selecting text in Obsidian surfaces `⧉ Selected N lines from <file>` `[ref: PRD/F2-AC3; PRD Success Metrics → Engagement]`. Verify the socat process is actually running in the container (`docker exec ... pgrep -af socat`) and bound to the configured port — don't trust the banner alone.
     - **Negative live check**: with IDE Bridge disabled (no lock file), launch and confirm no socat, no error, banner "IDE: not configured" `[ref: PRD/F2-AC2]`.
  3. **Implement**: only fixes surfaced by the runs (no new feature code). If the live run reveals a wiring gap (port mismatch, lock path, `host.docker.internal` resolution), fix at the source and re-run.
  4. **Validate**: full `pytest tests/` green; isolated install smoke green; live checklist passes against the real vault.
  5. **Success**: editor context flows host→container end-to-end; disabled state is silent `[ref: PRD/F2-AC1, F2-AC2, F2-AC3; SDD/EARS]`.

- [ ] **T4.2 Full-suite regression, bash 3.2 gate, and version-bump audit** `[activity: validate]`

  1. **Prime**: list every file this spec touched (configure-ide-bridge.sh, install-tomo.sh, update-tomo.sh, Dockerfile, entrypoint.sh, begin-tomo.sh.template, tomo-statusline.sh, CLAUDE.md.template).
  2. **Test / Validate**:
     - `pytest tests/` — full suite green (CON-6: no regression in voice, inbox, MOC, etc.)
     - `/bin/bash -n` on **every** edited/new shell file (CON-1 bash 3.2 gate; macOS `/bin/bash` is 3.2)
     - **version-bump audit**: confirm each edited file carrying `# version:` had its number bumped (memory `feedback_bump_version_on_managed_file_edit` — unchanged version = `update-tomo.sh` silently ships nothing). Number only, no parenthetical (memory `feedback_version_comments_number_only`).
     - **skill-author/agent-author audit**: N/A — this spec edits no agent/skill files. Confirm none were touched.
  3. **Success**: suite green, syntax clean, all versions bumped `[ref: SDD/Quality Requirements; SDD/EARS]`.

- [ ] **T4.3 Doc cleanup + spec close-out** `[activity: docs]`

  1. **Prime**: read the spec README "Context" bonus note and `docs/ai/memory/tools.md`.
  2. **Implement**:
     - **Verify-before-edit** (memory `feedback_verify_spec_impl_via_code_not_readme` / "verify before recommending from memory"): grep `docs/ai/memory/tools.md` for a stale Kado port reference. The PRD Open Questions resolved the *statusline showing 23027* as **not a 019 bug** (Marcus runs several Kado instances). Only fix `tools.md` if it states a wrong **canonical default** (Kado default is `23026`); if it's accurate, leave it and note so. Do not over-scope.
     - update `docs/XDD/specs/019-hashi-ide-bridge-docker-wiring/README.md`: set the `plan/` row to `completed`, add a Decisions-Log close-out entry, flip spec status to Implemented when T4.1 live check passes.
     - update `README.md` (repo root) / relevant `docs/tomo/` if the IDE Bridge needs a user-facing mention (per CLAUDE.md root rule: ship docs with the feature). Capture any WHY stripped from runtime files into the matching `docs/tomo/<path>.md`.
  3. **Validate**: links resolve; README status reflects reality; no rationale left orphaned in runtime files.
  4. **Success**: spec 019 is closed out with accurate status and the doc-debt item resolved or explicitly dismissed.
