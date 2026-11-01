# WHY: synthesis-conductor

> Rationale for decisions in `tomo/dot_claude/agents/synthesis-conductor.md`.
> This is the WHY-persistence layer per Tomo's runtime/rationale split rule.

## No Agent Tool — Script-Only Pipeline

WHY: synthesis-conductor does not dispatch leaf agents. All its work is deterministic: parse cached docs, render instructions, upload results, flip state, audit coverage. Each step is a Python script call. The Agent tool is unnecessary because there is no analysis or classification step that requires LLM reasoning in a subagent context. Contrast with suggestion-conductor, which dispatches inbox-analyst for per-item classification (an Opus-level reasoning task).

## Reads from Cache, Not Kado

WHY: inbox-triage.py (Layer A) already read every pending doc's full body via kado-read and cached it to tomo-tmp/inbox-cache/. The routing plan's `cache_path` field points to these local files. Re-reading from Kado would double the Kado call count and add latency for data the system already has on disk. The single-read principle: triage reads once, conductors consume from cache.

## Single Mode Design (synthesize only)

WHY: synthesis-conductor handles only the `synthesize` action from the routing plan. Analysis work (classify new sources, resolve force-atomic items) lives in suggestion-conductor. This split follows the SDD's conductor decomposition: suggestion-conductor is the analysis conductor (dispatches leaf agents, produces suggestions-type artifacts), synthesis-conductor is the rendering conductor (calls scripts in sequence, produces instructions). A single-mode conductor is smaller, loads fewer skills, and occupies less LLM context than a multi-mode agent.

## State Promotion Happens Here

WHY: The state flip (pending-approval to approved, pending-accept to accepted) happens after successful rendering and upload, not before. This is the terminal state for the source document — it means "I consumed this input and produced instructions from it." Flipping state before rendering would mark a doc as consumed even if rendering fails. Flipping after ensures the frontmatter state reflects reality: only documents that actually produced instructions are marked as consumed.

## Processing Order: Suggestions, Then Fan, Then MOC Proposals

WHY: Suggestions docs are the most common input and fan companions depend on a prior suggestions doc's parse context (the --fan-resolve-file flag merges fan resolutions into the primary doc's parsed output). Processing suggestions first ensures the primary parse is available if a fan companion needs it. MOC proposals are independent and processed last because they are the least common input type.

## Coverage Audit Is Mandatory and Blocking

WHY: The instructions-diff.py audit verifies that every approved suggestion has a corresponding instruction (and vice versa). A prior version of the pipeline reported success without this check, and users discovered missing items only when trying to apply instructions. Exit 1 from the audit stops the pipeline immediately — the conductor reports the diff verbatim and does not continue to the next doc. This catches producer bugs (in instruction-render.py) before they reach the user.

## stderr Discipline STRICT Block

WHY: All pipeline scripts print operational status and warnings to stderr. Appending `2>&1` to a stdout-captured command merges those log lines into the JSON output file before the JSON blob. The script exits 0 because it succeeded, so the parse failure only surfaces on the next pipeline step's json.load call. This failure mode was observed in production (the `feedback_never_redirect_stderr_into_json` memory entry). The STRICT block is warranted because LLMs repeatedly default to `2>&1` unless explicitly forbidden.

## Per-Doc-Type State Transitions

WHY: The state-promoter requires the exact doc_type as a positional argument because the state machine defines different transitions per type. suggestions and suggestions-fan share the same transition (pending-approval to approved) but are distinct doc_types in the schema. moc-proposal uses a different transition (pending-accept to accepted). Passing the wrong doc_type causes the promoter to reject the transition. The conductor lists all three variants explicitly to prevent the LLM from generalizing "just pass suggestions for all of them."

## Coverage-mismatch STRICT Guard (v0.8.2)

WHY: The coverage audit (`instructions-diff.py`, the coverage audit step) is a hard gate — exit 1
means the rendered instructions do not reconcile with the approved suggestions.
On the 2026-06-27 capture-delete live walk the conductor hit a real exit-1
mismatch (the coverage checker had not yet learned about tag-handler
`delete_source` actions) and, instead of stopping, went into debug-and-fix mode:
it read the pipeline source and started editing `instructions-diff.py` mid-run to
make the audit pass. The user aborted it. Two harms: (1) editing the **instance**
copy of a script is silently reverted on the next `update-tomo` (version-gated
sync), so the "fix" evaporates; (2) self-patching source to silence an audit
hides the very coverage gap the audit exists to surface. The pre-existing rules
("never proceed past a mismatch", "do not continue to the next doc") did not
explicitly forbid *fixing the code*, and the LLM generalized "resolve the
mismatch" into "patch the script". The STRICT guard now states the boundary
directly: on a mismatch, report the diff verbatim and STOP — never edit, patch,
or create Tomo scripts/code/schemas/config. Diagnosing or fixing the pipeline is
the user's call, out of scope for a synthesis run. The actual coverage gap was
fixed separately by teaching `instructions-diff.py` the fourth delete_source
source (tag-handler group sources), keyed by the same `group_id` the renderer
uses; the conductor also now passes `--groups-dir tomo-tmp/tag-handler-groups`.

## Pass-2 JSON-only precedence for `_suggestions.json` (ADR-026)

