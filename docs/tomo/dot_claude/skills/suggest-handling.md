# WHY: suggest-handling

> Rationale for decisions in `tomo/dot_claude/skills/suggest-handling/SKILL.md`.

## Clear inbox-state.jsonl + items/ at the top of Common setup

WHY: `tomo-tmp/inbox-state.jsonl` is append-only and is never truncated
between runs (`state-update.py` opens it in mode `'a'`). The aggregation
stages (`suggestions-reducer.py`, `mark-captured.py`) now scope their work-list
to the current `run_id` (#116), which is the real fix for stale-run
re-ingestion. Wiping the working state at the start of the suggest sub-flow is
belt-and-suspenders: even if the `run_id` filter ever regresses, a fresh run
cannot inherit a prior run's `done` stems and re-emit fabricated proposals for
source notes that no longer exist.

WHY the reset lives here and not in `reset-tomo-tmp.sh --pass1`: the `--pass1`
mode also clears `tomo-tmp/routing-plan.json`, which this skill reads in step 1
(before Common setup). Running `--pass1` here would delete the routing plan the
skill just consumed. The reset is therefore narrowed to exactly the two
prior-run artefacts that leak — `inbox-state.jsonl` and `items/` — and runs
after the routing plan has been read.

## Emit `_suggestions.json` alongside `_suggestions.md` (ADR-026)

WHY: Kokoro ADR-026 charters a Hashi Suggestions Editor that needs a
machine-readable sibling of the suggestions doc. Step 5 passes
`--json-output tomo-tmp/suggestions-wire.json` to `suggestions-render.py`, and
step 6 publishes it to the vault at the SAME `<YYYY-MM-DD_HHMM>` stem as the
`.md`. The markdown stays the baseline round-trip surface — Tomo never assumes
Hashi is installed.

WHY `kado-write-file.py` and not a raw `kado-write` note: the sibling is a JSON
file, and Kado's `operation=note` requires markdown (rejects non-`.md`). The
`file` op (base64) is the only correct write path; `kado-write-file.py` wraps
`kado_client.write_file` so the write is deterministic instead of asking the
model to base64-encode.

WHY the **markdown** goes through the same script (changed 2026-09-13): the
paragraph above is true and was read as narrower than it is. It explains why the
JSON cannot use the note op — and left the impression that the `.md`, which
*can*, should therefore be written inline. Step 6 did exactly that for a long
time: Read the rendered file, then hand its content to `mcp__kado__kado-write`.

The 2026-09-12 live run showed what that costs. 11055 characters of
deterministic renderer output were relayed through the model's own tokens and
back out as a literal. It came through byte-faithful — but that is only known
because the run was diffed afterwards. Verbatim relay is unverifiable by
construction: nothing in the pipeline distinguishes a faithful copy from a
subtly altered one, and the artefact in question is the document the user reads
and approves.

`kado-write-file.py` already routes by extension (`.md` → note, other → file)
and reads from disk, so the content never enters the model's context. Its own
docstring gave the reason before this change was made: "the content is read from
disk and pushed via this script's own Kado client, so it NEVER passes through
the agent's output-token budget." Both artefacts now take that path, and the
step carries a STRICT against the inline route — an unadorned imperative had
already been observed producing the deviation.

WHY the wire is a COMPLETE mirror of the review surface (not editable deltas):
Marcus's rule is "if Hashi edited the JSON, use ONLY the JSON; otherwise ONLY the
markdown — never a mix." Under that rule the changed JSON is the sole authority,
so anything the markdown lets the user decide must be carried in the JSON or it
would be silently dropped when a single field is edited. The wire therefore
mirrors: every note's full option set (title, template, location, tags,
decision, keep_source, delete_source, force_atomic, suppressed/worthiness,
candidate MOCs + anchors + source), proposed MOCs (with `M##` ids for
merge/rename as a graph op), daily-note updates, and tag-handler approvals. The
notes/proposed-MOCs are projected from the structured `item` the reducer now
persists; the daily + tag-handler sections are mirrored by parsing our OWN
freshly-rendered markdown with the parser's own section parsers (so the wire is
byte-faithful to the parse output — no second, divergent implementation).

