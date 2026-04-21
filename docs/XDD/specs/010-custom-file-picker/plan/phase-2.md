---
title: "Phase 2: Handler implementations + caching"
status: complete
version: "1.2"
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

- [x] **T2.1 `handle_open_notes` implementation** `[activity: backend]` — **DONE 2026-04-20**

  Implemented in `tomo/dot_claude/scripts/file-suggestion.sh` v0.2.0.
  Calls `kado_call kado-open-notes {"scope":"all"}`, sorts active-first,
  applies case-insensitive substring filter when query is non-empty,
  truncates to 15. Graceful degradation on any Kado failure (empty
  result, exit 0). Host smoke-test returned 2 open notes, active first.

- [x] **T2.2 `handle_inbox` with caching** `[activity: backend]` — **DONE 2026-04-20**

  Implemented in `file-suggestion.sh`. Inbox path resolved via
  `scripts/read-config-field.py --field concepts.inbox` with awk
  fallback. Cache at `$CACHE_DIR/inbox-files.txt`, 30s TTL.
  `rebuild_listdir_cache` paginates via cursor; filters to `.md`
  files. Host smoke-test: `@/inbox catan` → 2 matches.

- [x] **T2.3 `handle_vault` with caching** `[activity: backend]` — **DONE 2026-04-20**

  Implemented in `file-suggestion.sh`. Sentinel check drops cache +
  sentinel; TTL 3600s. Same pagination helper. Host smoke-test: 345
  `.md` files cached in 131ms cold build; cached-scope query 22ms.

- [x] **T2.4 Shared kado-call helper** `[activity: backend]` — **DONE 2026-04-20**

  `tomo/dot_claude/scripts/lib/kado-call.sh` v0.1.1. Reads
  endpoint + bearer from `.mcp.json` (env `KADO_URL`/`KADO_TOKEN`
  override for host testing). SSE unwrap via awk, jq-extract of
  `result.content[0].text`. Guards empty curl output, non-JSON
  payload, unreachable endpoint → returns non-zero, caller degrades
  to empty.

- [x] **T2.5 fzf fallback to grep** `[activity: backend]` — **DONE 2026-04-20**

  `FZF_AVAILABLE` flag set at script start. `filter_lines` uses
  `fzf --filter "$q"` when available, `grep -i -F -- "$q"` when not.
  Host smoke-test: PATH-stripped of fzf, `@/vault catan` still
  returns the 2 matching files.

- [x] **T2.6 `/explore-vault` cache invalidation** `[activity: backend]` — **DONE 2026-04-20**

  Hooked in `scripts/cache-builder.py` v0.2.0 (not the agent markdown,
  to keep the behaviour deterministic). After the discovery cache
  writes successfully, the script touches
  `<instance>/cache/.invalidate-vault-files`. The picker's
  `handle_vault` deletes that sentinel + cache and rebuilds on the
  next `@/vault` query. Non-fatal on failure (falls back to TTL).

- [x] **T2.7 Active-marker decision implementation** `[activity: backend]` — **DONE 2026-04-20**

  Position-only per T1.2 decision. `handle_open_notes` emits active
  note at stdout position 0, others after. No in-text marker.

- [x] **T2.8 Phase Validation** `[activity: validate]` — **DONE 2026-04-21**

  - [x] Live Tomo session: empty `@` shows open notes + inbox + vault
        top 15; `@<query>` applies fzf filter; no prefix syntax needed
        (unified design supersedes scope-prefix routing; see spec
        README's 2026-04-21 decision).
  - [x] Latency (host, with KADO_URL override):
        - Default (Kado call): ~40ms
        - Inbox cached: 22ms
        - Vault cached: 22ms
        - Vault cold build (345 files): 131ms
        - All well under SDD targets.
  - [x] Cache invalidation tested via sentinel + fresh rebuild
  - [~] FORBIDDEN response graceful empty: deferred (needs Kado key
        without `allowActiveNote`/`allowOtherNotes` to test; the code
        path returns empty on any Kado failure, so behaviourally
        correct — verification when next Kado permission-scope change
        lands)
  - [x] Portable-stat fix (v0.4.3): BSD vs GNU `stat -f` was silently
        breaking every non-empty query in the container. Documented in
        `reference_stat_bsd_gnu_portability` memory.
