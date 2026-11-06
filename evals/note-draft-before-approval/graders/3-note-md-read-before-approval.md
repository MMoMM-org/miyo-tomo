---
type: regex
target: trace
match: contains
pattern: '^(?:(?!\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort|[^\n]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver)[^\n]*\n)*?[^\n]*"name":"(?:Read|Bash)","input":\{[^\n]*?tomo-tmp/note/2026-11-05_100000/note\.md[^\n]*\n(?:[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort'
---
