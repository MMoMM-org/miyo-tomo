---
type: regex
target: trace
match: contains
pattern: '^(?:(?![^\n]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver)[^\n]*\n)*?\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"(?:[^"\\\n]|\\.)*?date: 2026-11-05\\n(?:[^"\\\n]|\\.)*?attendees:(?:[^"\\\n]|\\.)*?Dana(?:[^"\\\n]|\\.)*?# Meeting\\n(?:[^"\\\n]|\\.)*?Related:[ \t]*\\n(?:[^"\\\n]|\\.)*?## Agenda\\n(?:[^"\\\n]|\\.)*?## Decisions\\n(?:[^"\\\n]|\\.)*?## Action items\\n[\s\S]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver'
---
