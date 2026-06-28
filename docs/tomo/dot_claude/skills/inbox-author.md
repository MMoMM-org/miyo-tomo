# WHY: inbox-author (skill)

> Rationale for `tomo/dot_claude/skills/inbox-author/SKILL.md`.
> Renamed from `default-doc-writer` (spec 026, ADR-3).

## Why Renamed from default-doc-writer (ADR-3)

WHY: P1 broadens the skill's scope from `.md`-only free-form documents to all three companion
artifact formats: `.md` notes, `.base` Bases views, and `.canvas` JSON Canvas files. The name
`default-doc-writer` reflected only the `.md` path ("doc = document = markdown"). `inbox-author`
names the role — composing any free-form artifact and placing it in the inbox — without baking
in the format. Renaming rather than creating a new skill preserves the existing 5-step pipeline
and 3 STRICT guards rather than duplicating them. `RETIRED_SKILLS_DIRS` in `update-tomo.sh` will
prune the old `default-doc-writer` instance directory on next sync.

## Why This Skill Exists — Tomo Creates Artifacts Outside the Defined Types

WHY: Tomo's note-creation pipeline (`/inbox`) only emits the **defined** concept types —
atomic note, MOC, daily note, project, source — each with its own template. But the user also
asks Tomo, in a session, to produce *free-form* artifacts that fit none of those types:
"create me an overview of the vacations I took", a comparison table, a reading-list Bases view,
a canvas diagram. Before this skill there was no template and no path for these — Tomo would
improvise each time. This skill gives that request a deterministic shape: determine format,
compose the artifact, and write it to the inbox folder for later filing.

## Why a `default` Role in templates.mapping, Not a New Concept

WHY: The five defined types are real PKM *concepts* with folders, classification, and Pass-2
rendering. A catch-all "anything else" is not a concept — it has no destination folder (it lands
in the inbox) and no classification. Modelling it as a sixth concept would force it into
machinery that does not apply. Instead it is a **template role**: a `default` key in
`templates.mapping`, parallel to the concept keys but special-cased as the fallback for
"undefined document".

## Why the Built-in Default Template Is Only `tags:` + Body

WHY: The user's vault may be zettelkasten-lean and the *content* of a free-form doc is highly
individual. Imposing the full `t_note` frontmatter family onto arbitrary content would fight the
content. So the built-in fallback carries only `tags:{{tags}}` and `{{body}}` — the leanest
container that still lets later `/inbox` triage see a tag field. Users who want more structure
set `templates.mapping.default` to their own template; the built-in is the floor.

## Why the Fallback Is Materialised Inline, Not Read from a Path

WHY: The `t_*_tomo.md` files in `tomo/config/templates/` are **source-repo starters**, not
runtime artifacts. They are not copied into the Tomo instance at install/update. At runtime,
defined-type templates are read from the user's vault by stem via `kado-search` byName. So the
built-in fallback cannot be read from a container path — instead the skill writes the four-line
minimal default into `tomo-tmp/` on the fly. The STRICT block in step 2 exists because reaching
for a `config/templates/` path looks correct but silently fails inside the container.

## Why Render Tokens via a File, Not Inline JSON

WHY: The document body is multi-line markdown (headings, tables, bullet lists). Passing it
through `--tokens-json` means the shell and JSON parser fight the newlines and quotes —
a recurring corruption class. The skill writes tokens to `tomo-tmp/default-doc-tokens.json`
with the Write tool and renders with `--tokens <file>` so the body never transits the shell.
The STRICT block enforces this because the inline form looks fine for short bodies and only
breaks once real content is passed.

## Why Only kado-write-patterns Is Pre-Loaded (ADR-6)

WHY: The format-knowledge skills (`obsidian-markdown`, `obsidian-bases`, `obsidian-canvas`)
are **not** listed in `skills:` frontmatter. They auto-trigger by description-match when the
LLM determines the artifact type — `.md` authoring loads `obsidian-markdown`, a `.base` request
loads `obsidian-bases`, etc. Pre-loading all three on every `inbox-author` invocation would
waste context on `.md`-only requests (Constitution L2 Performance). `kado-write-patterns` IS
pre-loaded because it is always needed regardless of artifact type.

## Why the Inbox-Only Boundary

WHY: Tomo's MVP execution boundary is that it writes only to the inbox folder; everything else
is applied downstream after user approval. A free-form artifact is unclassified, so writing it
anywhere but the inbox would (1) leave that boundary and (2) place an unreviewed artifact into
structured vault space. The skill resolves `concepts.inbox` and writes there, with a
`sanitize_stem`-cleaned filename so titles containing forbidden characters do not get rejected.
