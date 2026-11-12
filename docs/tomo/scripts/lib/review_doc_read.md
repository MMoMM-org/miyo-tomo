# WHY: lib/review_doc_read.py

> Rationale for decisions in `tomo/scripts/lib/review_doc_read.py`.
> The module is the one reader of the review document for every Pass 2
> command (spec 045 T4.2): `review-doc.py parse`, `review-instructions.py
> preview` and `deliver`.

## WHY One Reader for Three Commands

`parse` reports counts, `preview` shows the section, `deliver` lands it. All
three must see the same items with the same `edited` and `deleted` answers,
and those answers depend on handing `meta.json`'s `pass1_links` map to
`review_doc_parse.parse_document` (docs/tomo/scripts/lib/review_doc_parse.md,
"WHY edited Is Structural"). `review-doc.py` held that as a private
`_read_document` plus a few lines of meta lookup; copying them into the
second script would be the day the copies drifted. The reader moved into
this lib with its body unchanged; `review-doc.py parse` calls it, and a test
patches `parse_document` to prove both scripts pass the map.

## WHY It Returns the `modified` Time

`deliver` marks the document as the last step with a guarded write; the
guard must be the `modified` of the text the delivery was built from, not a
later read. The reader is the only place that read that text, so it carries
the stamp along with it.

## WHY `doc_path_of` Is Separate

The path comes from `meta.json` or from the caller (`--doc-path`, the
`start` listing's path for a renamed document). Deciding which is a
one-liner the scripts share; keeping it next to the reader makes the
`not-found` answers of the scripts identical: no path, or nothing at it.

## WHY Kado Failures Map the Way They Do

A missing document is a normal answer (None → `not-found`); a refused key or
a dead connection is `review_vault.Stopped` with the SDD's error kinds, so
the scripts' one `Stopped` handler prints `status: stopped`. Any other
read failure is also a stop: a Pass 2 command cannot guess at the document.
