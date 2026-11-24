---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":"Agent","input":\{(?:(?=[^\n]*?"subagent_type":"(?!(?:tomo:)?review-(?:digester|carryover|proposer)"))|(?=[^\n]*?"subagent_type":"(?:tomo:)?review-digester")(?![^\n]*?digests/2026-W1[01]\.json))'
---
