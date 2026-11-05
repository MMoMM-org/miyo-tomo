# WHY: note (command)

> Rationale for decisions in `tomo/dot_claude/commands/note.md`.
> Spec 044 (issue #169). The flow itself is explained in [note-from-template](../skills/note-from-template.md).

## Command Is a Thin Shim Over the Skill

WHY: The `/note` command file only hands `$ARGUMENTS` to the `note-from-template` skill. Argument parsing
(`--process <template>` against a free-text request) does not happen here either: `note-session.py start`
parses it (ADR-6), because prose branching on a flag depends on the model. Anything else in the command
file would be a second copy of the flow that drifts from the skill. Same pattern as
[hashi-hook](hashi-hook.md): one source of truth in the skill, a discoverable `/` entry point in the command.

## Why /note Runs in the Main Session, Never as a Dispatched Subagent

WHY: The flow asks the user questions (template choice, the question rounds, approval, name collisions) with
`AskUserQuestion`. A dispatched subagent cannot ask the user, and subagents cannot use the Agent tool, so
a `/note` run dispatched as a subagent would have to guess every answer. The command therefore
invokes the skill directly in the session the user is typing in. Revisit only if the platform lets
subagents ask the user.
