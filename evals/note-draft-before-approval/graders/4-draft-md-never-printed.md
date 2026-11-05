---
type: regex
target: trace
match: not_contains
pattern: '\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?\{\{source_link\}\}'
---
