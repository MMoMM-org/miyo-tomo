---
title: "Custom File Picker — Implementation Plan"
status: draft
version: "1.0"
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

- [ ] [Phase 1: Spike + script skeleton](phase-1.md)
- [ ] [Phase 2: Handler implementations + caching](phase-2.md)
- [ ] [Phase 3: Settings integration + install flow](phase-3.md)
- [ ] [Phase 4: End-to-end test + docs](phase-4.md)

## Phase Dependencies

Linear: 1 → 2 → 3 → 4. Phase 1's spike findings drive details in Phase 2.

## Acceptance for Spec Completion

- `@` in a Tomo session shows currently-open Obsidian notes (active first).
- `@/inbox <q>` shows inbox files; `@/vault <q>` shows vault matches.
- Latency targets met (see SDD).
- FORBIDDEN/UNAUTHORIZED Kado responses cause graceful empty results, never errors.
- `/explore-vault` invalidates the vault cache.
- Inbox handoff `_inbox/from-kado/2026-04-20_*` marked `done`.
