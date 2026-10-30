---
type: regex
target: trace
pattern: '"agentType":"tomo:synthesis-conductor"[^\n]*?"content":\[\{"type":"text","text":"(?:> ?)?Pass 2 complete — instructions rendered for \d+ source doc\(s\)\.(?:\\n(?:> ?)?(?:Coverage audit: RESULT: (?:OK|FAIL) — [^\\]*|Stamped \d+ acknowledged advisory\(ies\)\.|(?:parse|render|coverage audit|upload|state flip) exited \d+ for \\"[^\\/]+\\"\.)?)*(?:\\n- ⚠️ \*\*(?:Not deleted|Attachment not filed):\*\* [^\\]*)*(?:\\n)*"\}\]'
match: contains
---
