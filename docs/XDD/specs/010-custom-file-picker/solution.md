---
title: "Custom @-File-Picker — Solution Design"
status: draft
version: "0.1"
---

# Solution Design Document

## Architecture Overview

```
User types @<query> in Tomo session
         │
         ▼
Claude Code reads settings.json :: fileSuggestion
         │
         ▼  (stdin: {"query": "<text>"})
┌─ scripts/file-suggestion.sh ──────────────────────────────┐
│                                                            │
│  1. Parse query → detect prefix (/inbox /vault) or default │
│  2. Route to handler:                                      │
│       default → handle_open_notes()                        │
│       /inbox  → handle_inbox()                             │
│       /vault  → handle_vault()                             │
│  3. Each handler returns ≤15 paths to stdout               │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ default: handle_open_notes() ────────────────────────────┐
│  curl Kado /mcp → kado-open-notes({scope: "all"})         │
│    │                                                       │
│    ├─ FORBIDDEN → return empty (silent)                    │
│    ├─ UNAUTHORIZED → return empty (silent)                 │
│    └─ {notes:[...]} → sort active-first → filter by query  │
│         → emit ≤15 paths                                   │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ /inbox: handle_inbox() ──────────────────────────────────┐
│  Check cache/inbox-files.txt mtime < 30s ?                 │
│    yes → fzf --filter "$query" < cache | head -15          │
│    no  → kado-search inbox path → write cache → fzf        │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ /vault: handle_vault() ──────────────────────────────────┐
│  Check cache/vault-files.txt mtime < 1h ?                  │
│    yes → fzf --filter "$query" < cache | head -15          │
│    no  → kado-search "" recursive → write cache → fzf      │
└────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Script: `scripts/file-suggestion.sh`
Single bash entry point. Parses query, routes to one of three handlers,
emits paths. Bash 3.2 compatible (per project guardrails). Always exits 0
unless something is catastrophically broken — non-zero would make Claude
Code fall back to built-in, which we do NOT want for graceful degradation
(better to return empty than fall back to filesystem walk of the instance).

### Helper script: `scripts/file-suggestion/kado-call.sh` (or inlined)
Curl wrapper for Kado MCP calls. Reads endpoint and bearer from
`tomo-install.json` once, caches them in env. Implements the existing SSE
unwrap pattern (per memory `reference_kado_sse_format`).

### Settings hook: `tomo/dot_claude/settings.json`
Add:
```json
"fileSuggestion": {
  "type": "command",
  "command": "bash .claude/scripts/file-suggestion.sh"
}
```

### Cache files
- `cache/vault-files.txt` — newline-separated relative vault paths.
  Built on demand or after `/explore-vault`. TTL 1h.
- `cache/inbox-files.txt` — newline-separated relative inbox paths.
  Built on demand. TTL 30s.

Cache lives in `tomo-instance/cache/` (gitignored, per-instance).

## Query Parsing

```bash
# After stripping JSON, $query contains the user's text.
case "$query" in
  /inbox\ *)  handle_inbox  "${query#/inbox }"  ;;
  /inbox)     handle_inbox  ""                  ;;
  /vault\ *)  handle_vault  "${query#/vault }"  ;;
  /vault)     handle_vault  ""                  ;;
  *)          handle_open_notes "$query"        ;;
esac
```

Trailing whitespace tolerated. Other prefixes silently fall through to
default (so `@/foo` searches open notes for "/foo" — fine, low-cost
graceful behaviour).

## Handler Logic

### `handle_open_notes <filter>`

```
1. POST kado-open-notes({"scope": "all"}) via curl.
2. On HTTP error, FORBIDDEN, or UNAUTHORIZED → emit nothing, exit 0.
3. Parse response: notes[] with {name, path, active, type}.
4. Stable sort: active=true first, others in returned order.
5. If filter non-empty: substring-match (case-insensitive) on name OR path.
6. Take first 14 results.
7. If filter empty AND >15 total: emit 14 + "... + N more (type to filter)".
8. Else: emit results (no synthetic line).
```

### `handle_inbox <filter>`

```
1. cache_path = $INSTANCE_PATH/cache/inbox-files.txt
2. If cache_path exists AND mtime < 30s: skip rebuild.
3. Else: kado-search inbox dir → write cache_path.
4. fzf --filter "$filter" < cache_path | head -15
   (empty filter: fzf returns all, head -15 caps it)
