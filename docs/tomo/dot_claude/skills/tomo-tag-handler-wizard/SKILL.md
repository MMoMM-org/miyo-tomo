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

## Why Question Ordering Mirrors the Handler Schema Dependency Graph

WHY: The wizard asks questions in the order that matches the schema's logical
dependencies — `id` and `tag_prefix` first (the identity anchor), then `capture_segments`
and `read_fields` (what to extract), then `action` (what to do), then `target`/`marker`
(where to put it), and finally `compose` (how to produce the content). This ordering
ensures that each answer can be validated in context of the answers already given (e.g.
the `target.by` question references a segment name the user just declared). Reversing
or interleaving the order would require the wizard to hold tentative state and re-validate
retroactively, which AskUserQuestion's sequential model doesn't support cleanly.

## Why Idempotent Edit Mode (Existing Handler Detected)

WHY: When the user invokes the wizard and the resolved `config/tag-handlers/<id>.json`
already exists, the wizard loads the current handler and pre-populates each question's
default with the current value. This makes re-invocation safe for editing — the user
can change one field (e.g. add a new repo to the target map) and leave the rest
unchanged. Without this mode, re-running the wizard would overwrite a handler with
whatever defaults the wizard proposes, which is destructive. The pre-population is
read-only during questions; the write only happens at the final confirmation step via
`tag-handler-writer.py`.

## Why Compose Mode Variants Are a Single `compose` Field

WHY: The handler schema's `compose` field accepts either a string (LLM directive) or
an array of strings (field template — a mechanical join with no model call). The wizard
asks the user to choose the mode first, then collects the appropriate value. This keeps
the JSON shape simple (one field, two shapes) rather than having two separate fields
(`compose_directive` / `compose_fields`) that are mutually exclusive. The schema expresses
this as a `oneOf` (string xor array of strings), so the validator catches a wrong shape
before the file is written. The wizard surfaces the mode choice explicitly because the
two shapes have very different runtime costs — an LLM directive triggers a model call per
batch group; a field template does not.
