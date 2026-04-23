# Tier 3: Instruction Set Apply (MVP: User)

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Implemented
> Executor: **User** (MVP) / **Tomo Hashi** (Post-MVP, in progress)
> Related: [Instruction Set Generation](instruction-set-generation.md) · [Instruction Set Cleanup](instruction-set-cleanup.md) · [instructions.json + .md contract](../../../../instructions-json.md)

---

## 1. Purpose

Define how the **user** applies the detailed instruction set to the vault during MVP. Tomo has already done the cognitive work — the user is just performing the mechanical steps with full context at each step.

This is **not a Tomo agent**. It's a **user workflow** that Tomo supports by producing clear, actionable instructions.

## 2. Why User Applies in MVP

From [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model):

> Even with Kado as a safe access layer, AI-driven execution introduces variance — the AI could misread the instruction set, skip actions, apply them in wrong order, or include unintended changes.

Having the user apply the actions manually:
- Keeps execution deterministic
- Gives the user a final verification checkpoint per action
- Eliminates AI-induced variance at write time
- Fits within Tomo's deterministic boundary (the inbox folder)

Post-MVP, **Tomo Hashi** (友橋, the Obsidian plugin; formerly "Seigyo" in pre-2026-04-20 drafts) will apply actions deterministically by reading `<date>_instructions.json` — the canonical machine-readable contract produced by Pass 2. Until then, the user is the executor, working from the human-readable `<date>_instructions.md` companion.

## 3. When the User Applies

Triggered by the instruction set document being tagged `#MiYo-Tomo/instructions`. The user opens it in Obsidian and works through the actions sequentially.

## 4. User Workflow

### Step 1: Open the instruction set

- Path: `+/YYYY-MM-DD_HHMM_instructions.md`
- Obsidian shows the document with wikilinks ready to click

### Step 2: Work through each action

For each `I##` action:

```
Read the action entry
   │
   ▼
Click the clickable target (wikilink)
   │
   ▼
Obsidian opens the target file (or creates it if missing)
   │
   ▼
Perform the change described
   │
   ▼
Return to the instruction set
   │
   ▼
Check the [x] Applied box
   │
   ▼
Next action
```

### Step 3: Mark the instruction set as applied

When all actions are done (or consciously skipped), the user changes the document tag:

```
#MiYo-Tomo/instructions  →  #MiYo-Tomo/applied
```

### Step 4: Run `/inbox` one more time

This triggers cleanup (see [Instruction Set Cleanup](instruction-set-cleanup.md)).

## 5. Action-Specific User Actions

### New atomic note

1. Instruction references a rendered file in the inbox: `[[+/2026-04-08_1430_oh-my-zsh-installation-configuration]]`
2. User clicks the wikilink → Obsidian opens the file
3. User verifies content looks right
4. **If template contains Templater syntax:** user runs `Templater: Replace Templates in Active File` command (Cmd+P in Obsidian) to resolve any `<% tp.* %>` expressions
5. User moves the file:
   - Drag-and-drop in file explorer, OR
   - Use "Move file to..." command (Cmd+P → "Move")
6. Destination: as specified in the instruction (`Atlas/202 Notes/`)
7. Rename if instruction specifies a different final filename
8. Return to instruction set, check `[x] Applied`

### New MOC (map note)

Same as atomic note but:
- Destination is typically `Atlas/200 Maps/`
- After moving, also open the parent MOC and add a link per the instruction
- Verify backlinks populate correctly

### MOC link addition

1. Instruction has `[[MOC Title#Section]]` — user clicks
2. Obsidian jumps to the target section
3. User adds the exact line shown in the instruction
4. **If section doesn't exist:** user creates it (instruction includes the fallback)
5. Save, return to instruction set, check `[x] Applied`

### Daily note tracker update

1. Instruction links to the daily note
2. User opens it (Templater creates it if missing, per user's normal flow)
3. User finds the tracker field (search for the tracker name)
4. User updates the value per instruction
5. Save, return to instruction set, check

### Note modification (diff)

1. Instruction references both the target note and a diff file
2. User opens the diff file — sees before/after
3. User opens the target note
4. User applies the change manually based on the diff
5. Save, return, check

## 6. Partial Application

The user does NOT have to apply everything at once. Valid patterns:

- **Apply a few, come back later:** check the boxes for applied actions, leave the tag as `#MiYo-Tomo/instructions`, come back tomorrow. Tomo sees it's still `instructions` and does nothing on next `/inbox`.
- **Apply nothing, skip this batch:** change the tag directly to `#MiYo-Tomo/applied` with no boxes checked. Cleanup will still run, inbox items will still be archived.
- **Partial apply + modify remaining:** apply some, realize the remaining are wrong, edit the instruction set or delete lines. Only checked actions are considered applied.

## 7. User-Modifiable Fields

Even in the instruction set, the user can still edit fields before applying:

- Change the title in `**Final filename:** <name>`
- Change the target section
- Change a tag
- Add a note to themselves

These modifications are **local to the user's execution** — Tomo doesn't re-read the instruction set after generation (it only reads it during cleanup to check which actions were applied). Modifications the user makes change what they do in Obsidian, not what Tomo thinks happened.

## 8. User Mistakes

What happens if the user makes a mistake while applying:

| Mistake | Recovery |
|---------|----------|
| Applied the wrong content | User fixes manually in Obsidian; Tomo has no knowledge |
| Moved file to wrong location | User moves it again; Tomo has no knowledge |
| Skipped an action that should have been done | Leave unchecked; next `/inbox` run can be triggered from the original captured items (after deleting/recreating them) |
| Checked a box but didn't actually do the action | Tomo will archive the instruction set thinking it was done; user must realize and recreate the action manually |
| Applied too much (took extra actions not in the instruction set) | No problem; Tomo doesn't mind extra vault changes |

**Key principle:** Tomo trusts the user. The `#MiYo-Tomo/applied` tag is the user's word that the work is done. Tomo does not verify.

## 9. UX Considerations

To make the user's workflow smooth:

- **Clickable everything:** every target is a wikilink the user can click
- **Direct section links:** `[[MOC#Section]]` lands at the right spot, not the top
- **Clear change descriptions:** exact text to add, with formatting preserved
- **Pre-rendered content:** new notes are already rendered files in the inbox; no copy-paste
- **Diffs for modifications:** before/after clarity, no guessing
- **Progress visible:** checkboxes show what's done
- **Resumable:** partial work is fine, Tomo is patient

## 10. Post-MVP Evolution

When **Tomo Hashi** ships, this document becomes the operator-side view of the same contract Tomo Hashi automates:

- Each action is already a structured payload in `<date>_instructions.json` (XDD 008 made JSON canonical; no parsing of the `.md` required).
- Tomo Hashi reads the JSON, executes actions in the declared order, and syncs the `- [x] Applied` checkboxes in the `.md` companion back to the vault after each successful apply.
- The user's role shifts from "run the mechanical steps" to "review + approve the proposed set" — the dual-vetting checkpoint remains in Pass 2 (ticking `[x] Approved` on the suggestions doc).

**Contract location:** the authoritative consumer spec (both `.json` envelope and `.md` companion layout) lives in [`docs/instructions-json.md`](../../../../instructions-json.md). Tomo Hashi implementations should read that document; this one describes the manual workflow it replaces.

The MVP User Applies workflow is the simplest version of the Tomo Hashi contract. Building it well in MVP prepares the ground for the plugin.
