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
