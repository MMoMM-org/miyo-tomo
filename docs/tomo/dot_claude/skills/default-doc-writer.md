# WHY: default-doc-writer (skill) + the default-doc template

> Rationale for `tomo/dot_claude/skills/default-doc-writer/SKILL.md`, the built-in
> `tomo/config/templates/t_default_tomo.md`, and the `templates.mapping.default` role
> (backlog F-25 — inbox-note / default template definition).

## Why This Skill Exists — Tomo Creates Documents Outside the Defined Types

WHY: Tomo's note-creation pipeline (`/inbox`) only emits the **defined** concept types —
atomic note, MOC, daily note, project, source — each with its own `t_<concept>_tomo.md`
template selected via `templates.mapping.<concept>`. But the user also asks Tomo, in a
session, to produce *free-form* artifacts that fit none of those types: "create me an
overview of the vacations I took and the events I attended", a comparison table, a working
list. Before F-25 there was no template and no path for these — Tomo would improvise a
structure each time and had no defined home to write them to. This skill gives that request
a deterministic shape: compose the content, wrap it in the **default** template, write it to
the inbox folder for later filing. The inbox is the right home because a free-form artifact
is, by definition, not yet classified — it joins the same review queue every capture does.

## Why a `default` Role in templates.mapping, Not a New Concept

WHY: The five defined types are real PKM *concepts* with folders, classification, and
Pass-2 rendering. A catch-all "anything else" is not a concept — it has no destination
folder of its own (it lands in the inbox) and no classification. Modelling it as a sixth
concept would force it into machinery (concept_defaults, Dewey classification, MOC matching)
that does not apply. Instead it is a **template role**: a `default` key in
`templates.mapping`, parallel to the concept keys but special-cased as the fallback for
"undefined document". The setup wizard (`/tomo-setup` Phase 4) asks about it exactly like
the concept roles — "which template should free-form docs use?" — so the user points it at
*their own* inbox template, mirroring how every other type is configured.

## Why the Built-in Default Is Only `tags:` + Body

WHY: The user's vault is zettelkasten-lean and the *content* of a free-form doc is highly
individual — an overview, a list, and a comparison share no frontmatter beyond tags. Imposing
the full `t_note` frontmatter family (UUID, DateStamp, title, Summary) or its callout skeleton
(Action Items, Recent Updates, connect/puzzle) onto arbitrary content would fight the content
rather than hold it. So the built-in `t_default_tomo.md` carries only a `tags:{{tags}}`
frontmatter line and `{{body}}` — the leanest container that still lets the later `/inbox`
triage see a tag field. Users who want more structure set `templates.mapping.default` to their
own template; the built-in is the floor, not the ceiling.

## Why the Fallback Is Materialised Inline, Not Read from a Path

WHY: The `t_*_tomo.md` files in `tomo/config/templates/` are **source-repo starters**, not
runtime artifacts. They are not copied into the Tomo instance at install/update; at runtime the
defined-type templates are read from the user's *vault* by stem via `kado-search` byName
(`instruction-render.py` resolves bare stems that way). So `t_default_tomo.md` follows the same
rule: it is the canonical reference + a starter the user can install into their vault and then
point `templates.mapping.default` at. When the mapping is unset, the skill cannot read the repo
file (the container sees only the instance), so it **writes the four-line minimal default into
`tomo-tmp/` on the fly** and renders against that. The repo file and the inline fallback share
the same trivial shape by design; the file is the human-facing reference, the inline copy is the
runtime floor. The STRICT block in step 2 exists because reaching for a `config/templates/` path
*looks* correct but silently fails inside the container.

## Why Render Tokens via a File, Not Inline JSON

WHY: The document body is multi-line markdown (headings, tables, list bullets). Passing it on
the command line through `--tokens-json` means the shell and the JSON parser both fight the
newlines and quotes in the body — a recurring corruption class. The skill writes the tokens to
`tomo-tmp/default-doc-tokens.json` with the Write tool and renders with `--tokens <file>`, so
the body never transits the shell. The STRICT block enforces this because the inline form
*looks* fine for short bodies and only breaks once real content is passed.

## Why the Inbox-Only Boundary

WHY: Tomo's MVP execution boundary is that it writes only to the inbox folder; everything else
is applied downstream after user approval. A free-form doc is unclassified, so writing it
anywhere but the inbox would (1) leave that boundary and (2) place an unreviewed artifact into
structured vault space. The skill therefore resolves `concepts.inbox` and writes there, with a
`sanitize_stem`-cleaned filename so external-character titles ("Urlaube: 2024/2025") do not get
rejected by `kado-write`.
