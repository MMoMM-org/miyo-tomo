# WHY: review-proposer

> Rationale for decisions in `tomo/dot_claude/agents/review-proposer.md`.
> Spec 047 (issue #270, `docs/XDD/specs/047-review-chunked-read/`); bare ADR and F-AC ids refer to its
> `solution.md` and `requirements.md`, ids of spec 045 and 046 are named with their spec. The agent builds
> `proposals.json` for the whole period from the digests, the carryover and the context. Its inputs are listed by
> `review-digest.py` ([review-digest](../../scripts/review-digest.md) "WHY the Proposer's Inputs Are Listed by the
> Script"); its file is checked by `review-doc.py write` ([review-doc](../../scripts/review-doc.md)); the skill that
> dispatches it is [periodic-review](../skills/periodic-review.md). Until spec 047 these rules were SKILL.md step 5 and
> their rationale sat in the skill's WHY document; they moved here with the step (ADR-8).

## WHY `sonnet` (ADR-7, amended)

WHY: the proposer is the one judgement-heavy step of `/review`: it merges findings across up to 16 condensed weeks,
counts themes over the whole period, judges open against later weeks, matches carried items to the days and marks
them, and places each finding once by the section descriptions the user wrote. That work stays the proposer's; only
the model changed. Spec 047 first ran it on `opus` (the owner chose quality before cost). The owner moved it from
`opus` to `sonnet` on 2026-11-27 after the live walk (R1d, R2) measured the cost: the proposer on `opus` cost $1.50 /
98 s for a week and $4.45 / 286 s for a month, so Pass 1 came to $2.40 for a week (guidance ≤ $0.80) and $6.27 /
8.3 min for a month (guidance ≤ $2.00 / 7 min), and a quarter could not have held its ≤ $5.00 guidance. The scripts
own the parts a slip would harm most: `review-doc.py write` builds the habits and the "Vault growth" group itself
and validates every proposal (sources, section keys, cap, one place per finding, carried marks) before anything is
rendered, refusing a bad file into one aimed rewrite, so a slip on `sonnet` is bounded to a weaker item the user can
untick, not a broken document. Revisit `opus` if the re-run of month 2026-03 on `sonnet`, compared with the `opus`
document of the walk, shows a loss of quality (themes missed, open items misjudged, carried items mismatched). The
digester is `haiku` and the carryover `sonnet` (their own WHY documents).

## WHY It Writes Only `proposals.json` (Spec 045 ADR-12)

WHY: habits, the vault growth group and the link differences of a month are numbers and lists; computed by the scripts
they are deterministic and testable (spec 045 F8), and the proposer gets them as facts. Its job is the one thing a
script cannot do: read the period's material and propose the items — what got done, what stayed open, recurring
themes, for a month what only the weekly notes hold and what they left out — in the review language. It writes them
to `proposals.json` in the schema `tomo/schemas/review-proposals.schema.json` and nothing else: no document, no
section, no frontmatter. `review-doc.py write` validates the file and renders the document.

- **Sources.** Every item names the notes it rests on, at least one a daily of the period (spec 045 F4-AC3; for
  `weekly_only` a weekly note, for `monthly_only` a monthly note): the user checks a proposal by its link, and the
  document check refuses an item without a day source.
- **A second line of `text`** becomes a continuation line of the item: the renderer's one way to carry a longer
  reminder without a second item.
- **Habits are computed by the script; never proposed.** A habit item by the model would duplicate, and could
  contradict, the computed lines.
- **The user's own sections.** The proposer never writes text for the user's own sections other than the mapped
  `sections`: a mapped section is the user's too, and without the carve-out a literal model leaves every section empty
  (spec 045 F4-AC7, spec 046).

## WHY the Rules Run Over the Whole Period

WHY: before spec 047 the model read the period itself, so "over the whole period" was implicit. Now every unit is
condensed alone and only the proposer sees all digests; a rule applied per digest would be applied per week. So each
whole-period rule is the proposer's and is said as its own imperative:

- **Themes over all days (F1-AC3).** A matter found on two days in different weeks is a recurring theme; the spec 045
  two-day rule counts days of the period, not of a week. A digest keeps single-day themes for exactly this reason, and
  `review_doc.check_item` re-checks the two days on the written file.
- **Open against later weeks (F1-AC4).** An item open on an earlier day and done on a later day, also in a later week,
  is proposed as done; open is judged against the whole period, or the review reports as open what the user finished.
- **One item across weeks (F1-AC5).** A finding in several weeks is one item with the sources of all those days, in
  one section or group (spec 046 Rule 5 across weeks): the user should see the matter once with every link, not once
  per digest.
- **Child marks over the whole period (F2-AC3).** `weekly_only` / `not_in_weekly` (and a quarter's `monthly_only` /
  `not_in_monthly`) compare the child notes with all days of the period, never per week: a weekly note may name a day
  of another week's unit.
- **Item text in the review language (F4-AC11).** The digests and the carryover may hold another language (a previous
  note written in German, a day written in English); every item, carried or not, is written in the review language
  the prompt names.

## WHY the Section Rules (Spec 046 ADR-1, F1, F2)

WHY: with a mapping, the context carries `sections` — one definition per configured row (`key`, heading, level,
parent, description, keywords, groups, cap; `analysis: true` on an analysis row). The proposer writes `sections:
[{key, items}]` beside `groups`. One imperative per rule the scripts cannot enforce, and only a fix line for the rules
they can:

- **The key is copied, never invented.** One entry per section with something to propose, `key` copied from the
  context. A key the context does not carry is refused `unknown-section`, a second entry `duplicate-section`
  (`lib/review_sections.check`); the rule is said so the first write is usually the last.
- **What a section receives follows its description and keywords (046 F1-AC2).** The fixed groups are not the frame: a
  section that asks what to start or stop doing, or what will be challenging next month, receives items for that when
  the material holds them, whatever group they would fit. A model that sorted by group first would leave such a
  section empty.
- **A row's `groups` are its starting point (046 F2-AC7).** When setup names groups for a row (for example `growth` for
  "Notes Created This Quarter"), the section starts from what those groups would hold, and such a finding goes into
  the section instead of the group. That keeps the one-place rule and leaves a group no row names in "Tomo Review"
  (owner decision 2026-11-19, 046 close-out). Before the rule only the description steered the section, which is
  why the 046 walk's s2 fix had to reword the description.
- **Reminders, not finished text (046 F1-AC3, F1-AC4).** A section is the user's own words in their note; Tomo reminds
  them of what happened or will need to happen, with the source, and leaves the judgement to them. A forward-looking
  section gets a reminder drawn from what the period shows, never an invented goal.
- **The cap by merging (046 F1-AC5).** Over `cap` the script refuses `over-cap (<key>)`. The rule says how to stay
  under it — merge findings that say the same and keep each one's sources — so a merge does not drop the evidence the
  user checks. Carried items are the exception the script resolves itself (see F4-AC10 below).
- **One place per finding (046 F1-AC6, F1-AC7).** A finding goes to the section it fits best, else to its group; never
  twice. `double-placement` refuses only the detectable cases (same normalised text, or same sources and first line),
  so the imperative carries the rule for the rest.
- **Analysis rows as overviews (046 F2-AC12).** A row marked `analysis: true` sits on a heading whose content is
  automatic (habits, trackers); its items land in the "Tomo Review" part as an overview of what the period's values
  show, never one item per day. The description alone does not say that reliably (the setup's model wrote it, the
  user may change it to anything), and since 046 T4.2 the placement is read from the config, so the read marks the
  row (docs/tomo/scripts/review-read.md) and the rule branches on the flag. The habits rule still holds: the habit
  lines are computed; an analysis item is the model's reading of them.
- **Marks stay on the items (046 F1-AC9).** A month's section item that only the weekly notes hold, or that they left
  out, carries `weekly_only` / `not_in_weekly` as `mark`, its sources as for that group; a quarter's carries
  `monthly_only` / `not_in_monthly`. The script refuses a mark the kind does not have (`mark-not-allowed`).

## WHY the Rewrite Gets the Errors Verbatim

WHY: `review-doc.py write` refuses a bad file as `proposals-invalid` with `"<pointer>: <error>"` strings. The skill
re-dispatches the proposer once with the errors verbatim (F6-AC3, "as today"): the proposer, not the main session,
holds the material, so it makes the fix. The agent maps each error to its fix in the entry the pointer names, so the
one rewrite is aimed: `unknown-section` / `duplicate-section` → each context key once; `over-cap` → merge to the cap;
`double-placement` → remove the item the pointer names (the check names the later one); `mark-not-allowed` → drop the mark; a `carried-*` error → fix
that item's `carried` / `carried_ids` / sources. A second refusal is shown and no document is written: looping on a
schema the model cannot satisfy burns the user's time.

## WHY a Rewrite Fixes the Previous File in Place

WHY: on a rewrite the prompt carries `errors`, and the proposer reads `out` — its own previous `proposals.json` —
once besides `inputs`, fixes each entry a pointer names and keeps every entry no error names. `review-doc.py write`
raises `proposals-invalid` before it writes or discards anything, so the refused file is still on the stage; the
skill's rewrite follows the refusal directly, with no `review-digest.py plan` in between (plan, which deletes a
leftover `proposals.json`, runs once per run, before the first proposer dispatch). Fixing in place is cheaper than a
rebuild — the pointers name the few broken entries — and it keeps the items that passed exactly as they were, so a
rewrite cannot trade one error for a new one or drop an item that was fine. Reading `out` is the one exception to
"read only `inputs`"; `plan` does not list it because it does not exist before the first run. When `out` cannot be
read or is not JSON, there is nothing to keep and the proposer builds it anew from `inputs`.

