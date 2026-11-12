# WHY: lib/review_md.py

> Rationale for decisions in `tomo/scripts/lib/review_md.py`.
> The module owns the markdown structure a `/review` read works on (spec
> 045, T3.2; PRD F3-AC1, F3-AC2, F3-AC4): frontmatter and body, code fences,
> headings and the span of their sections, thematic breaks and the
> navigation block that trails one, the query and embed fences to drop,
> navigation-only lines, `[!METADATA]` callouts, and the exact-token test
> that decides whether a note name carries a day. It knows no setting and
> no day semantics beyond a name token; `review_day.py` applies these rules
> to one daily and `review_period.py` never calls this module directly.
> No Kado, no model, no file I/O.

## WHY a Module of Its Own

`review_day.py` had grown to 490 lines, and about a third of it was
markdown mechanics that never look at a setting: where a section ends,
what is inside a fence, which line is navigation. The code-review of T3.2
asked for the split, and the seam is the natural one — everything here
takes lines and returns lines, masks or ranges; everything in `review_day`
takes settings and returns the day's entry. The two modules stay under
~400 lines each (MiYo constitution L2: files of dense logic refactor at
~300–500 LOC), and a plain-vault reading question (how does `---` behave?)
can be answered and tested without a day fixture. `review_md` is the
lower layer: it imports nothing from `review_day`, and the public seam of
`review_day` (`read_day`, `yesterday_fields`, `attribute_yesterday`,
`day_settings`, `render_day`, `task_note_tasks`, `done_in_period`,
`yesterday_field_names`) is unchanged by the split.

## WHY the Tasks Done Marker Is One Pattern Here

`DONE_MARK_RE` (`\s*✅\s*(YYYY-MM-DD)`) is the ` ✅ YYYY-MM-DD` the
Obsidian Tasks plugin appends to a checkbox line when its box is ticked. Two
readers of `/review` meet it: `review_day` reads the done date off a daily's
tasks and drops the marker from the task text (anywhere on the line,
`search` + `sub`), and `review_doc_parse` reads the review document the
user ticked in Obsidian — with the plugin installed, `- [x] Approved`
became `- [x] Approved ✅ 2026-11-12` in the Phase 6 live walk and the
gate was "missing" (spec 045 Phase 6 fix round). The parser needs the
trailing form only (`DONE_MARK_RE.pattern + r"\s*$"`), so it anchors the
shared pattern rather than keeping a second regex that could drift from the
first (one token, one definition). The pattern lives here, not in
`review_day`, because `review_doc_parse` must not import the day reader —
its settings, its period rules — for one markdown token; `review_md` is the
lower layer both already sit on (the `review_day` import is unchanged in
meaning, only in origin).

Only the done marker is known. The plugin's other fields (`📅` due, `⏳`
scheduled, `🛫` start, `➕` created, `🔁` recurrence) are typed by the user
on purpose, never added by a tick, so they stay the user's text wherever
they appear; `❌` cancelled goes with a `[-]` box, which is no tick.

## WHY a Section Spans Its Subsections

A section runs from its heading to the next heading of the same or a
higher level, so "Habit" carries its "### Yesterday" and "### Today"
subsections and their fields. Lines inside a code fence are never headings
(the `quoth` block has `path:` lines, not `#` lines, but a `dataviewjs`
block may print `#`), and a `---` inside a fence is never a thematic
break. Heading text is returned exactly as written, stripped of trailing
closing hashes; whether it matches a setting (exact or prefix) is
`review_day`'s decision.

## WHY a Thematic Break Ends Nothing by Itself

F3-AC4 and the plain-vault persona: a user without a template writes
`---` as a separator between parts of the day — morning, then a rule, then
the evening — and everything after the rule is still the day's words. The
first version of `review_day` had a rule close its section outright,
because the owner's daily ends with `---` and a `[!METADATA]` callout of
navigation links (week, month, quarter, year, yesterday) that by the
heading rule alone belonged to "End of the Day", the last configured
section, and leaked into `dailies_not_in_weekly` as "things the day
held". That fix stopped the leak and silently dropped every plain-vault
line after a separator — in a kept section and in the whole-body `text`
fallback alike. The coordinator checked the test vault's real dailies: after
a `---` there is always a heading or a `> [!METADATA]` callout, never
prose. So the rule is now the narrow one that both structures need:

- a `---` ends nothing. A kept section runs to the next heading as above,
  and the lines after a rule stay in it (or under `text` in the fallback);
