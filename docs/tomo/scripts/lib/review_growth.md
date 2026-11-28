# WHY: lib/review_growth.py

> Rationale for decisions in `tomo/scripts/lib/review_growth.py` (spec 047 T9.3, findings F-R1-3, F-R1-4, F-R3-1 and
> F-R3b-4; PRD F2-AC1; SDD v1.9 and v1.10 amendments, ADR-4, ADR-6; issue #274). The module builds the "Vault growth" /
> "Vault-Wachstum" group of the Pass 1 document from the created notes and the MOC lists of the read. No Kado, no
> model, no file read.

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

## WHY One Item per Folder (Owner Decision 2026-11-28, F-R3b-4, #274)

Until F-R3b-4 the group took the digests' growth candidates as items — the digester's text, the candidate's created
notes as links, then the daily of each creation day — and counted per folder only the created notes no candidate held
(F-R3-1: before it each such note was an item of its own, and live walk R3's 746 created notes gave 526 items, 460
of them bare single-note links). In live walk R3b (quarter 2026-Q1) that gave 65 candidate items, each ending in a creation-day daily link
that read like one more created note, and a count line "Calendar/301 Daily: 44 neue Notizen" that counted only the
dailies no candidate covered, so the number was neither the folder's growth nor the period's. The owner found the
group unreadable and replaced it: the created notes are grouped by their parent folder, and nothing else decides the
items. The candidates are gone from the digester and the digest schema (see
[review-digester](../../dot_claude/agents/review-digester.md)), so `group` takes the read alone and reads no stage
file.

- **The folder is the note's parent folder path in the vault**, the whole path (`Projects/Sub`), not its top
  folder: the path is what the user files by, and two subfolders of one parent are two places. A note at the top of
  the vault has no folder; its item uses the label word `growth_root` ("vault root" / "Vault-Wurzel") in place of a
  path, so a line never starts with a bare colon.
- **Calendar folders are counted, never linked.** A folder at or below the calendar base path holds periodic notes
  (dailies, weeklies, meeting notes filed by date). Listing each of them as a link says nothing the period does not
  already say, and a quarter has some 90 dailies. So such a folder is one count item over all its created notes:
  "Calendar/301 Daily: 44 new notes". The base path is `concepts.calendar.base_path` of the vault config, else the
  profile's `concept_defaults.calendar.base_path` (layer precedence; `review_config.calendar_base`, carried on
  `ReviewSetup.calendar_base`, which `review-doc.py write` passes in). The match is by folder, not by string prefix:
  `Calendar/` covers `Calendar` and `Calendar/Sub` but not `Calendarium`; surrounding blanks and slashes of the
  configured value are ignored, since vault-config values carry stray trailing slashes and blanks.
- **Other folders are linked up to `LINKS_MAX` (10) notes.** A folder with at most ten created notes is one item
  whose text is the folder path and whose links are the notes, rendered like the MOC items: "Projects (\[\[A]],
  \[\[B]])". Ten links still read as one line and let the user open each note; more turn the line into a list no one
  reviews, so a folder over ten is counted like a calendar folder. Ten is the owner's number, a named constant so the
  one place to change it is obvious.
- **No calendar base path → every folder follows the link rule.** Without a configured calendar there is no folder
  Tomo can call periodic; a dailies folder with more than ten notes is still counted by the size rule.
- **The count text.** A count item's text is a label of `review_doc._LABELS` (`growth_folder_one` for one note,
  `growth_folder_many` with `{n}` for more, both with `{folder}`), so the wording sits beside "MOCs changed" and
  reads in the review language: "Projects: 3 new notes" / "Projects: 3 neue Notizen", singular "1 new note" /
  "1 neue Notiz". It names no note and holds no note text (CON-3): a folder path, a count and label words.
  Renderer, parse and deliver handle an item with `links: []` (the habits items have them), and a test walks a count
  item and a link item through write → parse → deliver.
- **No daily links.** A creation day's daily was linked so the item had a day source; the group bypasses
  `check_items`, so no source is required, and the daily read as a duplicate note. Dropping it also drops the
  coupling to the read's `Sources` (a not-condensed unit's day).
- **Order.** One ordering for every folder item, calendar or not: folder path order, then the MOC items. A folder has
  no single day, so a timeline cannot hold it; path order keeps the group the same for the same notes. Links within a
  folder are in path order for the same reason.

## WHY These Links

A note's link is its stem, the form every other link uses; when two created notes (or a created note and a MOC)
share a stem the link is the vault path without `.md`, since `[[stem]]` would then name only one of them in
Obsidian. The links are what the user checks and what Pass 2 carries to the review note.

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
  folder item), so it is in no MOC item: every note the group names is named once.
- **Links, no dailies.** A MOC item's links are the MOCs themselves. The read keeps no day for a MOC change (only the
  path), and no item of the group links a daily. Like the folder items, MOC items bypass `check_items`, so no period
  source is required.
- **Link rule.** The created notes' rule — the stem, the path without `.md` when the stem is not unique — is applied
  over the created notes and the MOCs together, since a MOC and a created note of one stem would otherwise both
  render as the same `[[stem]]`.
- **Order.** After every folder item, changed before newly linked, links in path order: fixed by the paths alone,
  whatever order the lists arrive in.

## WHY an Empty Group Behaves as Before

No created note and no MOC change → no item; the renderer shows the group as spec 045/046 did: "nothing found" in
an unmapped document, left out of the mapped one (`keep_empty`). MOC changes alone are growth too, so a period with
them and no created note renders the group with its MOC items.

## WHY a Module of Its Own

`review_doc.py` was at 481 lines against the ≈ 500-line guidance (Constitution L2). The growth group is one seam —
group by folder, order, link — and renders nothing itself, so it lives here and `review-doc.py write` calls it.