## WHY "the Context Files of `inputs`", Not `context.json`

WHY: a context over the file ceiling is spilled by `review_stage` into `context-<n>.json` parts; the head keeps only
`read_id` and `period` (and empty lists), so the sections, the child-note link lists and the growth counts may sit in
a part. `plan` lists every context file in `inputs`, so the rules name "the context files of `inputs`" for that data;
only the period's kind is read from `context.json` by name, because the head always keeps `period`. The same spill
made the digester's bare `context.json` read unsafe (see [review-digester](review-digester.md)).

## WHY the Carried Rules (ADR-6, Feature 4)

WHY: the carryover lists what the previous reviews left open, intended or recurring. Whether the period did it is a
reading of the days, which no script can do; whether the marks are consistent is a rule, which a script can check. So
the split: `lib/review_carried.py` checks marks, ids and sources (every carryover id exactly once over the document, a
theme id never `done`, `done` / `still_open` with at least one day, `not_mentioned` with none, the previous-note
sources a subset of the ids' sources, the group/mark pairs); the model owns the match of each carried item to the
days. Every carried failure is an `errors` entry, never a `rejected` row, so a carried item is never silently dropped.

- **The marks (F4-AC2).** A carried open item or intention is `done` when a day shows it done, `still_open` when a day
  shows it still open or only partly done, `not_mentioned` when no day of the period mentions it.
- **A theme is never done (F4-AC3).** A carried theme is `still_open` when a day shows it again, `not_mentioned` when
  none does; a theme does not end, so `carried-theme-done` refuses it.
- **Placement (F4-AC4).** A carried item goes into the mapped section whose description it fits best, otherwise into
  the group of its mark: done into "done"; still open and not mentioned into "open"; a theme into "themes".
- **Never under an off-limits heading (F4-AC5).** A section the user marked off-limits receives no carried item; when
  the best fit is off limits, the item goes to the next fitting section or its group. Text in an off-limits section of
  a previous note may still be a source; the rule is about placing, not reading.
- **One item, nowhere else (F4-AC6, F4-AC7).** A carried item the days also hold is ONE item with its carried mark,
  whose sources are the previous note and those days; it appears nowhere else in the document. The same matter in both
  previous notes is one item with both notes among its sources. Without this the user sees one matter twice, once as
  carried and once as new; the script detects only the identical cases.
- **Carried again, no age (F4-AC8).** An item the previous note itself carried as still open, and still open now, is
  carried again with the same mark; Tomo counts no age and adds no text about how long it has been open (owner: a
  nagging counter is not a reminder).
- **Same-mark merge, never across marks (F4-AC10).** Carried items of the same mark merge under spec 046 F1-AC5,
  keeping every source link, never with an item of another mark: a merge across marks would hide that one part was
  done. A full section is the script's to resolve: `review_carried.overflow` moves the last carried items of an
  over-cap section into the group of their mark (`carried-moved`), so the proposer is not asked to drop one.
- **`carried: false` means no carried item (F6-AC2).** `plan` and `check` hand the proposer `carried` true only when
  the carryover passed. With `carried: false` (the carryover failed or no previous note was found) no item carries
  `carried`: an item marked against a carryover that is not there would be refused `carried-without-carryover`, and the
  document's top already says the previous reviews could not be taken into account.

## WHY It Proposes No Vault Growth Group (T9.3, F-R1-3)

WHY: owner decision 2026-11-26 after the live runs T9.2 R1b and R1c (week 2026-W13). The digester wrote 8 growth
candidates holding all 43 created notes, yet the opus proposer built no "Vault growth" group in either run: it named 33
of the notes inside section items and 10 nowhere. Its rules allowed that — "Leave out a group with nothing to propose"
and the one-place rule of the sections both let a growth finding vanish into a section or into nothing — so the
pre-047 behaviour (PRD F2-AC1: the document always holds the group with every created note of the period) was lost.
A list of every created note is data, not judgement, so a script builds it: `review-doc.py write` takes the created
notes of the read and groups them as the digests' growth candidates group them (`lib/review_growth.py`, its WHY
document). No created note can be dropped, and the proposer's output shrinks. The alternative — a stricter proposer rule
plus a write check with one rewrite — kept the model in a step a script does exactly, and was rejected.

