# WHY: lib/review_doc_parse.py

> Rationale for decisions in `tomo/scripts/lib/review_doc_parse.py`.
> The module reads the review document of `/review` back after the user
> edited it (spec 045, T3.7, PRD F5-AC1, F5-AC6, F6-AC1, Business Rules 1-3
> and 7, SDD ENTITY ReviewDoc / ApprovedReview, item identity, the 80/20
> boundary, ADR-9, ADR-13): the Approved line, the groups, Tomo's items by
> id, the user's items, the warnings. No Kado, no file I/O; `review-doc.py
> parse` reads the document and prints the content-free part of what this
> module returns; the ApprovedReview record stays in-process.

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

**The first column-0 Approved line decides.** A document can carry two
(the user copied the line, or typed a second one into a group). The parser
takes the first one in document order and ignores the rest: Tomo rendered
exactly one, at the top, so the first is the one Tomo asked about, and a
later copy is the user's stray text. "Any ticked Approved line approves"
would let a copied line deep in a group approve a review the user never
ticked at the top; "all must agree" would turn a stray copy into a silent
`approved: false`. Both are guesses; the first line is the rendered one.

## WHY the Grammar Tolerates What Editors Add, Not What Users Indent

Obsidian and other editors leave marks on a saved file that are not the
user's edits: a UTF-8 byte-order mark at the start, `\r\n` line ends, a
trailing space after a word, closing hashes on a heading (`## Done ##`,
written by some Markdown tools and accepted by CommonMark). Each of these
would otherwise break structure the user never touched — a BOM makes the
first line `﻿---` and the frontmatter "missing", a trailing space makes
`- [x] Approved ` fail the exact match and the review "unapproved", a
closing-hash heading becomes `unknown-group`. So the parser strips one
leading U+FEFF before it looks for the frontmatter, lets the Approved line
end in whitespace, strips closing hashes and whitespace from a heading's
label, and reads lines with `splitlines()`, which treats `\r\n` as one line
end — a CRLF document parses to the same result as its LF twin.

