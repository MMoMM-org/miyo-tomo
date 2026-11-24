---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":"(?:Read|Grep|Glob|Bash)","input":\{(?:[^\n]*?(?:(?:days|growth|children|previous)/|context[\w-]*\.json)|[^\n]*?\b(?:e?grep|rg)\b[^\n]*?tomo-tmp/review|[^\n]*?"(?:path|pattern)":"[^"]*tomo-tmp/review)[^\n]*?"parent_tool_use_id":null'
---