WHY the change signal is a SHA-256 `emit_digest` over the editable payload:
tool-agnostic — Hashi need do nothing to preserve it (any semantic edit moves the
digest; a canonical re-serialization means reformatting alone does not). See
`docs/tomo/dot_claude/agents/synthesis-conductor.md` for the JSON-only Pass-2
read-back side.

## The dispatch prompt passes `item_key` and never names the result file

WHY: the per-item result file is named `<readable>-<8 hex>.result.json`, derived
from the item's `item_key` by `lib/item_key.to_filename` (spec 034 ADR-5). This
block used to instruct `tomo-tmp/items/<stem>.result.json`, which the reducer no
longer reads — and because both this skill and `inbox-analyst.md` are LLM-loaded
verbatim, the two contradicting each other produced nondeterministic behaviour
rather than an honest failure. The instruction now points at the analyst's own
Step 10, which shells out to `scripts/item-result-filename.py`; one derivation,
one place to change it.

WHY `item_key` is passed even though it equals `path`: it is a declared input of
the analyst's IO Contract (ADR-1 makes derivation the identity function), and
the analyst must never reconstruct it from `stem` — two inbox items in different
subfolders share a stem and would collide on one result file.

WHY the prompt now says the contract is ALREADY LOADED, with a STRICT against
searching for it (added 2026-09-13): the line "Follow the IO Contract in your
agent definition strictly" names a document without saying where it is or that
the subagent already holds it. In the 2026-09-12 run, **11 of 12 subagents went
looking for it on disk** — `find … -path "*agents*" | xargs grep -l "IO
Contract"`, `grep -rl "shared_ctx_path"`, `find … -iname "*inbox-analyst*"`.

It was already in front of them: `inbox-analyst.md` carries `## IO Contract
(STRICT — the orchestrator depends on this)` and is loaded as the subagent's own
definition. The searching produced nothing that was not already available, and
cost one to several calls per item.

Naming a source without locating it reads as an instruction to go find it. The
related symptom in the same run: one subagent pretty-printed `shared-ctx.json`
and `item-result.schema.json` into `tomo-tmp/` to read them, leaving two stray
files behind in the pipeline's working directory.

**A `#` line inside an `Agent(prompt: |` block never reaches the subagent.** The
first attempt at this fix wrote the instruction as a `# STRICT` comment inside
the prompt template. The next run showed the dispatched prompt verbatim: the
plain sentence above it came through, the `#` lines did not, and 11 of 12
subagents searched exactly as before.

That is the conductor behaving correctly. Everywhere else in these skills a `#`
line is a directive to whoever is reading the skill — and inside a prompt
template the reader is still the conductor, so it reads the line as a note to
itself and leaves it out of the prompt body. The existing STRICTs in
`force-atomic-handling`'s dispatch section sit *before* the template for exactly
this reason.

So an instruction meant for the subagent must be plain prompt text with no `#`
prefix. The rule for anyone editing a dispatch template: `#` addresses the
conductor, unprefixed lines address the subagent, and there is no marker that
makes a comment travel.

## WHY There Is No Cost-Recording Step Here (spec 034 T6.1)

A `suggest` run's cost-history entry is written by `suggestions-reducer.py` in
step 4, not by a step of its own. It was briefly a separate command after
`mark-captured`, and that was wrong for one reason: a step in this file is
executed by an LLM, so no test can see whether it ran. The task's criterion is
"a history accumulates *without anyone remembering* to record it" — a guarantee
that cannot depend on the runtime remembering a line of markdown.

