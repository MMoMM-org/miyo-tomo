---
type: regex
target: trace
match: contains
pattern: '\{"type":"assistant","message":\{"model":"[^"]*","id":"(msg_[A-Za-z0-9]+)",(?=(?:[^\n]*?|[\s\S]*?\n\{"type":"assistant","message":\{"model":"[^"]*","id":"\1",[^\n]*?)"name":"Agent","input":\{(?=[^\n]*?review-digester")[^\n]*?digests/2026-W10\.json)(?=(?:[^\n]*?|[\s\S]*?\n\{"type":"assistant","message":\{"model":"[^"]*","id":"\1",[^\n]*?)"name":"Agent","input":\{(?=[^\n]*?review-digester")[^\n]*?digests/2026-W11\.json)(?=(?:[^\n]*?|[\s\S]*?\n\{"type":"assistant","message":\{"model":"[^"]*","id":"\1",[^\n]*?)"name":"Agent","input":\{[^\n]*?"subagent_type":"(?:tomo:)?review-carryover")'
---