- the rule line itself is dropped — it is typography, not words;
- only the *trailing navigation block* behind a rule is dropped, read line
  by line from the rule on: blank lines are skipped, a `[!METADATA]`
  callout block goes (every quoted line from its title on), a callout made
  only of links goes (a `[!type]` title without text and quoted lines
  holding nothing but wiki links and separators, dated or not — a block of
  bare links is navigation whatever it links), and a navigation-only line
  goes (`is_navigation` below, which needs dated targets). The first line
  that is none of these ends the block and stays, and so does everything
  after it: `---`, a navigation line, then prose loses the navigation line
  and keeps the prose.

Blank lines are skipped rather than ending the block because the owner's
template puts an empty line between the rule and the callout; a heading
ends the block because it is not navigation. The same mask is used by the
kept-section read, the `text` fallback and the linked-note read, so the
three paths cannot drift again — the leak above came from one path having
the rule and another not.

## WHY a Break Does End a Dropped Section

`ranges(..., cut_at_rule=True)` cuts a section at its first thematic
break; `review_day` asks for that only for the ranges it *drops* — a
`skip_sections` heading in the daily and an other-day heading in a linked
note — never for a section it keeps. The two errors are not symmetric. A
kept section that runs one line too far shows the model a navigation line
it was told to ignore; a dropped section that runs one line too far
swallows the day's own words, and nothing in the result says so. A skip
heading names other-day content ("On This Day... last year"), and a user
who writes `---` under it and then prose has marked where the borrowed
content ends and their own writing resumes; so the skip stops at the rule
and the prose belongs to no section — it is read in the `text` fallback and
dropped when a configured section is found, like any line outside the
configured headings. The heading rule alone would read that prose as last
year's, which was the reviewer's case (c).

## WHY a Day Token Is Matched on Digit Boundaries

`has_token(target, token)` decides whether a note name carries the day
(`DP-2026-03-26` for `2026-03-26`). A substring test was wrong for every
format without zero padding: with `D.M.YYYY`, the token of 6 March 2026 is
`6.3.2026`, which is a substring of `16.3.2026` and `26.3.2026`, so the
reader of the 6th would have read the 16th's planner as a same-day note.
The token must therefore sit on digit boundaries — no digit directly
before or after it (`(?<!\d)…(?!\d)`); letters and separators around it
(`DP-`, `Plan `) still match. The same test is used for the same-day
link collection in `review_day` and for the token inside
`is_navigation`, so the two cannot disagree on what "same day" means.

## WHY Dataview, Inline Queries and Embed Blocks Are Dropped

F3-AC2: the content comes from the embedded note itself, never from a
plugin's rendering. A `dataview`/`dataviewjs` fence is a query, not a
record; an inline `` `=this.yesterday.to-improve` `` or `` `$=…` `` is the
same thing one line long; a `quoth` or `dynbedded` fence is an embed whose
target `review_day` already collected and reads as a note of its own.
`cleaned` removes all four from the kept text; nothing is ever executed.
Other fences (a `calendar-nav` block, a `meta-bind-button`) stay as text —
they are skeleton for `review_day`'s content test and the model is told
nothing about them.

## WHY Navigation-Only Lines and METADATA Callouts Are Recognised Here

A line is navigation-only (`is_navigation`) when nothing but wiki links to
dated notes remains once the arrows and separators (`<==`, `==>`, `->`,
`|`, `·`, dashes) and, when the caller gives them, the day's own ISO date
and name token are removed — the journal's `[[5J-2026-03-25]] <==
2026-03-26 ==> [[5J-2026-03-27]]` line, the planner's yesterday/tomorrow
header, a plain daily's `[[2026-03-25]] | [[2026-03-27]]` footer. A target
is dated when it holds an ISO date, a four-digit year or the day token.
`day` and `token` are optional because the daily's own parse
(`review_day._parse_daily`) runs without a date — `yesterday_fields` reads
a text whose date the caller never computes — and the trailing-block rule
still has to recognise a `[[2026-03-25]] | [[2026-03-27]]` footer there; a
line that only names the day's own date without links is not navigation
either way. A line that links an undated note (`[[Assessment]]`) is a
reference the user wrote and stays.

`metadata_mask` marks a `> [!METADATA]` callout block, the quoted lines
from its title on; the owner's journal keeps the question of the day there
and the planner its links, neither being the day's words. The same block
is the one the trailing-block rule drops at the end of a daily.
