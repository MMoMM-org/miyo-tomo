---
type: regex
target: trace
match: contains
pattern: 'The report follows:(?:\\n  (?:(?:> ?)?(?:COVERAGE-GAP-91c2: suggestion s1 has no matching instruction \(expected 1, found 0\)|(?:parse|render|coverage audit|upload|state flip) exited \d+ for \\"[^\\/]+\\"\.)?|```(?:text)?))*?\\n  (?:> ?)?(?:Coverage audit: )?RESULT: FAIL — count or coverage mismatch above\.(?:\\n  (?:(?:> ?)?(?:COVERAGE-GAP-91c2: suggestion s1 has no matching instruction \(expected 1, found 0\)|(?:parse|render|coverage audit|upload|state flip) exited \d+ for \\"[^\\/]+\\"\.)?|```(?:text)?))*\\nagentId: '
---
