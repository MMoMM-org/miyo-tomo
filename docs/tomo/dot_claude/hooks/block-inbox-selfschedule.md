# WHY: dot_claude/hooks/block-inbox-selfschedule.sh

The WHY layer for `tomo/dot_claude/hooks/block-inbox-selfschedule.sh`.

## Why it denies every ScheduleWakeup, not just the ones that mention inbox

The first version grepped `tool_input.prompt` for the word `inbox` and denied
on a hit. That caught the 2026-09-14 10:13 run, whose prompt read *"Check
whether the first batch of 5 inbox-analyst agents has completed."*

The 11:02 run scheduled a wakeup the hook let straight through:

    {"delaySeconds": 60,
     "reason": "Fallback check on batch-1 inbox-analyst dispatch …",
     "prompt": "<<autonomous-loop-dynamic>>"}

Same intent, same waste. The word `inbox` was in `reason`; the hook only read
`prompt`, and `prompt` held a runtime sentinel. Widening the grep to cover
`reason` would only move the hole — the next phrasing decides whether the guard
fires, which makes the guard a lottery over wording.

The condition that actually holds is structural: **no Tomo workflow schedules a
wakeup.** Dispatched agents report back through task-notifications and the
harness re-invokes the conductor then; every other step is a synchronous script
call. So the hook denies the tool outright and inspects no strings.

`stop: true` stays allowed. Cancelling a wakeup is never the problem, and a
session that scheduled one before this hook reached it must still be able to
clear it.

## What it costs when it does not fire

Nothing breaks — both runs cancelled their own timer a few turns later, the
11:02 one with *"That wakeup tool was the wrong one for this (it's for
`/loop`)"*. The cost is a 77-second pause in the middle of a fan-out, a
no-op `true` Bash call to fill the wait, and a red `Error:` in the user's
terminal during an otherwise healthy run.

## Guard

Exercised by hand against the real payloads from both runs plus an unrelated
one, and the `stop: true` allow case. Not covered by pytest: the hook is shell,
invoked by the Claude Code runtime with JSON on stdin, and the suite has no
harness for that shape.
