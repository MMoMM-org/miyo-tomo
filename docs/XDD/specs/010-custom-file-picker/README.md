# Specification: 010-custom-file-picker

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-04-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | draft | First cut |
| solution.md | draft | First cut — design discussed in conversation 2026-04-20 |
| plan/ | draft | 4 phases scaffolded |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-20 | Use Claude Code `fileSuggestion` setting | Native customization point; receives `{query}` via stdin, returns up to 15 paths to stdout |
| 2026-04-20 | Default `@` shows only open Obsidian notes (via `kado-open-notes`) | Most common use case; minimizes load (single Kado call ~50-100ms) |
| 2026-04-20 | Prefix routing: `/inbox` and `/vault` as scope keywords | Opt-in for broader searches; keeps default fast |
| 2026-04-20 | Vault scope uses fzf on a cached file list | fzf already in container; cache invalidated by `/explore-vault` or TTL 1h |
| 2026-04-20 | Inbox scope uses cached Kado listing (TTL 30s) | Inbox accessed via Kado, not local FS — caching avoids per-keystroke calls |
| 2026-04-20 | Active note marker = position 0 (start) | API expects raw paths in stdout — markers in path break `@` resolution. Suffix-hack `path (active)` to be spike-tested in Phase 1; fallback = position-only |
| 2026-04-20 | FORBIDDEN feature-gate from Kado = silent skip | Per Kado contract: not an error, user just hasn't opted in |

## Context

Kado v0.7.0 ships `kado-open-notes` (handoff: `_inbox/from-kado/2026-04-20_*`),
which returns the user's currently-open Obsidian notes. Tomo's `@` file picker
today uses Claude Code's built-in filesystem traversal — useful for code repos,
but Tomo runs against a vault where the user's mental model is "the notes I'm
currently looking at" + "the notes in my inbox" + "everything else".

This spec replaces the built-in `@` picker via `fileSuggestion` setting:
- Default `@` returns currently-open Obsidian notes (active first).
- `@/inbox <text>` searches the inbox via Kado.
- `@/vault <text>` fuzzy-searches the cached vault file list.

Future enabler: when Tomo runs as a "Terminal" session inside an Obsidian
plugin, the user can fluidly type `@<note-name>` mid-conversation to bring
notes into context — the picker's UX matters disproportionately there.

## Inbox handoff status

This spec is the action on `_inbox/from-kado/2026-04-20_kado-to-tomo_2026-04-20-kado-open-notes-available.md`.
That handoff will be marked `done` when spec 010 is merged to main.

## Open Questions for SDD

(none — all design questions resolved in conversation)

## Open Questions for Plan / Implementation

- Suffix-hack viability for active-note marker — spike test in Phase 1.
- Cache file format: plain text (one path per line) for fzf compatibility,
  or JSON with metadata? Plain text is simpler; metadata can come later.
- Whether to expose more prefixes later (`/today`, `/recent`, `/starred`).
  Out of scope for MVP.
