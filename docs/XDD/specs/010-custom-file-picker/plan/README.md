---
title: "Custom File Picker — Implementation Plan"
status: complete
version: "1.1"
---

# Implementation Plan

## Context Priming

**Specification**:
- `docs/XDD/specs/010-custom-file-picker/README.md`
- `docs/XDD/specs/010-custom-file-picker/requirements.md`
- `docs/XDD/specs/010-custom-file-picker/solution.md`

**Key Design Decisions**:
- Single bash script `file-suggestion.sh` routes by query prefix
- Default: kado-open-notes (active first); `/inbox`: cached Kado-search;
  `/vault`: fzf on cached vault list
- Cache files in `tomo-instance/cache/` with TTL invalidation
- `/explore-vault` writes a sentinel to invalidate vault cache
- Active marker: position 0 always; suffix-hack `path (active)` to be
  spike-tested in Phase 1

## Implementation Phases

- [x] [Phase 1: Spike + script skeleton](phase-1.md) — 2026-04-20
- [x] [Phase 2: Handler implementations + caching](phase-2.md) — 2026-04-20/21
- [x] [Phase 3: Settings integration + install flow](phase-3.md) — retrospectively validated 2026-04-21
- [x] [Phase 4: End-to-end test + docs](phase-4.md) — 2026-04-21 (T4.5 deferred cross-repo)

## Phase Dependencies

Linear: 1 → 2 → 3 → 4. Phase 1's spike findings drove Phase 2 details.
Scope prefix retirement between Phase 2 and finalization (commit
`2a5966f`) simplified Phase 4 scope.

## Acceptance for Spec Completion

- ✅ `@` in a Tomo session shows currently-open Obsidian notes (active first).
- ✅ `@<query>` surfaces matches across open notes + inbox + vault
  (unified picker — scope prefixes retired).
- ✅ Latency qualitatively acceptable (daily use; debug log in place).
- ✅ FORBIDDEN/UNAUTHORIZED Kado responses cause graceful empty
  results — structural (guarded `kado_call` + independent source fans).
- ✅ `/explore-vault` invalidates the vault cache via
  `.invalidate-vault-files` sentinel.
- ⏳ Inbox handoff `_inbox/from-kado/2026-04-20_*` — deferred to next
  Kado session (symlink into Kado repo; Tomo can't close the file).
