# WHY: suggestions-doc-assist (skill)

> Rationale for decisions in `tomo/dot_claude/skills/suggestions-doc-assist/SKILL.md`.
> The skill applies a user's placement / merge / link intent to the active
> suggestions (or suggestions-fan) doc by editing its MOC checkboxes and
> `**Placement:**` lines, then writing it back (spec 022/023).

## Why This Skill Exists — Automating Placement Edits by Hand

WHY: Where an atomic note lands inside a MOC is steerable through an optional
`**Placement:**` line under a checked `- [x] [[…MOC]]` link. A user *can* hand-edit
that line directly, but the valid forms are exact (reverse-parsed verbatim by
`suggestion-parser.py`) and the merge rule — identical `(MOC, new-section name)`
pairs collapse into one section — is non-obvious. A reader steering several notes by
hand has to keep the form table and the merge semantics in their head while editing
markdown in the doc. This skill takes the intent ("put Beppu and Furano in Japanische
Städte") and produces the mechanically-correct edits, so the user supplies intent and
reviews the diff rather than authoring fragile syntax. It exists because the
`suggestions-doc-format` skill *documents* the forms but nothing *applies* them.

## Why This Skill Also Consolidates Proposed MOCs (v0.2.0)

WHY: Pass-1 can surface two *separate* new-MOC proposals in the `## Proposed MOCs` section
when an item's topics split across what is really one map (e.g. notes A,B propose "Games" and
note C proposes "Board Games", both not-yet-existing). The user wants them as one MOC. Done by
hand this is a two-front edit — rename the proposal's `**Name:**` line *and* re-point the
member notes — which is where the user previously spent manual effort.

WHY (the note-side edit is intentionally NOT performed): the parser already does the merge.
`suggestion-parser.py:parse_proposed_mocs` ends with `_merge_proposed_mocs_by_name`, which
collapses two approved blocks sharing the same final `**Name:**` into a single `create_moc`
and **unions their member stems** (#67, decision 2026-06-17 — the code comment even names the
"Games" → "Board Games" case). Member→MOC binding is recovered from each block's
`### Proposed MOC: <topic>` header via `_topic_member_stems`, keyed off the structured
suggestions-doc JSON — *not* the note body in `## Suggestions`. So the minimal correct edit is:
set the source block's `**Name:**` to the target name and tick both `Approve` boxes. Editing the
per-note section would be a no-op at best; the STRICT block in step 3b forbids it so the skill
does not waste edits chasing a binding that does not flow through the note body. Pass-2's
`instruction-render.py` backfill (`_prepend_create_moc_titles_to_supporting`) then stamps the
single MOC title onto every unioned member.

WHY (the markdown blocks are NOT physically collapsed): because the parser merges by Name at
Pass-2, leaving both `### Proposed MOC:` blocks in place produces the correct single MOC while
keeping the doc's rendered shape intact. Physically deleting a block would diverge from the
renderer's output for no functional gain and risks dropping a topic header that the binding
pass relies on. The skill therefore edits in place and lets the parser do the collapse.

## Why Vault Writes Route Through the kado-write Helper, Not Direct

WHY: Tomo runs sandboxed in Docker and has no direct filesystem access to the vault —
every vault write goes through Kado's MCP surface. The skill writes the edited doc back
with `scripts/kado-write-file.py --local … --vault …`, which routes a `.md` path to a
Kado note write. Writing the file "directly" is not an option that exists inside the
container, and bypassing Kado would violate the MiYo privacy contract (Kado is the only
vault-write gateway). The helper also owns the `.md`-only / base64 routing rules that the
skill must not re-implement.

## Why the Boundary Excludes MOC Edits

WHY: The skill changes *where a note will land* by editing the suggestions doc — it never
edits the destination MOC itself. Editing MOCs is the apply-time job downstream
(Hashi / manual), gated by the user's approval of the rendered instructions. If this skill
reached into MOCs it would (1) leave the sandbox's inbox-only execution boundary — Tomo's
MVP rule is that it writes only to the inbox folder — and (2) mutate vault structure before
the user has approved the instruction set. So the boundary is hard: edit ONLY the
suggestions / suggestions-fan doc inside the inbox, and within that doc change ONLY
checkboxes and `**Placement:**` lines — never classification, tags, analysis content, or
the `tomo:` frontmatter.

## Why Each STRICT Block Exists (Failure Modes)

WHY (STRICT — Placement line must match a `suggestions-doc-format` form verbatim):
a malformed Placement line is not reverse-parsed by `suggestion-parser.py`. The parser
silently drops the unrecognised override and Pass-2 falls back to heuristic placement —
so a typo'd form produces no error, just a note that lands somewhere other than where the
user asked. The damage is invisible until the user inspects the applied result. The STRICT
block forces the skill to copy a known-good form rather than improvise one.

WHY (STRICT — never write the doc without showing the diff AND getting explicit
confirmation): the suggestions doc is the artifact the user has already reviewed and is
approving. A silent rewrite — even a correct one — breaks the approval contract: the user
must see exactly what changed in their reviewed doc before it is overwritten. The diff +
confirmation gate keeps the human as the approver and the skill as a mechanical editor.

## Companion: "Steering Placements by Hand" in suggestions-doc-format

The `suggestions-doc-format` skill (v0.2.0) gained a "Steering Placements by Hand" section
that this skill depends on. WHY it lives there rather than here: `suggestions-doc-format`
is the single source of truth for doc *syntax* (checkbox patterns, item structure, the
Placement-line form table, the merge rule, frontmatter), loaded by both producers and
parsers. The Placement-line forms are syntax, so they belong with the rest of the format
spec; `suggestions-doc-assist` loads that skill and follows the forms rather than
restating them, keeping one authoritative form table. Key facts captured there:

- The `**Placement:**` line sits on the line **directly under** a checked
  `- [x] [[…MOC]]` link at column 0; a hand-edited line overrides the doc-JSON the
  reducer rendered.
- A checked `[x]` MOC with **no** Placement line still emits a link — Pass-2 resolves the
  section heuristically. The Placement line only overrides that default; it is not required
  for the link to exist. `parent_mocs` (every checked MOC) drives link emission;
  `candidate_mocs` carries the anchor override only. (See the `parent_mocs vs
  candidate_mocs` memory note.)
- The merge rule: same MOC + same new-section name collapse into one `## <Name>` section
  (one heading, multiple bullets) at Pass-2.

(There is no separate `docs/tomo/dot_claude/skills/suggestions-doc-format.md` mirror at the
time of writing; if one is created, move the bullet list above into it.)
