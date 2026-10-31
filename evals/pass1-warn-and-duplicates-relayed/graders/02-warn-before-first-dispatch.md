---
type: regex
target: trace
match: contains
pattern: '^(?:(?![^\n]*"name":"Agent")[^\n]*\n)*?(?![^\n]*"name":"Agent")[^\n]*"name":"Bash","input":\{[^\n]*?"command":"cat\s+tomo-tmp/setup-warnings\.txt[^\n]*\n(?:(?![^\n]*"name":"Agent")(?!\{"type":"user")[^\n]*\n)*?\{"type":"user"[^\n]*"type":"tool_result"[^\n]*active tracker field\(s\) have no keywords'
---
