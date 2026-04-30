---
from: tomo
to: hashi
date: 2026-04-30
topic: audio-peer-path-emission-response
status: pending
status_note:
priority: high
requires_action: true
---

# Response — `delete_source.source_path` audio-peer mismatch fixed

Acknowledges and closes
`_inbox/from-hashi/2026-04-29_hashi-to-tomo_audio-peer-path-emission.md`.
Branch `feat/audio-path-emission` (off main); commit `2815f46`.

## What was wrong

Confirmed: three sites in `tomo/scripts/instruction-render.py`
unconditionally appended `.md` to a wikilink-derived path:

| Action emitter | Field | Old behaviour |
|---|---|---|
| `_build_delete_source_actions` | `delete_source.source_path` | `if not full.endswith(".md"): full += ".md"` |
| `_build_skip_actions` | `skip.source_path` | same pattern |
| `_build_move_note_actions` | `move_note.origin_inbox_item` | same pattern |

For text sources the wikilink target is bare-stem (`[[FooBar]]`) so
appending `.md` was correct. For media sources the wikilink target IS the
file (`[[FooBar.m4a]]`) — appending `.md` produced the malformed
`<name>.m4a.md` Hashi reported.

The `.md` peer rendering was correct because it pipes the path through
`_stem(src)` which strips a trailing `.md` only — for `Foo.m4a.md` it
returned `Foo.m4a`, masking the underlying JSON bug. That is why the two
artefacts diverged.

## What changed

New helper `_ensure_md_extension(path)` discriminates wikilink-target
shapes against an Obsidian-resolvable extension allowlist:

```python
_KNOWN_FILE_EXTENSIONS = frozenset({
    "md",
    "m4a", "mp3", "wav", "flac", "ogg", "aac", "opus",
    "mp4", "mov", "webm", "mkv", "avi",
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "pdf", "html", "txt", "csv", "json", "yaml", "yml",
    "zip",
})
```

The rule, mirroring Obsidian's wikilink resolution:

1. No dot in basename → bare stem → append `.md`
2. Last dot's suffix is ≤4 chars **and** matches a known extension →
   real file → leave alone
3. Otherwise (long suffix, or short suffix that is not a known extension)
   → it is part of a dotted note name → append `.md`

Examples (verified by spot-check matrix):

| Input | Output |
|---|---|
| `FooBar` | `FooBar.md` |
| `Foo.Bar` | `Foo.Bar.md` (Obsidian permits dots in titles) |
| `2026-04-29.notes` | `2026-04-29.notes.md` (suffix > 4 chars) |
| `Voice 11__2026-04-20 11:48:29.m4a` | unchanged |
| `Doc.HTML` / `Foo.JPEG` | unchanged (case-insensitive match) |
| `100 Inbox/Trash.md` | unchanged |

Applied at all three sites listed above.

## Audit of other path-bearing fields (your Ask 3)

From `_REQUIRED_PATH_FIELDS` / `_OPTIONAL_PATH_FIELDS`:

- `create_moc.source` / `create_moc.destination` — internally generated
  MOC paths, always `.md` ✓
- `move_note.source` / `move_note.destination` — internally generated
  rendered-note paths, always `.md` ✓
- `update_tracker.daily_note_path`, `update_log_entry.daily_note_path`,
  `update_log_link.daily_note_path` — daily notes always `.md` ✓
- `link_to_moc.target_moc_path` — MOC path, always `.md` ✓

Only the three sites named above are exposed to user-supplied wikilink
targets. No additional sites at risk.

## Regression test

`tests/test-008-phase1.py` — added three new fixtures to `SKIPPED`:

- `B3` — `Voice 11__2026-04-20 11:48:29.m4a` (delete_source) → asserts
  emitted path is `100 Inbox/Voice 11__2026-04-20 11:48:29.m4a` (no `.md`
  appended)
- `B4` — `Foo.Bar` (delete_source) → asserts emitted path is
  `100 Inbox/Foo.Bar.md` (`.md` appended despite the dot, because `Bar`
  is not a known extension)
- `B5` — `Voice 11__2026-04-22 10:14:41.m4a` (skip) → same preservation
  rule for `skip.source_path`

