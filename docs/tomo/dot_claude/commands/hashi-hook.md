# WHY: hashi-hook (command)

> Rationale for decisions in `tomo/dot_claude/commands/hashi-hook.md`.

## Command Is a Thin Shim Over the Skill

WHY: The `/hashi-hook` command file only invokes the `hashi-hook-author` skill and forwards an optional behavior description. All workflow logic — disclaimer, path resolution, Kado probe, design, classification, inbox emission — lives in the skill. Duplicating any of those steps in the command would drift from the skill after the skill is updated, causing false-start invocations. The shim pattern keeps a single source of truth (the skill) and gives the user a discoverable `/`-entry point without a parallel copy of the flow.
