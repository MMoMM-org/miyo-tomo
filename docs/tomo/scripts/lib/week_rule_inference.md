# WHY: lib/week_rule_inference.py

> Rationale for decisions in `tomo/scripts/lib/week_rule_inference.py`.
> The module derives the week rule (first day, minimum days in week 1) from
> the dates the existing weekly notes carry (spec 045, T2.2, ADR-7, F1-AC3,
> F1-AC6). `review-session.py match` calls `infer_rule`; the Kado reads go
> through `lib/review_vault.py`.

## WHY the Inference Is Its Own Module (T2.2 review)

WHY: it is the one part of the setup preview that is an algorithm rather
than a lookup, and the part a reviewer most needs to read on its own. It
takes any object with `frontmatter(path)` and `note(path)` so the unit tests
(`tests/test_week_rule_inference.py`) drive it with a stub and no Kado; the
script-level tests then only pin how `match` uses the verdict. The split
also keeps `review-session.py` under the Constitution's file-size guidance
before T2.3 adds `start`.

## WHY the Week Rule Comes From the Notes' Dates and Never From `.obsidian`

WHY: ADR-7 and F1-AC6. The Obsidian plugin configuration (`.obsidian/
plugins/*/data.json`) says what a plugin would name a new note, not how the
user's existing notes are counted; the two differ whenever the user changed
the setting after the notes were made, or names the notes by hand. The notes
carry their own evidence: `journal-start-date` (or `journal-end-date`, start
= end − 6) in the frontmatter, else the dated links of the day headings. The
script-level test asserts that no path under `.obsidian` is ever requested
from Kado.

Up to eight notes are checked, the most recent by (year, week) of their
names, because the user's current counting is what the next review targets;
an old year counted differently would only make the rule ambiguous and the
dialogue asks then anyway. Eight is the budget: one frontmatter read each,
plus one note read only when the frontmatter holds no date, plus the folder
listing, the template reads and at most one daily-folder probe stay within
Kado's 20 calls per 5 s (CON-7), and the client retries a 429 with
Kado's Retry-After when the window is shared (ADR-4).

## WHY the Inference Intersects Candidate Rules Instead of Reading One Note

WHY: SDD "Week-rule inference": the first day is the weekday of the start
dates; `min_days` is fixed by the notes whose year makes a difference. For a
dated note the module keeps every rule `(start.weekday(), min_days 1..7)`
under which the note's own week number falls on its start date, and
intersects the sets over all dated notes. An empty intersection means the
notes contradict each other (two first days, or a numbering no single rule
reproduces) — `ambiguous`, the skill asks in plain words. A non-empty set
that does not pin `min_days` down (most years cannot tell `min_days` 1 from
4) is still `inferred`: every rule in the set reproduces every dated note, so
the names the user has are the names the setup will produce (F1-AC3). The
module picks 4 (ISO) when the set allows it, else 1 (week 1 holds 1 January),
else the smallest — the two conventions users actually set, preferred over
an arbitrary middle value. No dated note at all is `ambiguous` as well: a
rule guessed from nothing would target the wrong note silently (PRD risk 1).
No candidate at all (no name that parses) is `default`: there is nothing to
compare with, the script proposes ISO and says so (F1-AC4).

## WHY Candidates Are Parsed Under ISO

WHY: the rule is what the inference is looking for, so the names cannot be
parsed under it yet. ISO is used only to read the year and the week number
out of the name; `rules_fitting` then tests every rule on the start date the
note carries, and ISO itself is kept only when the note's dates support it.
The format is the proposal's name format, so a format the user gave with
`--format` changes which names count as candidates.

## WHY Two Notes With the Same Stem Are Both Checked

WHY: the owner's vault keeps older notes in year subfolders, and a copy of
the current year's note can sit next to the archived one. Keyed by stem, the
second path vanished: `notes_checked` undercounted, a copy whose dates
contradict the other went unseen, and the listing in the preview showed one
note where two exist. The candidates are therefore `(stem, path)` pairs, and
`Checked` records the path, so the script matches each note on its own
dates and the evidence lists every note by name — a duplicated stem appears
once per note.
