---
type: regex
target: trace
match: contains
pattern: 'The report follows:\\n  (?:> ?)?Pass 2 complete — instructions rendered for \d+ source doc\(s\)\.(?:\\n  (?:> ?)?(?:Coverage audit: RESULT: (?:OK — \d+\/\d+ actions reconciled(?:, \d+ observation\(s\))?|FAIL — count or coverage mismatch above)\.|Stamped \d+ acknowledged advisory\(ies\)\.|(?:parse|render|coverage audit|upload|state flip) exited \d+ for \\"[^\\/]+\\"\.)?)*(?:\\n  - ⚠️ \*\*(?:Not deleted|Attachment not filed):\*\* [^\\]*)*\\nagentId: '
---