```

### `handle_vault <filter>`

```
1. cache_path = $INSTANCE_PATH/cache/vault-files.txt
2. If cache_path exists AND mtime < 3600s: skip rebuild.
3. Else: kado-search "" with recursive=true → write cache_path.
4. fzf --filter "$filter" < cache_path | head -15
```

Cache write is atomic: write to `<cache>.tmp`, then `mv`.

## Active-Note Marker — Spike Plan (Phase 1)

Two-step experiment, max 30 minutes:

**Step A** — Output `path/to/note.md (active)` for active note. Test:
- Does Claude Code visually show the suffix? (likely yes)
- When user picks → does the inserted text include the suffix?
- Does Claude Code resolve the file content (i.e., does it strip ` (active)`
  before path lookup, or treat it as part of the path)?

**Step B** — If Step A's resolution fails:
- Fall back to position-only marker (active = position 0, no suffix).
- Document the API limitation in spec README.

Outcome captured in spec README's Decisions Log.

## Cache Mechanics

### Vault cache (`vault-files.txt`)

- Built from `kado-search` with empty query and recursive=true.
- One path per line, sorted alphabetically (deterministic for fzf).
- Excludes binary types (or includes them — Obsidian-native: yes for `.md`,
  `.canvas`, `.pdf`, `.png` if user has them; defer scope decision to Plan
  Phase 2).
- Invalidation:
  - mtime > 1h (TTL).
  - `/explore-vault` step writes a sentinel file
    `cache/.invalidate-vault-files`; script checks for it and rebuilds + clears.
  - User-triggered: `rm cache/vault-files.txt` works.

### Inbox cache (`inbox-files.txt`)

- Built from `kado-search` with the inbox path (read from `vault-config.yaml`
  or `tomo-install.json` — confirm at Plan Phase 2).
- TTL 30s — short enough that newly-dropped notes appear quickly, long
  enough to avoid per-keystroke calls.

## Settings Integration

`tomo/dot_claude/settings.json` extension:

```json
{
  "permissions": { ... existing ... },
  "fileSuggestion": {
    "type": "command",
    "command": "bash .claude/scripts/file-suggestion.sh"
  },
  "statusLine": { ... existing ... }
}
```

Script must live at the path `.claude/scripts/file-suggestion.sh` *inside the
instance* (not the source repo). Install / update flow copies it from
`tomo/dot_claude/scripts/file-suggestion.sh` (template source) to
`tomo-instance/.claude/scripts/file-suggestion.sh` per existing managed-files
pattern.

## File Layout

```
tomo/
├── dot_claude/
│   ├── scripts/
│   │   └── file-suggestion.sh        NEW (template source)
│   └── settings.json                  MODIFIED (add fileSuggestion entry)
scripts/
└── install-tomo.sh                    MODIFIED (copy file-suggestion.sh + create cache dir)

tomo-instance/                          (at runtime)
├── .claude/
│   ├── settings.json                  (rendered from template)
│   └── scripts/
│       └── file-suggestion.sh         (copied from template)
└── cache/
    ├── vault-files.txt                (built on demand)
    ├── inbox-files.txt                (built on demand)
    └── .invalidate-vault-files        (sentinel from /explore-vault)
```

## Error Handling

| Condition | Behaviour |
|---|---|
| stdin not valid JSON | Treat as empty query, route to default scope |
| Kado endpoint unreachable | Emit empty result, exit 0 |
| `kado-open-notes` returns FORBIDDEN | Empty result, exit 0; optionally synthetic hint line |
| `kado-search` returns UNAUTHORIZED | Empty result, exit 0 |
| Cache file unreadable | Rebuild it; if rebuild fails, empty result |
| fzf not installed | Fall back to grep substring match (degraded but functional) |
| Script crash (bash error) | exit non-zero → Claude Code falls back to built-in (acceptable) |

## Performance Targets

| Scope | Target latency |
|---|---|
| `@<query>` (open notes) | ≤ 200ms p95 (1 Kado call) |
| `@/inbox <q>` (cached) | ≤ 50ms p95 |
| `@/inbox <q>` (cache miss) | ≤ 200ms p95 (1 Kado call + fzf) |
| `@/vault <q>` (cached) | ≤ 50ms p95 (fzf only) |
| `@/vault <q>` (cache miss) | ≤ 500ms p95 (recursive Kado search + write + fzf) |

## Future Hooks (out of scope, anchored)

- **Obsidian Terminal plugin**: same picker behaviour applies; no changes to
  this script needed. The plugin sets up Claude Code with the same Tomo
  settings.json.
- **Additional prefixes** (`/today`, `/recent`, `/starred`): add new case
  branches, no architectural change.
- **Mixed-scope fallback** (e.g., default `@<q>` finds nothing in open notes
  → auto-fall-through to inbox): explicitly NOT implemented in MVP.

## Risks & Open Items for Plan

- **`fileSuggestion` exit-code behaviour**: docs say script outputs paths,
  but don't fully spec what happens on non-zero exit (fallback? error
  banner?). Verify in Phase 1 spike.
- **JSON-input parsing in bash**: `jq` is required (already in Dockerfile).
  No-jq fallback adds complexity — defer unless we hit a system without jq.
- **`kado-open-notes` returns paths**: confirm path format matches what
  Claude Code's `@`-resolver expects (vault-relative? absolute? CLAUDE_PROJECT_DIR-relative?).
  Critical detail — verify in Phase 1.
- **Cache file location and permissions**: container vs host mount semantics.
  `tomo-instance/cache/` is on host, mounted in — should work, confirm.
