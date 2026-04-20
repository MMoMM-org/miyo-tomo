---
title: "Phase 1: Spike + script skeleton"
status: pending
version: "1.0"
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

- [ ] **T1.1 Spike: `fileSuggestion` exit-code behaviour** `[activity: spike]`

  1. Prime: Read Claude Code docs (already fetched). Behaviour on non-zero
     exit not fully specified.
  2. Implement: Tiny test script `~/test-fs.sh` that exits with various
     codes and various stdout shapes. Wire into a throwaway settings.json
     `fileSuggestion`.
  3. Validate: Document observed behaviour in spec README:
     - exit 0 + paths → picker shows paths ✓
     - exit 0 + empty → picker shows empty ?
     - exit 1 → fallback to built-in? error banner? silent?
     - exit 0 + non-path text (e.g. `not a real path`) → behaviour ?

- [ ] **T1.2 Spike: active-note suffix marker** `[activity: spike]`

  1. Prime: SDD Active-Note Marker section.
  2. Implement: Test script outputs `Atlas/Japan (MOC).md (active)\nAtlas/Other.md`.
     Pick the first entry; check what's inserted into the prompt.
  3. Validate:
     - Suffix appears in picker UI? (likely yes)
     - Suffix included on insert? (probably yes)
     - Claude Code resolves the file content? (this is the question)
     If file resolves → suffix-hack works, document the exact behaviour.
     Else → mark suffix-hack rejected, note position-only as final design.

- [ ] **T1.3 Spike: kado-open-notes path format** `[activity: spike]`

  1. Prime: Need to know if returned paths are vault-relative, absolute, or
     project-dir-relative.
  2. Implement: Manual curl to kado-open-notes from inside the Tomo
     container. Inspect returned `notes[].path`.
  3. Validate: Compare format to what `@` expects to resolve. If mismatch,
     plan a path-transform step in handle_open_notes.

- [ ] **T1.4 Script skeleton** `[activity: backend]`

  1. Prime: Existing scripts in `tomo/dot_claude/` — none today; this is the
     first script under that managed dir. Use `scripts/lib/` patterns from
     the host scripts (dir setup, header comments) as inspiration.
  2. Implement: Create `tomo/dot_claude/scripts/file-suggestion.sh` with:
     - `# version: 0.1.0` header
     - bash 3.2 compatible (no `declare -A`, no extended bash-only tests)
     - Read JSON from stdin, extract `query` via jq
     - Prefix detection (`/inbox`, `/vault`, default)
     - Stub handlers that emit one placeholder line each so end-to-end
       wiring is visible
     - Always exit 0
  3. Validate: `bash -n` clean. Manual test:
     `echo '{"query":"foo"}' | bash file-suggestion.sh` → emits one stubbed line.

- [ ] **T1.5 Settings.json wiring (managed template)** `[activity: backend]`

  1. Prime: `tomo/dot_claude/settings.json` is the source-of-truth template.
     Read it, locate where to add `fileSuggestion`.
  2. Implement: Add `fileSuggestion` key pointing to `bash .claude/scripts/file-suggestion.sh`.
     Bump settings version comment.
  3. Validate: JSON is valid (`jq . settings.json`).

- [ ] **T1.6 Install copy step** `[activity: backend]`

  1. Prime: `scripts/install-tomo.sh` copies dot_claude/* into instance.
  2. Implement: Add a copy of `dot_claude/scripts/` recursively into
     `INSTANCE_PATH/.claude/scripts/`. Ensure `.sh` files chmod +x.
     Also: `mkdir -p $INSTANCE_PATH/cache/`.
  3. Validate: After install, files appear at correct path with executable bit.

- [ ] **T1.7 Phase Validation** `[activity: validate]`

  - Spike findings (T1.1-T1.3) documented in spec README's Decisions Log.
  - Script skeleton runs end-to-end with stub output.
  - Tomo session sees the picker invoke our script (verify by tail-logging
    inside the script for the duration of Phase 1).
  - Spec README updated with any design pivots from spike.
