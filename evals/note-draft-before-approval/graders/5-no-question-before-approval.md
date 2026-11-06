---
type: regex
target: trace
match: contains
pattern: '^(?:(?![^\n]*"name":"AskUserQuestion","input"|[^\n]*"name":"ToolSearch","input":\{[^\n]*?AskUserQuestion|\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?\?)[^\n]*\n)*?[^\n]*"name":"Bash","input":\{[^\n]*?note-instructions\.py\s+stage[^\n]*\n(?:[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort'
---
