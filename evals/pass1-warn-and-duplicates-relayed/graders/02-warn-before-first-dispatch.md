---
type: regex
target: trace
match: contains
pattern: '^(?:(?![^\n]*"name":"Agent")[^\n]*\n)*?(?![^\n]*"name":"Agent")[^\n]*"type":"tool_use","id":"(toolu_[A-Za-z0-9]+)","name":"Bash","input":\{[^\n]*?"command":"cat\s+tomo-tmp/setup-warnings\.txt[^\n]*\n(?:(?![^\n]*"name":"Agent")[^\n]*\n)*?[^\n]*"tool_use_id":"\1","type":"tool_result","content":"(?:[^"\\\n]|\\.)*?active tracker field\(s\) have no keywords'
---
