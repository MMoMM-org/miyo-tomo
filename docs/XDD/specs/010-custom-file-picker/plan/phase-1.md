---
title: "Phase 1: Spike + script skeleton"
status: complete
version: "1.1"
phase: 1
---

# Phase 1: Spike + script skeleton

## Phase Context

**Dependencies**: Kado v0.7.0 installed; `allowActiveNote` + `allowOtherNotes`
toggled on for the Tomo dev API key (so we can actually call kado-open-notes
without FORBIDDEN).

**Goal**: Validate the three open API behaviours that drive Phase 2's design,
then ship a script skeleton that does prefix routing but stubs the handlers.

---

## Tasks

- [x] **T1.1 Spike: `fileSuggestion` exit-code behaviour** `[activity: spike]` — **DONE 2026-04-20**

  1. Prime: Read Claude Code docs (already fetched). Behaviour on non-zero
     exit not fully specified.
  2. Implement: `scripts/spikes/xdd-010/spike-exit-codes.sh` (query-routed,
     installable via `prep-t1-1.sh`).
  3. Validate: Observations captured in `scripts/spikes/xdd-010/findings.md`.
     Confirmed: exit 0 + paths → rendered; exit 0 + empty → silent no-op;
     exit 1 → picker hidden, no fallback, stdout discarded; exit 0 +
     non-path text → selectable, inserts as `@"<text>"` quoted literal.
     Decisions promoted to spec README (2026-04-20 entries).

- [x] **T1.2 Spike: active-note suffix marker** `[activity: spike]` — **DECIDED WITHOUT SPIKE 2026-04-20**

  Rejected by inference from T1.1 Case D. That case showed non-path text
  inserts as `@"<text>"` quoted literal (no file resolution). The suffix
  `path.md (active)` would render as `@"path.md (active)"` on selection —
  Claude Code would see a string literal, not a file reference. Spike not
  needed to confirm: the evidence is in findings.md and the risk-reward of
  running a second Tomo-restart cycle is poor.

  **Decision**: Suffix-hack **rejected**. Use **position-only marker** —
  active note is emitted at stdout position 0, all other open notes
  follow. No in-text marker. SDD solution.md Active-Note Marker section
  updated to reflect this. Phase 2 implementation relies on ordering
  alone.

- [x] **T1.3 Spike: kado-open-notes path format** `[activity: spike]` — **DONE 2026-04-20**

  Direct curl against Kado at `http://127.0.0.1:23027/mcp` (host reachable
  per .mcp.json). Paths are **vault-relative** (`Calendar/301 Daily/2026-03-26.md`).
  Since instance ≠ vault, Claude Code's @-resolver hits ENOENT and Claude
  falls back to kado-read — one extra tool call per @-pick, acceptable.
  No transformation needed in the picker. Findings in scripts/spikes/xdd-010/findings.md.

- [x] **T1.4 Script skeleton** `[activity: backend]` — **DONE** (commit 2517896)

  Skeleton shipped at `tomo/dot_claude/scripts/file-suggestion.sh` v0.1.0:
  bash 3.2 compatible, reads JSON from stdin via jq, routes on `/inbox` /
  `/vault` / default, stub handlers emit `STUB-*` lines, always exits 0.
  Smoke-tested: `echo '{"query":"foo"}' | bash file-suggestion.sh` emits
  `STUB-open-notes:foo`.

- [x] **T1.5 Settings.json wiring (managed template)** `[activity: backend]` — **DONE** (commit 2517896)

  `tomo/dot_claude/settings.json` has:
  `"fileSuggestion": {"type": "command", "command": "bash .claude/scripts/file-suggestion.sh"}`.
  `jq empty` confirms JSON is valid. `update-tomo.sh` merges the entry
  into instance settings.

- [x] **T1.6 Install copy step** `[activity: backend]` — **DONE** (commit 2517896)

  `scripts/install-tomo.sh` copies `dot_claude/scripts/` recursively into
  `$INSTANCE_PATH/.claude/scripts/`, `chmod +x`'s `.sh` files, creates
  `$INSTANCE_PATH/cache/`. `scripts/update-tomo.sh` has the same copy
  step for update-time sync.

- [x] **T1.7 Phase Validation** `[activity: validate]` — **DONE 2026-04-20**

  - [x] Spike findings (T1.1/T1.2/T1.3) documented in spec README's Decisions Log (5 new entries).
  - [x] Script skeleton runs end-to-end with stub output (commit 2517896 + live T1.1 spike).
  - [x] Tomo session sees the picker invoke our script (confirmed during T1.1 spike: `SPIKE-ACTIVE` + case queries observed).
  - [x] Spec README updated with design pivots (suffix-hack rejection, vault-relative path consequence).

Phase 1 complete. Phase 2 handlers now shipped (see `plan/phase-2.md`).
