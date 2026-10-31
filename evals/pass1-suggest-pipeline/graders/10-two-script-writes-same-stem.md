---
type: regex
target: trace
match: contains
pattern: '"name":"Bash","input":\{[^\n]*?"command":"(?:[^"\\\n]|\\.)*?\bpython3?\s+scripts/kado-write-file\.py\s[^\n]*?--vault\s+\\"100 Inbox/(\d{4}-\d{2}-\d{2}_\d{4})_suggestions\.md\\"[\s\S]*"name":"Bash","input":\{[^\n]*?"command":"(?:[^"\\\n]|\\.)*?\bpython3?\s+scripts/kado-write-file\.py\s[^\n]*?--vault\s+\\"100 Inbox/\1_suggestions\.json\\"'
---
