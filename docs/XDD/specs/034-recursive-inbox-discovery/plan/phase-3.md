---
title: "Phase 3: Recursive discovery"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Recursive discovery

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3]`
- `[ref: SDD/Solution Strategy; step 2]`
- `[ref: PRD/Feature 1, Feature 5, Feature 9, Feature 10]`

**Key Decisions**:
- One recursive listing feeds both discovery and the attachment index; base Kado calls fall
  3 → 2. Recursion makes discovery **cheaper**, not dearer.
- The two file-type filters must be unified before the listing can be shared.
- Audio pairing compares paths, not bare filenames.

**Dependencies**: Phase 2 complete. This is the phase that makes collisions possible, so the
identity work must be finished and proven first — see the sequencing rule in `plan/README.md`.

**Visible effect**: this is where the feature becomes real. A note in a subfolder is triaged.

---

## Tasks

Turns on the behaviour the previous two phases prepared for.

- [x] **T3.1 One file-type filter** `[activity: backend]`

  1. **Prime**: Read `discover_files` (`inbox-triage.py:177`) — `(item.get("type") or "").lower()`,
     case-insensitive and None-safe — and `build_inbox_index` (`lib/attachment_index.py:54`) —
     `item.get("type") != "file"`, exact match. They disagree. Verified that the gateway emits
     lowercase literals (`Kado/src/obsidian/search-adapter.ts:194,247`), so this is latent
     robustness, not a live bug — but the two must agree before they share input.
  2. **Test** (RED):
     - both filters agree for an entry whose type differs only in letter case
       `[ref: PRD/AC Feature 10]`
     - both agree for a `None` type, a missing key, and a non-dict entry
     - folder entries are excluded by both
  3. **Implement**: one shared predicate; both call sites use it.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The two consumers cannot disagree about what a file is `[ref: SDD/ADR-3]`

- [x] **T3.2 Recursive discovery on one shared listing** `[activity: backend]`

  1. **Prime**: Read `discover_files` (`inbox-triage.py:167-193`) and `build_attachment_index`
     (`:200-217`), whose docstring already calls itself "a second, independent call from the
     existing depth=1 partition listing". Read `[ref: SDD/ADR-3]`.
  2. **Test** (RED):
     - a note at `100 Inbox/Places/Dresden.md` becomes an item `[ref: PRD/AC Feature 1]`
     - a note nested two levels deep is discovered — no depth limit
     - a `.png` in a subfolder is **not** partitioned as an item, exactly as a root-level image
       is not today (the `#93` partition is by suffix and must be untouched)
     - exactly **one** listing call is made per run, asserted against a fake client's own
       recorded calls rather than a hand-derived expectation
     - a flat inbox yields the same items as before
  3. **Implement**: drop `depth=1`; pass the single listing to both consumers.
  4. **Validate**: tests pass; `ruff` clean; the Kado call estimator is updated to match the new
     base count and its own docstring says 2, not 3.
  5. **Success**:
     - [ ] Subfolder notes are triaged `[ref: PRD/AC Feature 1]`
     - [ ] Base Kado calls are 2, down from 3 `[ref: PRD/AC Feature 9]`

- [x] **T3.3 Audio pairs by note, not by name** `[activity: backend]` `[parallel: true]`

  1. **Prime**: Read `check_audio` (`inbox-triage.py:526-541`). `md_stems` is a flat set of
     `Path(f["path"]).stem.lower()` with no folder component — safe only while discovery is flat.
  2. **Test** (RED):
     - `100 Inbox/memo.m4a` with no transcript, plus an unrelated `100 Inbox/Archive/memo.md`,
       still counts as needing transcription `[ref: PRD/AC Feature 5]`
     - `100 Inbox/Voice/memo.m4a` with `100 Inbox/Voice/memo.md` is recognised as paired
     - the existing flat-inbox pairing is unchanged, including the `sanitize_stem` handling of
       an audio filename that is not already Obsidian-safe
  3. **Implement**: compare on the containing folder plus stem, not the stem alone.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A namesake elsewhere cannot mark an audio file as already handled
           `[ref: PRD/AC Feature 5]`

