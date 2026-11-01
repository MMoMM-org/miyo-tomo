# vault-explorer — Why

Rationale for `tomo/dot_claude/agents/vault-explorer.md`.

## Step 7 emits only values the writer and the wire accept (#212)

WHY: Step 7 emitted `syntax: frontmatter` and `type: scale`, which
`vault-config-writer.py trackers` rejects, so one such field failed the whole tracker
write. It also emitted `task_checkbox`, which the writer accepts and the instructions
schema does not. The step now emits `checkbox`, and a 1-5 or 1-10 value becomes
`type: integer` with the separate `scale` key.

WHY frontmatter trackers are skipped and reported rather than converted: Hashi can
write `inline_field`, `callout_body` and `checkbox`, all of them in the note body. A
tracker that lives in frontmatter has no wire syntax, so configuring it would promise
updates Tomo cannot deliver. The report line keeps the skip visible.

`tests/test_tracker_value_sets.py` checks the values named in this step.

## Structure follows the repo's agent conventions (#44, v0.17.0)

WHY `## Workflow` keeps its name instead of becoming `## Activities`: the writing
agents here (`moc-architect`, `garden-auditor`) use `## Workflow`, and
`/explore-vault` tells the session to "execute its workflow". The audit's rename would
diverge from both without changing what runs.

WHY the `Agent` tool is gone: nothing in the file dispatches a subagent,
`/explore-vault` impersonates this agent in the main session, and a subagent cannot
use the tool anyway (platform constraint).

WHY `color: green`: green marks the agents that write artefacts; this one writes
`config/`.

WHY no `<example>` blocks: the description is loaded in every session, and this agent
is reached through `/explore-vault`, not by delegation, so examples would cost tokens
without helping it trigger.

WHY `## Output` describes rather than prescribes: it lists what Steps 9 to 10b already
produce. Fixing a new report block would change behaviour, which #44 excludes.

The file stays about 29 KB, over the 25 KB guideline. Moving steps into a reference
file changes what the model reads when, which needs a live `/explore-vault` run.
