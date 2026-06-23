# WHY — tomo-tag-handler-wizard

> WHY-persistence doc for the runtime skill at
> `tomo/dot_claude/skills/tomo-tag-handler-wizard/SKILL.md`.
> Audience: maintainers. Not loaded at runtime.

## Why the wizard delegates writing to `tag-handler-writer.py`

Three properties that the skill itself cannot guarantee — only the writer script can:

1. **Atomicity.** The writer uses `tempfile.mkstemp` + `os.replace` so a validation
   failure or mid-write I/O error never leaves a partial file on disk. A hand-write
   via the `Write` tool has no such guarantee; a validation failure would leave an
   invalid stub at `config/tag-handlers/<id>.json`.

2. **Schema validation before write.** The script validates the assembled handler
   dict against `tomo/schemas/tag-handler.schema.json` and exits non-zero before
   touching the output directory if the dict is invalid. The skill cannot reproduce
   this reliably inline — it would need to re-implement schema loading and
   jsonschema evaluation, duplicating logic that belongs in the tested script.

3. **Filename safety.** The writer applies `_safe_stem()` to derive the output
   filename from the handler `id`, replacing filesystem-unsafe chars (colon, space,
   slash …) with underscores. Deriving the filename inline in the skill risks
   mismatched output paths if the sanitisation logic ever changes.

## Why the skill surfaces non-zero exit as an error without retrying a hand-write

The non-zero exit is the writer's validation verdict. Retrying with a hand-write
would bypass atomicity and validation — exactly the guarantees the delegation
pattern is designed to provide. The correct recovery is to fix the inputs and
re-invoke the writer, not to circumvent it.

## T5.3 note

This is a seed doc. T5.3 will expand the wizard WHY-docs to cover the full
step-by-step design rationale (question ordering, idempotent Edit mode,
compose mode variants). Add those sections here when T5.3 lands.
