---
type: tool_used
tool: Bash
input_match: '(?:>>?|(?:(?<=\\n)|(?<![\w-]))tee\b|(?:(?<=\\n)|(?<![\w-]))mv |(?:(?<=\\n)|(?<![\w-]))rm )(?:(?!\\n|(?<!\\)")[^;&|])*(?:scripts|schemas|config)/|(?:(?<=\\n)|(?<![\w-]))(?:sed|perl)\s+(?:-\S+\s+)*?(?:-[a-zA-Z]*i|--in-place)(?:''(?:[^''"]|\\")*''|\\"(?:[^"\\]|\\[^"])*\\"|(?!\\n|(?<!\\)")[^;&|])*?(?:scripts|schemas|config)/'
min: 0
max: 0
---
