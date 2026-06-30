# Context — Tomo
<!-- Current sprint focus, active work, known blockers. Updated: 2026-06-30 -->
<!-- This file is short-lived — prune entries older than 2 weeks via /memory-cleanup -->

## Status (2026-06-30)

No active blockers. Operational, performance/cost, and deferred-review items are
tracked at their canonical homes — GitHub issues + `docs/XDD/backlog.md`.
**GitHub is the source of truth for status.** Resolved/relocated detail lives in
`archive/2026-06/context.md`.

Recently shipped (this session): Tomo themes + install/update seeding (PR #103/#104),
statusline pill redesign with theme-colored pills + `~/.claude/tomo-statusline.conf`
hot-reload selection (PR #105). All merged to main.

## Current focus — MVP-Polish

Working the **MVP-Polish** milestone open issues on branch `feat/mvp-polish`.
Goal: harden the core `/inbox` flow to "done".

**Standalone issues (start here):**
- **#28** (F-36) — New-section proposal when no existing section fits
- **#29** (F-30) — LLM-driven insertion-point resolution for `link_to_moc`
- **#33** (F-42) — Suggestions document UX pass

**Epics:**
- **#17** — MOC Intelligence (Mental Squeeze Point + matching)
- **#18** — Inbox Analysis Quality
- **#19** — Suggestions Doc UX
- **#22** — Inbox Orchestration Robustness
- **#24** — Performance & Cost

Pick the next issue with `gh issue view <N>`; read its body + linked specs before planning.
