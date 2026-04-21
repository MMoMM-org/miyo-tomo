# Specification: 010-custom-file-picker

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | DONE — unified picker live; Phases 3–4 retrospectively validated 2026-04-21 |
| **Last Updated** | 2026-04-21 |

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
| 2026-04-20 | **Default `@<text>` is merged across open notes ▶ inbox ▶ vault** (supersedes "only open notes" above) | Observed: typing `@inb` or `@catan` showed only 2 open notes and agent typeaheads, never inbox/vault items where matches really lived — discovery failure. Merged default surfaces hits from every scope, with open notes first (active context priority) and substring match (predictable, not fzf-fuzzy). Explicit `inbox/<q>` and `vault/<q>` still narrow for power users. Empty `@` unchanged (open notes only). |
| 2026-04-21 | **Scope prefixes retired entirely — unified picker (rg-snippet pattern)** | Observed: picking `inbox/` from the hint list inserted `@inbox/ ` (with trailing space) into the prompt, forcing the user to backspace before typing more. Also: portable-stat bug in `cache_fresh` was silently breaking all non-empty queries in the container. Fixed stat (separate commit) + switched to single candidate stream: open notes + all inbox + all vault → fzf `--filter` on query → head 15. Same mental model as `rg --files \| fzf` for plain file pickers. No prefix syntax to learn or insert. Side-effect: fzf fuzzy match is now default for all queries (was strict-substring in the prefix design) — users seem to prefer it. Agents still appear in Claude Code's `@` typeahead (confirmed: no documented way to hide them while preserving Task-tool spawning); dense file list visually drowns them. |
| 2026-04-20 | Prefix routing: `/inbox` and `/vault` as scope keywords | Opt-in for broader searches; keeps default fast |
| 2026-04-20 | **Scope prefixes: `inbox/` and `vault/` — suffix-slash, NOT leading-slash** | Superseded initial `/inbox` design. Claude Code bypasses `fileSuggestion` when the query starts with `/`, routing to a built-in absolute-path browser (shows `/boot/`, `/dev/`, etc.) — our handler is never called. Scope prefixes must start with a non-slash char. Script updated to `inbox/*` / `vault/*` patterns. |
| 2026-04-20 | Vault scope uses fzf on a cached file list | fzf already in container; cache invalidated by `/explore-vault` or TTL 1h |
| 2026-04-20 | Inbox scope uses cached Kado listing (TTL 30s) | Inbox accessed via Kado, not local FS — caching avoids per-keystroke calls |
| 2026-04-20 | Active note marker = position 0 (start) | API expects raw paths in stdout — markers in path break `@` resolution. Suffix-hack `path (active)` to be spike-tested in Phase 1; fallback = position-only |
| 2026-04-20 | **Suffix-hack rejected — position-only marker is final** | Decided without running T1.2: T1.1 Case D proved non-path text inserts as `@"<text>"` quoted literal with no file resolution. `path.md (active)` would suffer the same fate. Risk-reward of a second Tomo-restart cycle is poor; decision is inferred from existing evidence. SDD solution.md updated; Phase 2 relies on ordering alone. |
| 2026-04-20 | **kado-open-notes path format = vault-relative; accept one extra tool call on @-pick** | T1.3: Kado returns `notes[].path` as vault-relative strings (`Calendar/301 Daily/2026-03-26.md`). Tomo's `$CLAUDE_PROJECT_DIR` is the instance, so those paths don't exist locally and Claude Code's @-resolver will Read → ENOENT. Claude (the LLM) then falls back to `kado-read`. Net cost: one extra tool call per @-reference. No transformation applied in the picker. |
| 2026-04-20 | FORBIDDEN feature-gate from Kado = silent skip | Per Kado contract: not an error, user just hasn't opted in |
| 2026-04-20 | **`file-suggestion.sh` must always exit 0** | T1.1 spike: non-zero exit hides the picker silently. No fallback to built-in picker, no error banner, stdout discarded. Exit 0 + empty stdout achieves the same hide effect but permits best-effort partial results on recoverable errors. |
| 2026-04-20 | **Synthetic hint lines (non-path strings) are viable but selectable** | T1.1 spike Case D: non-path text renders verbatim in the picker; selection inserts as `@"<text>"` quoted literal, no file resolution. Safe for FORBIDDEN/UNAUTHORIZED user notices. Must be placed at the bottom of the result list because they are selectable and would otherwise surprise the user. |
| 2026-04-20 | **F4 "... + N more" affordance deferred to Phase 2** | T1.1 spike Case E: the synthetic overflow line renders and is selectable, inserting as `@"... + 42 more (type to filter)"` on pick. Viable but adds a selectable non-path line. Simpler alternative: silently truncate to 15 real results. Phase 2 decides between the two. |
| 2026-04-20 | **Active-note suffix-hack: strong negative prior from T1.1** | Case D showed non-path text inserts as `@"<text>"` quoted literal. `path.md (active)` will likely also insert quoted and not resolve. T1.2 still to run to confirm, but expected outcome: position-only marker (drop the `(active)` suffix). |

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
The file is a symlink into `Kado/_outbox/for-tomo/` and status must be
flipped from a Kado-hosted Claude session (cross-repo ownership rule).
Trigger for next Kado session: mark status=done with reason
"Consumed by Tomo XDD 010 — kado-open-notes drives default `@` scope."

## Completion Summary (2026-04-21)

**Shipped:**
- `tomo/dot_claude/scripts/file-suggestion.sh` v0.5.0 — unified picker
  (rg-snippet pattern: candidates → fzf filter → head 15)
- `tomo/dot_claude/scripts/lib/kado-call.sh` — shared Kado helper
- `tomo/dot_claude/settings.json` — `fileSuggestion` wired
- `scripts/install-tomo.sh` + `scripts/update-tomo.sh` — propagation
- `docker/Dockerfile` — jq + fzf present + comment
- Cache: `tomo-instance/cache/{inbox-files.txt, vault-files.txt,
  picker-debug.log, .invalidate-vault-files}`

**Known limits:**
- Agent typeaheads still appear in Claude Code's `@` dropdown —
  no documented way to hide them while preserving Task-tool spawning.
  Dense file list visually outweighs them in practice.
- Kado-returned vault-relative paths don't resolve locally; LLM
  falls back to `kado-read` (one extra tool call per `@`-pick).
  Acceptable per T1.3 decision.

## Open Questions for SDD

(none — all design questions resolved in conversation)

## Open Questions for Plan / Implementation

- Suffix-hack viability for active-note marker — spike test in Phase 1.
- Cache file format: plain text (one path per line) for fzf compatibility,
  or JSON with metadata? Plain text is simpler; metadata can come later.
- Whether to expose more prefixes later (`/today`, `/recent`, `/starred`).
  Out of scope for MVP.