- [x] **T3.3b The voice path follows recursion** `[activity: backend]`

  Added 2026-09-06 at the T3.3 review. T3.2 made discovery recursive; the voice path was never
  swept for it, and T3.3 alone makes subfolder audio **worse**, not better.

  Three sites, three different answers to "where does a transcript live":

  | Site | Target / pairing | Folder-aware | Sees subfolders |
  |---|---|---|---|
  | `inbox-triage.check_audio` (T3.3) | `(parent, stem)` | yes | yes |
  | `voice-precheck.py:42-45` `_expected_md_path` | `p.parent / f"{safe}.md"` | yes | **no — `depth=1` at `:50`** |
  | `voice-transcriber.md:118` | `<inbox_path>/<SAFE_STEM>.md` | **no — inbox root** | its own listDir |

  T3.3 aligned `check_audio` with `voice-precheck`'s already-folder-aware convention, which is the
  right direction. The outlier is the transcriber agent, which writes to the inbox root. Before
  recursion that *was* beside the audio, because all audio sat at the root; T3.2 broke that
  assumption silently.

  **The user-visible consequence, and why this cannot wait:** before T3.3, a subfolder audio with a
  root namesake was wrongly considered done and silently never transcribed. After T3.3 alone it
  never pairs, so every run reports it as needing transcription, dispatches the transcriber, which
  writes the transcript to the **root** — where the pairing still fails. Next run, same again. That
  is the repeated-dispatch shape of the `:`-versus-`-` infinite transcribe loop this repo has
  already hit once, with a folder mismatch instead of a character mismatch.

  1. **Prime**: Read `voice-precheck.py:42-52`, `voice-transcriber.md:90-125` (Step 3's sibling
     filter and target composition), and `voice-transcribe.py:146-153` (the CLI emits a bare
     `target` filename — the agent composes the folder). Read `[ref: SDD/CON-5]`.
  2. **Test** (RED):
     - `voice-precheck` sees an audio file in a subfolder at all — today `depth=1` hides it
     - a subfolder audio with its sibling transcript beside it is reported cached by
       `voice-precheck`, and `check_audio` agrees — the two must not disagree
     - a subfolder audio with **no** sibling is reported uncached by both
     - a root-level audio behaves exactly as before, including the `sanitize_stem` case
       (`Rec 2026-01-02 14:30.m4a` pairs with `Rec 2026-01-02 14-30.md`)
  3. **Implement**: drop `depth=1` in `voice-precheck.py`; change the transcriber's target
     composition to the audio file's **containing folder** plus the sanitised stem. Write the
     `docs/tomo/` counterpart first `[ref: SDD/CON-5]` — `voice-transcriber.md` is LLM-loaded
     verbatim and carries imperatives only.
  4. **Validate**: tests pass; `ruff` clean; the runtime agent file stays imperative-only.
  5. **Success**:
     - [ ] All three sites agree on where a transcript lives `[ref: PRD/AC Feature 5]`
     - [ ] A subfolder audio is transcribed exactly once and never re-dispatched
     - [ ] The `sanitize_stem` asymmetry is preserved — only the derived `.md` target is
           sanitised, never the source audio name

- [x] **T3.4 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - **Flat-inbox golden check**: render a suggestions document from a root-only fixture before
    and after this phase and compare the whole string. Not selected fields — the whole
    document `[ref: PRD/Success Metrics; no regression]`.
  - Verify the call-count claim by observing a fake client's recorded calls, not by reading the
    estimator's arithmetic. The estimator is the thing under test, so it cannot also be the
    evidence.
  - Confirm a same-name pair now survives a full Pass-1 run — Phase 2 made this safe, and this
    is the first phase where it can actually happen.
  - Bump `# version:` on every modified file.
