# /execute — Helper for applying an instruction set
# version: 0.2.2

Show the user how to apply the latest Pass-2 instruction set. Tomo never writes vault notes outside the inbox itself — application happens either by hand in Obsidian or via Tomo Hashi's instruction-set executor. This command is a reminder of those options, not an executor.

## STRICT — What this command does NOT do

`/execute` does **not** apply actions to the vault. It does **not** call `kado-write` on action targets. It does **not** flip the instruction-set `tomo.state` from `pending-apply` to `applied`. All of that is either the user's responsibility (manual path) or Tomo Hashi's responsibility (automated path). Pre-Hashi: the user deletes completed instruction docs manually once applied.

If you (the assistant reading this command) are tempted to start writing vault notes from the instruction set, **stop**. The MVP execution boundary in `CLAUDE.md` is unambiguous: "Tomo writes only to inbox folder; user applies everything else."

## Workflow

1. **Locate the instruction set.** Read `concepts.inbox` from `config/vault-config.yaml`. Use `kado-search` to find `*_instructions.md` files inside that path. Pick the most recent by filename timestamp.

   - If no instruction set exists yet → tell the user no Pass-2 output is ready and recommend `/inbox`.
   - If multiple exist → pick the newest, mention the others in a one-line aside.

2. **Read its action state.** Read the instruction set via `kado-read`. Count total actions (`- [ ] Applied` + `- [x] Applied`) and how many are already applied.

   - If every action is already applied → tell the user the instruction set is done. Delete the instruction doc from the inbox manually (or wait for Hashi to do it). The next `/inbox` run will skip applied instructions either way.

3. **Print the helper output.** Use the format below verbatim — substitute the file path and the action counts.

```
Instruction set ready: <inbox>/<YYYY-MM-DD_HHMM>_instructions.md
Actions: <pending> pending, <applied> already applied (of <total> total)

You apply the actions — Tomo doesn't write outside the inbox. Two paths:

  1) Apply manually in Obsidian
       - Open the instruction set in your Obsidian vault.
       - For each `- [ ] Applied` action: perform it (write the note,
         add the link, set the tag), then tick `- [x] Applied`.
       - When all actions are applied, delete the instruction doc from
         the inbox manually. Source items stay `captured` — that's
         their terminal state.

  2) Hand off to Tomo Hashi
       - Open Tomo Hashi (Obsidian plugin: miyo-tomo-hashi) and run
         its instruction-set executor on this file.
       - Choose your preview mode:
           Preview on        — Hashi shows each action and waits
                               for your approval before applying.
           Preview off       — Hashi applies actions while keeping
                               a visible UI you can interrupt.
           No confirmation   — Background apply with no UI gate.
       - Hashi flips `tomo.state=pending-apply → applied` after the
         last action and cleans up the instruction doc itself.

       See: https://github.com/MMoMM-org/miyo-tomo-hashi
```

4. **Stop after printing.** Do not start applying actions yourself. Do not ask whether the user wants you to apply for them. The boundary is intentional.

## Safety

- Read-only command. No writes to the vault, no writes to the instance.
- Always pick the newest `*_instructions.md` by filename timestamp; surface the existence of older ones but don't act on them.
- Never offer to apply actions on the user's behalf — even if asked. Point at the two paths instead.
