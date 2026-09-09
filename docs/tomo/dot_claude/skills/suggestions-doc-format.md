# WHY: suggestions-doc-format

> Rationale for decisions in `tomo/dot_claude/skills/suggestions-doc-format/SKILL.md`.

## Format Spec as Skill, Not Schema

WHY: Suggestions docs are markdown with embedded conventions (checkbox patterns, heading structure, frontmatter shape). A JSON schema can validate frontmatter but cannot express "the approval checkbox must be `- [x] Approved`, case-sensitive, line-start anchored." The skill format lets the conductor (and any future consumer) load the full contract — markdown structure, checkbox semantics, frontmatter mapping — in one artifact.

## Separate Checkbox Patterns per Doc Type

WHY: Suggestions/fan docs use `- [x] Approved` while MOC proposals use `- [x] Accept`. This is not arbitrary — the verbs reflect different user actions. "Approve" means "I agree these suggestions should become instructions." "Accept" means "I want this MOC created in my vault." Conflating them would blur the semantic boundary between analysis artifacts and structural proposals. The skill documents both patterns explicitly so parsers (suggestion-parser.py, squelch-unticked.py) and state-promoter.py use the correct checkbox for each doc type.

## Force Atomic Note as Per-Item Checkbox

WHY: Force Atomic Note is a per-item opt-in, not a document-level flag. A user might want atomic-note expansion for one complex item but not for three simple ones. The per-item checkbox `- [ ] Force Atomic Note` inside each suggestion item block gives granular control. The triage script (inbox-triage.py) scans these checkboxes and populates `force_atomic_items[]` in the routing plan — only ticked items trigger the fan-resolve flow.

## Tomo Frontmatter State Table

WHY: The state mapping (doc_type to valid states) is documented here rather than in tomo-lifecycle-states because it describes the data format of the frontmatter block — what fields exist and what values are valid. The lifecycle skill covers transitions and promotion logic. The boundary: this skill says "what the frontmatter looks like," the lifecycle skill says "how it changes."

## The Aliased Source Link (spec 034 T5.1)

WHY the format gained a second Source-line shape: recursive inbox discovery
lets two notes in different subfolders share a filename, and both used to
render `[[Dresden]]`. The reducer now emits `[[<path>|<stem>]]` for those
items only — the vault's own convention for a duplicate basename. The skill
states which half to read for what, because the failure mode is an LLM lifting
the path into `**Suggested name:**` and titling a note
`100 Inbox/Reise/Dresden`. Rationale for the change itself lives in
`docs/tomo/scripts/suggestions-reducer.md`.

## The Name Clash Notice (spec 034 T5.2)

WHY the format gained an informational line under `**Suggested name:**`: the
destination folder is flat, so two proposals cannot both be named `Dresden`
there. Pass 1 now renames the later claimant and states why. The skill spells
out that the notice is informational and that the name stays an ordinary
editable field, because the failure mode is an LLM treating an adjusted name as
special — re-deriving it, reverting it, or refusing the user's replacement.
T5.3's Pass-2 guard depends on the opposite: it must not be able to tell an
adjusted name from any other. Rationale for the check itself, including why the
vault half fails open, lives in `docs/tomo/scripts/suggestions-reducer.md`.
