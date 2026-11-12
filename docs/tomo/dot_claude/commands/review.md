# WHY: review (command)

> Rationale for decisions in `tomo/dot_claude/commands/review.md`.
> Spec 045 (issue #31, `docs/XDD/specs/045-weekly-monthly-review/`). The flow itself is explained in
> [periodic-review](../skills/periodic-review.md).

## Command Is a Thin Shim Over the Skill (ADR-1)

WHY: The `/review` command file only hands `$ARGUMENTS` verbatim to the `periodic-review` skill. It parses nothing:
`review-session.py start` reads the argument (`W13`, `2026-W13`, `2026-03`, `month`, `setup`, an `@`-picked note)
under the configured week rule and name formats, because a prose "if the first token is `month`" depends on the model
reading it right, and the same argument means different periods under different week rules (ADR-7). Anything else in
the command file would be a second copy of the flow that drifts from the skill. Same pattern as
[note](note.md) and [hashi-hook](hashi-hook.md): one source of truth in the skill, a discoverable `/` entry point in
the command.

## Why /review Runs in the Main Session, Never as a Dispatched Subagent

WHY: The flow asks the user at several points — the setup confirmation, the week question, start over, Deliver or
Abort, resume or drop — and every answer is the user's next message (see
[Why Every Question Is Plain Text](../skills/periodic-review.md#why-every-question-is-plain-text-and-the-turn-ends-there)).
A dispatched subagent cannot ask the user and cannot use the Agent tool (Anthropic platform constraint), so a
`/review` run dispatched as a subagent would have to guess every answer. The command therefore invokes the skill
directly in the session the user is typing in. Revisit only if the platform lets subagents ask the user.

## Why the Name Is `/review`

WHY: The owner's word for the feature is "review" (weekly and monthly review), and the review document is
`<period> Review.md`, so the command carries the same word. Claude Code's built-in review command is `/code-review`,
so no collision was expected, and the owner confirmed in a `tomo-instance` container session (T5.2, 2026-11-12) that
a project `/review` is offered and not shadowed. Should a later Claude Code version shadow it, the fallback is a mod
or another name, decided by the owner, never a silent rename.

## Why the Shim Carries `argument-hint` but No Example List

WHY: The `argument-hint` in the frontmatter is what the `/` menu shows next to the command, so it names the argument
kinds in a few words (a period, `month`, `setup`, an `@`-picked note). It is a menu label, not help: the forms
themselves stay with `review-session.py start` and `tomo-help.md`, as the section above says.

## Why the Command Carries No Argument Help

WHY: The argument forms are owned by `review-session.py start`, which answers an unusable argument with
`error.kind` (`invalid-period`, `unfinished-period`, `not-periodic-note`, `unknown-argument`), what it `expected` and
one `example` (PRD F2-AC5 to F2-AC7). The skill shows exactly that, so the user learns the forms from the script's
answer. A help text in the command file would be a third copy of the forms (after the script and `tomo-help.md`) and
the first one to go stale.
