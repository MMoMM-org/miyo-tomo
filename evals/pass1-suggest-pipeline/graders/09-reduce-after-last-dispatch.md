---
type: regex
target: trace
match: not_contains
pattern: '"name":"Bash","input":\{[^\n]*?"command":"(?:[^"\\\n]|\\.)*?\bpython3?\s+scripts/suggestions-reducer\.py[\s\S]*"name":"Agent","input":\{[^\n]*?"subagent_type":"tomo:inbox-analyst"'
---
