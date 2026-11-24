---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":"Agent","input":\{(?![^\n]*?"subagent_type":")'
---
