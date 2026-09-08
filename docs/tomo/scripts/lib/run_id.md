# WHY: lib/run_id.py

> Rationale for decisions in `tomo/scripts/lib/run_id.py`.
> Only non-obvious decisions are recorded here.

## WHY the Format Moved Out of `run-id.py` (spec 034 T6.1)

`run-id.py` was the only minter of run ids, called by the skills before Pass-1
dispatch. T6.1 added a second: `inbox-triage.py` records its own cost-history
entry for the three actions that terminate before any skill has minted one
(`idle`, `synthesize`, `transcribe`), and that entry needs a run id.

Re-deriving `YYYY-MM-DDTHH-MM-SSZ-<6 hex>` in the second caller would put the
identity format of every run artefact in two places. The generator moved to
`lib/`; `run-id.py` keeps its CLI unchanged and imports it.

## WHY Triage Mints Its Own Rather Than Sharing the Skill's

For the three triage-terminal actions there is no other id — the skill that
would mint one never runs. The two reducer actions (`suggest`, `fan-resolve`)
use the pipeline's run id, which reaches the entry through
`suggestions-reducer.py --run-id`, so each entry carries the id its own run
actually had.

WHY not a separate recording script: one existed (`record-run-cost.py`,
retired) and was invoked from a step in each skill's markdown. That made the
entry depend on an LLM executing that line, which no test can observe — and the
guarantee this history is for is that it accumulates *without anyone
remembering*. The reducer already runs on both paths as a plain process, so the
append happens there and the dependency is gone.
