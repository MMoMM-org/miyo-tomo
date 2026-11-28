# WHY: lib/review_discard.py

> Rationale for decisions in `tomo/scripts/lib/review_discard.py`.
> The module is the Kado half of `review-doc.py discard` (spec 047 Phase 9
> live walk, F-R5-2): one frontmatter read of the review document, one
> frontmatter merge of `tomo.state: discarded` guarded by the read's
> `modified`, and a closed stop reason for everything else. The stage is
> the script's.

## WHY Discard Exists (Spec 047 Walk F-R5-2)

WHY: step 1 of the skill handles every `open_reviews` entry before the new
request. For an unapproved `open` document the answers were Continue (Pass 2
on it, which stops at "not approved"), Start over (read that period again)
and Abort (end the run). None of them let the user put an unwanted review
aside, so one open document blocked `/review` for every other period. The
owner decided to add Discard.

## WHY the Document Is Marked and Kept, Not Deleted (Owner Decision)

The owner chose to mark the document and keep the file. Recorded as the
owner's decision; the facts it rests on:

- Tomo deletes nothing in the vault; removing a document from the inbox is
  the user's to do, as for every other document Tomo delivers (PRIVACY.md,
  "Your inbox").
- The user may have edited the document; a mark loses none of those edits.
- A frontmatter merge needs no Kado delete permission.

The mark is `tomo.state: discarded` (`review_state.DOC_STATE_DISCARDED`), so
the one owner of the open-review states decides that the document is not
listed (docs/tomo/scripts/lib/review_state.md). The review schema
(`tomo/schemas/doc-frontmatter.schema.json`) takes `discarded` as a review
state, so a marked document stays schema-valid, and `lib/tomo_lifecycle.py`
lists the `review-doc discard` transitions into it.

## WHY One Read, Then One Guarded Merge

The merge uses `mode: merge`: Kado deep-merges the `tomo` block, so
`doc_type`, `run_id`, `updated_at`, the `review_*` keys and the body stay
byte for byte what the user left. It sends the `modified` the read just
returned as `expectedModified`, so a save between the read and the merge is
a refusal, never a mark on a document the user changed under it. A read
that returned no `modified` is not merged without a guard: it stops
`kado-failed` with `error.kind` `modified-missing`.

The read also checks `tomo.doc_type` `review`: the path comes from
`meta.json` or the listing, and a note of the user's own at that path
(`not-a-review`) is never marked.

## WHY These Stop Reasons

The skill says each stop in one line by its code and ends the run, so the
codes are closed (`REASONS`):

- `doc-missing` — NOT_FOUND on the read or on the merge (deleted in
  between). Nothing to mark.
- `not-a-review` — see above.
- `doc-changed` — `review_kado_conflict.is_conflict`: the client's
  `KadoConcurrencyError` or a tool error whose code is `CONFLICT`. Its
  `conflict` is `review_kado_conflict.conflict_reason`
  (`open-unsaved`, `changed-since-read`, `unknown`), the same reading the
  delivery's `doc-changed` uses, so the skill can tell the user to save
  (Cmd+S) or close the document.
- `kado-failed` — any other Kado failure, on the read or the merge, with
  `error` from `review_kado_conflict.error_of`: the class name and Kado's
  closed uppercase code, never the message (a message can carry the
  note's path or text).
