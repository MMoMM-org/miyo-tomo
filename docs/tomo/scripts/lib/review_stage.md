# WHY: lib/review_stage.py

> Rationale for decisions in `tomo/scripts/lib/review_stage.py`.
> The module owns the stage folder a `/review` read rests in (spec 047, T2.3;
> PRD F1-AC2, F2-AC3, F6-AC5, F7-AC1; SDD ADR-1, ADR-2, ADR-3, ADR-10, "Data
> Storage Changes"): writing `days/`, `growth/`, `children/`, `previous/`,
> `context.json` (+ parts), `weeks.json` and `manifest.json`; the line-broken
> encoding and the 32 KB ceiling measured on it; the re-cut of an oversized
> day and the clip of an oversized child note; `load` back into the one dict
> `review-doc.py` consumes; `discard`; the continue check and
> `sections_digest`. It replaces `lib/review_read_parts.py` (spec 046 T3.4),
> whose history is kept at the end of this page.

## WHY Files per Day, Not per Month

WHY: ADR-1 and the per-call Read limit. Spec 046 split a quarter into
`read-index.json` and three month parts of up to ≈ 243 KB each. The live walk
of 2026-Q1 still left days unread (spec 047 PRD): one model context holding a
whole month is the problem, not just the file size. Spec 047 condenses the
period per unit (a week, `lib/review_weeks.py`), and a digester reads only
its unit's files; per-day files let a unit name exactly its days, whatever
week rule cuts them. A day file holds the `read_day` entry unchanged plus the
`read_id`, so a quarter's day file equals the week read's (F1-AC2): the same
reader, no kind-specific trimming.

## WHY Growth Is Filed by Creation Day

WHY: ADR-1 (amended, T1.5): `growth.created` measured 746 notes ≈ 157.7 KB
indented, four times the ceiling. `review_period` stamps each created entry
with its local creation `day`; the stage files the entries `{path, links}`
of a day, sorted by path, in `growth/<date>.json`, so a unit's growth files
are those of its days and need no packing of their own. A day over the
ceiling overflows into `growth/<date>-<n>.json` (n = 2, 3, …, `part: n` on
the overflow files only) at entry boundaries: an entry is never cut, never
dropped. An entry without a `day` goes to the period's first day (the same
rule `review_period.created_day` applies). `context.json` keeps only
`created_count` and the two MOC lists; `load` rebuilds `growth.created`
(the `day` back from the file's `date`, sorted by path) equal to the read's.

## WHY the Report Lives Only in the Manifest

WHY: ADR-1 (amended): the report measured 39.5 KB and is for scripts — the
not-read and top lines `review-doc.py` renders. No agent reads
`manifest.json`, and no agent-read file carries the report, so a digester
never spends its budget on paths and states.

## WHY Line-Broken UTF-8 With Texts as Line Arrays

WHY: ADR-2 (owner, 2026-11-23). The Read tool cuts long lines, and compact
one-line JSON is one long line. Every agent-read file is
`json.dumps(indent=1, ensure_ascii=False)`: UTF-8 so an umlaut costs two bytes
instead of a six-byte escape, and each section, linked-note, child-note and
previous-note text an array of its lines. `load` joins them back with `\n`;
the split is `str.split("\n")`, not `splitlines`, so the join is exact
(a trailing newline or a `\r` survives). The ceiling is measured in UTF-8
bytes of exactly this text: `size(encode(doc))` is the one measure, and the
written file is that text.

### WHY a Line Longer Than 1,000 Characters Becomes Pieces

WHY: the ceiling test's "no line over 2,000 characters". A text line can be
a paragraph without breaks; as one array element it is one file line. Such a
line is stored as a nested array of 1,000-character pieces, which `load`
joins with `""`. 1,000 leaves room for the indentation, the quotes and the
escapes of `"` and `\` within the 2,000. Only texts are pieced: a link target
or a task text is a value the scripts match on, and is never that long in a
vault (the scaled quarter's index-heavy shape pads them to 2–3 KB as filler,
which is why the line check runs on the children-heavy shape only).

## WHY the Manifest Is Written Last, and Compact

WHY: ADR-3. `write` first discards every earlier file of the stage (F6-AC5),
then writes the content files, the manifest last. A run that dies before the
manifest leaves a stage `load` calls `StageMissing`, exactly as if no read
happened — never a mix of two reads. Every file carries the `read_id`; `load`
raises `StageStale` on any file (and on `condensed.json`) of another read.
The manifest is script-only and stays compact and ASCII-escaped.
`manifest.child_labels` names the child levels the read carried (`weekly`,
`monthly`) so `load` gives back an empty `weekly: []` when a level was read
but found nothing — `files.children` alone (names) cannot say that.

## WHY Over-Ceiling Files Are Cut Through `review_day.cut_at_boundary`

WHY: ADR-2, one cutter. A day file can exceed 32,768 B only when the user
raised `max_chars_per_day` (the largest measured day is 8,303 B). The day's
sections and linked texts become the cutter's units (sections first, then
linked notes, as `read_day` orders them) and are re-cut with a smaller limit:
the room left after the non-text part (tasks, links, fields), times 1.0, 0.8,
0.6 — three tries, because line arrays cost about 7 bytes per line on top of
the characters the cutter counts. Every limit is clamped to ≥ 1: the cutter
slices `text[:max_chars]`, and a 0 or negative limit would slice wrongly
(T2.1 review). When three tries still do not fit (the non-text part alone is
large), the hard cut keeps the first section alone, cut at the last limit.
The day is named `partly_read` and its `has_content` recomputed from what was
kept (`review_day.has_content`), so `takes_part` sees the file as written.
The stage does not re-run `read_day`: it holds the entry, not the daily
texts, and the cut only removes whole trailing units (or the end of the
first), which is what a smaller `max_chars_per_day` would have kept.

A child note over the ceiling is clipped the same way at a heading boundary:
its own-section texts first, then its day blocks, each a unit; the file
carries `clipped: true`. `load` keeps `clipped` only when true, so an
unclipped read loads equal to `read_period`'s entry.

## WHY Context Lists Overflow Into Parts

WHY: ADR-2. `context.json` holds the dateless rest of the read: the
section definitions, open tasks, the link-difference lists over the whole
period, growth counts and MOC lists, and `fields` — every day's tracker
values (F2-AC3), so the proposer words analysis rows without day files.
It measured well under the ceiling once growth and the report left it, but
open tasks and link lists grow with the vault. Over the ceiling, every list
item (and every `fields` day) moves into `context-<n>.json` parts (n = 2, …),
each ≤ the ceiling and named in `context.json`'s `parts`; `load` merges them
back in order (lists extended, dicts merged).

## WHY `weeks.json` Names Its Files

WHY: SDD weeks.json data model. A unit's weight is its day files plus its
growth files as written (indented bytes), and `review_weeks.units` packs on
that; each unit then names its `day_files`, `growth_files` and its
`weekly_note` (the `children/weekly-<week>.json` of its week, `null` without
one), so `review-digest.py plan` hands a digester exactly its files.
`takes_part` is `review_weeks.takes_part` with the day's created count.

## WHY `sections_digest` and the Continue Check

WHY: ADR-3. A stored read is continued only when nothing it depends on
changed: the stage layout, the period and its kind, and the section mapping.
`sections_digest` is `sha256:` over the canonical JSON (sorted keys, compact,
ASCII) of the section definitions `review-read.py` builds, so key order does
not matter and any mapping row change (heading, cap, keywords, placement as
`analysis`) does; no mapping is `none`. Other setup changes do not invalidate
a stored read (ADR-3 trade-off; the PRD names the mapping only).

## WHY Discard Keeps Only `meta.json` and `payloads.json`

WHY: ADR-10, F7-AC1. Every other file of the stage may hold note content:
`days/`, `growth/`, `children/`, `previous/`, `digests/`, `context*.json`,
`weeks.json`, `carryover.json`, `proposals.json`, `condensed.json`,
`manifest.json`, and any legacy `read*.json` from spec 046. The manifest goes
first, so a discard that dies half-way leaves a stage `load` calls missing.
`meta.json` and `payloads.json` belong to the written document
(`review-doc.py`, `review-instructions.py`).

## History: `lib/review_read_parts.py` (spec 046 T3.4, ADR-7)

The stage before spec 047 was one compact, ASCII-escaped `read.json` for a
week or a month, and for a quarter `read-index.json` (every key but `days`,
`weekly`, `monthly`, plus `parts`) and one `read-<YYYY-MM>.json` per month.
The 2026-Q1 measurement (2026-11-15) was 710,106 bytes as one file — almost
three times the 256 KB Read limit — so the month was the seam: a day went to
its date's month, a monthly note to its month, a weekly note to the month
holding most of its in-quarter days (ties to the earlier month). The index
listed all three months in order, was written last, and the loader refused
both layouts at once, unsafe or repeated part names, and parts of another
month. What carried over into this module: the stage is cleared before a
write, the file that names the others is written last (a crash looks like no
read), names from a file on disk are checked with `fullmatch` before they are
opened, and the encoding lives next to the writer so the measured and the
written bytes are the same. What did not: one model reading a whole month —
the spec 046 walk showed that a model holding ≈ 240 KB still skipped days.
