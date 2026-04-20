---
title: "Custom @-File-Picker for Tomo Instance"
status: draft
version: "0.1"
---

# Product Requirements Document

## Product Overview

### Vision

Replace Tomo's `@` file picker with a vault-aware version that surfaces the
notes the user actually wants — open Obsidian notes by default, inbox + vault
on demand — so referencing notes mid-conversation is as fluid as switching
panes in Obsidian.

### Problem Statement

Today, `@` in a Tomo session uses Claude Code's built-in file picker, which:

- Walks the filesystem starting from `CLAUDE_PROJECT_DIR` — but Tomo's project
  dir is the instance, not the vault. The user's actual content is unreachable.
- Has no concept of "the note I'm currently looking at in Obsidian" — even
  though that's the most likely target when the user types `@`.
- Treats vault paths and instance paths the same — the user's noise/signal
  ratio is bad.

Result: users either paste paths manually ("the path to the note I'm editing
is X") or describe notes by name and let Claude search via `kado-search`
— both slower and more error-prone than picker-based selection.

### Value Proposition

- **Zero-friction "this note"**: `@` alone (no query) shows currently-open
  Obsidian notes, active first. One keystroke to reference what you're
  looking at.
- **Scope-prefixed search**: `@/inbox foo` and `@/vault foo` give explicit
  control over search scope without overloading the default fast path.
- **Cache-backed performance**: vault fuzzy search via fzf on a cached file
  index; inbox listing cached for keystroke-rate latency. Fast enough for
  typing-speed feedback.
- **Future-ready**: when Tomo runs in an Obsidian "Terminal" plugin, the
  same picker behaviour applies, and `@`-references map cleanly to vault
  paths.

## User Personas

### Primary: Vault-coupled Tomo user

- Has Obsidian open with one or more vault tabs.
- Asks Claude things like "given the MOC structure of @<current-note>,
  where should this fleeting note land?"
- Today: pastes path or describes note by name — friction.

### Secondary (future): Obsidian-Terminal user

- Runs Tomo as a session inside an Obsidian plugin.
- Switches between editing a note and conversing with Tomo without leaving
  Obsidian.
- Needs `@` to feel as native as Obsidian's own `[[link]]` autocomplete.

## User Journey Map

### Journey 1: reference the active note

1. User has note `Atlas/Japan (MOC).md` focused in Obsidian.
2. User types `@` in Tomo.
3. Picker shows list with `Atlas/Japan (MOC).md` first (active marker), then
   any other open notes.
4. User picks → `@Atlas/Japan (MOC).md` inserted → Claude resolves it.

### Journey 2: search inbox

1. User wants to reference a fleeting note from this morning.
2. Types `@/inbox today` (or part of the filename).
3. Picker shows inbox files matching "today" (or all inbox files, ranked).
4. User picks.

### Journey 3: search whole vault

1. User wants to reference a note they vaguely remember by topic.
2. Types `@/vault yoga`.
3. Picker fuzzy-matches "yoga" against the cached vault file list.
4. User picks.

### Journey 4: many open notes (>15)

1. User has 20 notes open in Obsidian.
2. Types `@`.
3. Picker shows active note + first 13 others + a synthetic 15th line
   `... + N more (type to filter)`.
4. User types `@meeting` → list re-filters to open notes with "meeting" in
   the name; if 5 match, all 5 shown; if 0 match, picker shows "(no open
   notes match — try @/inbox or @/vault)".

## Feature Requirements

### Must Have

#### F1 — Custom fileSuggestion script
- Tomo settings.json sets `fileSuggestion` to point to a Tomo-managed script.
- Script reads `{"query": "..."}` from stdin.
- Script writes ≤15 newline-separated file paths to stdout.
- Script exits 0 on success, non-zero on internal error (Claude Code falls
  back to built-in on non-zero — verify behaviour).

#### F2 — Default scope: open Obsidian notes
- Empty query OR query without prefix → call `kado-open-notes({scope: "all"})`.
- Sort: active note first, others in returned order.
- Apply text query as substring filter on filename if query is non-empty.
- If `kado-open-notes` returns FORBIDDEN (feature-gate) → silent skip,
  return zero results from this scope.
- If >15 results after filter → show 14 + synthetic line `... + N more`.

#### F3 — `/inbox` prefix scope
- Query starts with `/inbox` → strip prefix, remaining text = filter.
- Use cached inbox listing (Kado-backed); refresh if cache > 30s old.
- Fuzzy-match remaining query against filenames.

