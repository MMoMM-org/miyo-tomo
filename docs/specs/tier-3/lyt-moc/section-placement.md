# Tier 3: Section Placement

> Parent: [LYT/MOC Linking](../../tier-2/workflows/lyt-moc-linking.md)
> Status: Draft
> Related: [MOC Matching](moc-matching.md) · [Callout Mapping](../config/callout-mapping.md)

---

## 1. Purpose

Define how Tomo decides WHERE in a MOC to place a link to a new note. A MOC has sections (H2 headings), callouts, and DataviewJS blocks — Tomo needs to find the right spot and avoid the wrong ones.

## 2. Inputs

| Input | Source |
|-------|--------|
| Target MOC | From MOC matching result (path) |
| MOC content | Read via `kado-read` (live, not cached — we need current sections) |
| MOC sections | From cache (`map_notes[].sections[]`) for quick lookup, live for confirmation |
| Note topics | From inbox analysis |
| Callout mapping | From `vault-config.yaml → callouts` (editable vs protected) |

## 3. Section Selection Algorithm

### Step 1: Parse MOC Structure

Read the MOC and identify all structural elements:

```
For each line in MOC content:
  If line starts with "## " → record as H2 section (name, line number)
  If line starts with "> [!" → record as callout (type, line number, editable/protected)
  If line starts with "```dataview" → record as protected block
```

### Step 2: Identify Candidate Sections

Candidate sections are H2 headings that are:
- NOT inside a protected callout (`[!boxes]`, `[!shell]`, `[!keaton]`, etc.)
- NOT part of the "Related" footer area (heuristic: sections after the last `[!video]` or `[!calendar]` callout are typically footer)
- NOT the Overview/Anchor section (typically introductory, not a link list)

### Step 3: Match Topic to Section

For each candidate section:

```
section_name = heading text (e.g., "Tools", "Key Concepts", "Workflows")
score = 0

If note topic exactly matches section_name → score = 1.0
If note topic is substring of section_name → score = 0.7
If section contains existing links with similar topics → score = 0.5
If section is the [!blocks] callout content area → score = 0.3 (generic "Key Concepts")
```

### Step 4: Select Best Section

```
If best_score >= 0.5 → use that section
If best_score < 0.5 AND note has a clear topic → propose new section creation
If no sections found → propose adding at end of content area (before footer)
```

## 4. Link Insertion Point

Once a section is selected, where exactly to insert:

| Section type | Insertion point |
|-------------|-----------------|
| Section with existing bullet list | Append at end of the list (before the next H2 or callout) |
| Section with existing links (not bulleted) | Append as new bullet item at end |
| Empty section | Add as first bullet item |
| New section (to be created) | Create H2 heading + first bullet item |

### Format

The link is inserted as a bullet list item:
```markdown
- [[New Note Title]]
```

If the MOC uses a different link format (e.g., with summaries), match the existing pattern:
```markdown
- [[New Note Title]] — One-line description from suggestion
```

**Pattern detection:** Read the last 3 links in the section to detect the format (bullets? summaries? bare links?). Match the observed pattern.

## 5. Protected Zones

These areas of a MOC must NEVER be modified:

| Zone | Identification | Why |
|------|---------------|-----|
| Protected callouts | `callouts.protected` from config (e.g., `[!boxes]`, `[!shell]`, `[!keaton]`) | Contains DataviewJS — rendered dynamically |
| DataviewJS blocks | ```` ```dataviewjs ```` | Code queries — breaking them breaks the MOC |
| Dataview blocks | ```` ```dataview ```` | SQL-like queries |
| Folder-overview blocks | ```` ```folder-overview ```` | Plugin-rendered content |

Tomo's instruction set must explicitly note: "Insert ABOVE the Related section" or "Insert in ## Key Concepts" — never "somewhere in the note."

## 6. Section-Level Wikilinks in Instructions

The instruction set uses **direct section links** so the user clicks and lands at the right spot:

```markdown
### I02 — Add link to MOC
- [ ] Applied
- **Target:** [[Systems Thinking (MOC)#Key Concepts]]
- **Add this line at end of section:**
  `- [[Feedback Loops — How Systems Self-Correct]]`
```

Obsidian resolves `[[Note#Section]]` to jump directly to the H2 heading. This eliminates the "find the right spot" problem for the user.

## 7. New Section Proposal

When no existing section fits:

```markdown
### I02 — Add link to MOC (new section)
- [ ] Applied
- **Target:** [[2600 - Applied Sciences]]
- **Create section:** `## Shell & Terminal` (insert before ## Related)
- **Add this line:**
  `- [[oh-my-zsh — Installation & Configuration]]`
```

**Section naming:** Use the note's primary topic or the matched classification sub-category. Keep it short (2-4 words).

**Placement of new section:** Before the footer area (identified by the last structural callout like `[!video]`, `[!calendar]`, or `[!puzzle]`).

## 8. MOC Template Awareness

MiYo MOCs follow a consistent template structure (see [MiYo Profile](../profiles/miyo-profile.md)):

```
1. Frontmatter
2. [!connect] callout (up::/related::)     ← EDITABLE (relationships)
3. Title + summary DataviewJS
4. [!anchor] Overview                       ← EDITABLE (intro text)
5. [!blocks] Key Concepts                   ← EDITABLE (link lists go here)
6. Content sections (H2)                    ← EDITABLE (link lists go here)
7. [!video] Action Items                    ← EDITABLE (tasks)
8. [!calendar] Recent Updates               ← EDITABLE (changelog)
9. [!connect] Categories (tags)             ← EDITABLE
10. [!puzzle] Related Topics                ← EDITABLE
11. [!compass] Look at this                 ← EDITABLE
12. [!boxes] Unrequited Notes               ← PROTECTED
13. [!shell] Same-tag unmentioned           ← PROTECTED
14. [!keaton] Title-match notes             ← PROTECTED
```

**Safe insertion zones:** Sections 5-6 (Key Concepts and content H2s). These are where links to notes naturally belong.

**Footer boundary:** Section 7 (`[!video]`). Nothing after this is a content section.

## 9. Edge Cases

**MOC has no H2 sections:** Treat the entire body (after frontmatter + navigation) as one section. Insert at end before footer.

**MOC has only callouts, no free H2:** Insert before the first footer callout (`[!video]` or `[!calendar]`). Propose creating a new H2 section.

**Section name in a different language:** MiYo vault uses English section names but `locale: de`. Section matching should be case-insensitive and language-aware if possible. MVP: English exact match + substring.

**Duplicate section names:** If a MOC has two `## Tools` sections (shouldn't happen but might), use the first one.
