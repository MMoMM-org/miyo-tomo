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
