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

WHY: The coverage audit (`instructions-diff.py`, step 3e) is a hard gate — exit 1
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

## Step 4 Relays the Sanitized Markdown Notice for a Withheld Delete, Never Stderr (v0.17.0, 2026-09-18; superseded v0.18.0, 2026-09-18)

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

## garden-audit parser call passes --stamp-pushback (v0.16.0, 2026-07-23)

WHY the conductor's garden-audit invocation (and only this invocation) carries
`--stamp-pushback`: the conductor's parse IS the Pass-2 apply path — the one place where a
ticked Acknowledge is a user-confirmed decision. Read-only parser invocations (tests, diffs)
must not write the ledger, so the flag is opt-in at the call site rather than default-on in the
script. The relay instruction for the `stamped N acknowledged advisory(ies)` stderr line exists
because the stamp is otherwise invisible to the user — the confirmation belongs in the /inbox
summary.
