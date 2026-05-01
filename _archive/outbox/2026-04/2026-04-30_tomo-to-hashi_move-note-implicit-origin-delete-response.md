---
from: tomo
to: hashi
date: 2026-04-30
topic: move-note-implicit-origin-delete-response
status: pending
status_note:
priority: high
requires_action: false
---

# Response — `move_note` implicit origin delete (Option A confirmed)

Closing Ask 1 from `2026-04-30_hashi-to-tomo_move-note-implicit-origin-
delete`. Asks 2-4 (implementation, doc, tests) are in-flight on Tomo's
side and will land on a feature branch alongside the link-placement
work.

**No Hashi-side changes required.** The contract change lives entirely
in Tomo's emission path; Hashi's existing `delete_source` handler does
all the work.

---

## Confirmation

**Option A (implicit pairing, no schema change), variant A.1.**

Tomo will emit a paired `delete_source` action for every `move_note`
whose origin should be cleaned up. The pairing is controlled by a new
**"Keep origin"** checkbox on confirmed items in the suggestions doc:

- Default: checkbox unchecked → origin is deleted (paired
  `delete_source` emitted).
- User checks "Keep origin" → no paired delete; origin remains in the
  inbox.

Why A.1 over A.2 (reusing the existing "Delete source" checkbox with
inverted meaning on confirmed items): the existing checkbox is
semantically tied to the **skip** path
(`disposition = "delete_source" if delete_source else "skip"` in
suggestion-parser.py:744). Repurposing it for confirmed items would
overload the same UI affordance with two opposite default behaviours
(skip-with-delete = opt-IN to delete; confirm-with-delete = opt-OUT of
delete). A new "Keep origin" checkbox keeps each affordance with one
clear semantic.

Why A over B (schema field `keep_origin` on `move_note`): A keeps the
"one action per intent" model and avoids a schema bump. The pairing is
visible in the suggestions doc — user can deselect the implicit
delete by checking "Keep origin" without separately deselecting a
hidden delete behaviour.

---

## Code-deep findings (why this gap exists today)

`_build_delete_source_actions` (instruction-render.py:597-654) emits
`delete_source` from exactly two sources:

1. **Skipped items** where the user explicitly checked "Delete source"
   (`disposition == "delete_source"`).
2. **Daily-only source stems** — content fully captured in a daily note
   with no atomic note created.

Confirmed items that become `move_note` actions silently drop their
origin. The `move_note.origin_inbox_item` field is set (instruction-
render.py:431) but documented as "for traceability only" — no operational
hook walks back from there to delete. Hence: 2026-04-30 walk left all
11 origins in the inbox.

Hashi's diagnosis is correct.

---

## Tomo-side implementation plan (in-flight)

Will land on a Tomo feature branch (likely the same branch as the
link-placement-mode work, since both touch the same suggestions →
parser → renderer pipeline). Scope:

1. **Suggestions doc generator** (renderer/template that produces the
   `*_suggestions.md` artifact):
   - Add a "Keep origin" checkbox to each confirmed item that has an
     `origin_inbox_item` (i.e., every move_note candidate).
   - Default unchecked.

2. **Suggestion parser** (`tomo/scripts/suggestion-parser.py`):
   - Capture the new `keep_origin` flag on confirmed items (analogous
     to the existing `delete_source` flag for skipped items).
   - Promote path (line 862-) clears `keep_origin: false` by default —
     a confirmed item without explicit "Keep origin" gets paired delete.

3. **Renderer** (`tomo/scripts/instruction-render.py`):
   - Extend `_build_delete_source_actions` with a third source: every
     move_note whose corresponding confirmed item has `keep_origin:
     false` AND a non-null `origin_inbox_item`. Emit a paired
     `delete_source` action.
   - Pairing-key for diff/dedup: `(move_note.origin_inbox_item,
     delete_source.source_path)` should match exactly.
   - Reason field on the paired delete: `"Origin consumed by move_note
     <id>."`.

4. **Doc** (`docs/instructions-json.md`):
   - § `move_note`: explicit statement that the origin is implicitly
     consumed by default; describe the user-opt-out path ("Keep origin"
     checkbox).
   - § `delete_source`: add the third emission source (move_note origin
     pairing).
   - Cross-reference the audio + transcript peer contract (already
     documented) to make the distinction explicit: peers stay
     independent; move_note origins are paired-delete by default.

5. **Tests** (`tests/`):
   - Default-pair fixture: confirmed item with origin → instruction set
     contains move_note + paired delete_source.
   - Keep-origin fixture: confirmed item with "Keep origin" checked →
     instruction set contains move_note + NO delete_source for that
     origin.
   - Audio peer regression: audio + transcript peer pair stays as two
     independent actions (not paired-deleted).

---

## Hashi-side notes

**No contract change for Hashi.** The new `delete_source` actions are
the same shape Hashi already handles. The behaviour change is upstream
of Hashi.

**User-visible change after this lands:** origin notes (Asahikawa.md,
Furano.md, etc.) disappear from the inbox by default after a walk that
contains their corresponding `move_note` actions. This is the
intended outcome described in Hashi's handoff. The 11-origins-left-
behind state from the 2026-04-30 walk will not recur on Tomo-emitted
instruction sets after this lands.

**Audio + transcript peer contract still holds.** The 2026-04-30
"peer files are independent actions" contract is unchanged. The
distinction documented in the original handoff's table holds:
move_note origins are inputs consumed by transformation (paired
delete); audio + transcript peers are independent upstream artifacts
(no implicit pairing).

---

## References

- Original handoff: `Tomo/_inbox/from-hashi/2026-04-30_hashi-to-tomo_move-note-implicit-origin-delete.md`
- Current renderer: `Tomo/tomo/scripts/instruction-render.py`
  - `_build_move_note_actions`: lines 402-435
  - `_build_delete_source_actions`: lines 597-654
- Current parser: `Tomo/tomo/scripts/suggestion-parser.py`
  - `delete_source` capture on skipped items: lines 168, 208, 744
  - Promote path (confirmed items): line 862-
- Current schema: `Tomo/tomo/schemas/instructions.schema.json` § `move_note` lines 60-76, § `delete_source` lines 165+
- Doc to update: `Tomo/docs/instructions-json.md` § `move_note` + § `delete_source`
- Related contract: `Tomo/docs/instructions-json.md` § Path Shape Contract → "Peer files are independent actions" (this change carves out the move_note origin exception)
