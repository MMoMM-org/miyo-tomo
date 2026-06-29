# docs/tomo/dot_claude/skills/obsidian-bases.md

WHY file for `tomo/dot_claude/skills/obsidian-bases/SKILL.md`.

## Attribution

Adapted from [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) (MIT License).
Kepano is the creator of Obsidian. The original `obsidian-bases` skill and `FUNCTIONS_REFERENCE`
are the authoritative source for `.base` format knowledge; this adaptation is a condensed,
Tomo-specific version that follows the runtime-imperatives-only convention.

Per spec 026 ADR-8 and CON-4/CON-5: attribution lives here and in README only — never inside the
runtime `SKILL.md`.

## Why this skill exists

Obsidian Bases (`.base` files) use a YAML format that is not well-represented in Claude's training
data. A session without this skill will either refuse to author `.base` files or produce structurally
invalid output (wrong filter expression syntax, wrong view type names — `cards` not `gallery`,
`map` not `board`, incorrect formula expression language, missing Duration type handling). The skill
passes the "skill test" from the brainstorm charter: it encodes non-obvious knowledge the LLM does
not already have.

## Why access-agnostic

Per spec 026 ADR-6: format skills never mention Kado. The skill teaches the `.base` JSON schema
only. The `inbox-author` skill handles where to write the file; `kado-write-patterns` handles how.
This separation keeps each skill small and lets the correct skill auto-load from its description
trigger without co-loading unrelated write-side knowledge.

## Why trigger anchored to .base only

Per spec 026 ADR-6: each format skill's description anchors to exactly one artifact type to prevent
cross-format co-loading and avoid the `obsidian-fields` callout collision that existed before
differentiated descriptions were introduced. Loading this skill for a `.canvas` or `.md` task wastes
context; the skill's Troubleshooting section cross-references the sibling skills.

## Why references/FUNCTIONS_REFERENCE.md

Formula expressions are voluminous and rarely needed for simple views. Progressive disclosure keeps
SKILL.md under 200 lines (frequently-loaded budget) while the full function catalog is available
on demand when a formula needs to be written.

## Spec references

- Spec 026 ADR-6 (access-agnostic format skills, differentiated descriptions, no pre-load)
- Spec 026 ADR-8 (kepano attribution in README only)
- Spec 026 ADR-9 (safety logic in deterministic scripts; skill is pure knowledge)
- PRD Feature 2 (obsidian-bases new skill)
- Brainstorm charter §4.3 (Deliverables 2 & 3 design)
