# WHY: obsidian-markdown skill

> Rationale for decisions in `tomo/dot_claude/skills/obsidian-markdown/SKILL.md`.
> Spec 026, T2.1 — Companion Mode P1 Framework Authoring Skills.

## Why This Skill Exists

WHY: Tomo is asked to author `.md` notes in Obsidian-Flavored Markdown (OFM). OFM deviates from
CommonMark in significant ways — wikilinks, embeds, callouts, `==highlights==`, `%%comments%%`,
extended task statuses — and the model's general markdown knowledge produces recurring correctness
errors (the wikilink/backtick bug class was the observed trigger). A grounded reference skill
gives the model an authoritative per-format reference it loads on demand, rather than relying on
training-data recall which drifts across model versions.

## Why user-invocable: true (v0.2.0 upgrade — ADR-6)

WHY: The v0.1.0 skill was `user-invocable: false` and described as "Lazy-loaded by moc-architect".
In P1 the skill is also the format-knowledge reference for the companion authoring path
(`inbox-author` → obsidian-markdown on `.md` tasks). Making it user-invocable means:

1. Users can look up OFM syntax directly (`/obsidian-markdown`) without a roundabout.
2. The skill auto-triggers on description match when the task mentions writing or fixing `.md`
   note syntax — the session doesn't need to be in `/inbox` mode.

The `moc-architect` agent continues loading it via `skills:` frontmatter exactly as before — that
path is unaffected by the `user-invocable` flip.

## Why the Description Is Syntax-Scoped and Redirects to obsidian-fields (ADR-6)

WHY: The `obsidian-fields` skill covers frontmatter *field handling* — relationship markers,
callout *classification* (editable/protected/ignore), tag taxonomy resolution. If
`obsidian-markdown`'s description were broad ("Obsidian knowledge"), both skills would co-load
on callout-related tasks, wasting context tokens and potentially producing conflicting guidance.

The description is deliberately scoped to *syntax* ("writing/fixing .md note SYNTAX") and
explicitly redirects metadata/field semantics to `obsidian-fields`. The parenthetical
"(Metadata classification/field semantics → obsidian-fields; .base → obsidian-bases; .canvas →
obsidian-canvas.)" is the load-fence: it tells the model which skill to load for adjacent
concerns, preventing double-load. Per ADR-6, format skills are access-agnostic and
description-differentiated to achieve single-skill loading per artifact type.

## Why Content Was Expanded (kepano Attribution — ADR-8)

WHY: The v0.1.0 content covered callouts, wikilinks, embeds, and Dataview inline fields — the
constructs most relevant to the `/inbox` triage and MOC-linking workflows. P1 broadens Tomo's
authoring scope to free-form artifact creation, which requires grounded knowledge of the full OFM
surface: tables, task lists, fenced code, footnotes, frontmatter YAML, math, Mermaid, comments,
and highlights.

The expanded content is adapted from the kepano/obsidian-skills project (MIT licence).
Attribution: <https://github.com/kepano/obsidian-skills> — MIT, adapted with permission.
Full attribution also in the repo README (ADR-8: attribution in README + docs mirror, never in
runtime SKILL.md).

## Why `%%comments%%` and `==highlights==` Are Included

WHY: Both are Obsidian-specific extensions absent from CommonMark and GFM. Without a grounded
reference, the model either omits them entirely (not knowing they exist) or uses non-standard
approximations. These two are the most common "where did that syntax go in reading view?" surprises
for Tomo authoring output.

## Why the Properties/Frontmatter YAML Section Is Separate from Dataview Inline Fields

WHY: Properties (the `---` frontmatter block) and Dataview inline fields (`field:: value` in the
note body) are orthogonal — different syntax, different position, different tooling
(Obsidian Properties panel vs. Dataview plugin). Treating them as one section would be both
technically wrong (they have different YAML rules, different position requirements, different
rendering) and pedagogically confusing for a model expected to author both correctly.
