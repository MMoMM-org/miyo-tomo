---
type: regex
target: trace
match: contains
pattern: '^(?![\s\S]*?"name":"Bash","input":\{[^\n]*?note-instructions\.py\s+deliver)[\s\S]*?\n\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort'
---
