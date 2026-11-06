---
type: regex
target: trace
match: contains
pattern: '^(?:(?!\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort|[^\n]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver)[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?Template:\W{0,4}t_meeting_tomo(?:[^"\\\n]|\\.)*?Final name:\W{0,4}Atlas/Notes/(?:[^"\\\n]|\\.)*?In the inbox until applied:\W{0,4}(?:100 Inbox/)?2026-11-05_100000_(?:[^"\\\n]|\\.)*?Source\W{0,4}100 Inbox/Meeting with Dana\.md\W{0,4}is deleted when you apply(?:(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort|[^\n]*\n(?:[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort)'
---
