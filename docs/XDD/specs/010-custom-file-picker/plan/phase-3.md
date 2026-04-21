---
title: "Phase 3: Settings integration + install flow"
status: complete
version: "1.1"
phase: 3
---

# Phase 3: Settings integration + install flow

## Phase Context

**Dependencies**: Phase 2 complete (handlers work standalone).

**Key files**:
- `tomo/dot_claude/settings.json` (added Phase 1)
- `scripts/install-tomo.sh` (cache dir + script copy)
- `scripts/update-tomo.sh` (sync dot_claude/scripts/*.sh)

**Note:** Phase 3 was largely satisfied incidentally during Phase 1/2
commits. This retrospective audit (2026-04-21) marks each task with
evidence rather than re-executing them.

---

## Tasks

- [x] **T3.1 Settings.json final form** `[activity: backend]` — **DONE 2026-04-20** (commit `2517896`)

  `tomo/dot_claude/settings.json` carries the `fileSuggestion` entry
  pointing at `.claude/scripts/file-suggestion.sh`. Live-active in the
  running instance; audit 2026-04-21 confirms path is correct.

- [x] **T3.2 install-tomo.sh: copy scripts + create cache dir** `[activity: backend]` — **DONE 2026-04-20** (commit `2517896`)

  Template tree `tomo/dot_claude/` is copied wholesale during install,
  including `dot_claude/scripts/file-suggestion.sh` and `dot_claude/scripts/lib/`.
  `tomo-instance/cache/` is created by the script itself on first call
  (`mkdir -p "$CACHE_DIR"` in `file-suggestion.sh:48`).

- [x] **T3.3 update-tomo.sh: sync scripts dir** `[activity: backend]` — **DONE** (current tree)

  `scripts/update-tomo.sh:114-127` has the "Updating .claude/scripts"
  block — iterates `dot_claude/scripts/*.sh` + `dot_claude/scripts/lib/*.sh`
  through `update_managed`, chmod +x after copy. Version-diff display works.

- [x] **T3.4 Dockerfile: jq + fzf present** `[activity: backend]` — **DONE** (current tree, comment added 2026-04-21)

  `docker/Dockerfile:14,18` installs both. Inline comment added today
  so future readers don't remove them thinking they're unused.

- [x] **T3.5 Cache dir mount** `[activity: backend]` — **PASSIVELY SATISFIED**

  `begin-tomo.sh:338` mounts the entire `$INSTANCE_PATH` 1:1 into the
  container. Cache files (`tomo-instance/cache/inbox-files.txt`,
  `vault-files.txt`, `picker-debug.log`, `.invalidate-vault-files`)
  are host-visible and container-writable. No dedicated cache mount
  needed; the whole-instance mount subsumes it.

- [x] **T3.6 Restart + reload check** `[activity: validate]` — **DONE**

  Settings picked up after instance restart; live-active since Phase 2
  live-validation 2026-04-20/21. Documented implicitly: daily use
  confirms `@` routes to the custom picker.

- [x] **T3.7 Phase Validation** `[activity: validate]` — **DONE 2026-04-21**

  - Fresh install → picker works first `@`: confirmed via 2026-04-20
    container rebuild.
  - update-tomo.sh propagates script changes: confirmed by repeated
    picker-script iterations (v0.1.0 → v0.5.0) landing in the instance
    without full reinstall.
  - Cache survives restarts: cache files persist on host; container
    uses them on next start.
  - `fileSuggestion` respected by Claude Code: picker-debug.log shows
    per-keystroke invocations.