Do not re-add one. `inbox-triage.py` writes no entry for this action (the
reducer's destination-folder counts do not exist when it finishes), so a second
append here would double-record the run. See
`docs/tomo/scripts/lib/cost_history.md`.

## Why the dispatch template says `subagent_type`, not `name`

The fan-out template used to read:

    Agent(
      name: "inbox-analyst"
      prompt: | ...

`name` labels the agent that gets spawned — it is what makes it addressable
for a follow-up message. `subagent_type` is what chooses which definition it
runs. A dispatch carrying only `name` spawns **general-purpose under an
alias**: the call succeeds, the transcript shows an agent called
"inbox-analyst", and none of that agent's contract, tool restrictions or
skills are in play.

The 2026-09-14 live run did this for all twelve items. The session metadata is
unambiguous — twelve files reading `agentType: general-purpose, name:
inbox-analyst`, and exactly one reading `agentType: inbox-analyst`, which was a
nested dispatch a confused general-purpose agent made using the correct key.

Everything previously filed as disobedience was this:

- **The contract hunting.** Seven of twelve ran `ls .claude/agents/` or `find`
  for `inbox-analyst.md`. The contract genuinely was not loaded. They searched
  because they had to, and the eight that produced correct output are precisely
  the ones that searched and read the file.
- **The brute-forced filenames.** Three ran `md5sum`, `sha1sum`, `sha256sum`
  and `cksum` over the item key trying to reproduce a result filename.
  `scripts/item-result-filename.py` is named in the contract's Step 10, which
  they had never seen.
- **The hand-written state file.** Five bypassed `scripts/state-update.py`,
  one of them replacing the whole file with a `Write` while four siblings were
  appending to it. One `running` record was lost that way. Same cause.
- **The nested dispatch.** A general-purpose agent has the full toolset, so one
  of them loaded `Skill(inbox)` and re-dispatched its own item. `inbox-analyst`
  declares `tools: Read, Bash, Write, mcp__kado__kado-read` — no `Agent`, no
  `Skill`. Under its real definition that call is not available.

**Why the prompt's reassurance made it worse.** The template used to tell the
subagent *"Your agent definition is ALREADY LOADED … Do NOT run find, grep or
ls to locate your contract"*. That sentence was added to stop the searching. It
was false, and it was instructing agents not to fetch the one thing they were
missing. It has been removed rather than corrected: with `subagent_type` in
place the definition is loaded, so the reassurance has nothing left to do, and
a prompt that describes its own context is a claim that can silently go stale.

**Why nothing failed.** Every run still produced `done=12 failed=0` and a valid
suggestions document. A capable general-purpose agent handed a detailed prompt
reconstructs most of the pipeline from the filesystem. The cost was invisible:
duplicated work, a lost state record, an item processed twice, and every
tool-restriction in the agent definition quietly not applying.

**Guard.** `tests/test_dispatch_templates.py` asserts that every `Agent( … )`
block under `tomo/dot_claude/` names a `subagent_type`, that no template
selects with `name` alone, and that each named type has a definition in
`tomo/dot_claude/agents/`. It carries a non-vacuity test, because a shape-based
regex that stops matching would pass every other assertion in the file.

All four templates in the tree had the defect — both fan-out skills, plus
`synthesis-conductor` and `voice-transcriber` in the `/inbox` command. Pass 2
and transcription were dispatching general-purpose too.

## Why step 1 reads the routing plan through a script

The skill used to say `cat tomo-tmp/routing-plan.json`, then "Extract
`fresh_sources[]` and `inbox_path`". In the 2026-09-14 12:34 run the conductor
did the `cat`, and fifty records later — after the setup step, with the plan
scrolled well back — it needed the source list to build its first dispatch
batch and ran:

    python3 -c "
    import json
    d = json.load(open('tomo-tmp/routing-plan.json'))
    ...

`suggestion-conductor.md` forbids exactly that in a `STRICT` block, and Claude
Code's Bash validator flags such calls on their `#` characters. The model filed
a bug against itself for it, and named its own cause accurately: it needed the
exact list and there was no sanctioned way to get one.

That is the shape of the defect. `cat` does not hand back a list; it hands back
a document to re-derive a list from. Re-deriving is either inline Python — the
forbidden thing — or retyping twelve paths from a scrolled-back tool result,
which drops entries silently. The instruction "never do X" without a sanctioned
Y is a trap, and the model walked into it on the only step that had no helper.

`scripts/read-routing-plan.py` is that Y, following the precedent
`read-config-field.py` set for `vault-config.yaml` — whose own header says it
"replaces ad-hoc `python3 -c`". It also takes the batch arithmetic: the skill
now asks for `--batch-count` once and then `--sources --batch N --size K`,
instead of asking an LLM to slice twelve items into groups of five. The tail
batch (two items, not five) is the case that arithmetic gets wrong.

`cat` stays as the first step. Surfacing `drift_indicators` needs the whole
document, and a conductor that never sees its own plan is harder to debug.

## Why `INBOX_PATH` and not `inbox_path`

The publish step read `--vault "<inbox_path>/<stem>_suggestions.md"`. The plan
stores `inbox_path` as `"100 Inbox/"` — already terminated — so the template
produced `100 Inbox//2026-09-14_1234_suggestions.md`. Kado normalises the
double slash and the file landed correctly; the same run wrote the `.json`
sibling with a single slash, so the two commands disagreed about the shape of
the same path and both worked.

`read-routing-plan.py --field inbox_path` strips the trailing slash, and the
templates now name `<INBOX_PATH>` — a value with known shape, joined with `/`
unconditionally. The rename is the point: `<inbox_path>` reads as "the field
from the plan", which is the thing that carries the slash.

`moc-architect` had already solved this the other way, joining with no
separator and stating "it already ends in `/`". Both are correct in isolation;
having both in one tree is what let the wrong one look right. `force-atomic-
handling` carried the same defect on its own publish step and is converted to
match — found by grepping the shape rather than the site the bug appeared in.

## Why the context file is deleted before it is built (spec 040 ADR-8)

A failed `shared-ctx-builder.py` call used to leave the previous run's
`shared-ctx.json` in place, and nothing compared run ids, so analysts could
classify against another run's MOCs while every step reported success.
`rm -f tomo-tmp/shared-ctx.json` before the build means a failed build leaves
no file at all, and the abort that follows is the only outcome. The analysts'
`--run-id` check is the second layer: it holds even if a conductor ignores the
abort.

The context is still rebuilt from the local discovery cache on every run; the
only vault traffic is the reconcile listing per MOC folder. Caching across
runs stays in the discovery cache.

## Why Step 7 relays `duplicate_proposals_converted`

The reducer counts proposals it turned into existing-MOC candidates (spec 040
ADR-6). The count is the only sign of how often the analyst missed an
existing MOC by name — the metric the spec's zero-duplicate goal is measured
by. Nothing else reads the reducer's stderr, so the skill repeats the number
from the summary line; it computes nothing itself.

The line is added only when the count is above zero: a "0 converted" line on
every healthy run is noise the owner learns to skip, and the zero still sits
in the reducer's summary line in the transcript for anyone measuring it.

## Why step 7's report lines are an exact-output template

Step 7 used to show the report as a quoted template — a `> "…"` blockquote
wrapped over three lines, introduced by nothing. Spec 043's first Pass 1 smoke
(2026-10-31, `claude` 2.1.316; evidence in
`docs/XDD/specs/043-pass1-conductor-eval-gate/findings.md`, F1–F3) ran the
pipeline twice, and both runs paraphrased it:

- `Pass 1 is complete. The analysts processed 3 items (Alpha, Dresden, Gamma) with no failures, and the suggestions are written to [[…]].`
- `Pass 1 complete: 3 items analysed (Alpha, Dresden, Gamma). Suggestions are written to [[…]].`

The duplicate line was singularised the same way: `1 proposed MOC already
existed in the vault and is offered as an unticked link instead.` for a
template that reads `{n} proposed MOC(s) … are offered as unticked links`.

A quote reads as *what to say*, not *the words to output*. The model took it
as content to convey and wrote it in its own sentence, added the item list it
had at hand, and made the grammar agree with `n = 1`. Nothing in the old text
said the wording was fixed.

The template is now stated as an exact-output instruction behind a `STRICT`
block (observed deviation, 2 of 2 runs):

- **Fenced, not quoted.** Each line sits alone in a ```` ```text ```` fence on
  one line. A blockquote invites copying the `>` too, and the report line is
  recognised at the start of a line; a fence makes the boundary of the exact
  text unambiguous.
- **What may change is named.** Only `{N}`, `<date>` and `{n}` are replaced.
  Everything else — wording, punctuation, the line order, `MOC(s)` and
  `are offered as unticked links` for every `n` including 1 — stays, and the
  instruction says so in those words, because Sonnet follows literally what it
  is told and generalises from what it is not.
- **No item list.** The two runs inserted the same thing, so the instruction
  forbids it by name.
- **`<date>` is the full stem.** It is the `YYYY-MM-DD_HHMM` stem of the step 6
  writes (date and time), so the link resolves to the note that was written;
  saying only "date" would let the model drop the time.

The instruction does not forbid text after the template lines: a failed
`mark-captured.py` must still be reported (step 6), and the smoke's extra notes
below the template were harmless.

## Why the `WARN:` relay copies a tool result before the batch-count command

The step 2 `STRICT` said to repeat every `WARN:` line of `shared-ctx-builder.py`
"to the user, verbatim, before dispatching anything". In the first smoke (spec
043 findings F4) the model's only reaction before its first `Agent` call was a
**thinking** block noting the warning; the verbatim line first reached the user
in the final report, after every dispatch. It read "before dispatching
anything" as "somewhere in the reply", and treated noticing the warning as
relaying it.

The first fix (0.13.0) moved the instruction to the top of step 3 and named the
vehicle: "send them to the user now, before any command or Agent call of this
step: write them as a text message of your own (not a thought)". The second
smoke showed the same pattern: the model reached the top of step 3, wrote one
thinking block about the warning ("The shared-ctx builder flagged two active
trackers … I'll run /tomo-setup trackers …"), and its very next content block
was the batch-count `Bash` call. The placement worked — the reaction came
exactly where the instruction sat — the vehicle did not. "Not a thought" is an
abstract duty; the model satisfied it, in its own reading, by thinking about
the message it would send.

0.13.1 changes the vehicle from a duty to an output:

- **A `STRICT` block.** Observed twice (both smokes), so the emergency lever is
  justified. Its `Why:` names the failure mode in one line: a warning noted
  only in thinking reaches the user after every analyst has run.
- **A literal shape in a `text` fence.** A fixed header line (`Setup
  warnings:`) followed by the `WARN:` lines. The model has a concrete text to
  produce, in the same format the step 7 report template already uses, rather
  than a description of a message.
- **Anchored to the next tool call.** "Your next output is this text reply,
  before the batch-count command below" names the exact point where the model
  acted in both smokes (it went from thinking straight to that command). The
  rule is phrased against the command it must precede, not against the step.
- **Thinking named as not counting.** The one reading the model took is ruled
  out by name.
- **The no-warning branch is explicit.** "If it printed none, output nothing
  here" keeps a healthy run from emitting an empty header.

Placement stays at the top of step 3, not as the last item of step 2 right
after the `shared-ctx-builder.py` call. Both smokes show the model reacting to
the warning at the top of step 3 (after the two `read-config-field.py` calls),
so that is where it already pays attention; a second copy at the end of step 2
would put the rule between the build and the two config reads, where the
next action is another setup command and the model batches setup calls
without text between them. One location also means the mutations that remove
the early relay have a single block to remove.

The step 2 `STRICT` keeps the rule itself (same opening phrase, which
`tests/test_040_skill_prose.py` pins for both Pass 1 paths) and names both
moments: as the text reply that opens step 3, and again in the step 7 report.
The repeat in the report stays because the warning must also be in the final
reply (PRD F2-AC1), which is what the user reads when the run ends; the early
reply exists so a user watching the run sees it before analysts are spent on a
broken tracker configuration (F2-AC2).

The step 3 and step 7 lines name the script (`shared-ctx-builder.py`), not
"step 2", so they stay true if the build ever moves.

### 0.14.0: the relay is the copy of a tool result (Plan B)

The third smoke (findings F4, smoke 3, `e-QKbc19`) ran 0.13.1 and showed the
same shape a third time: the `WARN:` tool_result, one non-empty thinking block
("Setup check found two active trackers—mood and sleep—missing keywords …"),
then the batch-count `Bash` call, then the first dispatch. No `Setup warnings:`
text was written. Three wordings — a duty, a duty with a named vehicle, a fixed
text under `STRICT` — all produced the same thinking-only reaction at the same
point. Prose has reached its limit here: each version asked the model to
*remember* to say something it had already seen, and the model counted having
seen it.

0.14.0 makes the relay a copy instead of a memory (owner decision 2026-10-31,
"Plan B"):

- **The builder saves its own warnings.** `shared-ctx-builder.py` takes an
  optional `--warnings-out <path>` and writes every `WARN:` line it printed on
  stderr to that file, one per line, exactly as printed. The file is rewritten
  on every run (also on an error exit), and is empty when there were no
  warnings, so a stale warning from an earlier run can never be relayed. The
  lines are captured where they are printed (stderr is wrapped for the run),
  not re-derived, so the saved text cannot drift from what the user would see
  in the tool output.
- **Step 3 opens with `cat tomo-tmp/setup-warnings.txt`.** Its stdout is
  exactly the lines to relay and nothing else. The `STRICT` tells the model to
  output that stdout verbatim as its text reply before the batch-count command
  (and nothing when it is empty). Copying the result of the command just run is
  the pattern the model reliably follows elsewhere (the step 7 report, relay
  grader 01 green in all three smokes); the reaction point is the same one the
  model already uses, but now its trigger is a fresh tool result, not a line
  three tool calls back.
- **`cat`, not a new reader script.** `cat` is already allowed
  (`Bash(cat:*)` in `settings.json`), step 1 already uses it on `tomo-tmp/`,
  and the builder guarantees the file exists whenever the build succeeded (the
  skill aborts when it fails). A dedicated reader would add a script, a stub
  and tests for no behaviour `cat` lacks.
- **The flag is optional.** `force-atomic-handling` runs the same builder
  without it and is unchanged; `tests/test_040_skill_prose.py` compares the two
  builder commands with `--warnings-out <path>` removed, since that flag
  changes only a side file, not the built context.
- **No header line.** The `Setup warnings:` header of 0.13.1 is dropped: the
  model's reply is the command's stdout, so relay grader 02 (which searches the
  assistant text for the `WARN:` line) and the user see the builder's lines
  unaltered, and there is no template to reword.
- **Step 7 keeps its repeat** for PRD F2-AC1 (the warning in the final reply),
  unchanged.

The `STRICT` stays: the deviation was observed three times out of three.

### 0.14.1: the `cat` result is the relay; the text-reply `STRICT` is gone

Smoke 4 (findings F4, `e-GDBsiX`) ran 0.14.0. The `cat` ran where the skill
puts it, at the top of step 3, and its tool result carried the verbatim
`WARN:` line before the first dispatch. The model then reacted in a thinking
block once more and wrote no text. That makes four wordings and four runs, all
thinking-only.

Owner decision 2026-10-31: PRD F2-AC2 is met by the tool relay. The `cat` call
whose result carries the `WARN:` line, before the first `Agent` call, *is* the
early relay. Claude Code shows Bash output to the user, so the warning is on
screen before any analyst runs. The tool result is also deterministic: it needs
nothing from the model after the call.

What 0.14.1 changes and why:

- **The text-reply `STRICT` under the `cat` is removed**, together with "your
  next output is this command's stdout". It asked for something the model
  never did in four runs, and the requirement it served is now met by the
  command itself. An unmet `STRICT` left in the prose would only teach the
  model that `STRICT` lines are optional.
- **The `cat` stays, as the first command of step 3**, phrased as an imperative
  that names its position: run it before the batch-count command. Relay grader
  02 checks exactly this: the `cat` tool_use and its next tool_result, both
  before the first dispatch (SDD Complex Logic). Its position ties it to the
  point where the model already acted in all four smokes, the top of step 3.
- **`--warnings-out` stays.** Without the saved file the `cat` would have
  nothing to print. The builder's own tool result also carries the WARN text,
  but it comes several tool calls before step 3. In the eval it cannot be told
  apart from a run that swallows the warning, because the builder prints it in
  every run.
- **The step 2 `STRICT` keeps its opening phrase** ("repeat every `WARN:` line
  this script prints", pinned for both Pass 1 paths by
  `tests/test_040_skill_prose.py`). It now names the two places where the
  warning reaches the user: the `cat` that opens step 3, and the step 7 report.
  It no longer asks for a text reply before the dispatch.
- **Step 7 keeps its repeat** for PRD F2-AC1 (relay grader 01, green in all four
  smokes). The final reply is what the user reads when the run ends.

The mutation `warn-in-report-only` removes the `cat` and leaves only the step 7
repeat, so the warning reaches the user after every dispatch, and grader 02
goes red.
