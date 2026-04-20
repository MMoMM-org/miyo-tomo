# /execute — Execute an approved instruction set
# version: 0.1.0

Execute approved actions from an instruction set file.

## Workflow

1. Find instruction set files tagged `#miyo/approved` via Kado MCP `search`
   (or prompt user for a specific file path)
2. Read the instruction set via Kado MCP `read_file`
3. Parse all actions — only process checked items (`- [x]`)
4. For each checked action:
   - Create/update notes via Kado MCP `write_file`
   - Log what was done
5. After all actions: update the instruction set tag to `#miyo/done`
6. Archive processed inbox source files (tag or move — per vault-config)
7. Report summary of executed actions

## Safety

- Skip unchecked actions silently
- Never modify files not referenced in the instruction set
- If an action fails, log the error and continue with remaining actions
- Report all failures at the end
