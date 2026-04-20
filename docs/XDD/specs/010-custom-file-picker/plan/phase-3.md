---
title: "Phase 3: Settings integration + install flow"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Settings integration + install flow

## Phase Context

**Dependencies**: Phase 2 complete (handlers work standalone).

**Key files**:
- `tomo/dot_claude/settings.json` (already added in Phase 1; verify final shape)
- `scripts/install-tomo.sh` (cache dir + script copy)
- `scripts/update-tomo.sh` (sync new file-suggestion.sh on update)

---

## Tasks

- [ ] **T3.1 Settings.json final form** `[activity: backend]`

  1. Prime: Phase 1 added a `fileSuggestion` entry. Re-verify it points to
     the right script path inside the instance.
  2. Implement: Final settings.json fragment:
     ```json
     "fileSuggestion": {
       "type": "command",
       "command": "bash .claude/scripts/file-suggestion.sh"
     }
     ```
     Bump `# version` comment in tomo/dot_claude/settings.json (existing
     project convention for managed files).
  3. Validate: JSON valid. Path is relative to instance root (Claude Code's CWD).

- [ ] **T3.2 install-tomo.sh: copy scripts + create cache dir** `[activity: backend]`

  1. Prime: install-tomo.sh has a managed-files copy section.
  2. Implement:
     - Add: `cp -r "$TOMO_SOURCE/dot_claude/scripts/" "$INSTANCE_PATH/.claude/scripts/"`
     - Add: `chmod +x "$INSTANCE_PATH/.claude/scripts/"*.sh`
     - Add: `mkdir -p "$INSTANCE_PATH/cache"`
     - Verify cache dir has correct ownership/permissions for container access.
  3. Validate: Fresh install creates `tomo-instance/.claude/scripts/file-suggestion.sh`
     and `tomo-instance/cache/`. Both writable from container.

- [ ] **T3.3 update-tomo.sh: sync scripts dir** `[activity: backend]`

  1. Prime: update-tomo.sh updates managed files individually with version
     diff display.
  2. Implement: Add a section that loops over `dot_claude/scripts/*.sh`,
     calls `update_managed` for each. Same pattern as agents/skills/commands.
  3. Validate: After modifying file-suggestion.sh in the source, `update-tomo.sh`
     copies the new version to the instance and shows the version diff.

- [ ] **T3.4 Dockerfile: verify jq + fzf present** `[activity: backend]`

  1. Prime: Both already in Dockerfile (`jq`, `fzf` confirmed earlier).
  2. Implement: No change needed — but add a comment in Dockerfile noting
     these are required by file-suggestion.sh.
  3. Validate: `docker run --rm <tomo-img> bash -c "command -v jq && command -v fzf"` succeeds.

- [ ] **T3.5 begin-tomo.sh: cache dir mount** `[activity: backend]`

  1. Prime: begin-tomo.sh mounts instance dirs into the container.
  2. Implement: Verify `tomo-instance/cache/` is mounted into the container
     at `/tomo/cache/` (or wherever the script expects). If not present,
     add the mount.
  3. Validate: Inside running container, `ls /tomo/cache/` works after the
     script writes to it.

- [ ] **T3.6 Restart + reload check** `[activity: validate]`

  1. Prime: settings.json changes need a Claude Code restart inside the
     instance to pick up.
  2. Implement: Document in commit message + spec README: after install/update,
     restart Claude in the instance.
  3. Validate: Open a fresh Tomo session, type `@` → custom picker activates
     (stub or real, depending on phase).

- [ ] **T3.7 Phase Validation** `[activity: validate]`

  - Fresh install of Tomo from clean state → file picker works on first `@`
    in a fresh session (no manual setup).
  - update-tomo.sh propagates script changes to running instance.
  - Cache dir survives container restarts (it's host-mounted).
  - settings.json shows `fileSuggestion` entry; Claude Code respects it.
