# WHY: lib/review_growth.py

> Rationale for decisions in `tomo/scripts/lib/review_growth.py` (spec 047 T9.3, findings F-R1-3, F-R1-4 and F-R3-1;
> PRD F2-AC1; SDD v1.9 and v1.10 amendments, ADR-4, ADR-6). The module builds the "Vault growth" / "Vault-Wachstum" group of the
> Pass 1 document from the created notes of the read and the digests' growth candidates. No Kado, no model;
> it reads the stage's `digests/` files only.

## WHY the Script Builds the Group (Owner Decision 2026-11-26)

Before spec 047 the model read `read.json`'s growth lists itself, and the document always held the growth group
(PRD F2-AC1). Spec 047 moved the created notes to the digesters, which condense them into growth candidates
`{text, sources, notes}`, and left building the group to the opus proposer. In the live runs T9.2 R1b and R1c
(week 2026-W13) the digester wrote 8 candidates holding all 43 created notes, and the proposer built no growth group
in either run: 33 notes appeared inside section items, 10 nowhere. Its rules let that happen ("leave out a group with
nothing to propose", one place per finding). Listing every created note is data, not judgement, so `review-doc.py
write` builds the group and the proposer no longer proposes it. No created note can be dropped; the proposer's output is
smaller. The rejected alternative — a stricter proposer rule plus a write check with one rewrite — keeps the model in
a step a script does exactly.

## WHY Grouped by the Digests' Candidates

The digester already read every created note and its links and grouped them into what they are about, in the review
language. That text is the only part of the group that needs a model, and it exists already; the script keeps it and
guarantees completeness. A candidate's notes that are not created notes of the read are ignored (the digest check
`growth-note-outside-unit` refuses them anyway), and only digests of units `condensed.json` marks `passed` and of this
read are used: a failed unit's digest may be malformed or absent, and its notes are not lost — they are counted in
their folder's item.

## WHY Merging Across Units Keeps the First Item

A month or quarter has one digest per unit. Units hold disjoint days, so a note normally appears in one candidate;
the script still takes each note at its first candidate (unit order, then digest order) and drops a candidate left
without a note, so no note is listed twice whatever a digester wrote. Merging candidates that "say the same" (the old
proposer rule) is left out: two units' texts about different weeks' notes are two items, and the script cannot judge
sameness of wording.

## WHY Notes in No Candidate Are Counted per Folder (Owner Decision 2026-11-27, F-R3-1)

A created note no candidate holds — a day without a daily (the digester has no daily to source it by), a failed
unit, a digester that skipped it — still belongs in the group. F-R1-3 gave each such note an item of its own whose
text was its link (`[[stem]]`). In live walk R3 (quarter 2026-Q1) the read held 746 created notes; a digest covers at
most 150 notes per unit, so the group came out at 526 items, 460 of them bare single-note links — a list no one
reviews. The owner replaced that rule for uncovered notes: one item per folder, with a count and no links.

- **The folder is the note's parent folder path in the vault**, the whole path (`Projects/Sub`), not its top
  folder: the path is what the user files by, and two subfolders of one parent are two places. A note at the top of
  the vault has no folder; its item uses the label word `growth_root` ("vault root" / "Vault-Wurzel") in place of a
  path, so the line never starts with a bare colon.
- **Text, not links.** The item's text is a label of `review_doc._LABELS` (`growth_folder_one` for one note,
  `growth_folder_many` with `{n}` for more, both with `{folder}`), so the wording sits beside "MOCs changed" and reads
  in the review language: "Projects: 3 new notes" / "Projects: 3 neue Notizen", singular "1 new note" / "1 neue
  Notiz". It names no note and holds no note text (CON-3): a folder path, a count and label words. With no links, a
  folder item carries no creation day and so no daily either; renderer, parse and deliver already handle an item
  with `links: []` (the habits items have them), and a test walks one through write → parse → deliver.
- **Order.** Candidate items keep their order (first note's creation day, then path); the folder items follow all
  of them, in folder path order, then the MOC items. A folder has no single day, so it cannot join the timeline;
  sorting by path keeps the group the same for the same notes.
- **No folder item when every note is covered.** A period whose candidates hold all its created notes renders as
  before; nothing in the candidate or MOC items changed.

Later presentation work on the group (how candidates and folders read in a long period) is tracked in #274.

## WHY These Links

An item links its notes, then the dailies of their creation days. Before spec 047 a growth item's links came only
from its sources (dailies), so the created notes were named in the text at best; now the notes themselves are the
links, which is what the user checks and what Pass 2 carries to the review note. The dailies are taken from the read's
`Sources` (the same table every item check uses), so a day of a not-condensed unit links no daily, as for any item.
A note's link is its stem, the form every other link uses; when two created notes share a stem the link is the vault
path without `.md`, since `[[stem]]` would then name only one of them in Obsidian.

## WHY This Order

Notes in an item by (creation day, path); candidate items by their first note's creation day, then that note's path. The order
depends only on the notes, not on the digest order, so a re-run with the same notes renders the same group, and the
group reads as the period's timeline.

## WHY a Proposed `growth` Group Is Ignored, Not Refused

`review_doc.MODEL_GROUPS` leaves out `growth`, so `check_items`, the sections' double-placement pass and the carried
coverage never read a proposed growth group, and `review-doc.py write` puts the script's items in its place. The
proposals schema still allows the key (any array): an instance whose proposer file was not yet synced, or a model that
writes the group from habit, should get its review written, not a `proposals-invalid` refusal and a rewrite round for
a group that is discarded anyway. A carried item placed in `growth` is simply not seen, so its ids are reported
`carried-missing` and the rewrite places it by the Carried rules.

## WHY the MOC Changes Are in the Group (Owner Decision 2026-11-26, F-R1-4)

The first script group (F-R1-3) listed created notes only, so the MOC changes the pre-047 model could mention from
the read's growth lists appeared nowhere. The owner decided the group also shows them, as links. Their data is
already in the read: `review_period._growth` computes `mocs_changed` (MOCs in the configured MOC folders modified in
the period) and `mocs_linked_by_new` (MOCs a created note links), both sorted vault paths; `context.json` carries them
and `review_stage.load` returns them under `read["growth"]`. No digest and no model is involved.

- **Two items at most, not one per MOC.** A changed MOC says nothing about itself the script could word; one item per
  list keeps the group short in a quarter with many MOC edits and reads as one line per kind of change. The text is
  a label word in the review language (`growth_mocs_changed`, `growth_mocs_linked` in `review_doc._LABELS`, beside
  every other label; `review_doc.py` stays under its size limit), the links are the MOCs. Nothing of a MOC's text is
  read or written (CON-3): the document holds links only, stdout and `meta.json` no more than before.
- **Each MOC once.** A MOC in both lists is linked under "MOCs changed" only, the first list; "MOCs newly linked" holds
  the rest and is left out when nothing remains. A MOC that is itself a created note is already in the group (in a
  candidate item or its folder's count), so it is in no MOC item: every note the group names is named once.
- **Links, no dailies.** A MOC item's links are the MOCs themselves. The read keeps no day for a MOC change (only the
  path), and a newly-linked MOC's day would be the linking note's creation day, which that note's candidate item already
  links (a folder item links no daily). Like the created-note items, MOC items bypass `check_items`, so no period source is required.
- **Link rule.** The created notes' rule — the stem, the path without `.md` when the stem is not unique — is applied
  over the created notes and the MOCs together, since a MOC and a created note of one stem would otherwise both
  render as the same `[[stem]]`.
- **Order.** After every created-note item (candidate items, then folder items), changed before newly linked, links
  in path order: fixed by the paths alone, whatever order the lists arrive in.

## WHY an Empty Group Behaves as Before

No created note and no MOC change → no item; the renderer shows the group as spec 045/046 did: "nothing found" in
an unmapped document, left out of the mapped one (`keep_empty`). MOC changes alone are growth too, so a period with
them and no created note renders the group with its MOC items.

## WHY a Module of Its Own

`review_doc.py` was at 481 lines against the ≈ 500-line guidance (Constitution L2). The growth group is one seam —
read the digests, merge, order, link — and renders nothing itself, so it lives here and `review-doc.py write` calls it.
