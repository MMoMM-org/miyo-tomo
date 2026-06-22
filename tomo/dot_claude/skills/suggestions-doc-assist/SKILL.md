---
name: suggestions-doc-assist
description: Use PROACTIVELY when the user — while reviewing a suggestions, suggestions-fan, or Proposed-MOCs section of a suggestions doc — asks to change where atomic notes land in a MOC OR to consolidate two proposed new MOCs into one. Triggers: "put X and Y in section Z", "merge these into one section", "link X to MOC W", "give it a placement", "they should land together", "there's no section entry for this item", "merge proposed MOC X into Y", "X and Y are the same MOC, call it Z", "rename proposed MOC X to Y", "consolidate these proposed MOCs". Edits checkboxes, Placement lines, and Proposed-MOC Name lines after showing a diff and confirming.
user-invocable: true
argument-hint: "what to change, e.g. 'put Beppu and Furano in Japanische Städte' or 'merge proposed MOC Games into Board Games'"
---
# Suggestions Doc Assist
# version: 0.2.0

Apply a user's edit intent to the active suggestions doc, then write it back. Two intents:
**placement** (where atomic notes land in a MOC) and **consolidation** (collapse two proposed
new MOCs into one). The user stays the approver — this skill performs only the mechanical edit,
after a confirmed diff.

Placement-line forms, the section merge rule, and the Proposed-MOC consolidation rule are defined
in the `suggestions-doc-format` skill; load it and follow those forms exactly.

## Workflow

### 1. Locate the target doc

List the inbox (path from `concepts.inbox` in `config/vault-config.yaml`) with the
`kado-search` listDir operation and find the suggestions docs: `<date>_suggestions.md`
or `<date>_suggestions-fan.md`. `kado-read` each candidate; a live one carries
`tomo.state: pending-approval` in its frontmatter. Pick the doc that contains the notes
(in `## Suggestions`) or the proposed MOCs (in `## Proposed MOCs`) the user named. If more
than one matches, ask which doc.

### 2. Route by intent

The user asks to place/link a note inside a MOC → **placement** (steps 3a, 4, 5).
The user asks to merge, consolidate, or rename two **proposed new MOCs** → **consolidation**
(steps 3b, 4, 5).

### 3a. Placement — resolve targets and compute the edits

For every note the user named, determine the destination MOC and section. Read the target
MOC's structure for valid headings and footer presence:

```bash
cat config/moc-structure-cache.yaml
```

Choose the Placement form (from the `suggestions-doc-format` skill):
- destination is an existing heading in that MOC → ``under `## <Heading>` ``
- new section AND the MOC has a footer (`has_footer: true`) → ``new section `## <Name>` (before the footer)``
- new section AND no footer → ``new section `## <Name>` (at the end of the MOC)``
- inside an editable callout → ``inside the `[!<type>] <title>` callout``

To MERGE notes into one section: give them an identical `(MOC, new-section name)` pair.

For each target item block in `## Suggestions`, change ONLY:
- the destination MOC link → `- [x] [[…MOC]]`
- the `**Placement:**` line directly under that checked link (column 0) — add it or replace the existing one
- `- [x] Approve` when the user is approving the item

# STRICT — the Placement line MUST match a form from the `suggestions-doc-format` skill verbatim.
# Why: a malformed line is not reverse-parsed; the override is dropped and Pass-2 silently falls back to heuristic placement.

### 3b. Consolidation — unify proposed-MOC Name and approve

Operate ONLY inside the `## Proposed MOCs` section. Each proposed MOC is a
`### Proposed MOC: <topic>` block carrying a `- **Name:** <name>` line and a
`- [ ] Approve (create this MOC with the Name above)` checkbox.

1. Match each MOC the user named to a block by its header topic or its `**Name:**` value.
2. Determine the single target Name:
   - "merge X into Y" → target Name = Y's current `**Name:**`
   - "rename X to Z" / "call it Z" → target Name = Z
3. For every block joining the target (including the target's own block), set its
   `- **Name:**` value to the target Name, keeping the
   `    ← edit this to rename the MOC before approving` hint suffix.
4. Tick `- [x] Approve (create this MOC with the Name above)` on every block to be created;
   leave its `Skip` line unticked.

# STRICT — for consolidation edit ONLY `**Name:**` lines and Approve checkboxes inside `## Proposed MOCs`. Do NOT edit the `## Suggestions` section.
# Why: a note's MOC binding is recovered from the `### Proposed MOC: <topic>` header, so same-Name blocks merge into one MOC with unioned members at Pass-2 — note-body edits are no-ops.

### 4. Show the diff

Present every changed block as before → after, showing only the changed lines.

# STRICT — NEVER write the doc without first showing this diff AND getting explicit user confirmation.
# Why: this is the user's reviewed doc; a silent rewrite breaks the approval contract.

### 5. Confirm and write

Ask the user to confirm. On confirm, write the full edited markdown (with the `tomo:`
frontmatter block preserved unchanged) to a temp file, then write it back to the doc's
vault path — `.md` auto-routes to a Kado note write:

```bash
python3 scripts/kado-write-file.py --local tomo-tmp/assist-edit.md --vault "<doc vault path>"
```

Re-read the doc and report which notes now point where, or which MOCs now share one Name.
On decline, report the proposed edits and change nothing.

## Boundary

Edit ONLY the suggestions / suggestions-fan doc inside the inbox folder. Never touch MOCs,
notes, or any file outside the inbox. Change ONLY: checkboxes, `**Placement:**` lines, and
`**Name:**` lines in the `## Proposed MOCs` section — never classification, tags, analysis
content, or the `tomo:` frontmatter.