None of this loosens the column-0 rule. Leading whitespace is the user's
own mark (an item's continuation line is exactly that), so ` - [x]
Approved` and `  ## Done` stay item text, as before. Tolerance is for what
the editor adds around the line, never for where the line stands.

## WHY a Trailing Tasks Done Marker Is Tolerated and Stripped

The Obsidian Tasks plugin appends ` ✅ YYYY-MM-DD` to a checkbox line the
moment its box is ticked — in the Phase 6 live walk (spec 045) the owner
ticked Approved and the line became `- [x] Approved ✅ 2026-11-12`;
the exact-match grammar answered `approved: false`, `approved-line-missing`
and `item-outside-group`, and counted the gate as one added user item. The
same happens to every Tomo item the user unticks and ticks again: the
marker would have landed in the periodic note as part of the kept text.
The marker is a plugin's mark on the line, exactly like a BOM or a trailing
space, not the user's words, so it belongs with what the grammar tolerates:

- The Approved line is matched after a trailing done marker is cut, so
  `- [x] Approved ✅ 2026-11-12` is the gate (and an unticked line with a
  stale marker is still unticked — the plugin removes the marker on untick,
  and a marker left behind changes no box). Anything else after `Approved`
  stays what it was: no gate, one stray line.
- A checkbox line's text loses one trailing done marker after the ids are
  stripped — Tasks writes it after `%%t<n>%%`, a plugin that keeps the
  comment last would write it before, and both end up trailing once the
  ids are gone. The kept text, `approved_review`, the rendered section and
  the delivered MD therefore carry no marker, and `edited` is unaffected
  either way: the marker is no `[[link]]`, so the link stems do not change.
- Only a *trailing* marker on the *checkbox line* is the plugin's. A `✅`
  date inside the text or on a continuation line is the user's words and
  stays verbatim; a daily's own tasks never bring one into the document,
  because `review_day` drops the marker from a task's text before the
  model ever sees it, and the model proposes the item text.

The pattern is `review_md.DONE_MARK_RE`, the one `review_day` already uses
for a daily's tasks, anchored to the line end here — one definition of the
marker for both readers. Only the done marker is known; the plugin's other
fields (`📅 ⏳ 🛫 ➕ 🔁`) are typed on purpose and remain the user's text
(see `docs/tomo/scripts/lib/review_md.md`).

## WHY Tomo's Items Are Told Apart by Id, Not by Links (ADR-13)

The PRD's edge case: a Tomo item rewritten without its source links is
still Tomo's — kept and edited, not deleted plus added. The links are
part of the text the user may retype; the id `%%t<n>%%` on the checkbox
line is the only thing that survives a rewrite. The parser takes the first
id it finds on the checkbox line (the user may have typed after it), and
files the item as `origin: tomo`. A ticked line without an id is `origin:
user`. An id the user deleted makes the item a user item and its id counts
as deleted — the count difference is reported, never guessed (SDD item
identity). A second line carrying an id already seen (the user copied a
Tomo line) is a user item: one id names one Pass 1 item.

**Every id on the line is stripped from the text.** When the user merges
two Tomo lines into one (`- [x] b %%t2%% %%t3%%`), the first id names the
item and the second is a Pass 1 id this line does not represent — `t3` is
deleted unless another line still carries it. The `%%t3%%` marker is still
Tomo's bookkeeping, not the user's words: leaving it in the kept text would
land an Obsidian comment in the periodic note, and the next `link_stems`
of a replaced document would read it as a second item's marker. So the text
is the checkbox line with every `%%t<n>%%` removed, whitespace trimmed;
the ids themselves are never text.

**`[X]` is a tick.** Obsidian writes a lowercase `x`, but a user typing the
box by hand, or a plugin, may write `X`; CommonMark task lists accept both.
A ticked item read as unticked would silently drop the user's choice, so
the box is compared case-insensitively — for Tomo's items, the user's
items and the Approved line alike.

## WHY `edited` Compares Source Links, Not a Digest of the Text

`edited` is "the item differs from Pass 1's" (SDD item identity). Pass 1's
text exists only in the document: `read.json` and `proposals.json` are
deleted after the write (ADR-9), and the document is what the user edited.
Comparing needs a trace of Pass 1 in `meta.json`, and `meta.json` is
content-free (SDD ENTITY ReviewDeliveryMeta: nothing text-derived).

The first version stored a truncated SHA-256 of each item's text. That is
text-derived: a digest of a templated line is recoverable by enumeration.
The habit line `Sport: 6 von 7 Tagen` has eight possible values of one
number; whoever holds `meta.json` and the template can hash all eight and
read the user's habit count off the match. The same holds for every short,
low-entropy sentence. A hash hides long free text and nothing else, so it
is not a content-free trace.

What `meta.json` may hold is structure the document already exposes to
Tomo's own bookkeeping: the `[[stem]]` source links of each Tomo item —
daily-note dates and note stems, the same values `pass1_counts` and
`target` already name. `link_stems` collects, per Tomo id, the stems of
every `[[…]]` in the item as rendered (`|alias` and `#heading` cut off, so
a link the user decorated is still the same stem), and `review-doc.py
write` stores the map as `pass1_links`. The parser then reads `edited` as:
the item's current link stems are not the list Pass 1 stored.

**Ordered and de-duplicated.** The stems are compared as a list in document
order with repeats dropped, not as a set. A reorder of the sources is an
edit the user made on purpose — `([[2026-03-26]], [[2026-03-24]])` reads
differently from the rendered order — and the landing should say so; a set
would call it unchanged. A link typed twice is still one source, so
duplicates do not make a second edit. The tick state is not part of it:
unticking is not editing, and an unticked item is not landed anyway.

**Presence is `in`, not truthiness.** A habit item renders without links,
so its Pass 1 entry is `[]`. It is still present in `pass1_links`, and a
habit the user gave a link is edited. An id absent from `pass1_links` (an
older `meta.json`, a forged id, a `meta.json` from the digest version with
`pass1_items` and no `pass1_links`) gives `edited: False`: the parser
reports a difference it can see, never one it guesses. `pass1_links` also
gives `deleted` its exact id set.

**The accepted limit.** A retyped text that keeps its links reads as
unedited; so does a changed continuation line. The SDD accepts this: the
links are what the landing resolves (the anchor dates and the note stems
the text points to), the words are the user's either way, and the landed
text is always what the document holds now, edited flag or not. The flag
drives nothing but the count report and the `edited` marker Phase 4 may
show; a false "unedited" costs a marker, a text digest costs the habit
count.

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

## WHY an Item Above the First Heading Is Kept, Too

The rendered document has no checkbox line between the Approved line and
the first group heading, but the user may put one there: a Tomo line cut
and pasted upward, or a note of their own typed under the title. The first
version dropped such a line without a word — no item, no warning, no count
— which is the one thing the parser must never do: a ticked Tomo item
would vanish from `kept` and appear in `deleted`, and the user's own ticked
line would vanish altogether. So a checkbox line before any heading is
parsed like any other and filed under the group key `unknown` — the parser
does not guess which group the user meant, exactly as for a renamed
heading — with the warning `item-outside-group`. `unknown-group` keeps
its meaning (a heading matched no label); the two warnings name two
different things the user did, and the skill's report can say which. The
Approved line is still matched first, so it is never such an item; and a
mangled Approved line that still reads as a checkbox (`- [ ] Approved now`)
is reported as both `approved-line-missing` and `item-outside-group`,
which is what it is: no gate, one stray line.

## WHY the Counts Are Four Numbers

`kept` and `unticked` split Tomo's items by their box; `deleted` is every
Pass 1 id (from `pass1_links`, else the sum of `pass1_counts`) that the
document no longer carries; `added` is the user's ticked items — the ones
that land. An unticked line without an id is a note to self and counts
nowhere. These four are what the engagement KPI and the skill's report need
(ADR-13 rationale), and they carry no text, so they may go to stdout.

## WHY the Result Carries the Text, stdout Does Not, and No File Does (ADR-9)

Phase 4 lands the kept text; the skill reports counts. `ParsedDoc` holds the
items with their verbatim text and continuation lines; `approved_review`
turns it into the ApprovedReview record (kept items only, groups in the
document's rendering order). The record is an in-process value, never a
file (SDD ENTITY ApprovedReview): the vault document is the source of
truth and may change between the parse that reports counts and the
delivery that lands text, so Phase 4 reads the document fresh through Kado
at preview and at deliver time and calls `approved_review` on that — it
always lands what the document holds now, and `tomo-tmp` holds no second
copy of the user's text beyond the files ADR-9 already accounts for.
`public_items` is the same structure without text (`id`, `origin`, `kept`,
`edited`), for stdout. One module produces both so they cannot drift.

## WHY a Broken Frontmatter Is a Warning, Not a Stop

The body is what the user edited and what Pass 2 lands; the frontmatter is
Tomo's bookkeeping. YAML that does not parse, a non-mapping, or a block
without `tomo.doc_type: review` gives `frontmatter-broken` and the body is
still read, so the user is told what to fix without losing their edits.
A document that is not at its path at all is `review-doc.py parse`'s
`not-found` — the user renamed or moved it beyond recognition (SDD Error
Handling); the parser never sees it.

## WHY Sections Are Read Only When meta.json Expects Them (spec 046, ADR-11)

With a template mapping the document carries the user's own sections (spec
046 T4.2): `## <heading> %%sN%%`, the section checkbox `- [x] <label>
%%sN%%` (`- [ ]` when the section is empty), an italic landing line, then the
items with their global `%%tN%%` ids; the "Tomo Review" part starts with the
divider `## <review heading> %%review%%`. `review-doc.py write` stores the
expected keys as `pass1_sections` (`[{key, count, empty}]`) in `meta.json`
only with a mapping; `review_doc_read` hands that list to `parse_document`.

**No `pass1_sections`, no section grammar.** Without the list the parser is
spec 045's, line for line: a heading with `%%s1%%` is a heading that matches
no label (`unknown-group`), a checkbox line with `%%s1%%` is the user's item.
A spec 045 document never carries those ids (Tomo strips `%%` from item
text), so this changes nothing for one; a document whose `meta.json` lost the
list degrades to the renamed-heading case (warned, the section items
unlanded) instead of guessing a mapping. The golden in
`tests/fixtures/046-t4-3-unmapped-parse-golden/` pins the unmapped parse.

**The key on the heading names the section, not the heading text.** The id
is searched anywhere on a `## ` line, so a heading the user retyped keeps its
section, and a user section named like a group label ("Done", "Erledigt")
is the section, never group `done` — ids beat labels (ADR-11). Only an
expected key counts: a heading carrying a key `meta.json` does not list (the
user typed or copied one) is an ordinary heading, read by its label as
before, so an unknown key is `unknown-group` with its items kept under
`unknown` — the same answer as a renamed heading, and no new way to land
text Tomo cannot place. A second heading with the same key continues that
section, like a heading rendered twice (`duplicate-group`). A line carrying
several section ids, heading or checkbox, is named by the first one that is
an expected key, and an id after it changes nothing, expected or not: a
typed or copied `%%s9%%` in front of the rendered `%%s1%%` neither hides the
section nor stops, and `## <heading> %%s1%% %%s3%%` or
`- [x] <label> %%s1%% %%s3%%` stays `s1`'s line while `s3`'s own heading and
checkbox still count. Two expected keys need no rule of their own: an
expected key typed in front of the rendered one names the line, and the
checkbox rules below do the rest. In place of `s1`'s heading,
`## <heading> %%s3%% %%s1%%` is another heading of `s3` (`duplicate-group`,
the items under it are `s3`'s), so `s1`'s heading is gone and its checkbox
stands outside its part; in place of `s1`'s checkbox,
`- [x] <label> %%s3%% %%s1%%` is `s3`'s checkbox under another section, and
`s1` has none. Each key left without its checkbox in its own part stops
(`section-checkbox-missing`): `s1` in the first case, `s1` and `s3` in the
second.

**The divider is a boundary that holds no items.** `%%review%%` on a heading
ends the part before it; a checkbox line between the divider and the next
heading belongs to no group and section, so it is filed under `unknown` with
`item-outside-group`, exactly like a line above the first heading. The
divider's text is not compared (it is the setup's heading).

**The section checkbox is matched before `_ITEM`.** A column-0 checkbox line
carrying an expected `%%sN%%` is the checkbox of section `N`, whatever its
label says — the user may retype the label, and label matching is what a
section named "Done" would break. It is not an item and never counts. It is
valid only inside its own part (after the heading with the same key, before
the next heading) and only once per key; where it stands inside the part
does not matter, so an item the user moved above it still belongs to the
section. A Tomo id typed onto the checkbox line (`- [x] <label> %%s1%%
%%t3%%`) does not make it an item: the line is the checkbox, so `t3` counts
as deleted unless another line still carries it. Everything else is one
stop, `section-checkbox-missing`, for the key it concerns:

- no checkbox line for an expected key — deleted, or broken so it is no
  longer a column-0 checkbox carrying the id (indented, `-[x]`, `%%s1%`,
  the id dropped);
- a checkbox line for a key outside that key's part — under another
  section, under a group, under the divider, above the first heading, or
  with its own heading gone;
- a second checkbox line for a key.

Each is a document whose section state the parser cannot read without
guessing: the column-0 grammar would otherwise file a deleted checkbox's
items under the heading above, or read two boxes of one section that
disagree. Delivering nothing is the only answer that never lands a section
the user dropped (F3-AC6). The stop names the key and the line to restore:
`- [x] <label> %%sN%%` in the document's language (`take` of `review_doc`'s
table; English when the frontmatter is broken), `- [ ]` when Pass 1 rendered
the section empty (`pass1_sections[].empty`), so restoring it puts the
document back exactly as rendered. The in-process record also carries the
document's heading text for the key (without the id; None when the heading
is gone) so the preview can name the section; the public form carries only
the key and the restore line, which hold no user text.

