# WHY: review-digester

> Rationale for decisions in `tomo/dot_claude/agents/review-digester.md`.
> Spec 047 (issue #270, `docs/XDD/specs/047-review-chunked-read/`); ADR and F-AC ids refer to its
> `solution.md` and `requirements.md`. The agent condenses ONE unit of a `/review` read — a week, or part of one —
> into `digests/<unit>.json`. The job it gets is planned and checked by `review-digest.py`
> ([review-digest](../../scripts/review-digest.md)); the skill that dispatches it is
> [periodic-review](../skills/periodic-review.md).

## WHY the Agent Exists at All

WHY: the spec 046 quarter read was one 717 KB set of files, about 390k tokens; the Read tool stops at 25k tokens per
call, so the main session fell back to `grep` over parts of the files and once started four `general-purpose`
subagents of its own ($2.83), and the quarter was reviewed on a partial read (046 close-out, #270). F1-AC1 forbids
that: every day of the period takes part with everything read of it. The fix is to cut the period into units that fit
one agent (`lib/review_weeks.py`: ≤ 128 KB of day files and growth files, a heavy week split into `<week>a`,
`<week>b`…) and condense each unit into a small digest; the proposer then sees the whole period through the digests.
The digester is the step that reads every day file, so no day is ever sampled.

## WHY One Unit per Run

WHY: one unit is what fits one context comfortably (each file ≤ 32,768 B indented, the unit ≤ 128 KB) and what
`review-digest.py check` can judge on its own: the digest's `days` must equal the unit's taking-part days, every source
must lie inside the unit (`source-outside-unit`, `theme-day-outside-unit`, `growth-note-outside-unit`). A digester that
saw several units would blur those checks, and one failed run would cost several weeks. One unit per run also lets
the skill send all units of a quarter in one message and retry exactly the unit that failed.

## WHY `haiku`

WHY: ADR-7. The digester records what the days say — what got done, what stayed open, what recurs, what the weekly
note holds, which notes were created on which day — without judging across the period. The judgement-heavy work
(themes over all days, open against later weeks, one place per finding, carried marks) is the proposer's. Recording
on ≤ ~120 KB of input is the cheap-model job; a quarter runs 14–16 of them, so the model choice multiplies.

## WHY No Judgement

WHY: the digest is the proposer's only view of a unit's days, so anything the digester decides away is lost for good.
It therefore keeps findings rather than ranking or merging them across weeks, and a theme that shows on one day of its
unit is kept (the two-day rule is applied by the proposer over the whole period, F1-AC3; the schema allows a single
day here, see [review-digest](../../scripts/review-digest.md) "WHY a Single-Day Theme Is Allowed"). Each entry keeps its
day sources, because the document's every item needs a link to a day of the period and the proposer can only cite
what a digest names.

## WHY the Weekly Note Goes to `child_notes`

WHY: a month's or quarter's child marks (`weekly_only` / `not_in_weekly`) compare the weekly notes against the days
(F2-AC3). The digester reads its unit's weekly note together with the unit's days and writes what the note says into
`child_notes` with the note's stem as source, so the proposer can compare over the whole period without reading the
weekly notes itself. A quarter's monthly notes are not unit material; they go to the proposer directly
(`review_period.CHILD`).

## WHY Growth Candidates (v1.2)

WHY: owner deviation after the T1.5 measurement: a quarter's created notes measured about 157.7 KB indented, four
times the file ceiling, so the growth list cannot travel whole to the proposer. The digester reads its unit's
`growth/<date>.json` files and writes `growth` candidates `{text, sources, notes}`: the creation days as sources (the
day-source rule `review_doc.check_item` already applies to the growth group) and the created notes' paths in `notes`,
which is what the "Vault growth" group links. `check` refuses a candidate whose notes are not the unit's created notes
or whose sources are not their creation days.

## WHY the Cap

WHY: ADR-2. The byte cap comes with the job (`cap_bytes`, `min(8,192, 114,688 // units)`: 8 KB for 14 units, 7 KB for
16), so all digests together stay ≤ 112 KB and the proposer's input stays bounded; the item caps of the schema keep a
digest near it. Over the cap is `digest-too-large`, a failed attempt. The agent is told the number because only the
script knows how many units the period has.

## WHY the Cap Leaves Out the Growth Notes and the Sources (T9.3)

WHY: paths cannot be condensed — a created note's path and a day's daily path are what the proposer links, so the
digester can shorten a text but never a path. In live run R1a (2026-W13) the digest failed `digest-too-large` twice
at 9,404 B compact against 8,192 B: 3,243 B of it were growth (43 note paths in 8 groups) and 3,160 B the 89
`sources` lists; without the growth `notes` and the `sources` lists it was 2,871 B. So `cap_bytes` counts the digest without the growth `notes` and without
every `sources` list, and those paths are bounded by the data instead: each must lie in the unit (the unit checks),
no path twice in one `sources` list (`source-duplicate`) and no created note in two growth groups
(`growth-note-duplicate`). Step 7 tells the agent both, so its retry knows that shortening texts is the only lever
and that repeating a path is an error, not a way to keep a source. Owner decision 2026-11-26 (spec 047 README).

## WHY `tools: Read, Write` and Never Kado

WHY: ADR-7, F7-AC5. The digester reads stage files the read already took from the vault and writes exactly its `out`
path; no Bash, no MCP, no skills, no Agent. Every step other than the read sees only what the read took (F7-AC5), so
an agent with a Kado tool could read days the read's report does not account for and bypass the key's limits, and the
privacy record (`PRIVACY.md`) would be wrong. `permissionMode: acceptEdits` with the `Edit(tomo-tmp/*)` allow rule of
the unchanged `settings.json` lets the Write land under `tomo-tmp/review/<stem>/digests/` without a prompt (the T1.4
smoke proved the nested write), the same setup `inbox-analyst` writes `tomo-tmp/items/` under.

## WHY a One-Line Reply

WHY: SDD Integration Points and the gotcha on reply size: the reply lands in the main session's context. A digester
that echoes day text into its reply would put the journal into the main conversation — the content the privacy rule
keeps out of it — and grow the main context by up to 16 units. The reply is `<out> written` or
`<out> not written: <reason word>`; whether the file is any good is `check`'s verdict, not the agent's claim.

## WHY the Prompt Carries Paths Only

WHY: the prompt names the stem, unit, `read_id`, the file list, `out`, `cap_bytes` and the review language, never note
text: the main session must not read a stage file, so it has no note text to pass, and `read_id` lets `check` refuse a
digest written for another read (`read-id-mismatch`).

## WHY the Retry Gets the Errors Verbatim and Rebuilds `out`

WHY: ADR-4 and the SDD error table: a digest that `check` refuses the first time comes back in `check`'s `retry` with
its errors, and the skill re-dispatches the same job once with `errors` added verbatim — the pattern of the proposer's
rewrite. The errors are `"<pointer>: <code>"` strings (`digest-missing`, `not-json`, `schema (<pointer>)`,
`source-outside-unit`, `days-mismatch`, `unknown-section`, `digest-too-large`, …): codes and field paths, never note
text, so they may pass through the main session. A blind second run of a model that slipped once tends to slip the
same way; the code names the rule it broke.

The digester does **not** read its previous `out`. It writes the digest anew from its inputs on every run, and the
failed file is often useless or absent: the most common failure is `digest-missing` or `not-json` (a throttled or
cut-off run), where there is nothing to read. Where a file exists, reading it would carry its faults into the new
file and cost one more Read of up to `cap_bytes`, for nothing the inputs do not hold. So the errors say what to avoid,
by code and by the field their pointer names (an index in the old file means nothing in the new one); the inputs are
read again in full. This differs from the proposer on purpose: the proposer fixes in place because its file is the
judgement over the whole period and its errors point at single items the rest of the file must keep
([review-proposer](review-proposer.md) "WHY the Rewrite Gets the Errors Verbatim").

## WHY Section Items Come From `section_files`

WHY: with a section mapping, the job's `sections` is true and a digest may hold `sections` entries, whose `key` must
be a row id of the read's section definitions (`unknown-section` otherwise). The definitions (key, description,
keywords) sit in the context, not in the job, and a large context is spilled into `context-<n>.json` parts, so the
job names the file(s) that hold them as `section_files` ([review-digest](../../scripts/review-digest.md) "WHY a
Digester Job Names Its `section_files`"). The digester reads exactly those files and takes only `sections` from
them; it never reads a context file by fixed name and never uses the other context lists. It sorts the unit's
material by each row's description and keywords already at the unit level because a section can ask for something
no fixed group holds (what was challenging, what to stop doing); a digest without it would leave the proposer
nothing to fill such a section from. Without a mapping `sections` is an empty list.

## WHY Sources Are Daily Paths

WHY: `check` resolves a digest source through the read's dailies (`review_sources.Sources.daily_of`: a daily's path
or its stem). A day file's `date` equals the daily's stem only when the daily is named by its date, so the
digester copies a path from the day file's `dailies` list; the weekly note's source is that note's `path`. A linked
note is not a source: it does not resolve to a day and `check` refuses it as `source-outside-unit`.

## WHY Nothing Is Written When a Listed File Cannot Be Read

WHY: a digest that leaves out a day it could not read would still list every day in `days` (the prompt gives them)
and pass `check`, so the review would claim a day it never condensed — the partial read F1-AC1 forbids. Writing
nothing makes the missing file a `digest-missing` attempt, which `check` retries once and then names as not condensed.

## WHY `effort: low`

WHY: the effort follows the model choice of ADR-7: recording without judgement needs no long reasoning, and 14–16
digesters run per quarter, so the thinking budget multiplies like the model price.
