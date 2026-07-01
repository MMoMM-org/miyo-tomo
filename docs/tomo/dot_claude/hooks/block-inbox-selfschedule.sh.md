# WHY: block-inbox-selfschedule.sh

PreToolUse hook on the built-in `ScheduleWakeup` tool. Denies any wakeup whose
`prompt` references `inbox`, with a message telling the model that `/inbox` runs
only on explicit user invocation.

## The problem it guards against

On 2026-07-01, a live container session self-triggered `/inbox`. During the
first `/inbox` run the model improvised a `ScheduleWakeup(270s, prompt:"inbox")`
call ("fallback heartbeat while synthesis-conductor runs"). When the wakeup
fired, `prompt:"inbox"` re-ran the **entire** `/inbox` command → re-triage →
re-ingestion of the Pass-2 rendered staging notes (`source_items 4 → 9`).

This is the *trigger* half of the problem surfaced in issue #108. #108's
proposed fixes (state-marker skip / registry skip) address the *symptom* — they
make re-ingestion harmless if it happens. This hook removes the trigger itself,
so the re-run never occurs.

## Why a hook and not a prompt guard

`ScheduleWakeup` appears **nowhere** in the Tomo runtime — every route in
`inbox.md` already ends in `Exit`. The plain `Exit` imperative was observed
failing to prevent the improvised wakeup. A PreToolUse hook is a hard,
plugin-independent stop the model cannot reason around; a prompt-level STRICT
block would be one more soft imperative competing with the same improvisation.

## Why scoped to `inbox`, not all ScheduleWakeup

The observed harm was the direct `prompt:"inbox"` self-reschedule. Generic
autonomous-loop heartbeats (`<<autonomous-loop-dynamic>>`) behaved correctly in
the same session (they idled and never re-ran `/inbox`), so they pass through.
Scoping to inbox-referencing prompts kills the observed trigger without
disabling `/loop`'s self-pacing outright. Broaden to an unconditional
ScheduleWakeup deny only if autonomous looping in the (proposal-only,
user-driven) container is judged undesirable in general.

## Contract

- Input: PreToolUse stdin JSON; reads `.tool_input.prompt`.
- Deny shape: `{hookSpecificOutput:{hookEventName:"PreToolUse",
  permissionDecision:"deny", permissionDecisionReason:"…"}}` on stdout, exit 0.
- Match: `grep -qi inbox` on the prompt. Non-matching prompts → exit 0, no output (allow).

Refs: issue #108 (Pass-2 re-ingestion), spec 027 (#33) live testing.
