---
title: "Phase 2: Handler implementations + caching"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Handler implementations + caching

## Phase Context

**Dependencies**: Phase 1 complete. Spike findings inform handler details.

**Key files**:
- `tomo/dot_claude/scripts/file-suggestion.sh` (extend stubs into real handlers)
- `tomo/dot_claude/scripts/lib/kado-call.sh` (NEW — shared curl wrapper, optional)

---

## Tasks

- [ ] **T2.1 `handle_open_notes` implementation** `[activity: backend]`

  1. Prime: SDD `handle_open_notes` pseudocode + spike T1.3 findings on
     path format.
  2. Implement:
     - curl POST to `$KADO_ENDPOINT/mcp` with kado-open-notes call,
       bearer from `tomo-install.json :: kadoApiKey`.
     - SSE unwrap (per memory `reference_kado_sse_format` — `_unwrap_sse` pattern).
     - Parse JSON: extract notes[] with active flag.
     - Sort: active=true first (max 1 entry), others in returned order.
     - If query non-empty: case-insensitive substring match on path basename.
     - Take first 14 results.
     - If query empty AND >15 returned: append synthetic line `... + N more (type to filter)`.
     - On any HTTP error or FORBIDDEN/UNAUTHORIZED: emit nothing, exit 0.
  3. Validate: Tomo session, type `@` → list of open Obsidian notes appears,
     active first. Type `@meet` with a "meeting" note open → filtered.

- [ ] **T2.2 `handle_inbox` with caching** `[activity: backend]`

  1. Prime: SDD `handle_inbox` pseudocode. Inbox path comes from
     `vault-config.yaml :: concepts.inbox` (verify via `read-config-field.py`).
  2. Implement:
     - Cache path: `$CACHE_DIR/inbox-files.txt` where `$CACHE_DIR` =
       `/tomo/cache` (mounted from host `tomo-instance/cache/`).
     - Check cache mtime: if < 30s, skip rebuild.
     - Else: kado-search inbox path, write paths line-by-line to `$cache.tmp`,
       atomic mv.
     - `fzf --filter "$query" < cache | head -15`.
     - Empty query: `fzf --filter "" < cache | head -15` (fzf returns all).
  3. Validate: `@/inbox` → inbox files listed. Add a new file via Kado,
     wait 30s+, type again → new file appears.

- [ ] **T2.3 `handle_vault` with caching** `[activity: backend]`

  1. Prime: SDD `handle_vault` pseudocode. Vault root determined by Kado
     (no path prefix).
  2. Implement:
     - Cache path: `$CACHE_DIR/vault-files.txt`.
     - Check sentinel `.invalidate-vault-files`: if exists, delete cache and sentinel.
     - Check cache mtime: if < 3600s (1h) AND no sentinel, skip rebuild.
     - Else: kado-search "" recursive, paths to `$cache.tmp`, atomic mv.
     - `fzf --filter "$query" < cache | head -15`.
  3. Validate: `@/vault yoga` → fuzzy matches. Touch sentinel manually,
     type again → cache rebuilds.

- [ ] **T2.4 Shared kado-call helper** `[activity: backend]`

  1. Prime: Both inbox + vault handlers + open-notes handler hit Kado.
     DRY via shared lib.
  2. Implement: `tomo/dot_claude/scripts/lib/kado-call.sh` with function
     `kado_call <tool> <json_args>`:
     - Reads endpoint + bearer once into env (caches).
     - Issues curl POST with proper headers.
     - SSE unwrap.
     - Returns response JSON on stdout, non-zero on HTTP error.
  3. Validate: All three handlers refactored to use `kado_call`. Identical
     behaviour, less code.

- [ ] **T2.5 fzf fallback to grep** `[activity: backend]`

  1. Prime: SDD error table — fzf fall-back to grep if missing.
  2. Implement: At top of script, `command -v fzf >/dev/null || FZF_MISSING=1`.
     In handlers: if `$FZF_MISSING`, use `grep -i "<query>"` instead of
     `fzf --filter`. Substring match is degraded but not broken.
  3. Validate: temporarily mask fzf (alias to /bin/false) → script still
     produces results via grep.

- [ ] **T2.6 `/explore-vault` cache invalidation** `[activity: backend]`

  1. Prime: `tomo/dot_claude/commands/explore-vault.md` defines the existing
     command. After it completes, the vault file list may be stale.
  2. Implement: Add a final step in explore-vault command (or in
     `cache-builder.py` if vault scan happens there): touch
     `$CACHE_DIR/.invalidate-vault-files`.
  3. Validate: Run `/explore-vault`. Check sentinel exists. Type `@/vault`
     → cache rebuilds (verify via mtime change on `vault-files.txt`).

- [ ] **T2.7 Active-marker decision implementation** `[activity: backend]`

  1. Prime: Phase 1 spike T1.2 outcome.
  2. Implement (CASE A — suffix-hack works): in handle_open_notes, append
     ` (active)` to the active note's emitted line.
  3. Implement (CASE B — suffix-hack rejected): just keep position-0
     ordering; no suffix.
  4. Validate: User picks active note → file content actually resolves
     (CASE A ratifies; CASE B is the safe path).

- [ ] **T2.8 Phase Validation** `[activity: validate]`

  - All three scopes work end-to-end in a real Tomo session.
  - Latency: measure with `time bash file-suggestion.sh < input.json` for
    each scope; cached scopes ≤ 100ms, default ≤ 200ms (per SDD targets).
  - Cache invalidation works for both inbox (TTL) and vault (TTL + sentinel).
  - FORBIDDEN response from kado-open-notes → graceful empty result, no error.
