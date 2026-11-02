# WHY: obsidian-fields skill

> Rationale for decisions in `tomo/dot_claude/skills/obsidian-fields/SKILL.md`.

## Why there is no `frontmatter.strict` flag

WHY: The flag promised that Tomo refuses a note with missing required fields, or warns and proceeds. No script ever read it, and neither the installer nor a profile set it, so it was a switch with no effect. Removed in 0.1.2 rather than built, because a real gate would be new blocking behaviour in Pass 2 that nobody has asked for.

A `strict` key left in an existing `vault-config.yaml` stays harmless: nothing reads it.

## Why the skill no longer says Tomo never breaks the required schema

WHY: That was a guarantee no code backs. `token-render.py` reads `frontmatter.optional` for default values and stops on tokens a template requires, but it does not read `frontmatter.required`. Whether Tomo should enforce that list is a separate product decision.

The rule that an empty value counts as missing stays, unconditionally. It was the behaviour under the default `strict: true`, and it is guidance for the model, not a script check.