#### F4 — `/vault` prefix scope
- Query starts with `/vault` → strip prefix, remaining text = filter.
- Use cached vault file list; refresh if cache > 1h old OR after `/explore-vault`.
- Fuzzy-match via `fzf --filter` (already in container).

#### F5 — Active-note marker
- Active note appears at position 0 in the output list (always first).
- **Spike-test in Phase 1**: try suffix-hack `path (active)` to surface the
  marker visually. If Claude Code preserves the suffix on insertion AND
  still resolves the file → use it. Else: position-only.

### Should Have

#### F6 — Cache invalidation
- Vault cache: invalidated when `/explore-vault` runs (already builds caches).
- Inbox cache: 30s TTL.
- Open-notes: no cache (always fresh — list is small and changes often).

#### F7 — FORBIDDEN guidance
- If kado-open-notes returns FORBIDDEN, the picker shows zero open-notes
  results. Optional: append a synthetic last-line hint:
  `... open-notes disabled — enable in Kado settings`.
- Decided in Phase 1 spike based on whether Claude Code lets non-path
  trailing lines through.

### Could Have

#### F8 — Additional prefixes
- `/today` (notes modified today), `/recent` (last 24h), `/starred` (Obsidian
  starred). Out of scope for MVP; add to backlog.

#### F9 — Visual category icons
- If suffix-hack works, ` (active)` / ` (inbox)` / ` (vault)` markers per
  category. Else: position-grouping only (open block, then inbox block, then
  vault block — but currently we don't mix scopes in one query, so moot).

### Won't Have (MVP)

- Mixed-scope queries (e.g., one `@` query searching open + inbox + vault
  simultaneously). User picks scope explicitly via prefix.
- Recency / usage-frequency ranking beyond what each source naturally provides.
- Caching the open-notes list (low value, list is small + dynamic).

## Functional Requirements

### Inputs
- stdin: `{"query": "<text>"}` from Claude Code.
- Environment: `CLAUDE_PROJECT_DIR` (the instance path).
- Side reads: `tomo-install.json` (Kado endpoint + key), `cache/vault-files.txt`,
  `cache/inbox-files.txt` (created by script).

### Outputs
- stdout: ≤15 newline-separated file paths. Optional 15th synthetic line for
  hints (`... + N more` etc.).
- exit 0: normal. Non-zero: internal error → Claude Code falls back to default.

### Behaviour
- Default `@`: kado-open-notes call, filter by query, sort active-first.
- `/inbox <q>`: cached inbox list, fzf or substring filter.
- `/vault <q>`: cached vault list, fzf filter.
- All scopes return at most 15 lines (real or synthetic).

### Acceptance Criteria
- Empty `@` returns open notes with active first; no other source consulted.
- `@/inbox` returns inbox files; no open-notes call.
- `@/vault foo` returns up to 15 fuzzy matches from vault cache; no Kado calls.
- Picker latency p95 ≤ 200ms in default scope; ≤ 100ms in cached scopes.
- Disabling `kado-open-notes` (FORBIDDEN) gives a graceful empty list, not
  an error blocking other typing.
- `/explore-vault` invalidates the vault cache; next `@/vault` rebuilds it.

## Non-Functional Requirements

- **Latency**: per-keystroke calls ≤ 100ms cached, ≤ 200ms uncached.
- **Resilience**: any Kado error (timeout, FORBIDDEN, UNAUTHORIZED) → script
  still exits 0 with the best-effort partial result; never blocks the user
  from typing.
- **Privacy**: respect Kado's path-ACL (silent omit per spec); never leak
  paths the active key has no R permission on.
- **Reproducibility**: same inputs + same vault state = same output.

## Out of Scope

- Implementing `kado-open-notes` itself (already shipped in Kado v0.7.0).
- File picker for non-Tomo Claude sessions (this is Tomo-instance only).
- Obsidian Terminal plugin (separate project, future).
- Voice memo `.m4a` files in inbox listing — picker shows them as paths;
  resolution is the same as for `.md` files.

## Success Metrics

- After rollout, queries that begin "the path to the note I'm editing is..."
  drop to ~zero in transcript review.
- `@/vault` finds a target note in ≤ 3 keystrokes for ≥ 80% of queries
  (subjective, not measured automatically).
- Picker latency stays sub-200ms in p95 across a session.

## Open Questions for Plan

(none — see SDD for technical questions)