So the shape example no longer lists `growth` and the growth rule is gone. The proposer may still name a created note
inside a section or group item: the group lists the note regardless. A `growth` group a proposer still writes (an
instance not yet synced) is ignored by `write`, never refused ([review_growth](../../scripts/lib/review_growth.md)).
The digester keeps its growth candidates: they are the script's grouping and texts.

## WHY It Never Reads `manifest.json`

WHY: owner decision v1.2. `manifest.json` holds the read report (which dailies were found, what was not read, the
pacing). The report is for the user, shown by the skill in step 4 and named at the document's top by the script; it is
not material to propose from, and a model that reads "day X not read" might propose about it. The proposer never reads
`manifest.json`, and never a `days/` or `growth/` file either: the digests are the whole-period material, which keeps
its input bounded. `plan` lists exactly the inputs it reads, in read order.

## WHY `tools: Read, Write`, Never Kado, and a One-Line Reply

WHY: ADR-7, F7-AC5. The proposer reads stage files and writes exactly `proposals.json`; no Bash, no MCP, no skills, no
Agent, so it sees only what the read took from the vault and cannot write anywhere else. `permissionMode: acceptEdits`
with the unchanged `settings.json` lets the Write land under `tomo-tmp/review/<stem>/` without a prompt. Its one-line
reply (`<out> written` or `<out> not written: <reason word>`) keeps the period's content out of the main session's
context; the main session learns what was proposed only from `write`'s counts.

## WHY `effort: high`

WHY: the effort follows the model choice of ADR-7: the proposer is the one judgement-heavy step and runs once per
review, so a longer reasoning budget buys quality at the cost of one run. `sonnet` takes the `effort` setting like
`opus`, so `high` stays after the 2026-11-27 move to `sonnet`: the judgement work did not shrink with the model.
