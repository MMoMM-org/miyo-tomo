# WHY: lib/review_doc_parse.py

> Rationale for decisions in `tomo/scripts/lib/review_doc_parse.py`.
> The module reads the review document of `/review` back after the user
> edited it (spec 045, T3.7, PRD F5-AC1, F5-AC6, F6-AC1, Business Rules 1-3
> and 7, SDD ENTITY ReviewDoc / ApprovedReview, item identity, the 80/20
> boundary, ADR-9, ADR-13): the Approved line, the groups, Tomo's items by
> id, the user's items, the warnings. No Kado, no file I/O; `review-doc.py
> parse` reads the document and writes what this module returns.

## WHY Only an Exact Column-0 Line Is Structure

`moc-proposal-parser.py` reads `^\s*-\s*\[x\]` — any indentation, any
spacing — because the MOC proposal document has no continuation lines. The
review document has them: a multi-line item renders as one `- [x]` line and
two-space-indented continuation lines, and `review_doc` escapes every item
line that would be structure with a backslash. A parser that strips leading
whitespace would undo that defence: `  - [ ] Approved` inside an item would
become the gate, `  ## Done` a second group. So the grammar is exact: the
Approved line is `- [ ] Approved` or `- [x] Approved` at column 0 and
nothing else on the line; a group heading is `## ` at column 0; an item
starts with `- [ ] ` or `- [x] ` at column 0 (`X` accepted, as Obsidian
writes it). Every other line after an item start is that item's text,
verbatim — indentation, backslashes and all; the landing (Phase 4) decides
what the periodic note gets. The title (`# …`) and the info callout are not
structure the parser needs; they are skipped like any other line outside an
item.

The "nothing found" bullet needs no exception: `- nichts gefunden` is not
a checkbox line, so it is not an item in this grammar (the reason
`review_doc` renders it as a plain bullet).

The Approved line counts wherever it stands at column 0, also inside a
group: the 80/20 boundary lists "moving the Approved line into a group" as
something the document cannot carry safely, and the honest reading of an
exact `- [x] Approved` is still "the user ticked Approved". A ticked line
that reads `- [x] Approved` can therefore never become a user item.

## WHY Tomo's Items Are Told Apart by Id, Not by Links (ADR-13)

The PRD's edge case: a Tomo item rewritten without its source links is
still Tomo's — kept and edited, not deleted plus added. The links are
part of the text the user may retype; the id `%%t<n>%%` on the checkbox
line is the only thing that survives a rewrite. The parser takes the first
id it finds on the checkbox line (the user may have typed after it), strips
it from the text, and files the item as `origin: tomo`. A ticked line
without an id is `origin: user`. An id the user deleted makes the item a
user item and its id counts as deleted — the count difference is reported,
never guessed (SDD item identity). A second line carrying an id already
seen (the user copied a Tomo line) is a user item: one id names one Pass 1
item.

## WHY `edited` Needs a Fingerprint in `meta.json`

`edited` is "the text differs from Pass 1's" (SDD). Pass 1's text exists
only in the document: `read.json` and `proposals.json` are deleted after
the write (ADR-9), and the document is what the user edited. Comparing
needs a trace of the Pass 1 text that holds no content. `fingerprints`
hashes each Tomo item as rendered — the checkbox line after the box, id
stripped, plus its continuation lines — to a truncated SHA-256 per id, and
`review-doc.py write` stores the map as `pass1_items` in the content-free
`meta.json`. A fingerprint is not content: it cannot be read back into a
sentence, and it is computed from the same parser the edited document goes
through, so the only way to match it is an unchanged item. Without a
fingerprint for an id (an older `meta.json`, a forged id) `edited` is
False: the parser reports a difference it can see, never one it guesses.

The fingerprint ignores the tick state: unticking is not editing, and an
unticked item is not landed anyway.

## WHY Group Headings Are Matched Over Every Language

The heading labels live in `review_doc`'s de/en table. The document carries
`review_language` in its frontmatter, but the frontmatter is one of the
things the user can break (`frontmatter-broken`), so the parser matches a
heading against the labels of every language at once. The labels are
distinct across languages; a heading that matches none is `unknown-group`.

## WHY Items Under an Unknown Heading Are Kept, Not Dropped

A renamed heading is on the 80/20 list (warned, handed to the later editor
spec), but the items under it are the user's edits. Dropping them silently
would contradict "Pass 2 reads exactly what the user left". They are parsed
like any other and reported under the group key `unknown`, so nothing is
lost and nothing is guessed about which group the user meant. The heading
text itself never reaches stdout — it is the user's text — only the
warning does.

A heading rendered twice (`duplicate-group`) keeps both lists under the
one group, in document order.

## WHY the Counts Are Four Numbers

`kept` and `unticked` split Tomo's items by their box; `deleted` is every
Pass 1 id (from `pass1_items`, else the sum of `pass1_counts`) that the
document no longer carries; `added` is the user's ticked items — the ones
that land. An unticked line without an id is a note to self and counts
nowhere. These four are what the engagement KPI and the skill's report need
(ADR-13 rationale), and they carry no text, so they may go to stdout.

## WHY the Result Carries the Text and stdout Does Not (ADR-9)

Phase 4 lands the kept text; the skill reports counts. `ParsedDoc` holds the
items with their verbatim text and continuation lines; `approved_review`
turns it into the ApprovedReview record (kept items only, groups in the
document's rendering order) that `review-doc.py parse` writes to
`tomo-tmp/review/<stem>/approved.json` — content, in the place the SDD
already names as resting content. `public_items` is the same structure
without text (`id`, `origin`, `kept`, `edited`), for stdout. One module
produces both so they cannot drift.

## WHY a Broken Frontmatter Is a Warning, Not a Stop

The body is what the user edited and what Pass 2 lands; the frontmatter is
Tomo's bookkeeping. YAML that does not parse, a non-mapping, or a block
without `tomo.doc_type: review` gives `frontmatter-broken` and the body is
still read, so the user is told what to fix without losing their edits.
A document that is not at its path at all is `review-doc.py parse`'s
`not-found` — the user renamed or moved it beyond recognition (SDD Error
Handling); the parser never sees it.
