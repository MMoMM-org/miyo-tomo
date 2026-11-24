---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":"Agent","input":\{(?![^\n]*?"run_in_background":false)'
---
