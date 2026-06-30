---
title: "Phase 2: Two-box decision-block UX"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Two-box decision-block UX

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-4]` — two-box block, disposition matrix
- `[ref: SDD/Cross-Cutting Concepts; User Interface & UX]`
- `[ref: PRD/Feature 1, Feature 2]` — terminology + single decision

**Key Decisions**:
- ADR-4: per-item atomic block = `Approve` + `Keep source files` ONLY. Remove the redundant
  `Skip` box (un-approve IS skip) and the per-atomic `Delete source` box. Junk delete-only stays
  in the skipped-items `disposition=delete_source` flow (unchanged). Voice items render the source
  as the {transcript + audio} set.

**Dependencies**:
- Phase 1 (uses the renamed `keep_source` field).

---

## Tasks

Delivers the unambiguous review surface: one source decision per item, consistent "source"
wording, voice source shown as a set.

- [ ] **T2.1 Render the two-box decision block** `[activity: frontend]`

  1. Prime: Read the current per-item render `[ref: SDD/Code Context; suggestions-reducer.py]`
     (decision block ~369-376) and the disposition matrix `[ref: SDD/ADR-4]`.
  2. Test (red): assert the rendered atomic block contains exactly `- [ ] Approve`-style line +
     `Keep source files` line, contains NO `Skip` line and NO per-atomic `Delete source` line, and
     uses the word "source" not "origin" `[ref: PRD/AC F1, F2]`.
  3. Implement (green): rewrite the decision block in `suggestions-reducer.py` (~369-376): emit
     Approve + "Keep source files (don't delete the original(s) after the note is created — you may
     still need them)"; remove the Skip + Delete-source lines. Update the consolidation keep
     control (~788) to "Keep source files".
  4. Validate: reducer render tests pass; lint clean.
  5. Success: block has two controls, source wording, matches ADR-4 mock `[ref: SDD/ADR-4]`.

- [ ] **T2.2 Render the voice source as a file set** `[activity: frontend]`

  1. Prime: Read how the source line is rendered today + the audio_peer intent `[ref: SDD/ADR-1; Runtime View]`.
     (NOTE: the `audio_peer` value is plumbed in Phase 3; here render the SET shape, tolerant of a
     None peer.)
  2. Test (red): given an item WITH an audio_peer, the source renders as the set
     `[[transcript]] + [[audio.m4a]]`; given an item WITHOUT a peer, renders the single source —
     unchanged `[ref: PRD/AC F3]`.
  3. Implement (green): render the source line from the item's source set (primary + optional
     audio_peer). Wikilink by name; never apply `.md` coercion to the audio peer in display.
  4. Validate: render tests pass for set + single-file cases.
  5. Success: voice items show the {transcript + audio} set; non-voice unchanged `[ref: SDD/ADR-4]`.

- [ ] **T2.3 Parse the new label set** `[activity: backend]`

  1. Prime: Read parser checkbox handling `[ref: SDD/Code Context; suggestion-parser.py]`.
  2. Test (red): parsing the new block sets `keep_source` from the "Keep source files" line;
     absence of a per-atomic Delete line does not break parsing; an un-approved item parses as
     skip (stays in inbox) `[ref: PRD/AC F2]`.
  3. Implement (green): update the parser label matching to the new "Keep source files" label;
     ensure removal of the per-atomic Delete-source recognition does not strand the skipped-items
     `disposition=delete_source` path (that flow is separate, keep it intact).
  4. Validate: parser tests pass; round-trip (render→parse) test green.
  5. Success: new block round-trips; skipped-items delete-only flow still works `[ref: SDD/ADR-4]`.

- [ ] **T2.4 Update reference doc + version bumps** `[activity: backend]` `[parallel: true]`

  1. Prime: `docs/XDD/reference/tier-3/inbox/suggestions-document.md` §6 (tri-state model).
  2. Test: N/A.
  3. Implement: update the suggestions-document reference §6 to the two-box model; update
     `docs/tomo` counterparts; bump `# version:` on edited managed scripts.
  4. Validate: docs reflect the new model; versions bumped.
  5. Success: reference doc matches the shipped block `[ref: SDD/CON-3]`.

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - Run full suite; confirm green. Render a sample suggestions doc fixture and eyeball the block.
    Confirm zero "origin"/"Keep origin" in user-facing reducer output. Lint clean.
