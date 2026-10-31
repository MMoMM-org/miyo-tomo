---
type: regex
target: trace
match: not_contains
pattern: '"name":"Bash","input":\{[^\n]*?"command":"(?:[^"\\\n]|\\.)*?\bpython3?\s+scripts/mark-captured\.py[\s\S]*\bpython3?\s+scripts/kado-write-file\.py\s[^\n]*?--vault\s+\\"[^"\\]*_suggestions\.json\\"'
---
