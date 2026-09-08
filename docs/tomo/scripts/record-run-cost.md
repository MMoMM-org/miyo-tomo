# WHY: scripts/record-run-cost.py

> Rationale for decisions in `tomo/scripts/record-run-cost.py`.
> The terminal cost-history step for the two actions that run the reducer.
> Only non-obvious decisions are recorded here.

## WHY a Script and Not a Line Inside `mark-captured.py` (spec 034 T6.1)

`mark-captured.py` is called from `suggest-handling` **only**;
`force-atomic-handling` ended at a Report step with no state-writing step at
all. Bolting the append to `mark-captured` would have recorded one of the two
reducer paths and silently recorded nothing for every `fan-resolve` run.

It also fails at the wrong time. `mark-captured` returns 2 before doing any
work when Kado is unreachable, and `suggest-handling` is instructed to proceed
to the report when it fails. A run that could not reach Kado still spent its
base and byFrontmatter calls; folding the measurement into the vault-write
script makes the record contingent on the write succeeding. A separate step
runs either way — `[ref: SDD/Error Handling]`: measurement must never fail a
run, and equally must not be lost to an unrelated failure.

Both skills call the same script, so the two reducer paths cannot drift apart.

## WHY It Reads Two Artefacts Instead of Being Told the Numbers

The figures come from two processes. Triage's metrics
(`item_count`, `base_kado_calls`, `kado_calls`) ride in
`routing-plan.json["metrics"]`; the reducer's destination-folder counts ride in
the suggestions document. Passing them as flags would mean the skill
transcribing numbers out of JSON by hand — the kind of step an LLM runtime gets
wrong silently, and the reason
`docs/tomo/scripts/suggestions-reducer.md` already prefers deterministic
threading over prompt-carried values.

`action` comes from the routing plan too, so the script needs no `--action`
flag that could disagree with what triage actually decided.

## WHY Every Failure Path Exits 0

The script is a measurement, invoked from a STRICT step near the end of a
successful run. A non-zero exit would make a skipped bookkeeping line look like
a failed Pass 1. A missing suggestions document costs the two folder fields; an
unreadable routing plan costs the entry. Both warn on stderr.