WHY (Marcus's rule): "if Hashi edited the JSON, use ONLY the JSON; otherwise ONLY
the markdown — never a mix." So Step 3a always parses the `.md`, but when the
entry carries a `wire_cache_path` and that JSON was edited (its embedded
`emit_digest` no longer matches a recomputation over the editable payload), the
parser discards the markdown result and rebuilds its ENTIRE output from the wire
alone (`build_from_wire`) — confirmed notes, skips, proposed MOCs, daily updates,
tag-handler approvals, fan-resolutions. There is no field-level merge/override;
an unchanged / absent / unparseable / unknown-version JSON ⇒ the markdown path is
byte-for-byte unchanged (the no-Hashi guarantee). This is why the wire must be a
COMPLETE mirror — a partial JSON would drop whatever it omitted.

WHY the two paths provably agree on the default case: a golden test asserts
`build_from_wire(unedited wire) == parse(markdown)` for the same doc (including
daily + tag-handler). The wire's daily/tag-handler sections are mirrored by
parsing our own rendered markdown, so they are the parser's own output shape.

WHY the conductor reads a cached sibling instead of Kado directly: the conductor
has only the Bash tool and reads pre-cached bodies. `inbox-triage.py` fetches the
`_suggestions.json` sibling via the Kado file op (`read_file_bytes` — the note op
is `.md`-only) and caches it next to the `.md`, exposing `wire_cache_path` on the
approved-suggestions entry. A missing sibling (older doc / no Hashi) simply omits
the field, and the parser uses the markdown path. The JSON-only path is gated to
the primary flow (`--fan-resolve-file` absent) so the XDD-012 fan-resolve path is
untouched.

## Step 4 Relays the Sanitized Markdown Notice for a Withheld Delete, Never Stderr (v0.17.0, 2026-09-18; superseded v0.18.0, 2026-09-18; v0.18.0's own relay file superseded v0.19.0, 2026-09-18 — see below)

WHY: a live run on 2026-09-18 exposed two problems in the same withdrawal. The
user ticked "Delete [[Laufrunde Elbufer]]"; the daily note it depended on did
not exist, `filter_missing_daily_notes` dropped the paired daily actions, and
`withdraw_unjustified_deletes` correctly withdrew the delete (spec 036 working
exactly as designed — the note survives). Two things then went wrong: (1) the
coverage audit halted on a false `delete_source expected=2 actual=1 [DIFF]` —
fixed separately by `instructions-diff.py`'s `_subtract_withdrawn_deletes`
(tests/test_036_t4_4_withdrawn_delete_coverage.py); (2) **the user never
learned the delete was withheld.** They apply via the Hashi plugin and no
longer read the instructions markdown — the conductor's chat summary is their
only surface, and Step 4 said nothing about withdrawals.

The first fix considered was wrong: relay `instruction-render.py`'s stderr
withdrawal block (or the raw `tomo.delete_withdrawals` JSON) into Step 4's
report. Both carry action ids and guard function names
(`filter_missing_daily_notes`, `I05`) by design — that surface is for a
maintainer debugging the run, not the user. Relaying it verbatim into chat
would reproduce the exact ADR-11 leak ("no executor internals in the rendered
text") through a different door.

`render_md.py` renders a withdrawn delete as a plain-language bullet under
BOTH "## Skipped" (Change 2) AND "## Source Deletions" itself (Change 3b) —
"[[Note]] was **not** deleted — <plain reason>", sourced from
`describe_withdrawal_cause_for_user` (render_helpers.py), which by
construction never emits an id or a guard name. That much is unchanged.

**v0.17.0's relay mechanism was wrong, and its own commit message named the
weakness**: Step 3e grepped `tomo-tmp/rendered/instructions.md` for the
sanitized line after each entry and told the conductor to "record every
matching line verbatim, for every entry, before moving to the next" —
because `instruction-render.py` is always invoked with the fixed
`--output-dir tomo-tmp/rendered`, so that file is overwritten by the NEXT
entry's 3b. A Pass 2 run processing N approved docs therefore made the
notices from entries 1..N-1 survive only in the conductor's own
conversational memory, on a haiku-tier agent, across an arbitrary number of
intervening tool calls. That is the "works in today's single-entry run" trap
this repo has hit before: "prefer deterministic rendering over LLM assembly"
and "an agent definition's rules are not what the LLM actually does" both
apply here, and a memory-dependent relay across iterations is precisely the
thing the user's original requirement ("otherwise it might get lost") was
naming.

**v0.18.0 makes the relay deterministic instead of mnemonic**:
`instruction-render.py` now writes each entry's already-sanitized notices
(the exact same `_render_withdrawn_delete_notice` string, called a second
time — not re-derived, so the two surfaces cannot drift) to
`tomo-tmp/withheld-deletes.md`, a RUN-LEVEL file living one directory above
`--output-dir` so it is never touched by the per-entry overwrite that broke
v0.17.0. It is append-only across the several `instruction-render.py`
invocations one Pass 2 run makes (entry 2 does not erase entry 1), keyed on
the `--run-id` every 3b call already threads: a call whose run-id matches
what the file's own header (its invisible first line) already carries
appends; a call whose run-id does not match starts the file over, because
that means a NEW `/inbox` run has begun and the previous run's notices must
not leak into it — deleting the file outright when the new run's own entry
has nothing to add, so Step 4 never finds an empty or a stale file. Full
mechanism and the staleness rule's reasoning: `sync_withheld_deletes_file` in
`docs/tomo/scripts/instruction-render.md`.

Step 3e's grep-and-remember instruction is gone entirely — there is nothing
left for it to do, and nothing left for the conductor to hold in memory
across entries. Step 4 reads `tomo-tmp/withheld-deletes.md` exactly once,
after the whole work list has processed, and relays it if present. This
follows the same two standing rules v0.17.0 invoked, better satisfied: "docs
in the script, not the agent" (the file itself, not a remembered grep
result, is now the script's deterministic output) and "deterministic
rendering over LLM assembly" (the conductor now needs no cross-iteration
memory of this fact at all — a single stateless read at the end).

Per this repo's CLAUDE.md ordering rule ("docs/tomo/<mirrored-path>.md is the
WHY-persistence layer... write to docs/tomo first, strip/add to runtime
second"), this section was rewritten before the Step 3e/Step 4 edit it
documents.

## Step 4's `cat` Was Relaying a Header Line Into Chat (v0.19.0, 2026-09-18)

WHY this exists: code-quality review of v0.18.0 caught a Critical. Step 4's
own prose (above) claimed `tomo-tmp/withheld-deletes.md`'s "lines are
already-sanitized user-facing notices" and told the conductor to "append the
file's lines verbatim … one per line." Both statements were false for line
1: `instruction-render.py` wrote the run-scoping marker,
`<!-- run_id: <RUN_ID> -->`, as that file's first line. A `cat` followed by
"relay every line" therefore put a raw internal identifier into the user's
chat report on every run with a withheld delete — the exact ADR-11 leak this
whole Step 4 change exists to prevent, reintroduced by the fix itself.

WHY the fix is not "tell Step 4 to skip line 1": that was the review's other
option, and it was rejected. A `tail -n +2` instruction (or "remember the
file has a header") makes the file correct only if the reader follows that
instruction — and Step 4 already proved, by shipping `cat` without it, that
an instruction is not a strong enough guarantee for a haiku-tier agent that
has no reason to suspect its input needs trimming. The chosen fix instead
moves the run marker out of `tomo-tmp/withheld-deletes.md` into a sidecar
file (`instruction-render.py`'s `sync_withheld_deletes_file` — full mechanism
in `docs/tomo/scripts/instruction-render.md`, "Run Marker Moved to a
Sidecar"). `tomo-tmp/withheld-deletes.md` now contains ONLY notice lines, so
Step 4's `cat` is correct by construction and its own prose claim is true
without qualification — no reader discipline required.

WHAT changed in Step 4 itself: nothing about the `cat` command or the
relay-verbatim instruction — those were already correct, given a file that
actually contained only notices. What changed is which file that is: the
run identity that Step 4 never needed to read now lives entirely in
`tomo-tmp/withheld-deletes.run_id`, a file Step 4 does not touch.

## Coverage Audit Moved Before Upload and State Flip (v0.20.0, 2026-09-18)

WHY: Step 3's order was 3a parse → 3b render → 3c upload → 3d flip source
state → 3e coverage audit. The STRICT stop on a mismatch ("do not continue
to the next doc") only ever protected documents AFTER the one that failed —
by the time 3e ran, 3c had already uploaded the rendered instructions into
the vault and 3d had already flipped the source doc to its terminal state.
A gate that runs after delivery has already happened is not a gate; it is a
complaint filed after the fact.

This was observed live on 2026-09-18: a run halted on a coverage mismatch
(later found to be a false positive) and the container agent reported "it
did not write instructions." The instructions were, in fact, already
uploaded to the vault at `state: pending-apply` — reachable by the Hashi
plugin before the user ever read the stop message. Nothing in the pipeline
required this order: the audit reads `tomo-tmp/parsed-suggestions.json`
(3a's output), `tomo-tmp/rendered/instructions.json` (3b's output), and the
run-level `tomo-tmp/tag-handler-groups` — it has no dependency on the
upload or the state flip.

The fix reorders Step 3 to 3a parse → 3b render → 3c coverage audit → 3d
upload → 3e flip source state. Content and STRICT language of each step are
unchanged — only the position and the letters moved. Because the audit now
runs first, its STOP naturally prevents 3d and 3e from ever running for the
current entry: nothing is uploaded, and the source doc's frontmatter stays
at `FROM_STATE` (e.g. `pending-approval`) instead of being flipped to
`TO_STATE` (`approved`).

WHY the STOP still bypasses Step 4 entirely, unchanged by the reorder: the
STRICT instruction ("you STOP and report the diff verbatim ... and stop —
do not continue to the next doc") is a terminal action inside the Step 3
loop, not a condition Step 4 checks. Step 4 ("Report") is only reached after
"Repeat 3a–3e for the next entry in the work list" runs out of entries — a
halted run never gets there. This was already true before the reorder; what
changes is what has (and has not) happened by the time it fires. One
consequence worth naming explicitly: `instruction-render.py`'s
`sync_withheld_deletes_file` (called inside 3b, unconditionally, for every
entry that renders a withdrawn delete) writes to the run-level
`tomo-tmp/withheld-deletes.md` BEFORE 3c's audit runs. So on a halt that
file can already exist — but because Step 4 is never reached, its "relay
every line" instruction never fires either. Nothing about a halted, only
partially-rendered run gets surfaced as if it were a completed one.

WHY the retry behaviour is an improvement, not just a side effect: with the
state flip now gated behind the audit, a halted entry's source doc keeps
its pre-synthesis frontmatter state (`pending-approval` for suggestions,
`pending-accept` for MOC/garden-audit docs) with the user's approval marker
still ticked in the body. `inbox-triage.py`'s pending-approval query
(`tomo.state=pending-approval`) and `_RE_APPROVED` check re-admit that doc
into `approved_suggestions` on the very next `/inbox` run; since no
instructions were uploaded, `compute_coverage`'s `covered_paths` does not
include it, so it lands back in `to_process` and `determine_action` returns
`synthesize` again. Before this fix, the same halt still left the doc
flipped to `approved` (3d had already run), so `to_process` came back empty
and `determine_action` fell through to `idle` with reason "All approved
items already covered by existing instructions" — literally true (an
instructions doc existed) and completely misleading (the run had reported
failure). The reorder turns a silent dead end into an automatic retry.

Note on step letters in this file: this reorder is commit `4350ddd`
(2026-09-18), which moved the coverage audit from step 3e to step 3c (and
upload/flip from 3c/3d to 3d/3e). Sections above this one that were written
before that commit — e.g. "Coverage-mismatch STRICT Guard (v0.8.2)",
"Step 4 Relays the Sanitized Markdown Notice…" — describe the mechanism
using the step letters in force at the time of writing and are historical
records, not present-tense claims; do not read a "step 3e" in those
sections as today's coverage audit.

## garden-audit parser call passes --stamp-pushback (v0.16.0, 2026-07-23)

WHY the conductor's garden-audit invocation (and only this invocation) carries
`--stamp-pushback`: the conductor's parse IS the Pass-2 apply path — the one place where a
ticked Acknowledge is a user-confirmed decision. Read-only parser invocations (tests, diffs)
must not write the ledger, so the flag is opt-in at the call site rather than default-on in the
script. The relay instruction for the `stamped N acknowledged advisory(ies)` stderr line exists
because the stamp is otherwise invisible to the user — the confirmation belongs in the /inbox
summary.

## Step 4 Relays a Second File for a Withheld Attachment (spec 038 T4.5, v0.21.0)

WHY Step 4 now `cat`s `tomo-tmp/withheld-attachments.md` as well, under the same
rules as the delete relay above and not as a variation on them.

The gap this closes is the same one, one decision over: a withheld attachment
was reported on the wire, in `instructions.md` under "**Attachments still in the
inbox**", and as a `[warn]` line on stderr — and in none of the three places the
owner reads first. A skip is not an error, so `instruction-render.py` exits 0 and
Step 3b treats exit 0 as plain success; the report listed the document count, the
coverage audit, drift warnings and withheld *deletes*, and nothing about an
attachment left behind. Measured 2026-10-03. The owner's loop depends on the
missing step: see it in the shell, go back to the instructions document, change
the decision, re-run `/inbox --pass2 --force`.

Everything about the mechanism is inherited rather than re-decided, and the
reasons are in the delete-relay sections above — the file holds only already-
sanitized user-facing lines (no run id, no header, no internals), the run marker
lives in a `.run_id` sidecar Step 4 never touches, a file absent means there is
nothing to relay, and the lines are appended verbatim as the last lines of the
report. The writer is the same function:
`instruction-render.py`'s `sync_withheld_deletes_file` was generalised to
`sync_notice_relay_file` and each caller owns a distinct path, so the two relays
share one set of staleness semantics without contending.

### WHY the Prohibition Had to Be Widened, Not Just Repeated

The delete relay already forbade substituting the stderr withdrawal block or the
raw `tomo.delete_withdrawals` JSON, because an earlier version of this agent did
exactly that. The same prohibition now names the attachment path's own two
tempting substitutes — the stderr `[warn]`/`[attach]` lines and
`tomo.skipped_assets` — because a prohibition that lists only the delete surfaces
reads as satisfied by any attachment surface. The sanitising lives in a script,
where it is testable, rather than in an instruction asking the model to summarise
internals.

**`Never count them.`** The no-count ruling `[ref: PRD/C1]` is argued twice in
`render_md.py` and T3.4's undercount is the evidence; one line per withheld
attachment satisfies C1's intent without re-opening it. It is stated in the
runtime prompt because a model asked to report a list of notices will otherwise
summarise it as a number, which is the single most likely way this relay gets
quietly undone.

### WHY This Instruction Has a Wiring Guard and No Output Test

Explained once in `docs/tomo/scripts/instruction-render.md`, under "Why Step 4
Gets a Wiring Guard and Not an Output Test". That file is canonical because it
owns the `WITHHELD_DELETES_RELAY` / `WITHHELD_ATTACHMENTS_RELAY` constants the
guard compares this prompt's `cat` path against.

The one thing to carry away without following the link: a missing `cat` does not
error — it reports nothing withheld, which is indistinguishable from a clean run.
`TestAgentWiringGuard` pins this file's path to the writer's so that renaming
either alone fails. The executable check on the report itself is Phase 5's live
run.

## Step 4 Also Relays Attachment Targets That Could Not Be Checked (spec 039 T5.1, v0.22.0)

WHY `tomo-tmp/withheld-attachments.md` now carries a second kind of line, and
why Step 4's wording names it instead of describing the file as "attachments
left in the inbox" only.

Spec 039 ADR-8 (owner ruling 2026-10-12): when Kado cannot answer whether a
target folder already holds the attachment's name, Pass 2 still writes the move
— a failed move is safe for the origin, because the origin's delete waits for
it (ADR-10) — but the target is reported as **not checked**. An unanswered
check is never reported as a free target (PRD F3-AC6). The owner reads the shell
first, and a target nobody checked is exactly what they need to see before
applying, so the line reaches the shell through the same relay file rather than
a new one: one writer (`sync_notice_relay_file`), one staleness rule, one `cat`.
Each line is the very line the move's block in `instructions.md` carries
(`render_md._render_unchecked_target_notice`, called twice), so the two
surfaces cannot drift.

The runtime prompt says "could not be checked" in Step 4 because the earlier
description — "one per attachment this run left in the inbox" — is false for
these lines: the attachment IS moved. A model told every line is a withheld
attachment would either drop the unchecked lines or report them as withheld.
The no-count rule (038 C1) applies to them unchanged.

**`--cost-history state/inbox-cost-history.jsonl` in Step 3b** (carried from
T4.5). `instruction-render.py` appends a Pass 2 entry with the folder-listing
and basename-search counters only when the flag is given; the flag defaults to
absent so host tests never write `state/`. Until the conductor passed it, C1-AC1
held only at the `main()` level and no live run recorded the counters. The path
is the same default the triage and reducer scripts write to
(`lib/cost_history.DEFAULT_HISTORY_PATH`), so all three passes land in one
history file.

## Step 4 Relay Lines Are Copied, Not Re-Told (spec 039 T6.3, v0.23.0)

WHY Step 4 carries a STRICT block for the two relay files, and why the relay
lines no longer sit inside the `>` report example.

The live Pass 2 run of 2026-10-13 showed the relay was not verbatim. The
conductor did `cat` both `tomo-tmp/withheld-deletes.md` and
`tomo-tmp/withheld-attachments.md`, then rewrote each line into its own bullet
("`freiberg-dom.png` — target already occupied ...") and dropped the sentence
that tells the owner what to do about it. The unadorned imperative ("append
every line verbatim") had been in place since v0.18.0 and was observed to fail,
which is the condition the repo sets for a STRICT block. Its `Why:` names only
the failure mode.

Two things changed. The STRICT block names both files, requires character for
character, one per line, and forbids rewording, shortening, merging,
summarising, tables and counts, plus dropping a sentence from a line. The
report example no longer shows the two `<every line from ...>` placeholders
inside the blockquote: a blockquote line reads as template prose to fill in,
which invites exactly the paraphrase seen. The lines are now introduced after
the example as text to output, not text to compose.

This is the first of two paraphrase layers; `/inbox` Step 3b reworded the
conductor's report a second time (see `docs/tomo/dot_claude/commands/inbox.md`).
The single source for the shell relay is SDD K16; traceability F2-AC5 is
"sentence + document + shell relay". The tests are in
`tests/test_039_t5_1_reporting.py`
(`test_the_conductor_relays_withheld_lines_character_for_character`).

## Every Report Carries the Audit's Own Words, No Internals, Relay Lines Last (spec 041 T3.1, v0.24.0)

WHY the conductor gains one report-level STRICT block governing every report
it returns — the Step 4 report and every stop report, including the 3c
coverage-mismatch stop — and what each of its three rules answers.

### The Observed Deviations

Spec 041's eval suite ran the conductor at 0.23.0 (byte-identical to `main`)
3 cases × 3 runs, against stub scripts that print bait an owner must never see
(`docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/baseline.md:7-13`; all `baseline.md` lines below are this file). The step order, the audit stop and the no-tamper rule
held in every run (`baseline.md:40`). Everything that failed was in the report
the conductor itself returned, not in the main session's relay of it
(`baseline.md:44`):

- **Run id in the report** — all 9 runs (`baseline.md:48`).
- **Working-file names, temp paths, a trailing `Files used:` block of absolute
  paths** — all 9 runs (`baseline.md:49`). The `Files used:` block is the
  defect the SDD's spike 3 first saw (`docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/README.md:44`).
- **Raw render stderr quoted** — `[warn] withdrew delete act-… (guard
  validate_destinations)` and `[attach] skipped_assets … action=act-…`, in every
  case, also when no relay file existed, sometimes followed by "please review"
  (`baseline.md:50`). Together with the two above: `9-no-leak` **0/3 in every
  case** (`baseline.md:24`, `:32`, `:38`). The mismatch case leaked too
  (`baseline.md:32`) — its report is the 3c STOP report, which never reaches
  Step 4, so a rule scoped to Step 4 alone would leave it red.
- **Headings between the relay lines** — e.g. `Withheld-attachment relay
  (…):` between the delete and the attachment lines:
  `4-deletes-then-attachment-last` **0/3** (`baseline.md:37`, `:51`).
- **Relay markup dropped** — the `- ⚠️ **…:**` prefix removed: the three
  verbatim graders **2/3** each (`baseline.md:34-36`, `:52`).
- **`RESULT:` line paraphrased** — `RESULT: OK, 1/1 actions reconciled.`, a
  comma for the em dash: `3-audit-result-in-report` **1/3**
  (`baseline.md:22`, `:53`). The SDD had not predicted this one
  (`baseline.md:53`).

The existing Step 4 STRICT (v0.23.0, section above) only forbids rewording the
relay lines and substituting stderr *for* them. Nothing forbade quoting stderr
*beside* them, nothing forbade a heading between them, and nothing governed the
`Coverage audit:` line or any stop report. The unadorned imperatives that did
exist ("report the diff verbatim", "the last lines of the report") were
observed failing — the repo's precondition for a STRICT block (root
`CLAUDE.md`, Rules).

### WHY the `Coverage audit:` Line Is the `RESULT:` Line Verbatim

The owner and the gate both read the audit's own words. `instructions-diff.py`
prints exactly one of two fixed lines (`tomo/scripts/lib/instructions_diff_report.py:276-283`);
a paraphrase — even a comma for a dash — is a sentence the audit never said,
and the owner cannot tell a reworded OK from a reworded FAIL by shape. PRD
F3-AC3 requires the line unchanged in the final message
(`docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/solution.md:830`), and the mismatch report's diff and `RESULT: FAIL` line are
required unchanged too (F4-AC3, `solution.md:835`). The runtime rule names the
dash, the numbers and the final period because those are what the model
changed.

### WHY No Internals — and What Is Exempt

ADR-11: no executor internals in user-facing text (spec 038 CON-6,
`docs/XDD/specs/038-every-editable-decision-reaches-the-wire/solution.md:107`;
substantive treatment `docs/tomo/scripts/lib/render_md.md:506-511`; spec 041
widened its leak guard on it, `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/README.md:45`). The conductor's report is the
owner's only surface for a Pass 2 run (section "Step 4 Relays the Sanitized
Markdown Notice…" above). A run id, an action id (`act-…`), a guard or function
name, a raw script stderr line, a working-file name, a path or a script name
tells the owner nothing they can act on and teaches them to skim the report.
The stderr surface is the maintainer's debugging trace by design (same section
above): copying it into chat duplicates an operation trace into a second store,
against the metadata-only rule for traces (Constitution L2, Privacy &
Security, `~/Kouzou/projects/miyo/miyo-constitution.md:41`), and returns fields
the reader does not need (Constitution L2, Performance, "only the fields the
AI actually needs").

Exempt, and named as exempt in the runtime rule: text the conductor is told to
copy as printed — the coverage audit's stdout on a mismatch (3c), the `RESULT:`
line, the drift warnings from Step 1, and the relay lines. WHY the exemption
must be explicit: the relay lines themselves contain paths
(`` `100 Inbox/whiteboard.png` ``) and a command (`/inbox --pass2 --force`) —
the stub kit words them as production does (`evals/_lib/stubs.sh:69-70`) —
and a real mismatch diff carries document paths and item ids. A literal-minded
haiku given "no paths" without the exemption would redact the very lines the
verbatim rules require, and in production could hide the coverage gap 3c
exists to surface.

WHY the garden-audit `stamped N acknowledged advisory(ies)` relay is reported
in plain words rather than exempted: its stderr line also carries the script
name and the pushback-ledger path (`tomo/scripts/garden-audit-parser.py:800-804`).
Step 4's example gains a `Stamped N acknowledged advisory(ies).` line, so the
confirmation still reaches the owner without either. Step 3a changed too: it
used to tell the model to relay that stderr line, which contradicts rule 2
(the line is not exempt). It now says only to note the count N for the Step 4
line, so no instruction anywhere asks for stderr to be reported.

WHY rule 4 ("In the Step 4 report, NEVER add a line that is neither in the
example above nor a relay line") exists: it is the catch-all that makes rules 2
and 3 enforceable against lines no one predicted. The baseline saw the model
close the report with "Please review them before relying on this run's output."
(`baseline.md:50`), a sentence that is neither internals nor a relay line, so
rules 2 and 3 alone name nothing to refuse it by. Rule 3 forbids text after the
relay lines only when relay lines exist; rule 4 covers the report with none.
`4-no-notice-when-none-withheld` (`baseline.md:23`) grades exactly that case.

WHY only two touches outside Step 4: the 3c pointer sentence (the mismatch
stop never reaches Step 4, so it must send the model to the block) and the 3a
sentence above (it contradicted rule 2). Everything else lives in the Step 4
block.

WHY a failed or rejected step is reported in plain words with its exit code:
the stop and partial-failure paths (3b exit 2, 3d exit 1/2, 3e exit 1/2) are
exactly where the model reaches for stderr. The owner needs which step and
that it failed; the stderr stays in the maintainer's trace.

WHY `<step>` is a closed list (parse, render, coverage audit, upload, state
flip) rather than "name the step": an open placeholder was filled by a literal
model with what it had at hand — the script names (`instruction-render.py`,
`upload-rendered.py`, …), which rule 2 bans. Five fixed words, one per
sub-step 3a–3e, leave nothing to improvise and still tell the owner where the
run broke.

### WHY a Failed-Step Line Names the Note (spec 041 T3.2, owner decision 2026-10-25)

Owner decision after code review on 2026-10-25: the failure line is
`<step> exited <code> for "<note>".`, where `<note>` is the source doc's note
name — the last segment of the entry's `path` (`VAULT_PATH`) from the routing
plan, without the folder and without `.md`.

WHY: with several approved docs in one run, 3d ("surface to user") and 3e
("report and continue") let the run go on past a failure, so a bare
`upload exited 1.` cannot say WHICH doc failed. Rule 2 bans paths and file
names, so before this change the model had no permitted way to identify the
doc, and the owner had to re-run blind. A note name is not an internal: it is
what the owner sees in Obsidian's file list and tab title, and it is the one
thing they need to find the doc again. The folder is dropped because it adds
nothing the owner needs to recognise the doc and would reintroduce a path —
the very thing rule 2 forbids and the leak guard
(`evals/_lib/no-leak.md`) watches for. The runtime says explicitly that the
note name is the ONLY doc identifier allowed in a report and is never a path,
so a literal model does not read the new placeholder as a licence to quote
the cache path, the vault path, or the parsed working files.

Leak-guard compatibility, checked with Python `re` against the canonical
pattern in `evals/_lib/no-leak.md`: a note name such as
`2026-10-24_1200_suggestions`, and the full line
`state flip exited 1 for "2026-10-24_1200_suggestions".`, match none of its
alternatives (its run-id alternative needs a `T…Z-<hex>` time part; its path
alternatives need a `/`).

### WHY the Step 4 Template Has Two Conditional Placeholder Lines

The Step 4 example carries two lines that appear only on a condition:

- `Stamped N acknowledged advisory(ies).` — only when the garden-audit parser
  in 3a reported stamped advisories (see "WHY the garden-audit … relay is
  reported in plain words" above).
- `<step> exited <code> for "<note>".` — only for a step that exited
  non-zero, one line per failure.

WHY the failed-step line is written as the line itself followed by the
condition in parentheses, not as `<only for …: <step> exited <code>.>`: the
earlier form nested angle brackets, so the placeholder's own delimiters
wrapped the line's placeholders, and a literal reader could print the outer
brackets and the condition text into the report. With the line first, what to
print and when to print it are visibly separate.

### WHY the Fenced Relay Example Shows Three Lines

The fenced `text` example below the Step 4 template shows three relay lines
because it mirrors the relay case the eval suite exercises: two withheld
deletes followed by one withheld attachment — deletes first, then
attachments, as rule 3 orders them. It is a shape, not a count: the model
copies however many lines the two files hold. When neither file exists there
is no relay output at all — rule 3 forbids saying anything about withheld
deletes or attachments — so the example never implies a minimum.

### WHY the Relay Lines Are Consecutive and Last

The owner reads the shell; the relay lines are the last thing they see before
deciding whether to apply (section "Step 4 Relays a Second File…" above: see
it in the shell, go back to the document, change the decision, re-run). A
heading between them splits one list into two and reads as a different kind of
notice; text after them — a `Files used:` block, a closing "please review" —
pushes them off the last screen and dilutes the remedy sentence each line ends
with. `4-deletes-then-attachment-last` encodes exactly this: deletes, then
attachments, one newline apart, then only whitespace to the end
(`tests/test_eval_conductor_cases.py:278-291`). With no relay file there is
nothing to relay and nothing to say about withheld items — the stderr bait
must not turn into a "please review" line (`4-no-notice-when-none-withheld`,
`baseline.md:23`).

### WHY One STRICT Carries All Three Rules

Owner decision: ADR-10 was widened on 2026-10-25 after this baseline from two
rules to three, carried by one block rather than two, "to keep the emergency
lever used once" (`docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/solution.md:796-800`). The `Why:` line names only the
observed failure modes. The new block must not name `withheld-deletes.md`:
`tests/test_039_t5_1_reporting.py:412-425` requires exactly one Step 4 STRICT
paragraph naming that file — the v0.23.0 relay block, whose `Why:` carries
"remedy" — so the two blocks stay separate and both stand.

WHY the block lives in Step 4 and 3c points to it, instead of a top-level
section: ADR-10 places it in Step 4, and `###` step headers are pinned by
`tests/test_synthesis_conductor_step_order.py`. The 3c STOP carries one line sending the
model to it, and the block's first line says
it governs every report, whatever step the run ends in.

### WHY the Relay Lines Name Their Literal Prefix and Forbid an Introduction (T3.2 iteration 2)

The first paid run on 0.24.0 (relay case, run 0) passed the leak, `RESULT:`
and ordering graders but failed twice in the relay block. First, the leading
`- ` was dropped from the second and third relay lines (`⚠️ **Not deleted:** …`
instead of `- ⚠️ **Not deleted:** …`), the same markup loss the 0.23.0 baseline
showed in 1/3 runs: "character for character" never told a literal-minded
Haiku that the `- ` is part of the line, and it read the first line's `- ` as
list formatting it could drop once the list "continued". Second, the model
wrote its own line before the block (`- [[…]] and [[…]] were withheld as shown
below.`), which rule 4 already forbade in the abstract — "a line that is
neither in the example nor a relay line" asks the model to classify its own
sentence, and it classified it as part of the relay. The wording change is the
smallest that names both shapes: the relay STRICT now gives the literal prefix
`- ⚠️ **` and says to keep the leading `- ` on every line, backed by a fenced
three-line shape example placed after the `> Pass 2 complete` blockquote (the
blockquote paragraph must carry no relay marker, `tests/test_039_t5_1_reporting.py:424`);
rule 3 of the report block now forbids, by name, any sentence that introduces,
announces or summarises the relay lines. No new STRICT block was added — both
changes adjust existing rules, and each `Why:` gained only the newly observed
failure mode.

### What Keeps This True

The three eval cases — `audit-gates-delivery` (RESULT verbatim, no notice when
none withheld), `audit-mismatch-stops` (the stop report), and
`withheld-notices-relayed` (verbatim, consecutive, last) — plus the shared leak
guard `evals/_lib/no-leak.md` run against every case, with stub bait that
prints a run id, action ids, guard names and stderr markers
(`evals/_lib/stubs.sh:84-85`). `scripts/run-evals.sh` is the gate; a prose
change to Step 3c or Step 4 that reintroduces any of the deviations above
turns it RED.

## A Failed Upload Holds the Flip; Nothing Is Written Outside the Report (#205, v0.24.1)

WHY Step 3d now spells out what happens after a non-zero upload exit, and why
rule 4 of the report STRICT now covers the whole reply instead of "the Step 4
report".

### The Observed Deviation

The paid baseline of 2026-10-26 ran conductor 0.24.0 against the new case
`evals/upload-failure-reported`, whose upload stub exits 1 (partial failure)
and prints Kado failure detail on stderr. The flip was held in all three runs
(`2-no-state-flip-after-failed-upload` 3/3), and the failed-step line
`upload exited 1 for "2026-10-24_1200_suggestions".` was in the blockquote
report every time. But in 2 of 3 runs the conductor wrote text outside the
blockquote: a preface ("Pass 2 is partly done…"), a section headed "Notes for
you, outside the report:", the failure detail ("HTTP 503 from Kado after 4
retries", "Service Unavailable"), the full `state-promoter.py flip` command
line with vault path and run id, a "Run ID:" bullet, a working-file name
(`tomo-tmp/withheld-deletes.md`) and "Next step" advice.
`5-no-failure-detail-in-report` and `9-no-leak` failed in those runs; the clean
run returned only the three report lines.

Two sentences in the prose invited it:

- 3d said "Exit 1 = partial failure (surface to user, do not retry batch)".
  "Surface to user" reads as "explain it", and nothing said whether 3e runs
  after it, so the model reasoned about the flip in prose and handed the owner
  the command to finish it.
- Rule 4 said "In the Step 4 report, NEVER add a line …". A literal model read
  "the Step 4 report" as the blockquote, so everything before and after the
  blockquote seemed outside the rule.

### WHY a Failed Upload Skips the State Flip

Owner decision (#205): after ANY non-zero exit of `upload-rendered.py` for an
entry, 3e does not run for that entry, nothing is retried, the failure is
reported only as the failed-step line, and the run continues with the next
entry. A flipped source doc says "this was delivered": with instructions
missing from the inbox, the flip would hide the gap — the next `/inbox` would
treat the doc as done and never deliver them. Left `pending`, the doc is
picked up again by a later run, which retries the upload. Retrying inside the
run is not the conductor's call: the upload script already retries a
rate-limited Kado write itself, and a second batch attempt would rewrite the
files that did land without fixing what made the others fail.
Exit 2 (bad input) is covered by the same rule — nothing landed or the input
is broken, so a flip would be just as false.

A failed flip (3e non-zero) keeps its meaning: it is reported only as
`state flip exited <code> for "<note>".` and the run continues. 3e now points
at that line instead of a bare "report", so the model has one shape for both
failures.

### WHY the Report Rule Now Covers the Whole Reply

The conductor's reply is the report: the main session relays it verbatim and
the owner reads nothing else. A rule scoped to "the Step 4 report" left a
gap the model used — the same internals rule 2 bans inside the report came
back as "notes" outside it. Rule 4 now says the reply as a whole is only the
report and names the observed shapes (preface, notes, explanation of why a
step failed, next steps, command, run id, file name), because rule 2's
abstract ban was already in force and did not stop them.

### WHY No Failure Detail

ADR-11: no executor internals in user-facing text (see "WHY No Internals"
above). The owner needs to know which step failed for which note — that is
what the failed-step line carries, and it is enough to act: re-run Pass 2 for
that doc. The HTTP status, the retry count and the Kado message belong to the
script's stderr and logs, the maintainer's trace; copying them into chat
duplicates an operation trace and reads as something the owner must fix.

### What Keeps This True

`evals/upload-failure-reported` (failed-step line present, no flip after the
failed upload, no failure detail, no leak) and
`evals/state-flip-failure-reported` (failed-step line for the flip, no failure
detail, no leak). Both stub kits print failure bait on stderr, so a reply that
explains the failure outside the report turns the gate RED.

## The Stop Report Is Never Announced (spec 043 F5, v0.24.2)

WHY the "reply is ONLY the report" ban is its own rule of the report STRICT,
names the 3c stop report, and why 3c says where the stop report starts.

### The Observed Deviation

The spec 043 full suites of 2026-10-31 (claude 2.1.316, conductor 0.24.1) ran
`evals/audit-mismatch-stops` nine times. In 2 of 9 runs `7-report-only-mismatch`
was red: the hand-back frame began with the conductor's own sentence, then a
blank line, then the audit's stdout:

```
The coverage audit reported a mismatch, so I'm stopping here. The suggestions doc was not uploaded and its state was not flipped.

COVERAGE-GAP-91c2: suggestion s1 has no matching instruction (expected 1, found 0)
RESULT: FAIL — count or coverage mismatch above.
```

The second occurrence was kept (`findings.md`, "Full suite 2"). This is the
#205 deviation — text outside the report — on the stop path instead of the
failed-delivery path.

### WHY Two Existing Rules Did Not Stop It

- 3c said the stop report is "the audit's stdout copied as printed, and nothing
  else". "Nothing else" describes the report's content; the model wrote the
  preface as a frame around the report, not as part of it.
- Rule 4 said "Your reply is ONLY the report: NEVER write anything before or
  after it", but the sentence sat inside a rule that opened with "In the Step 4
  report". The #205 fix widened the ban to the whole reply, yet left it under a
  Step-4 label, so a literal model could read it as applying only to the Step 4
  blockquote and not to a stop in 3c.

### WHY the Ban Became Its Own Rule

The ban on writing anything before or after the report is now rule 5, separate
from rule 4 (no extra line inside the Step 4 report). Rule 5 names every report
it covers — the Step 4 report, the 3c stop report, any other stop — so no step
label scopes it, and it names the observed shape ("NEVER announce, explain or
summarise the stop") next to the #205 shapes. 3c now says the reply starts with
the audit's first stdout line, which gives the model a positive anchor for the
first character of the reply instead of only a negative rule. The STRICT's
`Why:` gained the stop-path preface as one more failure mode. No new STRICT
block was added: the change splits an existing rule.

### What Keeps This True

`evals/audit-mismatch-stops` grader `7-report-only-mismatch` (the hand-back
frame holds nothing but the audit's stdout) and the canary `8-handback-canary`.
The mutation `status-sentence-first` removes the ban and the 3c anchor and
injects a status sentence, so the grader goes red on it.

## The Conductor Runs on Sonnet (spec 043 T4.3, v0.25.0)

WHY the frontmatter says `model: sonnet` instead of `model: haiku`.

### The Observed Deviation

The spec 043 merge evidence of 2026-10-31 (three full suites on candidate
`e9127610`, claude 2.1.316, conductor 0.24.2 on haiku) was RED in suite 2:
`state-flip-failure-reported` and `upload-failure-reported` each failed
`7-report-only` in one run. Both hand-back frames began with the conductor's
own sentence before the report:

```
Pass 2 did not finish cleanly: the state flip for the one approved doc was rejected, so its state is still `pending-approval`.
```

```
Pass 2 synthesis did not complete. The Step 4 report is below.
```

A full suite earlier that day was RED on `audit-mismatch-stops`
(`7-report-only-mismatch`) in the same way. That makes three occurrences on one
day, after rule 5 of v0.24.2 had already split the ban into its own rule and
named the stop shape. Across the day's suites the preface appeared in about 1
of 20 Pass 2 runs, so about every second full suite went RED.

### WHY a Model Change, Not More Prose

Rule 5 already says, in a STRICT block with a `Why:` naming this shape, that
the reply is ONLY the report and that the model NEVER announces, explains or
summarises the stop. The deviation persisted. Each earlier prose iteration
(#205 in v0.24.1, F5 in v0.24.2) lowered the rate but did not remove it. A
further rewording would cost another round of paid suites with no evidence it
would hold. The owner chose sonnet over another prose iteration. The cost per
Pass 2 run rises, and the gate's measured cost per full suite rises with it.

The older sections above that say "haiku-tier agent" describe the model the
rule was written for. They still apply: every rule written for the literal
haiku reading stays in the runtime file.

### What Keeps This True

`evals/*-failure-reported` grader `7-report-only`, `evals/audit-mismatch-stops`
grader `7-report-only-mismatch`, and the canary `8-handback-canary`. The
mutation `status-sentence-first` must stay red on sonnet; `red-proofs.md` of
spec 043 records the re-proof.
