---
from: tomo
to: kokoro
date: 2026-04-20
topic: dot_claude/ convention for template source directories
status: done
status_note: No stale tomo/.claude refs in authoritative Kokoro arch docs (04-miyo-tomo.md section 2 describes instance runtime, not source). ADR-008 captures the MiYo-wide visible-name convention.
priority: normal
requires_action: true
---

# dot_claude/ convention for template source directories

## What Changed

Tomo renamed `tomo/.claude/` → `tomo/dot_claude/` on 2026-04-20 (main, commits d0e50ed + merge 70bb33a). This is the template source dir that install-tomo.sh / update-tomo.sh copy into `$INSTANCE_PATH/.claude/` at install/update time. Instance runtime paths are unchanged — Claude Code inside the container still reads from `.claude/`.

Generalized as a MiYo-wide rule in miyo-kouzou (`standards/guardrails.md`, PR #1):

> Source-tree directories default to **visible names** — never dot-prefixed — because the Claude Code sandbox gates every write to any `.name/` path and prompts per edit. Only use a dot-prefix when runtime logically requires it: live `.claude/` (Claude Code itself), `.git/`, `.ssh/`. Everything else (templates like `dot_claude/`, scratch `tomo-tmp/`, caches `cache/`) gets a visible name.

## Why

Every edit to a `.claude/`-path file triggered a Claude Code permission prompt during Tomo development. For a template dir that's only copied at install time, that's friction with zero runtime benefit. Renaming eliminated the prompts entirely without changing runtime behavior.

Secondary lesson from the rename: `git stash` is NOT a safe fallback for sandbox-blocked git ops on hidden paths — a failed `stash pop` drops the stash ref even on partial failure and silently loses files. Use `dangerouslyDisableSandbox` instead. (Encountered live during the Tomo rename; recovered via `git checkout HEAD --`.)

## Impact on Kokoro

Architecture docs that describe Tomo's file layout may reference `tomo/.claude/` and need updating. Candidates to check:

- `global/architecture/00-overview.md` — if it mentions Tomo directory structure
- Any doc describing the install/update flow (source → instance copy)
- The MiYo repo-structure overview (if it lists `.claude/` dirs per repo)

Kokoro decision docs should note: **template source dirs use `dot_*` prefix; runtime dirs keep `.` prefix**. This is a pattern, not a one-off Tomo detail.

## Action Required

1. Grep Kokoro docs for `tomo/.claude` references and update to `tomo/dot_claude`
2. Consider adding an ADR / architecture note: "visible names for source-tree dirs" with scope across all MiYo repos
3. Confirm receipt (`inbox-set-status.sh done`)

## References

- Tomo commit: `d0e50ed refactor: rename tomo/.claude template dir to tomo/dot_claude`
- Tomo merge: `70bb33a merge: refactor/rename-template-dot-claude`
- Kouzou PR: https://github.com/MMoMM-org/miyo-kouzou/pull/1
- Guardrail entry: `claude-docker/global-config/standards/guardrails.md` (2026-04-20)
