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
