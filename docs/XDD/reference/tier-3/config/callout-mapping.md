# Tier 3: Callout Mapping

> Parent: [User Config](../../tier-2/components/user-config.md)
> Status: Implemented

---

## 1. Purpose

Define how Tomo understands Obsidian callouts in the user's vault. Not all vaults use callouts the same way — MiYo uses custom callouts for structured sections, but other vaults may use few or no callouts. Callout tracking is therefore **optional** and only activated when the user's vault actually relies on callouts for structure.

### Optional Feature

Callout tracking is enabled per vault-config:

```yaml
callouts:
  enabled: true       # false = Tomo ignores all callouts entirely
```

When `enabled: false`: Tomo treats note content as flat markdown. It doesn't scan for callouts, doesn't avoid protected zones, and doesn't target specific callout sections for link insertion. This is simpler and sufficient for vaults that don't use callouts structurally.

When `enabled: true`: Tomo reads the first line of each callout (`> [!name] Title`) to classify it and respects the category assignments below.

## 2. Core Distinction — Three Categories

| Category | Meaning | Tomo behavior |
|----------|---------|---------------|
| `editable` | Semantic callouts where Tomo may read, insert, or update content. | Read/write allowed |
| `protected` | Auto-generated, code-containing, or scaffolding callouts. Content is transient or structural. | **Read only**, never write inside them |
| `ignore` | Decorative callouts (dividers, weather, visual elements). No semantic value for Tomo. | **Skip entirely** — don't read, don't write, don't parse |

**Default for unknown callouts:** `protected` (safe default — don't touch what you don't understand).

## 3. Schema Location

Lives under `callouts:` in `vault-config.yaml`:

```yaml
callouts:
  enabled: boolean            # true to activate callout tracking, false to ignore all
  editable:
    <callout_name>: string    # Description of what this callout holds
  protected:
    <callout_name>: string    # Why this callout is protected
  ignore:
    <callout_name>: string    # Why this callout is decorative / irrelevant
```

The `callout_name` is the literal word used in `> [!name]` syntax (without the brackets or exclamation).

## 4. Example: MiYo Mapping

```yaml
callouts:
  enabled: true
  editable:
    connect:  "Navigation breadcrumbs (up:: / related::)"
    anchor:   "Overview section introduction"
    blocks:   "Key Concepts section"
    video:    "Action Items / Tasks"
    calendar: "Recent Updates"
    puzzle:   "Related Topics"
    compass:  "Suggestions and things to explore"
  protected:
    boxes:    "Unrequited Notes (DataviewJS query output)"
    shell:    "Same-tag unmentioned (DataviewJS query output)"
    keaton:   "Title-match notes (DataviewJS query output)"
  ignore:
    weather:  "Auto-generated weather widget (decorative)"
    divider:  "Visual separator, no semantic content"
```

## 5. Why Protection Matters

Protected callouts typically wrap DataviewJS blocks:

```markdown
> [!boxes]- Unrequited Notes
> Notes which link to this note but are not mentioned in it.
> ```dataviewjs
> dv.view("dv_backLinksNotLinked", {filename: dv.current().file.name})
> ```
```

The **content inside the callout is rendered at read time** by DataviewJS. If Tomo writes anything inside this callout, the next DataviewJS render overwrites it. Worse, if Tomo modifies the DataviewJS query itself, the user's queries break.

**Tomo's rule:** never touch anything inside a protected callout. Not the callout text, not the code block, nothing.

## 6. Writing Inside Editable Callouts

When an action needs to place content in an editable callout:

1. **Locate the callout** — scan the note body for `> [!<name>]`
2. **Find the callout boundaries** — callout spans all consecutive lines starting with `> `
3. **Insert content** — append or replace within the callout, preserving the `> ` line prefixes
4. **Preserve foldable state** — if the callout uses `[!name]-` (collapsed) or `[!name]+` (expanded), keep the suffix

Example: adding a link to the `[!connect]` callout:

```markdown
Before:
> [!connect] Your way around
> up:: [[Parent MOC]]

After (adding peer link):
> [!connect] Your way around
> up:: [[Parent MOC]]
> related:: [[New Peer Note]]
```

## 7. Creating Editable Callouts

If a template or relationship config points to an editable callout that doesn't exist in the note, Tomo creates it:

1. Determine target position (based on `relationship.position` or template structure)
2. Insert the callout header: `> [!<name>] <optional title>`
3. Add the content line(s) with `> ` prefix
4. Ensure blank line separation above and below

## 8. Detection (during /explore-vault)

vault-explorer scans a sample of notes for callout usage:

1. Regex match `^> \[!(\w+)\]`
2. For each callout name, sample 10 occurrences
3. Check if the callout contains a code block with `dataviewjs`, `dataview`, or similar plugin syntax
4. **Classification heuristic:**
   - Callout contains code block → propose `protected`
   - Callout contains only prose and wikilinks → propose `editable`
   - Callout is empty → propose `editable` (new sections)
5. User confirms classifications

## 9. Standard and Custom Callouts

Obsidian ships with standard callout names (`note`, `tip`, `warning`, `danger`, `info`, etc.). Custom callouts use user-defined names (`connect`, `blocks`, `boxes`, etc.).

**Tomo treats both the same way.** There is no distinction between standard and custom callouts — the classification (editable/protected/ignore) is based on the callout's name and content, not on whether Obsidian recognizes it as a built-in type.

**Default for any callout NOT listed in config:** `protected` (safe — don't touch what you don't know about). The user adds callouts they want Tomo to interact with to the `editable` list explicitly.

## 10. Edge Cases

**Nested callouts:** Obsidian supports nesting (`> > [!info]`). Tomo respects nesting rules — writes are at the outermost callout's depth unless the action specifies a nested target.

**Callouts used as content scaffolding:** Some vaults use callouts purely for visual structure (dividers, banners, layout). These are `protected` — Tomo should not modify visual scaffolding even if it contains no code. If the user wants Tomo to use them, they can explicitly list them as `editable`.

**Callouts inside code blocks:** Not real callouts — ignored during scanning.

**Callouts with mixed content (prose + code block):** Treat the whole callout as `protected`. Tomo can't safely edit prose when code lives in the same callout.

**New callout types appearing in the vault:** `/explore-vault` detects them and asks for classification during refinement.
