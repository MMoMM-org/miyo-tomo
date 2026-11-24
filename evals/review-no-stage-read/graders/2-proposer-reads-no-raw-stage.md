---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":"(?:Read|Grep|Glob|Bash)","input":\{[^\n]*?(?:manifest\.json|days/|growth/)[^\n]*?"subagent_type":"(?:tomo:)?review-proposer"'
---
