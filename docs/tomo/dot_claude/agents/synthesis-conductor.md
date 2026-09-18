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
