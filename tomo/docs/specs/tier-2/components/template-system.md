# Tier 2: Template System

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Draft
> Children: [Token Vocabulary](../../tier-3/templates/token-vocabulary.md) · [Template Files](../../tier-3/templates/template-files.md)

---

## 1. Purpose

Define how Tomo creates new notes using templates. MVP approach: one dedicated `t_*_tomo` template per note type, using `{{token}}` placeholder syntax. Bypasses Templater chain-loading entirely.

## 2. Design Decision: Dedicated Templates with Tomo-Friendly Tokens

The user's vault may use Templater with chain-loading (e.g., `t_note` → `t_note_privat` → `i_*`), user prompts, and custom JS. Tomo cannot:
- Execute Templater syntax (`tp.*`)
- Run user prompts
- Evaluate custom JavaScript

**MVP solution:** The user provides **dedicated templates for Tomo** — one per note type — using `{{token}}` placeholders that Tomo can render. The template filename is **not hardcoded** to a `t_*_tomo` convention; the user specifies the actual template name in vault-config.

These templates may still contain Templater syntax (`tp.*`). When that's the case, Tomo writes the rendered note (with `{{tokens}}` resolved but Templater syntax preserved), and the user runs Obsidian's command "Templater: Replace Templates in Active File" after moving the note to its destination.

**MVP write destination — split by action:**

| Action | What Tomo writes (in inbox folder) | What the user does |
|--------|-----------------------------------|---------------------|
| **New note** | Full rendered note as a file in the inbox folder | Move file to target location, optionally run Templater to resolve `tp.*` |
| **Modified note** | Diff document (before/after) in the inbox folder | Open the target note, apply the diff manually |

In both cases, Tomo only writes inside the inbox folder. The instruction set entry in `instructions.md` references the inbox file (e.g., `[[+/2026-04-07_1430_oh-my-zsh.md]]`) so the user can navigate to the rendered output, review it, and act on it.

**MVP execution boundary:** Tomo never writes outside the inbox folder. See [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model).

**Post-MVP evolution:** Tomo could learn to render Templater syntax itself, eliminating the user's manual Templater step. Parked in [parking lot](../../references/tomo-lyt-knowledge-model-spec.md#8-parking-lot).

## 3. Template Mapping

One template per note type. Filenames are **user-specified** — no naming convention is enforced.

```yaml
templates:
  base_path: "X/900 Support/Templates/"
  mapping:
    atomic_note: "t_note_tomo"        # user picks the actual filename
    map_note:    "t_moc_tomo"
    daily:       "t_daily_tomo"
    project:     "t_project_tomo"
    source:      "t_source_tomo"
    # weekly/monthly/yearly are post-MVP
```

Templates are read via Kado (`kado-read` with path = `base_path + mapping[type] + ".md"`). The `t_*_tomo` examples are conventions, not requirements — the user can name their templates whatever they want.

## 4. Token Syntax

Templates use `{{token}}` placeholders. Tomo does string replacement — no engine needed.

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
title: {{title}}
tags:
{{tags}}
Summary: {{summary}}
---

> [!connect] Your way around
> up:: {{up}}
> related:: {{related}}

# [[{{title}}]]

{{body}}
```

### Built-in Token Categories

Tomo ships with a baseline set of tokens that cover the common cases:

- **Required** (error if unresolvable): `{{uuid}}`, `{{datestamp}}`, `{{title}}`
- **Generated** (computed at render time): `{{uuid}}`, `{{datestamp}}`, `{{updated}}`
- **Config-sourced** (from vault-config defaults): `{{locale}}`, `{{vault}}`, `{{vault_version}}`
- **Content tokens** (from the action context): `{{title}}`, `{{tags}}`, `{{summary}}`, `{{body}}`, `{{up}}`, `{{related}}`, `{{aliases}}`

### User-Defined Tokens

Token vocabulary is **extensible**. The user can declare custom tokens in vault-config.yaml with a description telling Tomo how to generate them. Examples:

```yaml
templates:
  custom_tokens:
    - name: "project_code"
      source: "frontmatter"        # pull from frontmatter of source/parent
      field: "ProjectCode"
      required: false
    - name: "weekday"
      source: "computed"
      logic: "weekday name in locale (e.g., Montag)"
      required: false
    - name: "moc_link"
      source: "context"
      logic: "the resolved primary MOC for this note as a wikilink"
      required: false
```

For sources Tomo can compute mechanically (`frontmatter`, common date formats), no LLM call is needed. For freeform `logic` descriptions, Tomo asks the LLM at render time. Custom tokens are best discussed in detail in [Tier 3 — Token Vocabulary](../../tier-3/templates/token-vocabulary.md).

## 5. Rendering Pipeline (MVP)

The pipeline branches based on whether the action is **new note** or **note modification**.

### New Note

1. **Read template** via Kado (`kado-read`)
2. **Resolve `{{tokens}}`** — substitute all placeholders
3. **Validate result** — required frontmatter fields are present, no unresolved required tokens
4. **Write to inbox folder** — `kado-write` creates the file in the inbox (this is allowed; inbox is Tomo's deterministic boundary)
5. **Reference in instruction set** — the action entry links to the inbox file: `[[+/2026-04-07_1430_oh-my-zsh.md]]`
6. **User picks up** — user opens the file, optionally runs "Templater: Replace Templates in Active File" if `tp.*` syntax is present, then moves the file to its target location

### Note Modification

1. **Read current note** via Kado (`kado-read`)
2. **Compute changes** — based on the action (add MOC link, update tag, modify section, etc.)
3. **Generate diff document** — before/after presentation in markdown
4. **Write diff to inbox folder** — `kado-write` creates the diff file in the inbox
5. **Reference in instruction set** — action entry links to the diff: `[[+/2026-04-07_1430_oh-my-zsh-diff.md]]`
6. **User picks up** — user opens the target note in Obsidian, applies the diff manually

### Templater Syntax Handling

If a template contains Templater syntax (`tp.*`), Tomo:
- Resolves only the `{{token}}` placeholders
- Leaves Templater syntax untouched in the rendered output
- Adds a note to the instruction set entry: "This file contains Templater syntax. After moving it to its target, run `Templater: Replace Templates in Active File` in Obsidian to resolve it."

**Post-MVP:** New-note step 4-6 and modification step 4-6 are replaced by Seigyo invoking locked scripts that do the file move and diff application deterministically. See [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model).

## 6. Template Creation Responsibility

- **Tomo provides:** example templates in `tomo/config/` as reference (with `{{token}}` placeholders pre-filled)
- **User creates:** actual templates in their vault's template folder, with **any filename they want**
- **User declares filenames** in vault-config.yaml `templates.mapping` — no naming convention enforced
- **Setup wizard suggests:** creating Tomo templates during first-session discovery, helps the user adapt their existing templates
- **Fallback:** if a template doesn't exist (referenced in mapping but file missing), Tomo generates notes using a hardcoded minimal structure (frontmatter + title + body). Warns user to create the template.