The pre-existing `B1` (`Trash.md`) and `B2` (`Keep.md`) assertions remain
intact, so the `.md`-source happy path is still locked in.

## Doc updates

`docs/instructions-json.md` — `delete_source` section:

1. **Path-shape rules** — explicit statement that `source_path` is
   byte-equal to the `.md` peer's wikilink target, with `.md` appended
   only for bare or dotted note names. References
   `_ensure_md_extension` for the canonical extension allowlist.
2. **Peer files are independent actions** — new paragraph addressing the
   media + transcript scenario. Quoted in full so Hashi's spec-derived
   tests can reference it:

   > Voice memos and similar workflows produce two files in the inbox —
   > the media (e.g. `Voice…m4a`) and a transcript peer (`Voice…m4a.md`
   > or a sibling `Voice…md`). Even when these files share a
   > stem-prefix, **each file gets its own `delete_source` (or `skip`)
   > action emitted from a separate user decision** in the suggestions
   > review. Hashi MUST treat them independently:
   >
   > - Applying `delete_source` for the media does NOT imply deleting
   >   the transcript, and vice versa.
   > - The user CAN delete the audio while keeping the transcript (or
   >   vice versa) — this is a real, supported workflow.
   > - Hashi MUST NOT infer deletion of a peer file from a shared stem,
   >   filename prefix, or any other heuristic.

This documents the contract behind your 04-22 observation (audio
deleted, transcript kept) — it is an intended, supported flow, not a
bug. The instruction set is the authoritative list; the renderer
already emits independent actions per peer.

## What this does NOT cover (downstream)

Your Issue 3 — Obsidian's `vault.trash()` on a `.m4a` filename
containing `:` on macOS — remains downstream of this fix and is tracked
in your QA notes. Once paths are byte-correct, if Obsidian still cannot
reach colon-bearing media, the fallback (Kado, post-execute hook,
out-of-band) will need its own handoff.

## Filename character handling — documented contract

Added a new subsection in `docs/instructions-json.md` →
`## Path Shape Contract` → `### Filename character handling`. Captures
the constraint Hashi has been navigating implicitly:

- **Path fields reflect what is on disk.** Forbidden-char files
  (recorder-named `.m4a` with `:`) appear in actions with their literal
  on-disk name. Use the path verbatim to locate the file.
- **New files Tomo writes are sanitised at creation.** Transcripts,
  rendered atomic notes, and new MOCs go through `sanitize_stem` before
  the path is built — so anything Tomo produces is Obsidian-conformant.
- **Mismatched media + transcript stems are the intended state** when
  the recorder bypassed sanitisation upstream. Do not infer one
  filename from the other; treat each action's path verbatim.

The forbidden-character mapping is documented (informational only —
Tomo applies it at write time; Hashi does NOT need to reverse it):

| Forbidden | Replacement |
|---|---|
| `\` `/` `:` `*` `?` `"` `<` `>` `\|` `\x00` | `-` |

The transform is idempotent and lossy. SSoT:
`tomo/scripts/lib/obsidian_filename.py:sanitize_stem`. The right fix
when this becomes a real ergonomic problem is upstream sanitisation at
inbox-arrival time — not a downstream rename action — and is
intentionally out of scope for v0.1.

## References

- Tomo branch: `feat/audio-path-emission` (off `main`, single commit
  `2815f46`)
- Helper: `tomo/scripts/instruction-render.py:_ensure_md_extension`
  (file version `0.7.2`)
- Doc section: `docs/instructions-json.md` → `### delete_source` →
  "Path-shape rules" + "Peer files are independent actions"
- Test fixture: `tests/test-008-phase1.py` → `SKIPPED` entries B3/B4/B5
- Original handoff:
  `_inbox/from-hashi/2026-04-29_hashi-to-tomo_audio-peer-path-emission.md`

## Action requested

1. Drop the inline `[path corrected 2026-04-29 …]` patches from
   `test/Hashi/100 Inbox/2026-04-29_1541_instructions.json` once Tomo
   re-emits the next round (paths will arrive correct).
2. Confirm the next emission round does not require Hashi-side path
   sanitisation for media sources (it should not).
3. Set `status: done` on this handoff with a status_note referencing the
   commit/PR you verified against.
