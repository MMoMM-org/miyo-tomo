# WHY: kado-write-patterns skill

> Rationale for decisions in `tomo/dot_claude/skills/kado-write-patterns/SKILL.md`.
> Spec 026, T3.1 — Companion Mode P1 Framework Authoring Skills.

## Why a Dedicated Write-Side Skill (ADR-1)

WHY: The read side already has `kado-discovery-patterns` (listing, querying by frontmatter,
reading note content). Companion authoring adds a write-side mirror: composing and uploading
`.md` notes, `.base` files, `.canvas` artifacts, updating frontmatter, rendering templates, and
resolving config. Without a dedicated skill, agents improvise these invocations from training
data — producing wrong flag spellings, skipping the parse gate, or calling `kado-write` directly
with body in args (which blows the token limit for large artifacts). A grounded invocation
catalog prevents all three failure modes.

## Why Mirror Structure Rather Than One Combined Skill

WHY: Read and write operations have different trigger contexts. A request like "list my inbox
notes" should not load write-side invocations; "write a summary to the inbox" should not load
the cache-and-query patterns. Symmetric separate skills keep each context lean. ADR-1 confirmed
this read/write split as the preferred design over a combined helper skill.

## Why kado-write-file.py Instead of Inline `kado-write` Tool Call

WHY: Content passes through the agent's output-token budget when written as tool-call args.
A 136 KB MOC proposal-doc cannot be transported that way. `kado-write-file.py` reads bytes from
disk and pushes them via its own embedded Kado client, keeping artifacts outside the token
stream. All write invocations in the skill use this script for the same reason.

## Why --no-overwrite Exit Code 3 + `EXISTS:<path>` Contract

WHY: The caller (inbox-author) needs to branch on collision vs. error vs. success without
parsing stderr. Three distinct exit codes (0=ok, 1=Kado error, 2=I/O error, 3=exists) plus a
predictable stdout token (`EXISTS:<vault-path>`) make the branch deterministic. ADR-7 documents
this as the collision-guard contract; `test_kado_write_file_no_overwrite.py` tests it.

## Why the Parse Gate Routes by Extension (.canvas=JSON, .base=YAML)

WHY: If a malformed artifact reaches the vault, Obsidian silently shows an empty or broken
canvas/base view. The parse gate is deterministic and unit-tested; it must run before
`kado-write-file.py` for every non-.md write. The gate routes by file extension because the two
formats are structurally different:

- `.canvas` — JSON Canvas 1.0 spec; gate: `validate-json.py` (json.loads)
- `.base` — Obsidian Bases; YAML-based view format; gate: `validate-yaml.py` (yaml.safe_load)

Running `validate-json.py` on a `.base` file would reject valid YAML (JSON is a strict subset of
YAML syntax requirements; a YAML file with e.g. unquoted strings is valid YAML but not valid JSON).
ADR-4 and ADR-9 document the parse-gate requirement; the extension-routing decision reflects the
confirmed format distinction from the kepano/obsidian-skills source. The skill lists both gate
invocations in the non-.md write section so the correct gate cannot be forgotten.

## Why write_frontmatter Uses mode='merge' as Default

WHY: In-place frontmatter updates (setting `tomo.state`, adding a tag) must not destroy existing
fields the agent didn't touch. `mode='replace'` writes a verbatim block — any field not
explicitly supplied is deleted. `mode='merge'` deep-merges: arrays and scalars replace in place,
untouched keys survive. The default is merge to make the safe path the easy path.

## Why sanitize_stem Applies to the Stem Only

WHY: Applying `sanitize_stem` to the full filename including the extension would turn
`artifact.base` into `artifact-base` (the dot is not in the forbidden set, but a careless
full-string call with `.` variants can mangle unexpectedly). The invariant is: sanitize the stem
(`artifact`), then append the extension (`.base`) separately. The skill's section states this
explicitly because it is the observed failure mode.