**The landing line is no structure.** It is italic text at column 0; outside
an item it is skipped like the title and the callout, as rendered (it
follows the checkbox, which ends no item and starts none).

## WHY an Unticked Section Drops Everything in It (F3-AC4, F3-AC5, Rule 7)

`ParsedDoc.sections` is `{key: True | False | None}` for every expected key
(ticked, unticked, missing); items in a section carry the key as their
group. An unticked section lands nothing: `approved_review` and
`nothing_to_deliver` leave out every item of a section that is not ticked —
Tomo's and the user's own alike, whatever their boxes say (Rule 7). The
user's own items are the ones without a fresh `%%tN%%` id (`origin: user`,
as spec 045 tells them apart); `section_counts` gives, per expected key,
the box (`ticked`), Tomo's `kept` / `unticked`, the user's ticked items
(`added` — the ones an unticked section drops with it, for
`section-dropped`), and `empty`: ticked but with no ticked item at all (all
unticked or deleted, or never any — `section-empty`). `counts()` keeps its
four spec 045 numbers by the item boxes, so the engagement KPI and the
unmapped report do not change meaning; the preview's wording of the two
notices is `review-instructions.py`'s (Phase 5).

## WHY `SECTION_KEY` Is Public (spec 046 T6.2)

The section key `^s[0-9]{1,3}$` is what `review_mapping.assign_ids` mints
and the config schema allows. The parser reads `pass1_sections` keys with
it, and `review-instructions.py` checks its `--section-choice` /
`--confirm-moved` keys against it. Two patterns drifted: the flags' private
`[A-Za-z0-9_-]+` let keys no configuration can hold through to the planner,
where they surfaced as `choice-invalid` (a "preview again" answer) instead
of a bad invocation. One public definition here, where the key is read from
Tomo's own record, keeps both checks the same. ASCII digits, not `\d`: a
`str` pattern's `\d` takes every script's digits, and no id has them.
