# WHY: lib/review_growth.py

> Rationale for decisions in `tomo/scripts/lib/review_growth.py` (spec 047 T9.3, finding F-R1-3; PRD F2-AC1;
> SDD v1.9 amendment, ADR-4, ADR-6). The module builds the "Vault growth" / "Vault-Wachstum" group of the
> Pass 1 document from the created notes of the read and the digests' growth candidates. No Kado, no model;
> it reads the stage's `digests/` files only.

## WHY the Script Builds the Group (Owner Decision 2026-11-26)

Before spec 047 the model read `read.json`'s growth lists itself, and the document always held the growth group
(PRD F2-AC1). Spec 047 moved the created notes to the digesters, which condense them into growth candidates
`{text, sources, notes}`, and left building the group to the opus proposer. In the live runs T9.2 R1b and R1c
(week 2026-W13) the digester wrote 8 candidates holding all 43 created notes, and the proposer built no growth group
in either run: 33 notes appeared inside section items, 10 nowhere. Its rules let that happen ("leave out a group with
nothing to propose", one place per finding). Listing every created note is data, not judgement, so `review-doc.py
write` builds the group and the proposer no longer proposes it. No created note can be dropped; the opus output is
smaller. The rejected alternative — a stricter proposer rule plus a write check with one rewrite — keeps the model in
a step a script does exactly.

## WHY Grouped by the Digests' Candidates

The digester already read every created note and its links and grouped them into what they are about, in the review
language. That text is the only part of the group that needs a model, and it exists already; the script keeps it and
guarantees completeness. A candidate's notes that are not created notes of the read are ignored (the digest check
`growth-note-outside-unit` refuses them anyway), and only digests of units `condensed.json` marks `passed` and of this
read are used: a failed unit's digest may be malformed or absent, and its notes are not lost — they get items of
their own.

## WHY Merging Across Units Keeps the First Item

A month or quarter has one digest per unit. Units hold disjoint days, so a note normally appears in one candidate;
the script still takes each note at its first candidate (unit order, then digest order) and drops a candidate left
without a note, so no note is listed twice whatever a digester wrote. Merging candidates that "say the same" (the old
proposer rule) is left out: two units' texts about different weeks' notes are two items, and the script cannot judge
sameness of wording.

## WHY a Note in No Candidate Gets Its Link as Its Text

A created note no candidate holds — a day without a daily (the digester has no daily to source it by), a failed
unit, a digester that skipped it — still belongs in the group. The script writes no wording of its own about the
note: the item's text is the note's link (`[[stem]]`) and nothing else, which names the note without inventing a
summary, holds no note content, and reads the same in every language. The creation day's daily is its link when the
day has one the read lists.

## WHY These Links

An item links its notes, then the dailies of their creation days. Before spec 047 a growth item's links came only
from its sources (dailies), so the created notes were named in the text at best; now the notes themselves are the
links, which is what the user checks and what Pass 2 carries to the review note. The dailies are taken from the read's
`Sources` (the same table every item check uses), so a day of a not-condensed unit links no daily, as for any item.
A note's link is its stem, the form every other link uses; when two created notes share a stem the link is the vault
path without `.md`, since `[[stem]]` would then name only one of them in Obsidian.

## WHY This Order

Notes in an item by (creation day, path); items by their first note's creation day, then that note's path. The order
depends only on the notes, not on the digest order, so a re-run with the same notes renders the same group, and the
group reads as the period's timeline.

## WHY a Proposed `growth` Group Is Ignored, Not Refused

`review_doc.MODEL_GROUPS` leaves out `growth`, so `check_items`, the sections' double-placement pass and the carried
coverage never read a proposed growth group, and `review-doc.py write` puts the script's items in its place. The
proposals schema still allows the key (any array): an instance whose proposer file was not yet synced, or a model that
writes the group from habit, should get its review written, not a `proposals-invalid` refusal and a rewrite round for
a group that is discarded anyway. A carried item placed in `growth` is simply not seen, so its ids are reported
`carried-missing` and the rewrite places it by the Carried rules.

## WHY the MOC Lists Are Not in the Group

The pre-047 model could mention changed MOCs from the read's growth lists, and the spec 047 proposer rule named the
context's MOC lists. The script group lists created notes only: the owner decision names the digests' candidates
(text, note links, creation days) as the group's content, and the T8.1 parity oracle
(`tests/test_047_e2e_failures.py`) derives the group from the created notes alone. `context.json` still carries the
counts and MOC lists.

## WHY an Empty Group Behaves as Before

No created note → no item; the renderer shows the group as spec 045/046 did: "nothing found" in an unmapped document,
left out of the mapped one (`keep_empty`).

## WHY a Module of Its Own

`review_doc.py` was at 481 lines against the ≈ 500-line guidance (Constitution L2). The growth group is one seam —
read the digests, merge, order, link — and renders nothing itself, so it lives here and `review-doc.py write` calls it.
