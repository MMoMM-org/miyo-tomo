---
type: tool_order
before: { tool: Bash, input_match: 'python3?\s+scripts/kado-write-file\.py\s[\s\S]*?--vault\s+\\"[^"\\]*_suggestions\.json\\"' }
after: { tool: Bash, input_match: 'python3?\s+scripts/mark-captured\.py' }
---
