# /inbox — Analyse inbox and generate instruction set
# version: 0.1.0

Analyse all files in the configured inbox folder and generate a structured instruction set.

## Workflow

1. Read vault-config.md for the inbox path
2. List all files in the inbox via Kado MCP `list_directory`
3. For each file: read content via Kado MCP `read_file`, analyse type/topic/relevance
4. Generate an instruction set file with proposed actions (one checkbox per action)
5. Write the instruction set to the inbox folder via Kado MCP `write_file`
6. Report: "Instruction set created: [[YYYY-MM-DD_HHMM_instruction-set]]"

## Instruction Set Format

```markdown
---
tags: miyo/pending
created: YYYY-MM-DD HH:MM
source: tomo-inbox-analysis
---

# Instruction Set — YYYY-MM-DD

## Source Files
- [[source-file-1]]
- [[source-file-2]]

## Actions

- [ ] Create atomic note: [[proposed-note-title]] from [[source-file]]
- [ ] Add to MOC: [[existing-moc]] ← [[proposed-note-title]]
- [ ] Update daily note: add summary of [[source-file]]
- [ ] Archive: move [[source-file]] to archive
```
