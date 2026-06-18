---
name: suggestions-doc-assist
description: Use PROACTIVELY when the user — while reviewing a suggestions or suggestions-fan doc — asks to change where atomic notes land in a MOC. Triggers: "put X and Y in section Z", "merge these into one section", "link X to MOC W", "give it a placement", "they should land together", "there's no section entry for this item". Edits the doc's checkboxes and Placement lines after showing a diff and confirming.
user-invocable: true
argument-hint: "what to change, e.g. 'put Beppu and Furano in Japanische Städte'"
---
# Suggestions Doc Assist
# version: 0.1.0

Apply a user's placement / merge / link intent to the active suggestions doc by editing
its MOC checkboxes and `**Placement:**` lines, then write it back. The user stays the
approver — this skill performs only the mechanical edit, after a confirmed diff.

Placement-line forms and the merge rule are defined in the `suggestions-doc-format` skill;
load it and follow those forms exactly.

## Workflow

### 1. Locate the target doc

List the inbox (path from `concepts.inbox` in `config/vault-config.yaml`) with the
`kado-search` listDir operation and find the suggestions docs: `<date>_suggestions.md`
or `<date>_suggestions-fan.md`. `kado-read` each candidate; a live one carries
`tomo.state: pending-approval` in its frontmatter. Pick the doc that contains the items
the user named. If more than one matches, ask which doc.

### 2. Resolve each target (note → destination)

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

### 3. Compute the edits

For each target item block, change ONLY:
- the destination MOC link → `- [x] [[…MOC]]`
- the `**Placement:**` line directly under that checked link (column 0) — add it or replace the existing one
- `- [x] Approve` when the user is approving the item

# STRICT — the Placement line MUST match a form from the `suggestions-doc-format` skill verbatim.
# Why: a malformed line is not reverse-parsed; the override is dropped and Pass-2 silently falls back to heuristic placement.

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

Re-read the doc and report which items now point where. On decline, report the proposed
edits and change nothing.

## Boundary

Edit ONLY the suggestions / suggestions-fan doc inside the inbox folder. Never touch MOCs,
notes, or any file outside the inbox. Change ONLY checkboxes and `**Placement:**` lines —
never classification, tags, analysis content, or the `tomo:` frontmatter.
