---
type: regex
target: trace
match: contains
pattern: '\{"type":"user"[^\n]*"type":"tool_result"[^\n]*\n(?:\{"type":"(?:system|rate_limit_event|tool_progress)"[^\n]*\n|\{"type":"assistant"[^\n]*?"content":\[\{"type":"(?:redacted_)?thinking"[^\n]*\n)*\{"type":"assistant"[^\n]*?"content":\[\{"type":"text","text":"Pass 1 complete: 3 items analysed, suggestions written to(?:\s|\\n)+\[\[\d{4}-\d{2}-\d{2}_\d{4}_suggestions\]\]'
---
