---
type: regex
target: trace
match: contains
pattern: '^(?:(?!\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort|[^\n]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver)[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?date: 2026-11-05\\n(?:[^"\\\n]|\\.)*?attendees:(?:[^"\\\n]|\\.)*?Dana(?:[^"\\\n]|\\.)*?# Meeting\\n(?:[^"\\\n]|\\.)*?Related:[ \t]*\\n(?:[^"\\\n]|\\.)*?## Agenda\\n(?:[^"\\\n]|\\.)*?## Decisions\\n(?:[^"\\\n]|\\.)*?## Action items\\n(?:(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort|[^\n]*\n(?:[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort)'
---
