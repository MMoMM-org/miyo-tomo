# Memory Index — Tomo

> Routing rules are in CLAUDE.md (root). This file is the index only.
> Budget: ≤ 200 lines. Archive entries when stale. Run /memory-sync to check.

## Files
- [general.md](general.md) — conventions, style, naming [updated: 2026-06-30]
- [tools.md](tools.md) — CI, build, local dev [updated: 2026-06-24]
- [domain.md](domain.md) — business rules, data models [updated: 2026-06-09]
- [decisions.md](decisions.md) — architecture choices [updated: 2026-06-24]
- [context.md](context.md) — current focus [updated: 2026-06-30]
- [troubleshooting.md](troubleshooting.md) — known issues [updated: 2026-06-29]

## Archive
<!-- Archived entries live in archive/YYYY-MM/. Not loaded at session start. -->
<!-- memory-cleanup manages archive creation. Do not list archive files here. -->
- archive/2026-06/ — resolved troubleshooting + context bug-fix entries (cleanup 2026-06-29); R11/R13 resolved + 2026-05 open blocks relocated (cleanup 2026-06-30)

## Critical Documentation
<!-- Add important docs here when created — Claude loads these on demand -->
<!-- - [Architecture Overview](../architecture/overview.md) -->
- [Inbox Change Detection & Pass Routing](../../XDD/reference/tier-2/workflows/inbox-change-detection.md) — how triage detects what changed (new/drift/coverage) + the determine_action routing tree + flag semantics (--pass2 vs --force). Mermaid flowchart + state diagram. (#74/#78)
