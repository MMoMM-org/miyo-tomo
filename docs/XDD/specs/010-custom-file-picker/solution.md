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
Single bash entry point. Collects candidates (open notes via kado-
open-notes, cached inbox listing, cached vault listing), dedupes,
applies the query via fzf (with grep fallback), emits top 15 paths.
Bash 3.2 compatible (per project guardrails). Always exits 0 — T1.1
spike confirmed that non-zero hides the picker silently with no
fallback to built-in.

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

## Query Handling (unified — no scope prefixes)

The picker emits ONE candidate stream and applies the query via fzf
(or grep fallback). No prefix routing.

```bash
# After stripping JSON, $query contains the user's text.
{
  emit_open_notes      # kado-open-notes, active first
  cat inbox-files.txt  # cached, 30s TTL
  cat vault-files.txt  # cached, 1h TTL + /explore-vault sentinel
} | awk 'NF && !seen[$0]++' | {
    if [ -z "$query" ]; then
        cat
    elif command -v fzf >/dev/null; then
        fzf --filter "$query"
    else
        grep -i -F -- "$query"
    fi
} | head -n 15
```

**Why no prefixes**: earlier designs used `inbox/<q>` and `vault/<q>`.
Selecting the prefix-entry (from a hint-line in the picker) inserted
`@"inbox/"` or `@inbox/ ` (with trailing space) into the user's prompt,
forcing a backspace before continuing to type. The unified stream
covers the same use cases — typing `@<inbox-note-name>` naturally
surfaces inbox matches via fzf.

**Claude Code's `/`-prefix trap** (retained for reference): queries
starting with `/` bypass `fileSuggestion` entirely — Claude Code routes
them to its built-in absolute-path browser (`/boot/`, `/dev/`, etc.).
The unified design sidesteps this because no synthetic prefix is ever
suggested, so the user won't type one.

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

## Active-Note Marker — Resolved (position-only)

**Decision 2026-04-20**: position-only marker. No in-text suffix.

The active note is emitted at stdout position 0; all other open notes
follow in the order Kado returns them. There is no visual marker in the
path itself.

**Why**: T1.1 spike Case D proved that non-path text in a picker entry
inserts as `@"<text>"` — a quoted literal, not a file reference. A
suffix like `path.md (active)` would therefore render in the picker but
would not resolve to the file on selection. Position-only is the only
viable marker strategy given Claude Code's fileSuggestion contract.

**Implication for UX**: users must infer "active" from ordering. The
first entry is always the active note (when one exists). Documentation
and/or README should make this clear. If we later add a Tomo Hashi
(Obsidian) plugin that runs this picker, the plugin can render a visual
marker client-side without affecting the script contract.

Spike decision captured in spec README's Decisions Log (2026-04-20
entries). Original spike plan moved to the spec git history.

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
