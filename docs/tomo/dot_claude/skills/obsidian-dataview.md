# docs/tomo/dot_claude/skills/obsidian-dataview.md

WHY file for `tomo/dot_claude/skills/obsidian-dataview/SKILL.md`.

## Attribution

Knowledge adapted from the official [blacksmithgu/obsidian-dataview](https://github.com/blacksmithgu/obsidian-dataview)
documentation (MIT License). Text is original, not copied verbatim. Per the spec 026 attribution
convention (CON-4/CON-5): attribution lives here and in README only — never inside the runtime
`SKILL.md`.

## Why this skill exists

DQL has a small set of non-obvious rules that an LLM gets wrong by default, each of which silently
produces an empty or wrong-result query (no error). The skill encodes exactly those: inline fields
need a **double** colon (`key::`), inline keys are normalized to lowercase-hyphen while frontmatter
keys are not, `FROM` folders must be quoted, missing fields evaluate to `null` (so undated rows leak
into "overdue" filters), comparisons are case-sensitive, and dates must be wrapped in `date()`. This
passes the "skill test" — it encodes knowledge the model lacks, not a restatement of obvious syntax.

## Why DataviewJS is out of scope

The `dataviewjs` / `dv.*` JavaScript API is a large surface (hundreds of methods) best served by
TypeScript type definitions and IDE IntelliSense in a coding session — a tooling loop the Tomo
companion does not have. A prose skill would be a thin, lossy slice of that API and would invite the
companion to emit `dataviewjs` blocks it cannot reliably get right. The skill therefore covers DQL
only and points the JS surface back to the IDE/types path.

## Why "prefer Bases"

Obsidian Bases (`.base`, see `obsidian-bases`) is the native, no-plugin, mobile-friendly default for
the common "filtered list/table of notes" job, and is what kepano (Obsidian's creator) shipped a skill
for while deliberately omitting Dataview. The companion's default for dynamic views is therefore a
`.base`; this skill exists for the narrower case where the user explicitly asks for a Dataview block
(e.g. a Dataview-centric vault, or computed/task-aggregation output Bases does not cover).

## Why trigger anchored to dataview/DQL only

Mirrors the spec 026 ADR-6 format-skill convention: each format skill's description anchors to one
artifact type to prevent cross-format co-loading. This skill triggers on a requested `dataview`
block; field semantics route to `obsidian-fields`, filtered note views to `obsidian-bases`, plain
note syntax to `obsidian-markdown`. The Troubleshooting section cross-references those siblings.

## Decision provenance (#91)

Created from the #91 research pass (Epic #16). The research decided: **drop Templater** (it is an
insertion-time/template-file construct that never appears in a finished note, is AGPLv3 so not
adaptable under MiYo Constitution L1, and is genuinely user-instance/template-maintenance territory
already read-covered by `template-render`); **no DataviewJS authoring skill** (types/IntelliSense
territory); **build a thin DQL skill** (this file). The deferred companion artifacts that motivated
the epic do not embed DQL by default — Bases is the native path — so this skill is opt-in by explicit
request, not part of the default authoring flow.
