---
type: regex
target: trace
match: contains
pattern: '^(?![\s\S]*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?Related:[ \t]*\{\{source_link\}\})[\s\S]*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?# Meeting\\n'
---
