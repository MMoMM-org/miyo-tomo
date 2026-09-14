# WHY: dot_claude/hooks/block-state-file-handwrite.sh

The WHY layer for `tomo/dot_claude/hooks/block-state-file-handwrite.sh`.
Created 2026-09-14, after a run in which five of twelve fan-out agents wrote
the shared state file by hand.

## What it denies, and what it deliberately does not

`tomo-tmp/inbox-state.jsonl` is appended to by every agent in a fan-out batch
while its siblings are appending too. `scripts/state-update.py` is the only
writer that understands that: it appends one schema-shaped record and nothing
else.

The hook denies a `Write` or `Edit` whose `file_path` ends in
`inbox-state.jsonl`, and a `Bash` command containing a shell redirect aimed at
it. It does not care about the tool otherwise.

Reading stays open on purpose. `cat`, `tail` and `grep` on the file are how an
agent checks its own record, and passing the path as an argument —
`state-update.py --state tomo-tmp/inbox-state.jsonl` — is the sanctioned write
path and must not trip on its own filename. That is why the Bash branch keys on
the redirect operator rather than on the filename appearing anywhere in the
command. `rm -rf tomo-tmp/items tomo-tmp/inbox-state.jsonl` in the skill's setup
step passes for the same reason.

## Why a hook rather than an instruction

The agent definition already says to use `state-update.py`. In the run that
prompted this, five agents did not — but that was downstream of a dispatch bug
that meant they never received the definition at all (see
`docs/tomo/dot_claude/skills/suggest-handling.md`). With `subagent_type` fixed
the instruction should be enough.

It is kept anyway, for two reasons. The failure it prevents is silent and
asymmetric: a `Write` to this file replaces entries other agents appended, and
nothing downstream notices, because the reducer and `mark-captured` key on
`done` records and simply see fewer of them. And the same session had already
shown that a `PreToolUse` denial stops a behaviour that a prompt only
discourages — the `ScheduleWakeup` guard fired correctly in the same run where
a prompt-level instruction was ignored.

The denial message names the exact command to run instead. A hook that only
refuses teaches an agent to find another way around.

## Guard

Exercised by hand against the eleven real commands from the 2026-09-14
transcript — the four hand-writes it must refuse and seven legitimate accesses
it must let through. Not covered by pytest: the hook is shell, invoked by the
Claude Code runtime with a JSON payload on stdin, and the suite has no harness
for that shape. If one is ever added, those eleven cases are the fixture.
